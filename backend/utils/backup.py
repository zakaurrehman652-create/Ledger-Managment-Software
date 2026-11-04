import os
import glob
import sqlite3
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger("ledger.backup")

BACKUP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backups"))
DEFAULT_SQLITE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "ledger.db"))


def ensure_backup_dir() -> str:
    """Ensure the backup directory exists."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    return BACKUP_DIR


def create_database_backup(tag: str = "backup", max_backups: int = 30) -> Dict[str, Any]:
    """
    Creates an atomic, consistent database backup using SQLite online backup API.
    Guarantees zero database corruption and validates the created backup with PRAGMA integrity_check.
    Also rotates older backups beyond max_backups.
    """
    ensure_backup_dir()
    db_path = os.getenv("SQLITE_PATH", DEFAULT_SQLITE_PATH)

    if not os.path.exists(db_path):
        logger.warning(f"Database file not found at {db_path}; skipping backup.")
        return {
            "success": False,
            "message": f"Database file not found at {db_path}",
            "filename": None,
            "path": None
        }

    clean_tag = "".join(c for c in tag if c.isalnum() or c in ("-", "_")).strip() or "backup"
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"ledger_backup_{clean_tag}_{timestamp}.db"
    dest_path = os.path.join(BACKUP_DIR, backup_filename)

    try:
        # SQLite native online backup: locks source read-only, copies page by page
        source_conn = sqlite3.connect(db_path, timeout=30.0)
        dest_conn = sqlite3.connect(dest_path)

        with dest_conn:
            source_conn.backup(dest_conn, pages=100)

        dest_conn.close()
        source_conn.close()

        # Validate newly created backup using integrity check
        check_conn = sqlite3.connect(dest_path)
        check_cur = check_conn.cursor()
        check_cur.execute("PRAGMA integrity_check;")
        check_result = check_cur.fetchone()
        check_conn.close()

        if not check_result or check_result[0] != "ok":
            if os.path.exists(dest_path):
                os.remove(dest_path)
            raise RuntimeError(f"Backup verification failed: {check_result}")

        size_bytes = os.path.getsize(dest_path)
        logger.info(f"Database backup successfully created at {dest_path} ({size_bytes} bytes).")

        # Cleanup older backups to preserve disk space
        cleanup_old_backups(max_backups)

        return {
            "success": True,
            "filename": backup_filename,
            "path": dest_path,
            "tag": clean_tag,
            "size_bytes": size_bytes,
            "size_kb": round(size_bytes / 1024, 2),
            "created_at": datetime.utcnow().isoformat(),
            "integrity": "ok"
        }
    except Exception as e:
        logger.exception(f"Database backup failed: {e}")
        if os.path.exists(dest_path):
            try:
                os.remove(dest_path)
            except Exception:
                pass
        return {
            "success": False,
            "message": str(e),
            "filename": None,
            "path": None
        }


def list_backups() -> List[Dict[str, Any]]:
    """List all available database backups in descending chronological order."""
    ensure_backup_dir()
    files = glob.glob(os.path.join(BACKUP_DIR, "ledger_backup_*.db"))
    backups = []

    for fpath in sorted(files, key=os.path.getmtime, reverse=True):
        fname = os.path.basename(fpath)
        size = os.path.getsize(fpath)
        mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
        backups.append({
            "filename": fname,
            "path": fpath,
            "size_bytes": size,
            "size_kb": round(size / 1024, 2),
            "created_at": mtime.isoformat()
        })

    return backups


def cleanup_old_backups(keep_count: int = 30) -> int:
    """Retains the most recent `keep_count` backups and removes older ones."""
    ensure_backup_dir()
    files = glob.glob(os.path.join(BACKUP_DIR, "ledger_backup_*.db"))
    sorted_files = sorted(files, key=os.path.getmtime, reverse=True)

    removed = 0
    if len(sorted_files) > keep_count:
        for old_file in sorted_files[keep_count:]:
            try:
                os.remove(old_file)
                removed += 1
            except Exception as e:
                logger.warning(f"Could not remove old backup {old_file}: {e}")

    return removed


def restore_database_backup(filename: str) -> Dict[str, Any]:
    """
    Safely restores a backup after creating a pre-restore backup.
    """
    ensure_backup_dir()
    safe_filename = os.path.basename(filename)
    backup_path = os.path.join(BACKUP_DIR, safe_filename)
    db_path = os.getenv("SQLITE_PATH", DEFAULT_SQLITE_PATH)

    if not os.path.exists(backup_path):
        return {"success": False, "message": f"Backup file {safe_filename} not found."}

    # Verify backup integrity before restoring
    try:
        check_conn = sqlite3.connect(backup_path)
        check_cur = check_conn.cursor()
        check_cur.execute("PRAGMA integrity_check;")
        check_result = check_cur.fetchone()
        check_conn.close()
        if not check_result or check_result[0] != "ok":
            return {"success": False, "message": "Target backup is corrupt. Restore aborted."}
    except Exception as e:
        return {"success": False, "message": f"Failed to verify backup: {e}"}

    # Step 1: Create a safety backup of current state
    create_database_backup(tag="pre-restore")

    # Step 2: Restore via SQLite backup API to active database
    try:
        src_conn = sqlite3.connect(backup_path)
        dst_conn = sqlite3.connect(db_path, timeout=30.0)
        with dst_conn:
            src_conn.backup(dst_conn, pages=100)
        dst_conn.close()
        src_conn.close()

        return {
            "success": True,
            "message": f"Successfully restored database from {safe_filename}.",
            "restored_from": safe_filename,
            "restored_at": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.exception(f"Restore failed: {e}")
        return {"success": False, "message": f"Restore failed: {str(e)}"}
