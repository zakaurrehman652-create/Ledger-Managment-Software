from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import Party, VoucherEntry, Voucher
from backend.schemas import PartyOut, PartyCreate, PartyUpdate

router = APIRouter(prefix="/api/v1/parties", tags=["Parties (Customers & Vendors)"])

@router.get("", response_model=List[PartyOut])
def get_parties(
    type: Optional[str] = Query(None, description="Filter by party type: Customer or Vendor"),
    db: Session = Depends(get_db)
):
    query = db.query(Party)
    if type:
        query = query.filter(Party.type.ilike(type))
    return query.order_by(Party.name.asc()).all()

@router.post("", response_model=PartyOut, status_code=status.HTTP_201_CREATED)
def create_party(party_in: PartyCreate, db: Session = Depends(get_db)):
    existing = db.query(Party).filter(Party.name == party_in.name.strip()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Party '{party_in.name}' is already registered."
        )

    party = Party(
        name=party_in.name.strip(),
        type=party_in.type.capitalize(),
        contact_person=party_in.contact_person,
        phone=party_in.phone,
        email=party_in.email,
        address=party_in.address,
        city=party_in.city or "Karachi",
        credit_limit=party_in.credit_limit,
        current_balance=party_in.current_balance
    )
    db.add(party)
    db.commit()
    db.refresh(party)
    return party

@router.get("/{party_id}", response_model=PartyOut)
def get_party_by_id(party_id: int, db: Session = Depends(get_db)):
    party = db.query(Party).filter(Party.id == party_id).first()
    if not party:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Party record not found.")
    return party

@router.put("/{party_id}", response_model=PartyOut)
@router.put("/{party_id}/", response_model=PartyOut)
def update_party(party_id: int, update_in: PartyUpdate, db: Session = Depends(get_db)):
    party = db.query(Party).filter(Party.id == party_id).first()
    if not party:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Party record not found.")

    for field, val in update_in.dict(exclude_unset=True).items():
        setattr(party, field, val)

    db.commit()
    db.refresh(party)
    return party

@router.delete("/{party_id}")
@router.delete("/{party_id}/")
def delete_party(party_id: int, force: bool = False, db: Session = Depends(get_db)):
    party = db.query(Party).filter(Party.id == party_id).first()
    if not party:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Party record not found.")

    entries_count = db.query(VoucherEntry).filter(VoucherEntry.party_id == party_id).count()
    if entries_count > 0 and not force:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete party '{party.name}' because it has {entries_count} recorded transaction entries in the ledger. Please delete those transactions first or edit the party."
        )

    if entries_count > 0 and force:
        # Nullify party_id on entries
        db.query(VoucherEntry).filter(VoucherEntry.party_id == party_id).update({VoucherEntry.party_id: None})

    db.delete(party)
    db.commit()
    return {"message": f"Party '{party.name}' deleted successfully.", "id": party_id}
