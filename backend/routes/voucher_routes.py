from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import Voucher, VoucherEntry, Account, Party
from backend.schemas import VoucherOut, VoucherCreate, VoucherEntryOut

router = APIRouter(prefix="/api/v1/vouchers", tags=["Vouchers & Journal Entries"])

def get_balancing_account(db: Session) -> Account:
    acc = db.query(Account).filter(Account.code == "1010").first()
    if acc:
        return acc
    acc = db.query(Account).filter(Account.type == "Asset", Account.name.ilike("%Cash%")).first()
    if acc:
        return acc
    acc = db.query(Account).filter(Account.type == "Asset").first()
    if acc:
        return acc
    acc = Account(
        code="1010",
        name="Cash in Hand",
        type="Asset",
        description="Physical Cash in Vault / Register",
        balance=0.0,
        is_active=True
    )
    db.add(acc)
    db.flush()
    return acc

def generate_voucher_number(db: Session, v_type_or_date=None, v_date: Optional[datetime] = None) -> str:
    """
    Auto-generates voucher number in format: TA-YYYY-MMM-000001 (e.g. TA-2026-OCT-000001)
    Sequenced sequentially till infinite.
    """
    target_date = datetime.utcnow()
    if isinstance(v_type_or_date, datetime):
        target_date = v_type_or_date
    elif isinstance(v_date, datetime):
        target_date = v_date
    
    year = target_date.year
    month_abbr = target_date.strftime("%b").upper()
    prefix = f"TA-{year}-{month_abbr}-"

    vouchers = db.query(Voucher).filter(Voucher.voucher_number.like(f"{prefix}%")).all()
    max_seq = 0
    for v in vouchers:
        vnum = (v.voucher_number or "").replace(" ", "").strip()
        if vnum.startswith(prefix):
            suffix = vnum[len(prefix):].strip()
            if suffix.isdigit():
                max_seq = max(max_seq, int(suffix))

    next_seq = max_seq + 1
    return f"{prefix}{next_seq:06d}"

def generate_reference_number(db: Session) -> str:
    """
    Auto-generates reference number in format: TA-ref-000001
    Unified sequence across Vouchers and Gate Passes.
    """
    prefix = "TA-ref-"
    max_seq = 0
    vouchers = db.query(Voucher).filter(Voucher.reference_no.like(f"{prefix}%")).all()
    for v in vouchers:
        rnum = (v.reference_no or "").strip()
        if rnum.startswith(prefix):
            suffix = rnum[len(prefix):].strip()
            if suffix.isdigit():
                max_seq = max(max_seq, int(suffix))

    from backend.models import GatePass
    gps = db.query(GatePass).filter(GatePass.reference_no.like(f"{prefix}%")).all()
    for g in gps:
        rnum = (g.reference_no or "").strip()
        if rnum.startswith(prefix):
            suffix = rnum[len(prefix):].strip()
            if suffix.isdigit():
                max_seq = max(max_seq, int(suffix))

    next_seq = max_seq + 1
    return f"{prefix}{next_seq:06d}"

def update_account_balance(account: Account, entry_type: str, amount: float):
    # Asset & Expense normal balance: DEBIT
    # Liability, Equity, Revenue normal balance: CREDIT
    if account.type in ["Asset", "Expense"]:
        if entry_type == "Debit":
            account.balance += amount
        else:
            account.balance -= amount
    else:
        if entry_type == "Credit":
            account.balance += amount
        else:
            account.balance -= amount

def update_party_balance(party: Party, entry_type: str, amount: float):
    # Ensure current_balance inherits opening_balance if uninitialized
    if (party.current_balance == 0.0 or party.current_balance is None) and party.opening_balance:
        party.current_balance = float(party.opening_balance)

    if party.type == "Customer":
        if entry_type == "Debit":
            party.current_balance += amount
        else:
            party.current_balance -= amount
    else: # Vendor / Supplier
        if entry_type == "Credit":
            party.current_balance += amount
        else:
            party.current_balance -= amount

def reverse_account_balance(account: Account, entry_type: str, amount: float):
    if account.type in ["Asset", "Expense"]:
        if entry_type == "Debit":
            account.balance -= amount
        else:
            account.balance += amount
    else:
        if entry_type == "Credit":
            account.balance -= amount
        else:
            account.balance += amount

def reverse_party_balance(party: Party, entry_type: str, amount: float):
    if party.type == "Customer":
        if entry_type == "Debit":
            party.current_balance -= amount
        else:
            party.current_balance += amount
    else:
        if entry_type == "Credit":
            party.current_balance -= amount
        else:
            party.current_balance += amount


@router.get("/next-sequence")
@router.get("/next-sequence/")
def get_next_sequence(date: Optional[str] = Query(None), db: Session = Depends(get_db)):
    target_date = datetime.utcnow()
    if date:
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            pass
    
    return {
        "next_voucher_number": generate_voucher_number(db, v_date=target_date),
        "next_reference_no": generate_reference_number(db)
    }

@router.get("", response_model=List[VoucherOut])
def get_vouchers(
    voucher_type: Optional[str] = Query(None),
    account_id: Optional[int] = Query(None),
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    query = db.query(Voucher)
    if voucher_type:
        query = query.filter(Voucher.voucher_type.ilike(voucher_type))
    if account_id:
        query = query.join(Voucher.entries).filter(VoucherEntry.account_id == account_id)

    vouchers = query.order_by(Voucher.date.desc(), Voucher.id.desc()).offset(offset).limit(limit).all()

    result = []
    for v in vouchers:
        entries = []
        for e in v.entries:
            entries.append(VoucherEntryOut(
                id=e.id,
                account_id=e.account_id,
                party_id=e.party_id,
                entry_type=e.entry_type,
                amount=e.amount,
                narration=e.narration,
                account_name=e.account.name if e.account else "N/A",
                party_name=e.party.name if e.party else None
            ))
        result.append(VoucherOut(
            id=v.id,
            voucher_number=v.voucher_number,
            date=v.date,
            voucher_type=v.voucher_type,
            reference_no=v.reference_no,
            narration=v.narration,
            total_amount=v.total_amount,
            created_by=v.created_by,
            is_synced=v.is_synced,
            client_uuid=v.client_uuid,
            entries=entries,
            created_at=v.created_at
        ))
    return result

@router.post("", response_model=VoucherOut, status_code=status.HTTP_201_CREATED)
def create_voucher(voucher_in: VoucherCreate, db: Session = Depends(get_db)):
    # Deduplication check for offline sync
    if voucher_in.client_uuid:
        existing = db.query(Voucher).filter(Voucher.client_uuid == voucher_in.client_uuid).first()
        if existing:
            entries = [
                VoucherEntryOut(
                    id=e.id,
                    account_id=e.account_id,
                    party_id=e.party_id,
                    entry_type=e.entry_type,
                    amount=e.amount,
                    narration=e.narration,
                    account_name=e.account.name if e.account else "N/A",
                    party_name=e.party.name if e.party else None
                )
                for e in existing.entries
            ]
            return VoucherOut(
                id=existing.id,
                voucher_number=existing.voucher_number,
                date=existing.date,
                voucher_type=existing.voucher_type,
                reference_no=existing.reference_no,
                narration=existing.narration,
                total_amount=existing.total_amount,
                created_by=existing.created_by,
                is_synced=existing.is_synced,
                client_uuid=existing.client_uuid,
                entries=entries,
                created_at=existing.created_at
            )

    if not voucher_in.entries or len(voucher_in.entries) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Voucher must have at least one line entry."
        )

    from backend.schemas import VoucherEntryCreate
    entries_list = list(voucher_in.entries)

    total_debits = sum(e.amount for e in entries_list if e.entry_type == "Debit")
    total_credits = sum(e.amount for e in entries_list if e.entry_type == "Credit")

    # Auto-balance if single entry or unequal debit/credit
    diff = round(total_debits - total_credits, 2)
    if abs(diff) > 0.01:
        bal_acc = get_balancing_account(db)
        if diff > 0:
            # Add contra Credit entry
            entries_list.append(VoucherEntryCreate(
                account_id=bal_acc.id,
                party_id=None,
                entry_type="Credit",
                amount=abs(diff),
                narration=voucher_in.narration or "Auto-balancing contra entry"
            ))
            total_credits += abs(diff)
        else:
            # Add contra Debit entry
            entries_list.append(VoucherEntryCreate(
                account_id=bal_acc.id,
                party_id=None,
                entry_type="Debit",
                amount=abs(diff),
                narration=voucher_in.narration or "Auto-balancing contra entry"
            ))
            total_debits += abs(diff)

    v_date = voucher_in.date or datetime.utcnow()
    v_num = (voucher_in.voucher_number.strip() if getattr(voucher_in, "voucher_number", None) and voucher_in.voucher_number.strip() else None) or generate_voucher_number(db, v_date=v_date)
    ref_no = voucher_in.reference_no.strip() if voucher_in.reference_no and voucher_in.reference_no.strip() else generate_reference_number(db)

    voucher = Voucher(
        voucher_number=v_num,
        date=v_date,
        voucher_type=voucher_in.voucher_type,
        reference_no=ref_no,
        narration=voucher_in.narration,
        total_amount=total_debits,
        created_by="Muhammad Saad",
        is_synced=True,
        client_uuid=voucher_in.client_uuid
    )
    db.add(voucher)
    db.flush()

    out_entries = []
    for entry_data in entries_list:
        acc = db.query(Account).filter(Account.id == entry_data.account_id).first()
        if not acc:
            db.rollback()
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Account id {entry_data.account_id} not found.")

        party = None
        if entry_data.party_id:
            party = db.query(Party).filter(Party.id == entry_data.party_id).first()

        entry = VoucherEntry(
            voucher_id=voucher.id,
            account_id=acc.id,
            party_id=party.id if party else None,
            entry_type=entry_data.entry_type,
            amount=entry_data.amount,
            narration=entry_data.narration or voucher_in.narration
        )
        db.add(entry)

        # Update running ledger balances
        update_account_balance(acc, entry_data.entry_type, entry_data.amount)
        if party:
            update_party_balance(party, entry_data.entry_type, entry_data.amount)

        out_entries.append(VoucherEntryOut(
            id=0, # populated after commit
            account_id=acc.id,
            party_id=party.id if party else None,
            entry_type=entry_data.entry_type,
            amount=entry_data.amount,
            narration=entry.narration,
            account_name=acc.name,
            party_name=party.name if party else None
        ))

    try:
        db.commit()
        db.refresh(voucher)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to commit voucher transaction: {str(e)}"
        )

    for i, e in enumerate(voucher.entries):
        if i < len(out_entries):
            out_entries[i].id = e.id

    return VoucherOut(
        id=voucher.id,
        voucher_number=voucher.voucher_number,
        date=voucher.date,
        voucher_type=voucher.voucher_type,
        reference_no=voucher.reference_no,
        narration=voucher.narration,
        total_amount=voucher.total_amount,
        created_by=voucher.created_by,
        is_synced=voucher.is_synced,
        client_uuid=voucher.client_uuid,
        entries=out_entries,
        created_at=voucher.created_at
    )

@router.get("/{voucher_id}", response_model=VoucherOut)
def get_voucher(voucher_id: int, db: Session = Depends(get_db)):
    voucher = db.query(Voucher).filter(Voucher.id == voucher_id).first()
    if not voucher:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Voucher with id {voucher_id} not found.")
    entries = []
    for e in voucher.entries:
        entries.append(VoucherEntryOut(
            id=e.id,
            account_id=e.account_id,
            party_id=e.party_id,
            entry_type=e.entry_type,
            amount=e.amount,
            narration=e.narration,
            account_name=e.account.name if e.account else "N/A",
            party_name=e.party.name if e.party else None
        ))
    return VoucherOut(
        id=voucher.id,
        voucher_number=voucher.voucher_number,
        date=voucher.date,
        voucher_type=voucher.voucher_type,
        reference_no=voucher.reference_no,
        narration=voucher.narration,
        total_amount=voucher.total_amount,
        created_by=voucher.created_by,
        is_synced=voucher.is_synced,
        client_uuid=voucher.client_uuid,
        entries=entries,
        created_at=voucher.created_at
    )


@router.delete("/{voucher_id}")
@router.delete("/{voucher_id}/")
def delete_voucher(voucher_id: int, db: Session = Depends(get_db)):
    voucher = db.query(Voucher).filter(Voucher.id == voucher_id).first()
    if not voucher:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Voucher id {voucher_id} not found."
        )

    v_num = voucher.voucher_number or f"#{voucher_id}"

    # Reverse entry balances
    for entry in voucher.entries:
        if entry.account_id:
            acc = db.query(Account).filter(Account.id == entry.account_id).first()
            if acc:
                reverse_account_balance(acc, entry.entry_type, entry.amount)
        if entry.party_id:
            party = db.query(Party).filter(Party.id == entry.party_id).first()
            if party:
                reverse_party_balance(party, entry.entry_type, entry.amount)
        db.delete(entry)

    # Clean up linked income and payment allocation records to prevent FK errors
    try:
        from backend.models import IncomeTransaction, PaymentAllocation
        linked_incomes = db.query(IncomeTransaction).filter(IncomeTransaction.voucher_id == voucher_id).all()
        for inc in linked_incomes:
            db.delete(inc)
        linked_payments = db.query(PaymentAllocation).filter(PaymentAllocation.voucher_id == voucher_id).all()
        for p in linked_payments:
            db.delete(p)
    except Exception as e:
        pass

    db.delete(voucher)
    db.commit()

    return {
        "success": True,
        "message": f"Voucher {v_num} successfully deleted and reversed.",
        "id": voucher_id
    }
