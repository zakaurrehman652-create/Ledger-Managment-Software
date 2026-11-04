from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Dict, Any
from pydantic import BaseModel

from backend.auth import get_current_user
from backend.models import User
from backend.utils.backup import (
    create_database_backup,
    list_backups,
    restore_database_backup
)

router = APIRouter(prefix="/api/v1/system/backup", tags=["Database Safety & Backup"])


class BackupRequest(BaseModel):
    tag: str = "manual"


class RestoreRequest(BaseModel):
    filename: str


@router.post("", status_code=status.HTTP_201_CREATED)
def trigger_manual_backup(
    req: BackupRequest = BackupRequest(),
    current_user: User = Depends(get_current_user)
):
    """
    Creates an atomic, consistent database backup. Requires authentication.
    """
    res = create_database_backup(tag=req.tag)
    if not res.get("success"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Backup creation failed: {res.get('message')}"
        )
    return res


@router.get("/list")
def get_backups_list(current_user: User = Depends(get_current_user)):
    """
    Returns list of all stored backups with timestamps and sizes. Requires authentication.
    """
    return {
        "count": len(list_backups()),
        "backups": list_backups()
    }


@router.post("/restore")
def restore_backup(
    req: RestoreRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Restores the database from a verified backup snapshot.
    Automatically creates a pre-restore backup first. Requires authentication.
    """
    res = restore_database_backup(filename=req.filename)
    if not res.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=res.get("message", "Restore failed")
        )
    return res
