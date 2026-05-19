"""Agent memory maintenance helpers.

This module is intentionally independent from Telegram handlers so memory
maintenance can be tested and run safely before wiring it into bot.py.
"""
from __future__ import annotations

import json
import shutil
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Any

from agent_core import MEMORY_DIR, _SafeJSONEncoder
from agent_memory_sanitize import DEFAULT_TOOL_OUTPUT_KEEP_CHARS, compact_short_term_metadata

DEFAULT_RECENT_FACTS_KEEP = 200
DEFAULT_BACKUP_DIRNAME = "backups"


def _now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _memory_files(memory_dir: Path = MEMORY_DIR) -> list[Path]:
    if not memory_dir.exists():
        return []
    return sorted(memory_dir.glob("user_*.json"))


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, default=_SafeJSONEncoder.default),
        encoding="utf-8",
    )


def _estimate_items(data: dict[str, Any]) -> dict[str, int]:
    long_term = data.get("long_term") or {}
    return {
        "short_term": len(data.get("short_term") or []),
        "learned_facts": len(long_term.get("learned_facts") or []),
        "user_profile": len(long_term.get("user_profile") or {}),
        "knowledge_base": len(long_term.get("knowledge_base") or {}),
        "patterns": len(long_term.get("patterns") or {}),
    }


def get_memory_status(memory_dir: Path = MEMORY_DIR) -> dict[str, Any]:
    """Return size and item statistics for all agent memory files."""
    files = []
    total_bytes = 0
    for path in _memory_files(memory_dir):
        stat = path.stat()
        total_bytes += stat.st_size
        item_counts: dict[str, int] = {}
        parse_error = None
        last_updated = None
        try:
            data = _load_json(path)
            item_counts = _estimate_items(data)
            last_updated = data.get("last_updated")
        except Exception as exc:  # pragma: no cover - defensive reporting
            parse_error = str(exc)
        files.append({
            "filename": path.name,
            "size_bytes": stat.st_size,
            "size_mb": round(stat.st_size / 1024 / 1024, 3),
            "last_updated": last_updated,
            "item_counts": item_counts,
            "parse_error": parse_error,
        })
    return {
        "memory_dir": str(memory_dir),
        "file_count": len(files),
        "total_bytes": total_bytes,
        "total_mb": round(total_bytes / 1024 / 1024, 3),
        "files": files,
    }


def backup_memory_files(memory_dir: Path = MEMORY_DIR, backup_root: Path | None = None) -> Path:
    """Copy current memory JSON files into a timestamped backup directory."""
    backup_root = backup_root or (memory_dir / DEFAULT_BACKUP_DIRNAME)
    backup_dir = backup_root / f"agent-memory-{_now_stamp()}"
    backup_dir.mkdir(parents=True, exist_ok=False)
    for path in _memory_files(memory_dir):
        shutil.copy2(path, backup_dir / path.name)
    return backup_dir


def _dedupe_learned_facts(facts: list[Any]) -> tuple[list[Any], int]:
    """Deduplicate learned facts by category + fact text, keeping the newest."""
    deduped: OrderedDict[tuple[str, str], Any] = OrderedDict()
    for item in facts:
        if not isinstance(item, dict):
            key = ("", json.dumps(item, ensure_ascii=False, sort_keys=True, default=str))
        else:
            fact = str(item.get("fact") or "").strip()
            category = str(item.get("category") or "general").strip()
            key = (category, fact)
        if key in deduped:
            del deduped[key]
        deduped[key] = item
    return list(deduped.values()), max(0, len(facts) - len(deduped))


def compact_memory_file(
    path: Path,
    *,
    dry_run: bool = True,
    keep_recent_facts: int = DEFAULT_RECENT_FACTS_KEEP,
    tool_output_keep_chars: int = DEFAULT_TOOL_OUTPUT_KEEP_CHARS,
) -> dict[str, Any]:
    """Compact one memory file.

    Current policy is deliberately conservative:
    - keep only the newest 20 short_term turns, matching AgentMemory.save();
    - de-duplicate long_term.learned_facts by category+fact;
    - keep the newest ``keep_recent_facts`` learned facts after de-duplication;
    - preserve user_profile, knowledge_base and patterns untouched;
    - omit bulky metadata.tool_results.raw and truncate huge output strings.
    """
    before_size = path.stat().st_size
    data = _load_json(path)
    before_counts = _estimate_items(data)

    short_term = data.get("short_term") or []
    long_term = data.setdefault("long_term", {})
    learned_facts = long_term.get("learned_facts") or []

    deduped_facts, duplicate_facts = _dedupe_learned_facts(learned_facts)
    trimmed_facts = deduped_facts[-keep_recent_facts:] if keep_recent_facts > 0 else deduped_facts
    compacted_short_term, metadata_stats = compact_short_term_metadata(
        short_term[-20:],
        output_keep_chars=tool_output_keep_chars,
    )

    data["short_term"] = compacted_short_term
    long_term["learned_facts"] = trimmed_facts
    data["last_compacted"] = datetime.now().isoformat()

    after_payload = json.dumps(data, ensure_ascii=False, indent=2, default=_SafeJSONEncoder.default)
    after_size = len(after_payload.encode("utf-8"))
    after_counts = _estimate_items(data)

    if not dry_run:
        path.write_text(after_payload, encoding="utf-8")

    return {
        "filename": path.name,
        "dry_run": dry_run,
        "before_size": before_size,
        "after_size": after_size,
        "saved_bytes": max(0, before_size - after_size),
        "before_counts": before_counts,
        "after_counts": after_counts,
        "duplicate_facts": duplicate_facts,
        "trimmed_facts": max(0, len(deduped_facts) - len(trimmed_facts)),
        "raw_omitted": metadata_stats["raw_omitted"],
        "output_truncated": metadata_stats["output_truncated"],
        "metadata_fixed": metadata_stats["metadata_fixed"],
    }


def compact_all_memories(
    *,
    memory_dir: Path = MEMORY_DIR,
    dry_run: bool = True,
    keep_recent_facts: int = DEFAULT_RECENT_FACTS_KEEP,
    tool_output_keep_chars: int = DEFAULT_TOOL_OUTPUT_KEEP_CHARS,
    create_backup: bool = True,
) -> dict[str, Any]:
    """Compact all memory files and optionally create a backup first."""
    backup_dir = None
    files = _memory_files(memory_dir)
    if files and create_backup and not dry_run:
        backup_dir = backup_memory_files(memory_dir)
    results = [
        compact_memory_file(
            path,
            dry_run=dry_run,
            keep_recent_facts=keep_recent_facts,
            tool_output_keep_chars=tool_output_keep_chars,
        )
        for path in files
    ]
    return {
        "dry_run": dry_run,
        "backup_dir": str(backup_dir) if backup_dir else None,
        "file_count": len(results),
        "results": results,
        "saved_bytes": sum(item["saved_bytes"] for item in results),
    }
