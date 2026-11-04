"""
Supplier Management Routes
Handles CRUD for suppliers and supplier custom fields.
Suppliers are stored in the 'parties' table with type='Supplier'.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import json

from backend.database import get_db
from backend.models import Party, SupplierCustomField, supplier_custom_values
from backend.auth import get_current_user
from backend.models import User

router = APIRouter(prefix="/api/v1/suppliers", tags=["Suppliers"])


# --------------------------------------------------------------------------- #
#  Helpers                                                                      #
# --------------------------------------------------------------------------- #

def _is_authorized(current_user: User = Depends(get_current_user)):
    return current_user


def _require_admin(current_user: User = Depends(get_current_user)):
    role = (current_user.role or "").lower()
    if role not in ("admin", "lead financial controller"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return current_user


def _options_to_list(options_str: Optional[str]) -> Optional[List[str]]:
    if not options_str:
        return None
    return [o.strip() for o in options_str.split(",") if o.strip()]


def _build_supplier_out(supplier: Party, db: Session) -> Dict[str, Any]:
    """Build a dict representation of a Supplier with its custom field values."""
    # Fetch custom field values
    rows = db.execute(
        supplier_custom_values.select().where(
            supplier_custom_values.c.supplier_id == supplier.id
        )
    ).fetchall()
    field_map: Dict[str, str] = {}
    for row in rows:
        field = db.query(SupplierCustomField).filter(SupplierCustomField.id == row.field_id).first()
        if field:
            field_map[field.label] = row.value or ""

    return {
        "id": supplier.id,
        "name": supplier.name,
        "phone": supplier.phone,
        "address": supplier.address,
        "business_name": supplier.contact_person,
        "opening_balance": supplier.opening_balance or 0.0,
        "current_balance": supplier.current_balance if supplier.current_balance is not None else (supplier.opening_balance or 0.0),
        "balance_type": supplier.balance_type or "Payable",
        "notes": supplier.notes,
        "created_at": supplier.created_at.isoformat() if supplier.created_at else None,
        "custom_field_values": field_map,
    }


# --------------------------------------------------------------------------- #
#  Supplier CRUD                                                                #
# --------------------------------------------------------------------------- #

@router.get("")
@router.get("/")
def list_suppliers(
    search: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(_is_authorized),
):
    q = db.query(Party).filter(Party.type == "Supplier")
    if search:
        q = q.filter(
            Party.name.ilike(f"%{search}%") |
            Party.phone.ilike(f"%{search}%") |
            Party.contact_person.ilike(f"%{search}%")
        )
    suppliers = q.order_by(Party.name.asc()).offset(skip).limit(limit).all()
    return [_build_supplier_out(s, db) for s in suppliers]


@router.get("/count")
def count_suppliers(
    db: Session = Depends(get_db),
    current_user: User = Depends(_is_authorized),
):
    total = db.query(Party).filter(Party.type == "Supplier").count()
    suppliers = db.query(Party).filter(Party.type == "Supplier").all()
    total_payable = sum(
        s.opening_balance or 0 for s in suppliers if (s.balance_type or "Payable") == "Payable"
    )
    total_receivable = sum(
        s.opening_balance or 0 for s in suppliers if (s.balance_type or "Payable") == "Receivable"
    )
    return {
        "total": total,
        "total_payable": total_payable,
        "total_receivable": total_receivable,
    }


@router.get("/{supplier_id}")
def get_supplier(
    supplier_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(_is_authorized),
):
    s = db.query(Party).filter(Party.id == supplier_id, Party.type == "Supplier").first()
    if not s:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return _build_supplier_out(s, db)


@router.post("", status_code=status.HTTP_201_CREATED)
@router.post("/", status_code=status.HTTP_201_CREATED)
def create_supplier(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(_is_authorized),
):
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Supplier name is required")

    balance_type = payload.get("balance_type", "Payable")
    if balance_type not in ("Payable", "Receivable"):
        raise HTTPException(status_code=400, detail="balance_type must be 'Payable' or 'Receivable'")

    supplier = Party(
        name=name,
        type="Supplier",
        contact_person=payload.get("business_name"),
        phone=payload.get("phone"),
        address=payload.get("address"),
        opening_balance=float(payload.get("opening_balance") or 0),
        current_balance=float(payload.get("current_balance") if payload.get("current_balance") is not None else (payload.get("opening_balance") or 0)),
        balance_type=balance_type,
        notes=payload.get("notes"),
    )
    db.add(supplier)
    db.flush()

    # Save custom field values
    custom_fields = payload.get("custom_fields") or {}
    for field_id_str, value in custom_fields.items():
        field_id = int(field_id_str)
        field = db.query(SupplierCustomField).filter(SupplierCustomField.id == field_id).first()
        if not field:
            raise HTTPException(status_code=400, detail=f"Custom field {field_id} not found")
        if field.required and not value:
            raise HTTPException(status_code=400, detail=f"Field '{field.label}' is required")
        db.execute(supplier_custom_values.insert().values(
            supplier_id=supplier.id, field_id=field_id, value=str(value)
        ))

    db.commit()
    db.refresh(supplier)
    return _build_supplier_out(supplier, db)


@router.put("/{supplier_id}")
def update_supplier(
    supplier_id: int,
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(_is_authorized),
):
    s = db.query(Party).filter(Party.id == supplier_id, Party.type == "Supplier").first()
    if not s:
        raise HTTPException(status_code=404, detail="Supplier not found")

    if "name" in payload and payload["name"]:
        s.name = payload["name"].strip()
    if "phone" in payload:
        s.phone = payload["phone"]
    if "address" in payload:
        s.address = payload["address"]
    if "business_name" in payload:
        s.contact_person = payload["business_name"]
    if "opening_balance" in payload:
        s.opening_balance = float(payload["opening_balance"] or 0)
    if "balance_type" in payload:
        if payload["balance_type"] not in ("Payable", "Receivable"):
            raise HTTPException(status_code=400, detail="balance_type must be 'Payable' or 'Receivable'")
        s.balance_type = payload["balance_type"]
    if "notes" in payload:
        s.notes = payload["notes"]

    # Update custom fields
    if "custom_fields" in payload and payload["custom_fields"] is not None:
        db.execute(
            supplier_custom_values.delete().where(supplier_custom_values.c.supplier_id == s.id)
        )
        for field_id_str, value in payload["custom_fields"].items():
            field_id = int(field_id_str)
            field = db.query(SupplierCustomField).filter(SupplierCustomField.id == field_id).first()
            if not field:
                raise HTTPException(status_code=400, detail=f"Custom field {field_id} not found")
            if field.required and not value:
                raise HTTPException(status_code=400, detail=f"Field '{field.label}' is required")
            db.execute(supplier_custom_values.insert().values(
                supplier_id=s.id, field_id=field_id, value=str(value)
            ))

    try:
        db.commit()
        db.refresh(s)
        return _build_supplier_out(s, db)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update supplier: {str(e)}")


@router.delete("/{supplier_id}", status_code=204)
def delete_supplier(
    supplier_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(_is_authorized),
):
    s = db.query(Party).filter(Party.id == supplier_id, Party.type == "Supplier").first()
    if not s:
        raise HTTPException(status_code=404, detail="Supplier not found")
    db.execute(supplier_custom_values.delete().where(supplier_custom_values.c.supplier_id == s.id))
    db.delete(s)
    db.commit()
    return None


# --------------------------------------------------------------------------- #
#  Supplier Custom Fields                                                       #
# --------------------------------------------------------------------------- #

@router.get("/custom-fields/list")
def list_supplier_custom_fields(
    db: Session = Depends(get_db),
    current_user: User = Depends(_is_authorized),
):
    fields = db.query(SupplierCustomField).order_by(SupplierCustomField.order).all()
    return [
        {
            "id": f.id,
            "name": f.name,
            "label": f.label,
            "field_type": f.field_type,
            "required": f.required,
            "enabled": f.enabled,
            "order": f.order,
            "options": _options_to_list(f.options),
        }
        for f in fields
    ]


@router.post("/custom-fields/list", status_code=201)
def create_supplier_custom_field(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(_require_admin),
):
    name = (payload.get("name") or "").strip()
    label = (payload.get("label") or "").strip()
    field_type = (payload.get("field_type") or "").strip()

    if not name or not label or not field_type:
        raise HTTPException(status_code=400, detail="name, label, and field_type are required")
    if field_type not in ("text", "long_text", "number", "date", "dropdown", "checkbox"):
        raise HTTPException(status_code=400, detail="Invalid field_type")

    existing = db.query(SupplierCustomField).filter(SupplierCustomField.name == name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Field name already exists")

    max_order = db.query(SupplierCustomField).order_by(SupplierCustomField.order.desc()).first()
    order_val = (max_order.order + 1) if max_order else 0

    options_raw = payload.get("options")
    options_str = ",".join(options_raw) if isinstance(options_raw, list) else None

    field = SupplierCustomField(
        name=name,
        label=label,
        field_type=field_type,
        required=bool(payload.get("required", False)),
        enabled=bool(payload.get("enabled", True)),
        order=order_val,
        options=options_str,
    )
    db.add(field)
    db.commit()
    db.refresh(field)
    return {
        "id": field.id,
        "name": field.name,
        "label": field.label,
        "field_type": field.field_type,
        "required": field.required,
        "enabled": field.enabled,
        "order": field.order,
        "options": _options_to_list(field.options),
    }


@router.put("/custom-fields/{field_id}")
def update_supplier_custom_field(
    field_id: int,
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(_require_admin),
):
    field = db.query(SupplierCustomField).filter(SupplierCustomField.id == field_id).first()
    if not field:
        raise HTTPException(status_code=404, detail="Custom field not found")

    if "label" in payload:
        field.label = payload["label"]
    if "field_type" in payload:
        field.field_type = payload["field_type"]
    if "required" in payload:
        field.required = bool(payload["required"])
    if "enabled" in payload:
        field.enabled = bool(payload["enabled"])
    if "order" in payload:
        field.order = int(payload["order"])
    if "options" in payload:
        opts = payload["options"]
        field.options = ",".join(opts) if isinstance(opts, list) else opts

    db.commit()
    db.refresh(field)
    return {
        "id": field.id,
        "name": field.name,
        "label": field.label,
        "field_type": field.field_type,
        "required": field.required,
        "enabled": field.enabled,
        "order": field.order,
        "options": _options_to_list(field.options),
    }


@router.delete("/custom-fields/{field_id}", status_code=204)
def delete_supplier_custom_field(
    field_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(_require_admin),
):
    field = db.query(SupplierCustomField).filter(SupplierCustomField.id == field_id).first()
    if not field:
        raise HTTPException(status_code=404, detail="Custom field not found")
    # Remove all values for this field first
    db.execute(supplier_custom_values.delete().where(supplier_custom_values.c.field_id == field_id))
    db.delete(field)
    db.commit()
    return None


@router.patch("/custom-fields/reorder")
def reorder_supplier_custom_fields(
    order: List[int],
    db: Session = Depends(get_db),
    current_user: User = Depends(_require_admin),
):
    for idx, fid in enumerate(order):
        db.query(SupplierCustomField).filter(SupplierCustomField.id == fid).update({"order": idx})
    db.commit()
    return list_supplier_custom_fields(db=db, current_user=current_user)
