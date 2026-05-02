"""NewAPI Guardian Bot - MySQL 只读查询层"""
import pymysql
from decimal import Decimal
from datetime import datetime, date, time, timedelta
from contextlib import contextmanager
from config import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE
from cache import cache


@contextmanager
def get_conn():
    conn = pymysql.connect(
        host=MYSQL_HOST, port=MYSQL_PORT, user=MYSQL_USER,
        password=MYSQL_PASSWORD, database=MYSQL_DATABASE,
        charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=10, read_timeout=30,
    )
    try:
        yield conn
    finally:
        conn.close()


def _convert_for_json(obj):
    """递归转换为 JSON 可序列化的类型"""
    if obj is None:
        return None
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (datetime, date, time)):
        return obj.isoformat()
    if isinstance(obj, timedelta):
        return obj.total_seconds()
    if isinstance(obj, bytes):
        try:
            return obj.decode('utf-8')
        except UnicodeDecodeError:
            return obj.hex()
    if isinstance(obj, set):
        return [_convert_for_json(item) for item in obj]
    if isinstance(obj, dict):
        return {k: _convert_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_convert_for_json(item) for item in obj]
    return obj


# 向后兼容：保留旧名称
_convert_decimals = _convert_for_json


def query(sql: str, args=None) -> list[dict]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, args or ())
            results = cur.fetchall()
            return _convert_for_json(results)


# ── 渠道相关 ──

def get_all_channels() -> list[dict]:
    cached = cache.get("channels:all")
    if cached is not None:
        return cached
    result = query(
        "SELECT id, name, type, status, test_model, used_quota, "
        "response_time, priority, weight, auto_ban, base_url, models, "
        "`group`, tag, remark "
        "FROM channels ORDER BY id"
    )
    cache.set("channels:all", result, ttl=180)  # 3 分钟
    return result


def get_enabled_channels() -> list[dict]:
    cached = cache.get("channels:enabled")
    if cached is not None:
        return cached
    result = query(
        "SELECT id, name, type, status, test_model, used_quota, "
        "response_time, priority, weight, base_url, models "
        "FROM channels WHERE status = 1 ORDER BY priority DESC, id"
    )
    cache.set("channels:enabled", result, ttl=180)  # 3 分钟
    return result


def get_disabled_channels() -> list[dict]:
    cached = cache.get("channels:disabled")
    if cached is not None:
        return cached
    result = query(
        "SELECT id, name, type, status, response_time, base_url, models "
        "FROM channels WHERE status != 1 ORDER BY id"
    )
    cache.set("channels:disabled", result, ttl=180)  # 3 分钟
    return result


def get_channel_by_id(channel_id: int) -> dict | None:
    rows = query(
        "SELECT id, name, type, status, test_model, used_quota, "
        "response_time, priority, weight, auto_ban, base_url, models, "
        "`group`, tag, remark "
        "FROM channels WHERE id = %s", (channel_id,)
    )
    return rows[0] if rows else None


# ── 日志相关 ──

def get_recent_logs_by_minutes(minutes: int = 60, limit: int = 500) -> list[dict]:
    return query(
        "SELECT id, type, channel_id, model_name, quota, use_time, "
        "created_at, LEFT(content, 200) AS content "
        "FROM logs "
        "WHERE created_at > UNIX_TIMESTAMP(NOW() - INTERVAL %s MINUTE) "
        "ORDER BY id DESC LIMIT %s",
        (minutes, limit)
    )

# 新增：获取最近日志（不限制时间）
def get_recent_logs(limit: int = 10) -> list[dict]:
    """返回最近 `limit` 条日志，按创建时间倒序。"""
    return query(
        "SELECT created_at, type, is_stream, channel_id, channel_name, user_id, username, token_name, model_name, use_time, prompt_tokens, completion_tokens, quota, ip "
        "FROM logs "
        "ORDER BY created_at DESC LIMIT %s",
        (limit,)
    )


def get_recent_failures(minutes: int = 60, limit: int = 200) -> list[dict]:
    """获取最近失败的日志（type != 2 表示非正常消费，或 content 包含错误关键词）"""
    return query(
        "SELECT id, type, channel_id, model_name, quota, use_time, "
        "created_at, LEFT(content, 300) AS content "
        "FROM logs "
        "WHERE created_at > UNIX_TIMESTAMP(NOW() - INTERVAL %s MINUTE) "
        "  AND (type != 2 OR content LIKE '%%insufficient%%' "
        "       OR content LIKE '%%余额%%' OR content LIKE '%%quota%%' "
        "       OR content LIKE '%%balance%%' OR content LIKE '%%error%%' "
        "       OR content LIKE '%%failed%%' OR content LIKE '%%timeout%%' "
        "       OR content LIKE '%%rate limit%%' OR content LIKE '%%429%%' "
        "       OR content LIKE '%%500%%' OR content LIKE '%%502%%' "
        "       OR content LIKE '%%503%%' OR content LIKE '%%524%%') "
        "ORDER BY id DESC LIMIT %s",
        (minutes, limit)
    )


def get_channel_failure_stats(minutes: int = 60) -> list[dict]:
    """按渠道统计最近失败次数"""
    return query(
        "SELECT l.channel_id, c.name AS channel_name, c.status, "
        "COUNT(*) AS fail_count, "
        "GROUP_CONCAT(DISTINCT l.model_name ORDER BY l.model_name SEPARATOR ', ') AS models, "
        "MAX(l.created_at) AS last_fail_time "
        "FROM logs l "
        "LEFT JOIN channels c ON l.channel_id = c.id "
        "WHERE l.created_at > UNIX_TIMESTAMP(NOW() - INTERVAL %s MINUTE) "
        "  AND (l.type != 2 OR l.content LIKE '%%insufficient%%' "
        "       OR l.content LIKE '%%余额%%' OR l.content LIKE '%%quota%%' "
        "       OR l.content LIKE '%%balance%%' OR l.content LIKE '%%error%%' "
        "       OR l.content LIKE '%%failed%%' OR l.content LIKE '%%timeout%%' "
        "       OR l.content LIKE '%%rate limit%%' OR l.content LIKE '%%429%%' "
        "       OR l.content LIKE '%%500%%' OR l.content LIKE '%%502%%' "
        "       OR l.content LIKE '%%503%%' OR l.content LIKE '%%524%%') "
        "GROUP BY l.channel_id, c.name, c.status "
        "ORDER BY fail_count DESC",
        (minutes,)
    )


def get_model_failure_stats(minutes: int = 60) -> list[dict]:
    """按模型统计最近失败，并归因到渠道"""
    return query(
        "SELECT l.model_name, l.channel_id, c.name AS channel_name, "
        "COUNT(*) AS fail_count, "
        "MAX(l.created_at) AS last_fail_time "
        "FROM logs l "
        "LEFT JOIN channels c ON l.channel_id = c.id "
        "WHERE l.created_at > UNIX_TIMESTAMP(NOW() - INTERVAL %s MINUTE) "
        "  AND (l.type != 2 OR l.content LIKE '%%insufficient%%' "
        "       OR l.content LIKE '%%余额%%' OR l.content LIKE '%%quota%%' "
        "       OR l.content LIKE '%%balance%%' OR l.content LIKE '%%error%%' "
        "       OR l.content LIKE '%%failed%%' OR l.content LIKE '%%timeout%%') "
        "GROUP BY l.model_name, l.channel_id, c.name "
        "ORDER BY l.model_name, fail_count DESC",
        (minutes,)
    )


def get_balance_suspect_channels(minutes: int = 120) -> list[dict]:
    """疑似无余额的渠道"""
    return query(
        "SELECT l.channel_id, c.name AS channel_name, "
        "COUNT(*) AS balance_fail_count, "
        "GROUP_CONCAT(DISTINCT l.model_name SEPARATOR ', ') AS models "
        "FROM logs l "
        "LEFT JOIN channels c ON l.channel_id = c.id "
        "WHERE l.created_at > UNIX_TIMESTAMP(NOW() - INTERVAL %s MINUTE) "
        "  AND (l.content LIKE '%%insufficient%%' OR l.content LIKE '%%余额%%' "
        "       OR l.content LIKE '%%quota%%' OR l.content LIKE '%%balance%%' "
        "       OR l.content LIKE '%%credit%%' OR l.content LIKE '%%billing%%') "
        "GROUP BY l.channel_id, c.name "
        "ORDER BY balance_fail_count DESC",
        (minutes,)
    )


def get_slow_channels(minutes: int = 60, min_response_ms: int = 5000) -> list[dict]:
    """最近响应慢的渠道"""
    return query(
        "SELECT l.channel_id, c.name AS channel_name, "
        "AVG(l.use_time) AS avg_time, MAX(l.use_time) AS max_time, "
        "COUNT(*) AS request_count "
        "FROM logs l "
        "LEFT JOIN channels c ON l.channel_id = c.id "
        "WHERE l.created_at > UNIX_TIMESTAMP(NOW() - INTERVAL %s MINUTE) "
        "  AND l.type = 2 AND l.use_time > 0 "
        "GROUP BY l.channel_id, c.name "
        "HAVING avg_time > %s "
        "ORDER BY avg_time DESC LIMIT 15",
        (minutes, min_response_ms / 1000)
    )


def get_overview_stats(minutes: int = 60) -> dict:
    """总览统计"""
    rows = query(
        "SELECT "
        "  (SELECT COUNT(*) FROM channels WHERE status = 1) AS enabled_channels, "
        "  (SELECT COUNT(*) FROM channels WHERE status != 1) AS disabled_channels, "
        "  (SELECT COUNT(*) FROM logs WHERE created_at > UNIX_TIMESTAMP(NOW() - INTERVAL %s MINUTE)) AS recent_requests, "
        "  (SELECT COUNT(*) FROM logs WHERE created_at > UNIX_TIMESTAMP(NOW() - INTERVAL %s MINUTE) AND type = 2) AS recent_success",
        (minutes, minutes)
    )
    return rows[0] if rows else {}


def get_channel_recent_logs(channel_id: int, minutes: int = 60, limit: int = 20) -> list[dict]:
    return query(
        "SELECT id, type, model_name, quota, use_time, created_at, "
        "LEFT(content, 200) AS content "
        "FROM logs WHERE channel_id = %s "
        "AND created_at > UNIX_TIMESTAMP(NOW() - INTERVAL %s MINUTE) "
        "ORDER BY id DESC LIMIT %s",
        (channel_id, minutes, limit)
    )


def get_model_channels(model_name: str) -> list[dict]:
    """查找支持某模型的所有渠道"""
    return query(
        "SELECT id, name, status, response_time, priority, weight, used_quota "
        "FROM channels "
        "WHERE status = 1 AND models LIKE %s "
        "ORDER BY priority DESC, id",
        (f"%{model_name}%",)
    )


# ── 统计查询 ──

def get_model_usage_stats(minutes: int = 0, limit: int = 20) -> list[dict]:
    """模型使用排行。minutes=0 表示全部时间"""
    where = "WHERE type = 2"
    args = ()
    if minutes > 0:
        where += " AND created_at > UNIX_TIMESTAMP(NOW() - INTERVAL %s MINUTE)"
        args = (minutes,)
    return query(
        f"SELECT model_name, COUNT(*) AS call_count, "
        f"SUM(quota) AS total_quota, "
        f"SUM(prompt_tokens) AS total_prompt, "
        f"SUM(completion_tokens) AS total_completion, "
        f"AVG(use_time) AS avg_time "
        f"FROM logs {where} "
        f"GROUP BY model_name ORDER BY call_count DESC LIMIT %s",
        args + (limit,)
    )


def get_today_stats() -> dict:
    cached = cache.get("stats:today")
    if cached is not None:
        return cached
    rows = query(
        "SELECT COUNT(*) AS total_calls, "
        "COALESCE(SUM(quota),0) AS total_quota, "
        "COALESCE(SUM(prompt_tokens),0) AS total_prompt, "
        "COALESCE(SUM(completion_tokens),0) AS total_completion "
        "FROM logs WHERE type = 2 AND created_at > UNIX_TIMESTAMP(CURDATE())"
    )
    result = rows[0] if rows else {}
    cache.set("stats:today", result, ttl=60)  # 1 分钟
    return result


def get_yesterday_stats() -> dict:
    """获取昨日统计"""
    cached = cache.get("stats:yesterday")
    if cached is not None:
        return cached
    rows = query(
        "SELECT COUNT(*) AS total_calls, "
        "COALESCE(SUM(quota),0) AS total_quota, "
        "COALESCE(SUM(prompt_tokens),0) AS total_prompt, "
        "COALESCE(SUM(completion_tokens),0) AS total_completion "
        "FROM logs WHERE type = 2 "
        "AND created_at >= UNIX_TIMESTAMP(CURDATE() - INTERVAL 1 DAY) "
        "AND created_at < UNIX_TIMESTAMP(CURDATE())"
    )
    result = rows[0] if rows else {}
    cache.set("stats:yesterday", result, ttl=300)  # 5 分钟
    return result


def get_today_model_usage(limit: int = 15) -> list[dict]:
    return query(
        "SELECT model_name, COUNT(*) AS calls, SUM(quota) AS quota "
        "FROM logs WHERE type = 2 AND created_at > UNIX_TIMESTAMP(CURDATE()) "
        "GROUP BY model_name ORDER BY calls DESC LIMIT %s",
        (limit,)
    )


def get_user_usage_stats(limit: int = 10) -> list[dict]:
    return query(
        "SELECT username, COUNT(*) AS calls, SUM(quota) AS quota "
        "FROM logs WHERE type = 2 "
        "GROUP BY username ORDER BY calls DESC LIMIT %s",
        (limit,)
    )


def get_token_usage_stats(limit: int = 10) -> list[dict]:
    return query(
        "SELECT token_name, COUNT(*) AS calls, SUM(quota) AS quota "
        "FROM logs WHERE type = 2 "
        "GROUP BY token_name ORDER BY calls DESC LIMIT %s",
        (limit,)
    )


def get_log_stat_api() -> dict:
    """从 API 获取实时 RPM/TPM"""
    return query(
        "SELECT COUNT(*) AS rpm FROM logs "
        "WHERE created_at > UNIX_TIMESTAMP(NOW() - INTERVAL 1 MINUTE)"
    )[0] if True else {}


def get_channel_health_scores(minutes: int = 1440) -> dict[int, dict]:
    """计算渠道健康度评分: 成功率60% + 响应时间20% + 失败频率20%"""
    rows = query(
        "SELECT c.id AS channel_id, c.name, c.status, "
        "SUM(CASE WHEN l.type = 2 THEN 1 ELSE 0 END) AS success_count, "
        "COUNT(l.id) AS total_count, "
        "AVG(CASE WHEN l.type = 2 AND l.use_time > 0 THEN l.use_time END) AS avg_time, "
        "SUM(CASE WHEN l.type != 2 THEN 1 ELSE 0 END) AS fail_count "
        "FROM channels c "
        "LEFT JOIN logs l ON l.channel_id = c.id "
        "AND l.created_at > UNIX_TIMESTAMP(NOW() - INTERVAL %s MINUTE) "
        "GROUP BY c.id, c.name, c.status "
        "ORDER BY c.id",
        (minutes,)
    )
    result = {}
    for row in rows:
        total = int(row.get('total_count') or 0)
        success = int(row.get('success_count') or 0)
        fail = int(row.get('fail_count') or 0)
        avg_time = float(row.get('avg_time') or 0)
        success_rate = (success / total) if total > 0 else 1.0
        success_score = success_rate * 60
        if avg_time <= 0:
            resp_score = 20
        elif avg_time <= 2:
            resp_score = 20
        elif avg_time >= 10:
            resp_score = 0
        else:
            resp_score = max(0, 20 * (1 - (avg_time - 2) / 8))
        fail_rate = (fail / total) if total > 0 else 0
        fail_score = max(0, 20 * (1 - min(fail_rate, 1)))
        score = int(round(success_score + resp_score + fail_score))
        result[row['channel_id']] = {
            'channel_id': row['channel_id'],
            'name': row.get('name', ''),
            'status': row.get('status', 0),
            'success_count': success,
            'total_count': total,
            'fail_count': fail,
            'avg_time': avg_time,
            'health_score': max(0, min(100, score)),
        }
    return result
