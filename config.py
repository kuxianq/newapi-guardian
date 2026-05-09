"""NewAPI Guardian Bot - 配置"""
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()


def read_file_env(name: str, default: str = "") -> str:
    path = os.getenv(f"{name}_FILE")
    if path and Path(path).exists():
        return Path(path).read_text().strip()
    return os.getenv(name, default)

# Telegram
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
AUTHORIZED_IDS = set(
    int(x.strip()) for x in os.getenv("AUTHORIZED_TELEGRAM_IDS", "").split(",") if x.strip()
)

# MySQL (只读)
MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "newapi_guardian")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "newapi")

# NewAPI
NEWAPI_BASE_URL = os.getenv("NEWAPI_BASE_URL", "http://127.0.0.1:3000")
NEWAPI_ADMIN_TOKEN = read_file_env("NEWAPI_ADMIN_TOKEN")
NEWAPI_ADMIN_USER_ID = os.getenv("NEWAPI_ADMIN_USER_ID", "1")

# 备份/恢复
MYSQL_ROOT_PASSWORD = read_file_env("MYSQL_ROOT_PASSWORD")
BACKUP_DIR = os.getenv("BACKUP_DIR", "/root/.openclaw/backups/mysql")

# 监控参数
CHECK_INTERVAL_MINUTES = int(os.getenv("CHECK_INTERVAL_MINUTES", "10"))
ALERT_CONSECUTIVE_FAILURES = int(os.getenv("ALERT_CONSECUTIVE_FAILURES", "3"))
ALERT_COOLDOWN_MINUTES = int(os.getenv("ALERT_COOLDOWN_MINUTES", "30"))
DAILY_REPORT_HOUR = int(os.getenv("DAILY_REPORT_HOUR", "9"))
