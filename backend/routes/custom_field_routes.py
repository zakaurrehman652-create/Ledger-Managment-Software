from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from backend.database import get_db
from backend.models import Party, CustomField, customer_custom_values
from backend.schemas import PartyCreate, PartyUpdate, PartyOut, CustomFieldOut, CustomFieldCreate, CustomFieldUpdate
from backend.auth import get_current_user, require_admin
from backend.models import User

router = APIRouter(prefix="/api/v1/custom_fields", tags=["Custom Fields"])

@router.get("/", response_model=List[CustomFieldOut])
def list_fields(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(CustomField).order_by(CustomField.order).all()

@router.post("/", response_model=CustomFieldOut, status_code=status.HTTP_201_CREATED)
def create_field(field: CustomFieldCreate, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    # Validate uniqueness of name
    existing = db.query(CustomField).filter(CustomField.name == field.name).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Field name already exists")
    # Determine order – place at end
    max_order = db.query(CustomField).order_by(CustomField.order.desc()).first()
    order_val = (max_order.order + 1) if max_order else 0
    db_field = CustomField(
        name=field.name,
        label=field.label,
        field_type=field.field_type,
        required=field.required,
        enabled=field.enabled,
        order=order_val,
        options=",".join(field.options) if field.options else None,
    )
    db.add(db_field)
    db.commit()
    db.refresh(db_field)
    return db_field

@router.put("/{field_id}", response_model=CustomFieldOut)
def update_field(field_id: int, field: CustomFieldUpdate, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    db_field = db.query(CustomField).filter(CustomField.id == field_id).first()
    if not db_field:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Custom field not found")
    if field.label is not None:
        db_field.label = field.label
    if field.field_type is not None:
        db_field.field_type = field.field_type
    if field.required is not None:
        db_field.required = field.required
    if field.enabled is not None:
        db_field.enabled = field.enabled
    if field.order is not None:
        db_field.order = field.order
    if field.options is not None:
        db_field.options = ",".join(field.options)
    db.commit()
    db.refresh(db_field)
    return db_field

@router.patch("/reorder", response_model=List[CustomFieldOut])
def reorder_fields(order: List[int], db: Session = Depends(get_db), _: User = Depends(require_admin)):
    # `order` is a list of field IDs in the desired sequence
    for idx, fid in enumerate(order):
        db.query(CustomField).filter(CustomField.id == fid).update({"order": idx})
    db.commit()
    return db.query(CustomField).order_by(CustomField.order).all()

@router.delete("/{field_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_field(field_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    db_field = db.query(CustomField).filter(CustomField.id == field_id).first()
    if not db_field:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Custom field not found")
    db.delete(db_field)
    db.commit()
    return None
