"""运行日志诊断辅助。

只读解析本机 NewAPI 容器日志与 OpenClaw fallback 日志，用于弥补数据库 logs 表不记录 relay 失败的情况。
"""
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from core.error_classifier import classify_error

CHANNEL_ERROR_RE = re.compile(r"channel error \(channel #(\d+), status code: (\d+)\):\s*(.*)")
RELAY_MODEL_RE = re.compile(r'"model_name":"([^"]+)"')
FALLBACK_REQUESTED_RE = re.compile(r'"requestedModel":"([^"]+)"')
FALLBACK_CANDIDATE_RE = re.compile(r'"candidateModel":"([^"]+)"')
FALLBACK_ERROR_RE = re.compile(r'"errorPreview":"([^"]+)"')
FALLBACK_DETAIL_RE = re.compile(r'"fallbackStepFromFailureDetail":"([^"]+)"')
REQUEST_ID_RE = re.compile(r"request id: ([A-Za-z0-9._:-]+)")
REQUEST_ID_HASH_RE = re.compile(r"requestIdHash[\"']?:[\"']?sha256:([A-Za-z0-9]+)")
TIME_RE = re.compile(r"(\d{4}/\d{2}/\d{2} - \d{2}:\d{2}:\d{2}|\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}|\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z)")


def _run_command(args: list[str], timeout: int = 10) -> str:
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except Exception as exc:
        return f"__ERROR__ {exc}"
    return (result.stdout or "") + (result.stderr or "")


def _decode_json_line(line: str) -> dict[str, Any] | None:
    try:
        return json.loads(line)
    except Exception:
        return None


def _extract_time(line: str) -> str | None:
    match = TIME_RE.search(line)
    return match.group(1) if match else None


def _match_model(line: str, model: str | None) -> bool:
    if not model:
        return True
    return model in line


def parse_newapi_log_lines(lines: list[str], model: str | None = None, channel_id: int | None = None) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    recent_model_by_request: dict[str, str] = {}

    for line in lines:
        model_match = RELAY_MODEL_RE.search(line)
        req_match = REQUEST_ID_RE.search(line)
        if model_match and req_match:
            recent_model_by_request[req_match.group(1)] = model_match.group(1)

        ch_match = CHANNEL_ERROR_RE.search(line)
        if not ch_match:
            continue

        cid = int(ch_match.group(1))
        if channel_id is not None and cid != int(channel_id):
            continue

        status_code = int(ch_match.group(2))
        message = ch_match.group(3).strip()
        req_match = REQUEST_ID_RE.search(message)
        req_id = req_match.group(1) if req_match else None
        inferred_model = recent_model_by_request.get(req_id or "")
        if model and inferred_model and inferred_model != model:
            continue
        # 如果没有模型字段但行里也没有目标模型，不强行过滤；NewAPI channel error 行常常不带 model。
        if model and not inferred_model and not _match_model(line, model):
            pass

        events.append({
            "source": "newapi_container_log",
            "time": _extract_time(line),
            "channel_id": cid,
            "model_name": inferred_model,
            "status_code": status_code,
            "content": message[:500],
            "request_id": req_id,
            "error_type": classify_error(message),
        })

    return events


def _openclaw_payload(line: str) -> dict[str, Any] | None:
    data = _decode_json_line(line)
    if not isinstance(data, dict):
        return None
    payload = data.get("1")
    return payload if isinstance(payload, dict) else None


def _request_hash_prefix(request_id: str | None) -> str | None:
    if not request_id:
        return None
    if request_id.startswith("sha256:"):
        return request_id.removeprefix("sha256:")[:12]
    # OpenClaw 会把 request id hash 成 sha256；NewAPI 日志是原始 request id，无法反推。
    # 这里保留原始前缀用于同源日志行关联。
    return request_id[:12]


def _failed_model_from_payload(payload: dict[str, Any]) -> str | None:
    event = payload.get("event")
    if event in {"embedded_run_agent_end", "embedded_run_failover_decision"}:
        return payload.get("model")
    if event == "model_fallback_decision":
        if payload.get("fallbackStepFromModel"):
            return payload.get("fallbackStepFromModel", "").split("/")[-1]
        if payload.get("decision") == "candidate_failed":
            return payload.get("candidateModel") or payload.get("requestedModel")
        if payload.get("fallbackStepFromFailureDetail"):
            return payload.get("fallbackStepFromModel", "").split("/")[-1] or payload.get("requestedModel")
        if payload.get("errorPreview"):
            return payload.get("requestedModel") or payload.get("candidateModel")
    return payload.get("candidateModel") or payload.get("requestedModel") or payload.get("model")


def parse_openclaw_log_lines(lines: list[str], model: str | None = None) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in lines:
        payload = _openclaw_payload(line)
        if not payload:
            continue
        event = payload.get("event")
        if event not in {"model_fallback_decision", "embedded_run_agent_end", "embedded_run_failover_decision"}:
            continue

        requested = payload.get("requestedModel") or payload.get("model")
        candidate = payload.get("candidateModel") or payload.get("model")
        failed_model = _failed_model_from_payload(payload)
        if model and model != failed_model:
            continue

        error = (
            payload.get("errorPreview")
            or payload.get("rawErrorPreview")
            or payload.get("fallbackStepFromFailureDetail")
            or payload.get("error")
            or ""
        )
        req_match = REQUEST_ID_RE.search(str(error))
        request_id = req_match.group(1) if req_match else payload.get("requestIdHash")
        events.append({
            "source": "openclaw_fallback_log",
            "time": _extract_time(line),
            "failed_model": failed_model,
            "requested_model": requested,
            "candidate_model": candidate,
            "status_code": payload.get("status"),
            "reason": payload.get("reason") or payload.get("failoverReason"),
            "content": str(error)[:500],
            "request_id": request_id,
            "request_hash_prefix": _request_hash_prefix(request_id),
            "error_type": classify_error(str(error)),
        })
    return events


def collect_runtime_failures(model: str | None = None, channel_id: int | None = None, minutes: int = 60) -> dict[str, Any]:
    """收集运行日志失败事件。"""
    since = f"{max(1, int(minutes))}m"

    log_path = Path(f"/tmp/openclaw/openclaw-{datetime.now().date().isoformat()}.log")
    openclaw_events: list[dict[str, Any]] = []
    if log_path.exists():
        lines = log_path.read_text(errors="replace").splitlines()[-3000:]
        openclaw_events = parse_openclaw_log_lines(lines, model=model)

    request_ids = {event.get("request_id") for event in openclaw_events if event.get("request_id") and not str(event.get("request_id")).startswith("sha256:")}

    newapi_output = _run_command(["docker", "logs", "--since", since, "new-api"], timeout=15)
    newapi_events = parse_newapi_log_lines(newapi_output.splitlines(), model=model, channel_id=channel_id)
    if model and request_ids:
        newapi_events = [event for event in newapi_events if event.get("request_id") in request_ids]

    return {
        "success": True,
        "scope": {"model": model, "channel_id": channel_id, "minutes": minutes},
        "newapi_events": newapi_events[-20:],
        "openclaw_events": openclaw_events[-20:],
    }
