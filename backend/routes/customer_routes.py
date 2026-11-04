"""
Customer Management Routes
Customers are stored in the 'parties' table with type='Customer'.
Custom field values are stored in 'customer_custom_values'.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any

from backend.database import get_db
from backend.models import Party, CustomField, customer_custom_values
from backend.auth import get_current_user
from backend.models import User

router = APIRouter(prefix="/api/v1/customers", tags=["Customers"])


def _require_auth(current_user: User = Depends(get_current_user)):
    return current_user


def _options_to_list(options_str: Optional[str]) -> Optional[List[str]]:
    if not options_str:
        return None
    return [o.strip() for o in options_str.split(",") if o.strip()]


def _build_customer_out(customer: Party, db: Session) -> Dict[str, Any]:
    rows = db.execute(
        customer_custom_values.select().where(
            customer_custom_values.c.customer_id == customer.id
        )
    ).fetchall()
    field_map: Dict[str, str] = {}
    for row in rows:
        field = db.query(CustomField).filter(CustomField.id == row.field_id).first()
        if field:
            field_map[field.label] = row.value or ""

    return {
        "id": customer.id,
        "name": customer.name,
        "phone": customer.phone,
        "email": customer.email,
        "address": customer.address,
        "contact_person": customer.contact_person,
        "city": customer.city,
        "credit_limit": customer.credit_limit or 0.0,
        "current_balance": customer.current_balance or 0.0,
        "opening_balance": customer.opening_balance or 0.0,
        "balance_type": customer.balance_type or "Receivable",
        "notes": customer.notes,
        "created_at": customer.created_at.isoformat() if customer.created_at else None,
        "custom_field_values": field_map,
    }


@router.get("/")
def list_customers(
    search: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(_require_auth),
):
    q = db.query(Party).filter(Party.type == "Customer")
    if search:
        q = q.filter(
            Party.name.ilike(f"%{search}%") |
            Party.phone.ilike(f"%{search}%")
        )
    customers = q.order_by(Party.name.asc()).offset(skip).limit(limit).all()
    return [_build_customer_out(c, db) for c in customers]


@router.get("/{customer_id}")
def get_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(_require_auth),
):
    c = db.query(Party).filter(Party.id == customer_id, Party.type == "Customer").first()
    if not c:
        raise HTTPException(status_code=404, detail="Customer not found")
    return _build_customer_out(c, db)


@router.post("/", status_code=201)
def create_customer(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(_require_auth),
):
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Customer name is required")

    customer = Party(
        name=name,
        type="Customer",
        contact_person=payload.get("contact_person"),
        phone=payload.get("phone"),
        email=payload.get("email"),
        address=payload.get("address"),
        city=payload.get("city", "Karachi"),
        credit_limit=float(payload.get("credit_limit") or 0),
        current_balance=float(payload.get("current_balance") if payload.get("current_balance") is not None else (payload.get("opening_balance") or 0)),
        opening_balance=float(payload.get("opening_balance") or 0),
        balance_type=payload.get("balance_type", "Receivable"),
        notes=payload.get("notes"),
    )
    db.add(customer)
    db.flush()

    custom_fields = payload.get("custom_fields") or {}
    for field_id_str, value in custom_fields.items():
        field_id = int(field_id_str)
        field = db.query(CustomField).filter(CustomField.id == field_id).first()
        if not field:
            raise HTTPException(status_code=400, detail=f"Custom field {field_id} not found")
        if field.required and not value:
            raise HTTPException(status_code=400, detail=f"Field '{field.label}' is required")
        db.execute(customer_custom_values.insert().values(
            customer_id=customer.id, field_id=field_id, value=str(value)
        ))

    db.commit()
    db.refresh(customer)
    return _build_customer_out(customer, db)


@router.put("/{customer_id}")
def update_customer(
    customer_id: int,
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(_require_auth),
):
    c = db.query(Party).filter(Party.id == customer_id, Party.type == "Customer").first()
    if not c:
        raise HTTPException(status_code=404, detail="Customer not found")

    for field in ["name", "phone", "email", "address", "contact_person", "city", "notes"]:
        if field in payload:
            setattr(c, field, payload[field])
    if "credit_limit" in payload:
        c.credit_limit = float(payload["credit_limit"] or 0)
    if "opening_balance" in payload:
        c.opening_balance = float(payload["opening_balance"] or 0)
    if "balance_type" in payload:
        c.balance_type = payload["balance_type"]

    if "custom_fields" in payload and payload["custom_fields"] is not None:
        db.execute(customer_custom_values.delete().where(customer_custom_values.c.customer_id == c.id))
        for field_id_str, value in payload["custom_fields"].items():
            field_id = int(field_id_str)
            field = db.query(CustomField).filter(CustomField.id == field_id).first()
            if not field:
                raise HTTPException(status_code=400, detail=f"Custom field {field_id} not found")
            if field.required and not value:
                raise HTTPException(status_code=400, detail=f"Field '{field.label}' is required")
            db.execute(customer_custom_values.insert().values(
                customer_id=c.id, field_id=field_id, value=str(value)
            ))

    try:
        db.commit()
        db.refresh(c)
        return _build_customer_out(c, db)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update customer: {str(e)}")


@router.delete("/{customer_id}", status_code=204)
def delete_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(_require_auth),
):
    c = db.query(Party).filter(Party.id == customer_id, Party.type == "Customer").first()
    if not c:
        raise HTTPException(status_code=404, detail="Customer not found")
    db.execute(customer_custom_values.delete().where(customer_custom_values.c.customer_id == c.id))
    db.delete(c)
    db.commit()
    return None
