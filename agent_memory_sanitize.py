"""Sanitize Agent memory metadata before persisting it."""
from __future__ import annotations

from typing import Any

DEFAULT_TOOL_OUTPUT_KEEP_CHARS = 4000


def compact_tool_result(result: Any, *, output_keep_chars: int = DEFAULT_TOOL_OUTPUT_KEEP_CHARS) -> tuple[Any, dict[str, int]]:
    stats = {"raw_omitted": 0, "output_truncated": 0}
    if not isinstance(result, dict):
        return result, stats

    compacted = dict(result)
    raw = compacted.pop("raw", None)
    if raw is not None:
        stats["raw_omitted"] = 1
        compacted["raw_omitted"] = True

    output = compacted.get("output")
    if isinstance(output, str) and len(output) > output_keep_chars:
        compacted["output"] = output[:output_keep_chars] + f"\n... [truncated {len(output) - output_keep_chars} chars]"
        compacted["output_truncated"] = True
        stats["output_truncated"] = 1

    arguments = compacted.get("arguments")
    if isinstance(arguments, str) and len(arguments) > 1000:
        compacted["arguments"] = arguments[:1000] + f"... [truncated {len(arguments) - 1000} chars]"
        compacted["arguments_truncated"] = True

    if stats["raw_omitted"] or stats["output_truncated"]:
        compacted["compacted"] = True
    return compacted, stats


def compact_turn_metadata(metadata: Any, *, output_keep_chars: int = DEFAULT_TOOL_OUTPUT_KEEP_CHARS) -> dict:
    """Return a safe-to-persist metadata dict for one Agent turn."""
    if metadata is None:
        return {}
    if not isinstance(metadata, dict):
        return {"compacted_note": "legacy non-dict metadata omitted"}

    new_metadata = dict(metadata)
    tool_results = new_metadata.get("tool_results")
    if isinstance(tool_results, list):
        new_results = []
        raw_omitted = 0
        output_truncated = 0
        for result in tool_results:
            new_result, item_stats = compact_tool_result(result, output_keep_chars=output_keep_chars)
            new_results.append(new_result)
            raw_omitted += item_stats["raw_omitted"]
            output_truncated += item_stats["output_truncated"]
        new_metadata["tool_results"] = new_results
        if raw_omitted or output_truncated:
            new_metadata["tool_results_compacted"] = {
                "raw_omitted": raw_omitted,
                "output_truncated": output_truncated,
            }
    elif tool_results is not None:
        new_metadata["tool_results"] = []
        new_metadata["tool_results_compacted_note"] = "legacy non-list tool_results omitted"
    return new_metadata


def compact_short_term_metadata(short_term: list[Any], *, output_keep_chars: int = DEFAULT_TOOL_OUTPUT_KEEP_CHARS) -> tuple[list[Any], dict[str, int]]:
    stats = {"raw_omitted": 0, "output_truncated": 0, "metadata_fixed": 0}
    compacted_turns = []
    for turn in short_term:
        if not isinstance(turn, dict):
            compacted_turns.append(turn)
            continue
        metadata = turn.get("metadata")
        new_turn = dict(turn)
        new_turn["metadata"] = compact_turn_metadata(metadata, output_keep_chars=output_keep_chars)
        compacted = new_turn["metadata"].get("tool_results_compacted") or {}
        stats["raw_omitted"] += int(compacted.get("raw_omitted") or 0)
        stats["output_truncated"] += int(compacted.get("output_truncated") or 0)
        if metadata is not None and not isinstance(metadata, dict):
            stats["metadata_fixed"] += 1
        if isinstance(metadata, dict) and metadata.get("tool_results") is not None and not isinstance(metadata.get("tool_results"), list):
            stats["metadata_fixed"] += 1
        compacted_turns.append(new_turn)
    return compacted_turns, stats
