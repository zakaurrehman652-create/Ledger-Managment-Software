from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import Account, VoucherEntry
from backend.schemas import AccountOut, AccountCreate, AccountUpdate

router = APIRouter(prefix="/api/v1/accounts", tags=["Chart of Accounts"])

@router.get("", response_model=List[AccountOut])
def get_accounts(
    type: Optional[str] = Query(None, description="Filter by account type: Asset, Liability, Equity, Revenue, Expense"),
    active_only: bool = True,
    db: Session = Depends(get_db)
):
    query = db.query(Account)
    if active_only:
        query = query.filter(Account.is_active == True)
    if type:
        query = query.filter(Account.type.ilike(type))
    return query.order_by(Account.code.asc()).all()

@router.post("", response_model=AccountOut, status_code=status.HTTP_201_CREATED)
def create_account(account_in: AccountCreate, db: Session = Depends(get_db)):
    existing = db.query(Account).filter(Account.code == account_in.code.strip()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Account code '{account_in.code}' already exists."
        )

    acc = Account(
        code=account_in.code.strip(),
        name=account_in.name.strip(),
        type=account_in.type.capitalize(),
        description=account_in.description,
        balance=account_in.balance,
        is_active=account_in.is_active
    )
    db.add(acc)
    db.commit()
    db.refresh(acc)
    return acc

@router.get("/{account_id}", response_model=AccountOut)
def get_account_by_id(account_id: int, db: Session = Depends(get_db)):
    acc = db.query(Account).filter(Account.id == account_id).first()
    if not acc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found.")
    return acc

@router.put("/{account_id}", response_model=AccountOut)
@router.put("/{account_id}/", response_model=AccountOut)
def update_account(account_id: int, update_in: AccountUpdate, db: Session = Depends(get_db)):
    acc = db.query(Account).filter(Account.id == account_id).first()
    if not acc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found.")

    if update_in.code is not None:
        code_str = update_in.code.strip()
        existing = db.query(Account).filter(Account.code == code_str, Account.id != account_id).first()
        if existing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Account code '{code_str}' is already used by another account.")
        acc.code = code_str
    if update_in.name is not None:
        acc.name = update_in.name.strip()
    if update_in.type is not None:
        acc.type = update_in.type.capitalize()
    if update_in.description is not None:
        acc.description = update_in.description
    if update_in.is_active is not None:
        acc.is_active = update_in.is_active

    db.commit()
    db.refresh(acc)
    return acc

@router.delete("/{account_id}")
@router.delete("/{account_id}/")
def delete_account(account_id: int, force: bool = False, db: Session = Depends(get_db)):
    acc = db.query(Account).filter(Account.id == account_id).first()
    if not acc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found.")

    # Check for linked transactions
    entries_count = db.query(VoucherEntry).filter(VoucherEntry.account_id == account_id).count()
    if entries_count > 0 and not force:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete account '{acc.name}' ({acc.code}) because it has {entries_count} recorded transaction entries in the ledger. Please delete those transactions first or edit the account."
        )

    if entries_count > 0 and force:
        # If force delete requested, remove linked entries
        db.query(VoucherEntry).filter(VoucherEntry.account_id == account_id).delete()

    db.delete(acc)
    db.commit()
    return {"message": f"Account '{acc.name}' deleted successfully.", "id": account_id}
