from datetime import datetime, date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.database import get_db
from backend.models import (
    PaymentAllocation, Voucher, VoucherEntry, Account, Party, User
)
from backend.schemas import (
    PaymentCreate, PaymentOut, PaymentListOut
)
from backend.routes.voucher_routes import (
    generate_voucher_number,
    generate_reference_number,
    update_account_balance,
    reverse_account_balance,
    update_party_balance,
    reverse_party_balance
)
from backend.routes.expense_routes import get_or_create_payment_account
from backend.routes.income_routes import get_accounts_receivable_account

router = APIRouter(prefix="/api/v1/payments", tags=["Payment Management"])


def generate_payment_number(db: Session, p_type: str, target_date: Optional[datetime] = None) -> str:
    """
    Format: TA-RCP-YYYY-MMM-000001 for Customer Receipts
            TA-PAY-YYYY-MMM-000001 for Supplier Payments
    """
    if not target_date:
        target_date = datetime.utcnow()

    year = target_date.year
    month_abbr = target_date.strftime("%b").upper()
    sub_code = "RCP" if "receipt" in p_type.lower() or "customer" in p_type.lower() else "PAY"
    prefix = f"TA-{sub_code}-{year}-{month_abbr}-"

    records = db.query(PaymentAllocation).filter(
        PaymentAllocation.payment_number.like(f"{prefix}%")
    ).all()

    max_seq = 0
    for r in records:
        pnum = (r.payment_number or "").strip()
        if pnum.startswith(prefix):
            suffix = pnum[len(prefix):].strip()
            if suffix.isdigit():
                max_seq = max(max_seq, int(suffix))

    return f"{prefix}{max_seq + 1:06d}"


def get_accounts_payable_account(db: Session) -> Account:
    acc = db.query(Account).filter(Account.code == "2010").first()
    if acc:
        return acc
    acc = db.query(Account).filter(
        Account.type == "Liability",
        Account.name.ilike("%Payable%")
    ).first()
    if acc:
        return acc
    acc = Account(
        code="2010",
        name="Accounts Payable",
        type="Liability",
        description="Trade Creditors / Supplier Balances",
        balance=0.0,
        is_active=True
    )
    db.add(acc)
    db.flush()
    return acc


def get_party_effective_balance(party: Party) -> float:
    """
    Computes current authoritative balance for customer (Receivable) or supplier (Payable).
    Uses the live current_balance which is updated by every voucher entry.
    Falls back to opening_balance if current_balance has never been set (0.0 and opening > 0).
    """
    current = float(party.current_balance or 0.0)
    opening = float(party.opening_balance or 0.0)
    # Use current_balance as the live balance; add opening_balance only when no
    # voucher movement has occurred yet (current_balance stayed at default 0.0).
    if current == 0.0 and opening != 0.0:
        return opening
    return current


def get_party_total_paid(db: Session, party_id: int) -> float:
    """
    Returns the sum of all non-voided payments made against this party.
    Used to compute accurate remaining balance across multiple partial payments.
    """
    from sqlalchemy import func as sqlfunc
    result = db.query(sqlfunc.sum(PaymentAllocation.amount)).filter(
        PaymentAllocation.party_id == party_id,
        PaymentAllocation.is_voided == False
    ).scalar()
    return float(result or 0.0)


@router.get("/next-number")
def get_next_payment_number(
    payment_type: str = Query("CustomerReceipt"),
    date_str: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    target_date = datetime.utcnow()
    if date_str:
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            pass
    return {
        "next_payment_number": generate_payment_number(db, payment_type, target_date),
        "next_reference_no": generate_reference_number(db)
    }


@router.get("", response_model=PaymentListOut)
def list_payments(
    payment_type: Optional[str] = Query(None),
    party_id: Optional[int] = Query(None),
    date_filter: Optional[str] = Query(None, alias="date"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(PaymentAllocation).order_by(
        PaymentAllocation.payment_date.desc(), PaymentAllocation.id.desc()
    )

    all_payments = query.all()
    today_str = date.today().isoformat()

    total_rcp = 0.0
    total_pay = 0.0
    today_total = 0.0

    filtered_items = []
    for p in all_payments:
        if not p.is_voided:
            if "receipt" in p.payment_type.lower() or "customer" in p.payment_type.lower():
                total_rcp += p.amount
            else:
                total_pay += p.amount

            p_date_str = p.payment_date.strftime("%Y-%m-%d") if p.payment_date else ""
            if p_date_str == today_str:
                today_total += p.amount

        # Filter check
        p_date_str = p.payment_date.strftime("%Y-%m-%d") if p.payment_date else ""
        if date_filter and p_date_str != date_filter:
            continue
        if start_date and p_date_str < start_date:
            continue
        if end_date and p_date_str > end_date:
            continue
        if payment_type and payment_type.lower() not in p.payment_type.lower():
            continue
        if party_id and p.party_id != party_id:
            continue

        # BUG FIX: remaining_balance_pkr should reflect the party's live outstanding balance
        # (opening + all debits - all credits), not a naive subtraction of this one payment.
        # The party.current_balance is updated atomically by each voucher entry, so it IS
        # the authoritative remaining balance after all payments to date.
        orig_bal = get_party_effective_balance(p.party) if p.party else 0.0
        total_paid = get_party_total_paid(db, p.party_id) if p.party else 0.0
        # Opening balance minus all payments = current outstanding
        party_opening = float(p.party.opening_balance or 0.0) if p.party else 0.0
        rem_bal = max(0.0, party_opening - total_paid) if party_opening > 0 else max(0.0, orig_bal)

        filtered_items.append(PaymentOut(
            id=p.id,
            payment_number=p.payment_number,
            payment_date=p.payment_date,
            payment_type=p.payment_type,
            party_id=p.party_id,
            party_name=p.party.name if p.party else None,
            party_type=p.party.type if p.party else None,
            amount=p.amount,
            payment_method=p.payment_method,
            reference_no=p.reference_no,
            notes=p.notes,
            created_by=p.created_by,
            created_at=p.created_at,
            voucher_id=p.voucher_id,
            is_voided=p.is_voided,
            void_reason=p.void_reason,
            original_balance_pkr=orig_bal,
            remaining_balance_pkr=rem_bal
        ))

    return PaymentListOut(
        total_receipts_pkr=total_rcp,
        total_supplier_payments_pkr=total_pay,
        today_pkr=today_total,
        items=filtered_items
    )


@router.post("", response_model=PaymentOut, status_code=status.HTTP_201_CREATED)
def create_payment(
    payment_in: PaymentCreate,
    db: Session = Depends(get_db)
):
    if payment_in.amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment amount must be greater than zero."
        )

    party = db.query(Party).filter(Party.id == payment_in.party_id).first()
    if not party:
        raise HTTPException(status_code=404, detail="Commercial party not found.")

    p_date = payment_in.payment_date or datetime.utcnow()
    p_num = generate_payment_number(db, payment_in.payment_type, p_date)
    ref_no = payment_in.reference_no.strip() if payment_in.reference_no and payment_in.reference_no.strip() else generate_reference_number(db)

    # Duplicate payment check: prevent accidental duplicate submission in quick succession
    recent_dup = db.query(PaymentAllocation).filter(
        PaymentAllocation.party_id == party.id,
        PaymentAllocation.amount == payment_in.amount,
        PaymentAllocation.is_voided == False,
        PaymentAllocation.payment_type == payment_in.payment_type
    ).order_by(PaymentAllocation.id.desc()).first()

    if recent_dup:
        diff_secs = (datetime.utcnow() - recent_dup.created_at).total_seconds()
        if diff_secs < 10 and recent_dup.reference_no == ref_no:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Duplicate payment submission detected for {party.name}. Already recorded as {recent_dup.payment_number}."
            )

    original_balance = get_party_effective_balance(party)

    # 1. Resolve Payment Asset Account (Cash / Bank)
    payment_acc = get_or_create_payment_account(db, method_name=payment_in.payment_method)

    user = db.query(User).first()
    creator_name = user.full_name if user and user.full_name else "Muhammad Haris"

    is_receipt = "receipt" in payment_in.payment_type.lower() or "customer" in payment_in.payment_type.lower()

    # --- Double-Entry Voucher Creation ---
    v_num = generate_voucher_number(db, v_date=p_date)
    v_type = "Receipt" if is_receipt else "Payment"
    narration = payment_in.notes or (
        f"Customer Receipt from {party.name}" if is_receipt else f"Payment to Supplier {party.name}"
    )

    voucher = Voucher(
        voucher_number=v_num,
        date=p_date,
        voucher_type=v_type,
        reference_no=ref_no,
        narration=narration,
        total_amount=payment_in.amount,
        created_by=creator_name,
        is_synced=True,
        client_uuid=f"pay-{int(datetime.utcnow().timestamp() * 1000)}"
    )
    db.add(voucher)
    db.flush()

    if is_receipt:
        # CUSTOMER RECEIPT:
        # Collecting an existing customer receivable.
        # CRITICAL: DOES NOT CREATE DUPLICATE INCOME!
        # Debit: Cash/Bank Account (Asset increases)
        # Credit: Accounts Receivable (Asset decreases) + Party credit (reduces customer receivable)
        e_debit = VoucherEntry(
            voucher_id=voucher.id,
            account_id=payment_acc.id,
            party_id=None,
            entry_type="Debit",
            amount=payment_in.amount,
            narration=narration
        )
        db.add(e_debit)
        update_account_balance(payment_acc, "Debit", payment_in.amount)

        ar_acc = get_accounts_receivable_account(db)
        e_credit = VoucherEntry(
            voucher_id=voucher.id,
            account_id=ar_acc.id,
            party_id=party.id,
            entry_type="Credit",
            amount=payment_in.amount,
            narration=f"Receipt settled against balance for {party.name}"
        )
        db.add(e_credit)
        update_account_balance(ar_acc, "Credit", payment_in.amount)
        update_party_balance(party, "Credit", payment_in.amount)

        remaining_balance = float(party.current_balance or 0.0)
    else:
        # SUPPLIER PAYMENT:
        # Settling an existing supplier payable.
        # CRITICAL: DOES NOT COUNT AS A NEW EXPENSE!
        # Debit: Accounts Payable (Liability decreases) + Party debit (reduces supplier payable)
        # Credit: Cash/Bank Account (Asset decreases)
        ap_acc = get_accounts_payable_account(db)
        e_debit = VoucherEntry(
            voucher_id=voucher.id,
            account_id=ap_acc.id,
            party_id=party.id,
            entry_type="Debit",
            amount=payment_in.amount,
            narration=f"Payment settlement against payable balance for {party.name}"
        )
        db.add(e_debit)
        update_account_balance(ap_acc, "Debit", payment_in.amount)
        update_party_balance(party, "Debit", payment_in.amount)

        e_credit = VoucherEntry(
            voucher_id=voucher.id,
            account_id=payment_acc.id,
            party_id=None,
            entry_type="Credit",
            amount=payment_in.amount,
            narration=narration
        )
        db.add(e_credit)
        update_account_balance(payment_acc, "Credit", payment_in.amount)

        remaining_balance = float(party.current_balance or 0.0)

    # Record PaymentAllocation
    payment_alloc = PaymentAllocation(
        payment_number=p_num,
        payment_date=p_date,
        payment_type="CustomerReceipt" if is_receipt else "SupplierPayment",
        party_id=party.id,
        amount=payment_in.amount,
        payment_method=payment_in.payment_method,
        reference_no=ref_no,
        notes=payment_in.notes,
        created_by=creator_name,
        created_at=datetime.utcnow(),
        voucher_id=voucher.id,
        is_voided=False
    )
    db.add(payment_alloc)

    try:
        db.commit()
        db.refresh(payment_alloc)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to record payment transaction: {str(e)}"
        )

    return PaymentOut(
        id=payment_alloc.id,
        payment_number=payment_alloc.payment_number,
        payment_date=payment_alloc.payment_date,
        payment_type=payment_alloc.payment_type,
        party_id=party.id,
        party_name=party.name,
        party_type=party.type,
        amount=payment_alloc.amount,
        payment_method=payment_alloc.payment_method,
        reference_no=payment_alloc.reference_no,
        notes=payment_alloc.notes,
        created_by=payment_alloc.created_by,
        created_at=payment_alloc.created_at,
        voucher_id=payment_alloc.voucher_id,
        is_voided=payment_alloc.is_voided,
        original_balance_pkr=original_balance,
        remaining_balance_pkr=remaining_balance
    )


@router.get("/{payment_id}", response_model=PaymentOut)
def get_payment(payment_id: int, db: Session = Depends(get_db)):
    p = db.query(PaymentAllocation).filter(PaymentAllocation.id == payment_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Payment record not found.")

    orig_bal = get_party_effective_balance(p.party) if p.party else 0.0
    total_paid = get_party_total_paid(db, p.party_id) if p.party else 0.0
    party_opening = float(p.party.opening_balance or 0.0) if p.party else 0.0
    rem_bal = max(0.0, party_opening - total_paid) if party_opening > 0 else max(0.0, orig_bal)
    return PaymentOut(
        id=p.id,
        payment_number=p.payment_number,
        payment_date=p.payment_date,
        payment_type=p.payment_type,
        party_id=p.party_id,
        party_name=p.party.name if p.party else None,
        party_type=p.party.type if p.party else None,
        amount=p.amount,
        payment_method=p.payment_method,
        reference_no=p.reference_no,
        notes=p.notes,
        created_by=p.created_by,
        created_at=p.created_at,
        voucher_id=p.voucher_id,
        is_voided=p.is_voided,
        void_reason=p.void_reason,
        original_balance_pkr=orig_bal,
        remaining_balance_pkr=rem_bal
    )


@router.post("/{payment_id}/void")
def void_payment(
    payment_id: int,
    reason: str = Query("Voided and reversed by authorized controller"),
    db: Session = Depends(get_db)
):
    """
    Voids and reverses the payment voucher and reinstates customer/supplier balances.
    """
    p = db.query(PaymentAllocation).filter(PaymentAllocation.id == payment_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Payment record not found.")
    if p.is_voided:
        raise HTTPException(status_code=400, detail="Payment is already voided.")

    if p.voucher_id:
        v = db.query(Voucher).filter(Voucher.id == p.voucher_id).first()
        if v:
            for entry in v.entries:
                if entry.account_id:
                    acc = db.query(Account).filter(Account.id == entry.account_id).first()
                    if acc:
                        reverse_account_balance(acc, entry.entry_type, entry.amount)

    # Reverse party balance exactly once
    if p.party:
        is_rcp = "receipt" in (p.payment_type or "").lower() or "customer" in (p.payment_type or "").lower()
        if is_rcp:
            reverse_party_balance(p.party, "Credit", p.amount)
        else:
            reverse_party_balance(p.party, "Debit", p.amount)

    p.is_voided = True
    p.void_reason = reason
    p.voided_at = datetime.utcnow()

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to void payment transaction: {str(e)}"
        )
    return {
        "success": True,
        "message": f"Payment {p.payment_number} has been voided and party balances reversed."
    }


@router.delete("/{payment_id}")
def delete_payment(payment_id: int, db: Session = Depends(get_db)):
    """
    Permanently deletes a payment/receipt record, reverses account and party balances, and cleans up linked voucher.
    """
    p = db.query(PaymentAllocation).filter(PaymentAllocation.id == payment_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Payment record not found.")

    p_num = p.payment_number or f"#{payment_id}"

    # If the payment was NOT already voided, reverse the ledger entries and account balances
    if not p.is_voided:
        if p.voucher_id:
            v = db.query(Voucher).filter(Voucher.id == p.voucher_id).first()
            if v:
                for entry in list(v.entries):
                    if entry.account_id:
                        acc = db.query(Account).filter(Account.id == entry.account_id).first()
                        if acc:
                            reverse_account_balance(acc, entry.entry_type, entry.amount)
                    db.delete(entry)
                db.delete(v)
        if p.party:
            is_rcp = "receipt" in (p.payment_type or "").lower() or "customer" in (p.payment_type or "").lower()
            if is_rcp:
                reverse_party_balance(p.party, "Credit", p.amount)
            else:
                reverse_party_balance(p.party, "Debit", p.amount)
    elif p.voucher_id:
        v = db.query(Voucher).filter(Voucher.id == p.voucher_id).first()
        if v:
            for entry in list(v.entries):
                db.delete(entry)
            db.delete(v)

    try:
        db.delete(p)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete payment transaction: {str(e)}"
        )

    return {
        "success": True,
        "message": f"Payment {p_num} successfully deleted and ledger balances reversed."
    }
