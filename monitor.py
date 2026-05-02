"""NewAPI Guardian Bot - 主动监控 Worker"""
import time
import logging
import sqlite3
from pathlib import Path
from config import ALERT_CONSECUTIVE_FAILURES, ALERT_COOLDOWN_MINUTES
import db as newapi_db

logger = logging.getLogger("guardian.monitor")

STATE_DB = Path(__file__).parent / "data" / "state.db"


def _init_state_db():
    STATE_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(STATE_DB))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS channel_state (
            channel_id INTEGER PRIMARY KEY,
            consecutive_failures INTEGER DEFAULT 0,
            last_alert_time REAL DEFAULT 0,
            last_fail_content TEXT DEFAULT '',
            last_fail_models TEXT DEFAULT ''
        )
    """)
    conn.commit()
    conn.close()


def _get_state_conn():
    _init_state_db()
    return sqlite3.connect(str(STATE_DB))


def check_failures() -> tuple[list[dict], list[dict]]:
    """
    检查最近失败，返回 (alerts, recoveries)
    alerts: 需要告警的渠道列表
    recoveries: 已恢复的渠道列表
    """
    alerts = []
    recoveries = []
    now = time.time()

    # 获取最近失败统计
    fail_stats = newapi_db.get_channel_failure_stats(minutes=15)
    fail_map = {row["channel_id"]: row for row in fail_stats}

    # 获取所有启用渠道
    enabled = newapi_db.get_enabled_channels()
    enabled_ids = {ch["id"] for ch in enabled}

    conn = _get_state_conn()
    cur = conn.cursor()

    # 更新失败计数
    for cid, info in fail_map.items():
        if cid not in enabled_ids:
            continue

        cur.execute(
            "SELECT consecutive_failures, last_alert_time FROM channel_state WHERE channel_id = ?",
            (cid,)
        )
        row = cur.fetchone()
        old_failures = row[0] if row else 0
        last_alert = row[1] if row else 0

        # 只看最近 15 分钟的失败次数，不累加历史
        new_failures = info["fail_count"]
        models = info.get("models", "")
        content = ""

        # 判断是否需要告警
        should_alert = (
            new_failures >= ALERT_CONSECUTIVE_FAILURES
            and (now - last_alert) > ALERT_COOLDOWN_MINUTES * 60
        )

        cur.execute(
            "INSERT OR REPLACE INTO channel_state "
            "(channel_id, consecutive_failures, last_alert_time, last_fail_content, last_fail_models) "
            "VALUES (?, ?, ?, ?, ?)",
            (cid, new_failures, now if should_alert else last_alert, content, models)
        )

        if should_alert:
            alerts.append({
                "channel_id": cid,
                "channel_name": info.get("channel_name", ""),
                "fail_count": new_failures,
                "models": models,
                "content": content,
            })

    # 检查恢复：之前有失败记录，但最近 15 分钟没有新失败
    cur.execute("SELECT channel_id, consecutive_failures FROM channel_state WHERE consecutive_failures > 0")
    for cid, old_count in cur.fetchall():
        if cid not in fail_map and cid in enabled_ids:
            # 该渠道最近没有失败 → 恢复
            ch = newapi_db.get_channel_by_id(cid)
            if ch:
                recoveries.append({
                    "channel_id": cid,
                    "channel_name": ch.get("name", ""),
                })
            cur.execute(
                "UPDATE channel_state SET consecutive_failures = 0 WHERE channel_id = ?",
                (cid,)
            )

    conn.commit()
    conn.close()

    return alerts, recoveries
