"""NewAPI Guardian Bot - 备份与恢复"""
import subprocess
import time
import logging
from pathlib import Path
from config import MYSQL_HOST, MYSQL_PORT, MYSQL_DATABASE, MYSQL_ROOT_PASSWORD, BACKUP_DIR

logger = logging.getLogger("guardian.backup")

BACKUP_PATH = Path(BACKUP_DIR)
BACKUP_PATH.mkdir(parents=True, exist_ok=True)
MAX_BACKUPS = 20


def create_backup(tag: str = "") -> tuple[bool, str, Path | None]:
    """创建数据库备份，返回 (success, message, filepath)"""
    ts = time.strftime("%Y%m%d-%H%M%S")
    suffix = f"-{tag}" if tag else ""
    filename = f"newapi-{ts}{suffix}.sql.gz"
    filepath = BACKUP_PATH / filename

    try:
        cmd = [
            "mysqldump",
            f"-uroot", f"-p{MYSQL_ROOT_PASSWORD}",
            f"-h{MYSQL_HOST}", f"-P{MYSQL_PORT}",
            "--single-transaction", "--quick",
            "--routines", "--triggers",
            MYSQL_DATABASE,
        ]
        with open(filepath, "wb") as f:
            dump = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            gz = subprocess.Popen(["gzip"], stdin=dump.stdout, stdout=f, stderr=subprocess.PIPE)
            dump.stdout.close()
            gz.communicate(timeout=120)
            dump.wait(timeout=120)

        if dump.returncode != 0:
            filepath.unlink(missing_ok=True)
            return False, f"mysqldump 失败 (code {dump.returncode})", None

        size = filepath.stat().st_size
        if size < 100:
            filepath.unlink(missing_ok=True)
            return False, "备份文件异常（太小）", None

        _cleanup_old_backups()
        size_mb = size / 1024 / 1024
        return True, f"备份成功：{filename}（{size_mb:.1f}MB）", filepath

    except Exception as e:
        logger.error(f"backup failed: {e}")
        filepath.unlink(missing_ok=True)
        return False, f"备份异常：{e}", None


def list_backups() -> list[dict]:
    """列出所有备份"""
    backups = []
    for f in sorted(BACKUP_PATH.glob("newapi-*.sql.gz"), reverse=True):
        stat = f.stat()
        backups.append({
            "filename": f.name,
            "path": str(f),
            "size_mb": round(stat.st_size / 1024 / 1024, 2),
            "created": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime)),
        })
    return backups


def restore_backup(filename: str) -> tuple[bool, str]:
    """恢复指定备份"""
    filepath = BACKUP_PATH / filename
    if not filepath.exists():
        return False, f"备份文件不存在：{filename}"

    try:
        # 先做一次当前状态备份
        ok, msg, _ = create_backup(tag="pre-restore")
        if not ok:
            return False, f"恢复前备份失败：{msg}"

        cmd_mysql = [
            "mysql",
            f"-uroot", f"-p{MYSQL_ROOT_PASSWORD}",
            f"-h{MYSQL_HOST}", f"-P{MYSQL_PORT}",
            MYSQL_DATABASE,
        ]
        with subprocess.Popen(["zcat", str(filepath)], stdout=subprocess.PIPE, stderr=subprocess.PIPE) as zcat:
            result = subprocess.run(
                cmd_mysql, stdin=zcat.stdout,
                capture_output=True, timeout=300,
            )

        if result.returncode != 0:
            err = result.stderr.decode("utf-8", errors="replace")[:200]
            return False, f"恢复失败：{err}"

        return True, f"恢复成功：{filename}"

    except Exception as e:
        logger.error(f"restore failed: {e}")
        return False, f"恢复异常：{e}"


def _cleanup_old_backups():
    """保留最近 MAX_BACKUPS 份"""
    files = sorted(BACKUP_PATH.glob("newapi-*.sql.gz"), key=lambda f: f.stat().st_mtime, reverse=True)
    for f in files[MAX_BACKUPS:]:
        f.unlink(missing_ok=True)
        logger.info(f"cleaned old backup: {f.name}")
