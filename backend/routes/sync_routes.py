from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import Voucher
from backend.schemas import SyncPayload, SyncResult
from backend.routes.voucher_routes import create_voucher

router = APIRouter(prefix="/api/v1/sync", tags=["Offline Synchronization"])

@router.post("", response_model=SyncResult)
@router.post("/", response_model=SyncResult)
def sync_offline_vouchers(payload: SyncPayload, db: Session = Depends(get_db)):
    synced_count = 0
    duplicates_skipped = 0

    for v_in in payload.vouchers:
        if v_in.client_uuid:
            existing = db.query(Voucher).filter(Voucher.client_uuid == v_in.client_uuid).first()
            if existing:
                duplicates_skipped += 1
                continue

        try:
            create_voucher(v_in, db)
            synced_count += 1
        except Exception:
            # Skip invalid offline voucher but continue syncing others
            continue

    return SyncResult(
        synced_count=synced_count,
        duplicates_skipped=duplicates_skipped,
        message=f"Sync successful: {synced_count} vouchers synchronized, {duplicates_skipped} duplicates resolved."
    )
