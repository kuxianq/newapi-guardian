"""核心数据库层 - 通用只读查询能力"""
import re
import pymysql
from decimal import Decimal
from contextlib import contextmanager
from typing import Any
from config import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE


@contextmanager
def get_conn():
    """获取数据库连接"""
    conn = pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=10,
        read_timeout=30,
    )
    try:
        yield conn
    finally:
        conn.close()


def _convert_decimals(obj):
    """递归转换 Decimal 为 float，确保 JSON 可序列化"""
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: _convert_decimals(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_decimals(item) for item in obj]
    return obj


def query(sql: str, args=None) -> list[dict]:
    """基础查询函数"""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, args or ())
            results = cur.fetchall()
            return _convert_decimals(results)


def is_safe_sql(sql: str) -> tuple[bool, str]:
    """
    检查 SQL 是否安全（只允许 SELECT）
    
    Returns:
        (is_safe, error_message)
    """
    sql_upper = sql.upper().strip()
    
    # 只允许 SELECT 开头
    if not sql_upper.startswith("SELECT"):
        return False, "只允许 SELECT 查询"
    
    # 禁止的关键词
    dangerous_keywords = [
        "DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "CREATE",
        "TRUNCATE", "REPLACE", "GRANT", "REVOKE", "EXEC", "EXECUTE",
        "INTO OUTFILE", "INTO DUMPFILE", "LOAD_FILE"
    ]
    
    for keyword in dangerous_keywords:
        if keyword in sql_upper:
            return False, f"禁止使用 {keyword}"
    
    # 禁止多语句
    if ";" in sql.rstrip(";"):
        return False, "禁止执行多条 SQL 语句"
    
    return True, ""


def execute_readonly_sql(sql: str, params: dict = None, limit: int = 100) -> dict:
    """
    AI 专用只读 SQL 执行器
    
    Args:
        sql: SELECT 语句
        params: 参数字典（可选）
        limit: 最多返回行数（默认 100）
    
    Returns:
        {
            "success": bool,
            "data": list[dict],
            "row_count": int,
            "error": str | None,
            "limited": bool  # 是否被限制了行数
        }
    """
    # 安全检查
    is_safe, error_msg = is_safe_sql(sql)
    if not is_safe:
        return {
            "success": False,
            "data": [],
            "row_count": 0,
            "error": f"SQL 安全检查失败: {error_msg}",
            "limited": False
        }
    
    # 自动添加 LIMIT（如果没有）
    sql_upper = sql.upper()
    has_limit = "LIMIT" in sql_upper
    limited = False
    
    if not has_limit:
        sql = f"{sql.rstrip(';')} LIMIT {limit}"
        limited = True
    else:
        # 检查 LIMIT 是否超过限制
        limit_match = re.search(r'LIMIT\s+(\d+)', sql, re.IGNORECASE)
        if limit_match:
            requested_limit = int(limit_match.group(1))
            if requested_limit > limit:
                sql = re.sub(r'LIMIT\s+\d+', f'LIMIT {limit}', sql, flags=re.IGNORECASE)
                limited = True
    
    try:
        # 执行查询
        with get_conn() as conn:
            with conn.cursor() as cur:
                if params:
                    # 参数化查询
                    cur.execute(sql, params)
                else:
                    cur.execute(sql)
                
                results = cur.fetchall()
                
                return {
                    "success": True,
                    "data": results,
                    "row_count": len(results),
                    "error": None,
                    "limited": limited
                }
    
    except Exception as e:
        return {
            "success": False,
            "data": [],
            "row_count": 0,
            "error": str(e),
            "limited": False
        }


# 向后兼容：保留一些常用的快捷查询
def get_all_channels() -> list[dict]:
    """快捷查询：获取所有渠道"""
    return query(
        "SELECT id, name, type, status, test_model, used_quota, "
        "response_time, priority, weight, auto_ban, base_url, models, "
        "`group`, tag, remark "
        "FROM channels ORDER BY id"
    )


def get_channel_by_id(channel_id: int) -> dict | None:
    """快捷查询：根据 ID 获取渠道"""
    rows = query(
        "SELECT id, name, type, status, test_model, used_quota, "
        "response_time, priority, weight, auto_ban, base_url, models, "
        "`group`, tag, remark "
        "FROM channels WHERE id = %s",
        (channel_id,)
    )
    return rows[0] if rows else None
