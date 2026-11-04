from backend.routes.voucher_routes import generate_reference_number
import json
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import GatePass, User
from backend.schemas import GatePassCreate, GatePassOut, GatePassItem

router = APIRouter(prefix="/api/v1/gate-pass", tags=["Gate Pass Management"])


def generate_gate_pass_number(db: Session, target_date: Optional[datetime] = None) -> str:
    """
    Auto-generates sequential Gate Pass number: TA-GP-YYYY-MMM-000001
    """
    if not target_date:
        target_date = datetime.utcnow()

    year = target_date.year
    month_abbr = target_date.strftime("%b").upper()
    prefix = f"TA-GP-{year}-{month_abbr}-"

    records = db.query(GatePass).filter(GatePass.pass_number.like(f"{prefix}%")).all()
    max_seq = 0
    for r in records:
        pnum = (r.pass_number or "").strip()
        if pnum.startswith(prefix):
            suffix = pnum[len(prefix):].strip()
            if suffix.isdigit():
                max_seq = max(max_seq, int(suffix))

    return f"{prefix}{max_seq + 1:06d}"


def _deserialize_items(items_raw: Optional[str]) -> List[GatePassItem]:
    if not items_raw:
        return []
    try:
        data = json.loads(items_raw)
        if isinstance(data, list):
            return [GatePassItem(**item) for item in data]
    except Exception:
        pass
    return []


@router.get("/next-number")
def get_next_number(date_str: Optional[str] = Query(None), db: Session = Depends(get_db)):
    target_date = datetime.utcnow()
    if date_str:
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            pass
    return {
        "next_pass_number": generate_gate_pass_number(db, target_date),
        "next_reference_no": generate_reference_number(db)
    }


@router.get("", response_model=List[GatePassOut])
def list_gate_passes(
    pass_type: Optional[str] = Query(None, description="Outward or Inward"),
    from_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    to_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    search: Optional[str] = Query(None),
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    query = db.query(GatePass)

    if pass_type and isinstance(pass_type, str):
        query = query.filter(GatePass.pass_type.ilike(pass_type.strip()))

    if from_date and isinstance(from_date, str):
        try:
            fd = datetime.strptime(from_date, "%Y-%m-%d")
            query = query.filter(GatePass.date >= fd)
        except ValueError:
            pass

    if to_date and isinstance(to_date, str):
        try:
            td = datetime.strptime(f"{to_date} 23:59:59", "%Y-%m-%d %H:%M:%S")
            query = query.filter(GatePass.date <= td)
        except ValueError:
            pass

    if search and isinstance(search, str):
        s = f"%{search.strip()}%"
        query = query.filter(
            (GatePass.pass_number.ilike(s)) |
            (GatePass.party_name.ilike(s)) |
            (GatePass.vehicle_number.ilike(s)) |
            (GatePass.driver_name.ilike(s)) |
            (GatePass.reference_no.ilike(s)) |
            (GatePass.remarks.ilike(s))
        )

    passes = query.order_by(GatePass.date.desc(), GatePass.id.desc()).offset(offset).limit(limit).all()

    out_list = []
    for gp in passes:
        items = _deserialize_items(gp.items_json)
        out_list.append(GatePassOut(
            id=gp.id,
            pass_number=gp.pass_number,
            date=gp.date,
            pass_type=gp.pass_type,
            party_name=gp.party_name,
            vehicle_number=gp.vehicle_number,
            driver_name=gp.driver_name,
            driver_phone=gp.driver_phone,
            bilty_number=gp.bilty_number,
            reference_no=gp.reference_no,
            items=items,
            total_amount=gp.total_amount or 0.0,
            payment_type=gp.payment_type or "Debit (Customer Ledger / Receivable)",
            remarks=gp.remarks,
            prepared_by=gp.prepared_by or "Muhammad Saad",
            gate_incharge=gp.gate_incharge or "Security Gate",
            authorized_by=gp.authorized_by or "Farm General Manager",
            created_at=gp.created_at
        ))
    return out_list


@router.post("", response_model=GatePassOut, status_code=status.HTTP_201_CREATED)
def create_gate_pass(
    gp_in: GatePassCreate,
    db: Session = Depends(get_db)
):
    gp_date = gp_in.date or datetime.utcnow()
    pass_num = (gp_in.pass_number.strip() if getattr(gp_in, 'pass_number', None) and gp_in.pass_number.strip() else None) or generate_gate_pass_number(db, gp_date)
    ref_no = (gp_in.reference_no.strip() if getattr(gp_in, 'reference_no', None) and gp_in.reference_no.strip() else None) or generate_reference_number(db)

    user = db.query(User).first()
    creator_name = gp_in.prepared_by or (user.full_name if user and user.full_name else "Muhammad Saad")

    # Serialize items to JSON
    items_dicts = [item.dict() for item in gp_in.items] if gp_in.items else []
    items_json_str = json.dumps(items_dicts)

    gp = GatePass(
        pass_number=pass_num,
        date=gp_date,
        pass_type=gp_in.pass_type or "Outward",
        party_name=gp_in.party_name,
        vehicle_number=gp_in.vehicle_number,
        driver_name=gp_in.driver_name,
        driver_phone=gp_in.driver_phone,
        bilty_number=gp_in.bilty_number,
        reference_no=ref_no,
        items_json=items_json_str,
        total_amount=gp_in.total_amount or 0.0,
        payment_type=gp_in.payment_type or "Debit (Customer Ledger / Receivable)",
        remarks=gp_in.remarks,
        prepared_by=creator_name,
        gate_incharge=gp_in.gate_incharge or "Security Officer",
        authorized_by=gp_in.authorized_by or "Muhammad Saad",
        created_at=datetime.utcnow()
    )
    try:
        db.add(gp)
        db.commit()
        db.refresh(gp)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create gate pass: {str(e)}"
        )

    return GatePassOut(
        id=gp.id,
        pass_number=gp.pass_number,
        date=gp.date,
        pass_type=gp.pass_type,
        party_name=gp.party_name,
        vehicle_number=gp.vehicle_number,
        driver_name=gp.driver_name,
        driver_phone=gp.driver_phone,
        bilty_number=gp.bilty_number,
        reference_no=gp.reference_no,
        items=gp_in.items,
        total_amount=gp.total_amount or 0.0,
        payment_type=gp.payment_type or "Debit (Customer Ledger / Receivable)",
        remarks=gp.remarks,
        prepared_by=gp.prepared_by or "Tri Agro Farms Dispatch",
        gate_incharge=gp.gate_incharge or "Security Officer",
        authorized_by=gp.authorized_by or "Farm General Manager",
        created_at=gp.created_at
    )


@router.get("/{gp_id}", response_model=GatePassOut)
def get_gate_pass(gp_id: int, db: Session = Depends(get_db)):
    gp = db.query(GatePass).filter(GatePass.id == gp_id).first()
    if not gp:
        raise HTTPException(status_code=404, detail="Gate Pass not found")
    items = _deserialize_items(gp.items_json)
    return GatePassOut(
        id=gp.id,
        pass_number=gp.pass_number,
        date=gp.date,
        pass_type=gp.pass_type,
        party_name=gp.party_name,
        vehicle_number=gp.vehicle_number,
        driver_name=gp.driver_name,
        driver_phone=gp.driver_phone,
        bilty_number=gp.bilty_number,
        reference_no=gp.reference_no,
        items=items,
        total_amount=gp.total_amount or 0.0,
        payment_type=gp.payment_type or "Debit (Customer Ledger / Receivable)",
        remarks=gp.remarks,
        prepared_by=gp.prepared_by or "Muhammad Saad",
        gate_incharge=gp.gate_incharge or "Security Gate",
        authorized_by=gp.authorized_by or "Muhammad Saad",
        created_at=gp.created_at
    )


@router.delete("/{gp_id}")
def delete_gate_pass(gp_id: int, db: Session = Depends(get_db)):
    gp = db.query(GatePass).filter(GatePass.id == gp_id).first()
    if not gp:
        raise HTTPException(status_code=404, detail="Gate Pass not found")
    try:
        pnum = gp.pass_number
        db.delete(gp)
        db.commit()
        return {"success": True, "message": f"Gate Pass {pnum} deleted successfully."}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete gate pass: {str(e)}"
        )
