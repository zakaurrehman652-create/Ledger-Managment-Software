from datetime import datetime, date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import Voucher, VoucherEntry, Account, User, Party
from backend.schemas import ExpenseCreate, ExpenseItemOut, ExpenseListOut, ExpenseUpdate
from backend.routes.voucher_routes import reverse_account_balance
from backend.routes.voucher_routes import generate_voucher_number, generate_reference_number, update_account_balance

router = APIRouter(prefix="/api/v1/expenses", tags=["Expenditures & Daily Expenses"])

def get_or_create_expense_account(db: Session, category_name: str) -> Account:
    clean_name = category_name.strip()
    acc = db.query(Account).filter(
        Account.name.ilike(clean_name),
        Account.type == "Expense"
    ).first()
    if acc:
        return acc

    # Generate next 5xxx code for Expense
    expense_accounts = db.query(Account).filter(Account.type == "Expense").all()
    codes = []
    for a in expense_accounts:
        try:
            if a.code.isdigit():
                codes.append(int(a.code))
        except ValueError:
            pass

    next_code = max(codes) + 10 if codes else 5010
    new_acc = Account(
        code=str(next_code),
        name=clean_name,
        type="Expense",
        description=f"Operational expense account for {clean_name}",
        balance=0.0,
        is_active=True
    )
    db.add(new_acc)
    db.flush()
    return new_acc

def get_or_create_payment_account(db: Session, account_id: Optional[int] = None, method_name: Optional[str] = "Cash in Hand") -> Account:
    if account_id:
        acc = db.query(Account).filter(Account.id == account_id).first()
        if acc:
            return acc

    clean_method = (method_name or "Cash in Hand").strip()
    acc = db.query(Account).filter(
        Account.name.ilike(clean_method),
        Account.type == "Asset"
    ).first()
    if acc:
        return acc

    # Try any cash or bank account
    cash_acc = db.query(Account).filter(
        Account.type == "Asset",
        Account.name.ilike("%Cash%")
    ).first()
    if cash_acc:
        return cash_acc

    # Otherwise auto-create Cash in Hand
    new_acc = Account(
        code="1010",
        name="Cash in Hand",
        type="Asset",
        description="Physical Cash in Vault / Register",
        balance=0.0,
        is_active=True
    )
    db.add(new_acc)
    db.flush()
    return new_acc

@router.get("", response_model=ExpenseListOut)
def list_expenses(
    date_filter: Optional[str] = Query(None, alias="date", description="Specific date in YYYY-MM-DD"),
    start_date: Optional[str] = Query(None, description="Start date in YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="End date in YYYY-MM-DD"),
    category: Optional[str] = Query(None, description="Filter by expense category name"),
    db: Session = Depends(get_db)
):
    # Query all debit entries belonging to Expense accounts
    base_query = db.query(VoucherEntry, Voucher, Account).join(
        Voucher, VoucherEntry.voucher_id == Voucher.id
    ).join(
        Account, VoucherEntry.account_id == Account.id
    ).filter(
        Account.type == "Expense",
        VoucherEntry.entry_type == "Debit"
    )

    all_entries = base_query.all()

    # Calculate overall total
    total_all_time = sum(entry[0].amount for entry in all_entries)

    # Calculate today's total
    today_str = date.today().isoformat()
    today_total = 0.0
    for entry, v, acc in all_entries:
        v_date_str = v.date.strftime("%Y-%m-%d") if v.date else ""
        if v_date_str == today_str:
            today_total += entry.amount

    # Apply filters
    filtered_items = []
    for entry, v, acc in all_entries:
        v_date_str = v.date.strftime("%Y-%m-%d") if v.date else ""

        if date_filter and v_date_str != date_filter:
            continue
        if start_date and v_date_str < start_date:
            continue
        if end_date and v_date_str > end_date:
            continue
        if category and category.lower() not in acc.name.lower():
            continue

        # Find payment method (the credit entry on this voucher)
        credit_entry = db.query(VoucherEntry, Account).join(
            Account, VoucherEntry.account_id == Account.id
        ).filter(
            VoucherEntry.voucher_id == v.id,
            VoucherEntry.entry_type == "Credit"
        ).first()

        pm_name = credit_entry[1].name if credit_entry and credit_entry[1] else "Cash / Bank"

        party_name = entry.party.name if entry.party else None
        filtered_items.append(ExpenseItemOut(
            id=entry.id,
            voucher_id=v.id,
            voucher_number=v.voucher_number,
            date=v.date,
            category=acc.name,
            account_code=acc.code,
            payment_method=pm_name,
            amount=entry.amount,
            narration=entry.narration or v.narration,
            reference_no=v.reference_no,
            supplier_id=entry.party_id,
            supplier_name=party_name,
            notes=entry.narration or v.narration
        ))

    # Sort descending by date, then id
    filtered_items.sort(key=lambda x: (x.date, x.id), reverse=True)
    filtered_total = sum(item.amount for item in filtered_items)

    return ExpenseListOut(
        total_all_time_pkr=total_all_time,
        today_pkr=today_total,
        filtered_total_pkr=filtered_total,
        items=filtered_items
    )

@router.post("", response_model=ExpenseItemOut, status_code=status.HTTP_201_CREATED)
def create_expense(expense_in: ExpenseCreate, db: Session = Depends(get_db)):
    if expense_in.amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Expense amount must be greater than zero."
        )

    # 1. Resolve or provision Expense Account
    expense_acc = get_or_create_expense_account(db, expense_in.category)

    # 2. Resolve or provision Payment Account (Cash/Bank)
    payment_acc = get_or_create_payment_account(
        db,
        account_id=expense_in.payment_account_id,
        method_name=expense_in.payment_method
    )

    # 3. Create double-entry Voucher
    v_date = expense_in.date or datetime.utcnow()
    v_num = generate_voucher_number(db, v_date=v_date)
    ref_no = expense_in.reference_no.strip() if expense_in.reference_no and expense_in.reference_no.strip() else generate_reference_number(db)

    party = None
    if expense_in.supplier_id:
        party = db.query(Party).filter(Party.id == expense_in.supplier_id).first()

    user = db.query(User).first()
    creator_name = user.full_name if user and user.full_name else "Muhammad Haris"
    narration = expense_in.narration or expense_in.notes or f"Expense for {expense_acc.name}"

    voucher = Voucher(
        voucher_number=v_num,
        date=v_date,
        voucher_type="Payment",
        reference_no=ref_no,
        narration=narration,
        total_amount=expense_in.amount,
        created_by=creator_name,
        is_synced=True,
        client_uuid=f"exp-{int(datetime.utcnow().timestamp() * 1000)}"
    )
    db.add(voucher)
    db.flush()

    # Entry 1: Debit to Expense Account
    e_debit = VoucherEntry(
        voucher_id=voucher.id,
        account_id=expense_acc.id,
        party_id=party.id if party else None,
        entry_type="Debit",
        amount=expense_in.amount,
        narration=narration
    )
    db.add(e_debit)
    update_account_balance(expense_acc, "Debit", expense_in.amount)

    # Entry 2: Credit to Cash/Bank Account
    e_credit = VoucherEntry(
        voucher_id=voucher.id,
        account_id=payment_acc.id,
        party_id=party.id if party else None,
        entry_type="Credit",
        amount=expense_in.amount,
        narration=narration
    )
    db.add(e_credit)
    update_account_balance(payment_acc, "Credit", expense_in.amount)

    try:
        db.commit()
        db.refresh(voucher)
        db.refresh(e_debit)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save expense transaction: {str(e)}"
        )

    return ExpenseItemOut(
        id=e_debit.id,
        voucher_id=voucher.id,
        voucher_number=voucher.voucher_number,
        date=voucher.date,
        category=expense_acc.name,
        account_code=expense_acc.code,
        payment_method=payment_acc.name,
        amount=e_debit.amount,
        narration=e_debit.narration,
        reference_no=voucher.reference_no,
        supplier_id=party.id if party else None,
        supplier_name=party.name if party else None,
        notes=expense_in.notes
    )

@router.put("/{voucher_id}", response_model=ExpenseItemOut)
def update_expense(voucher_id: int, expense_up: ExpenseUpdate, db: Session = Depends(get_db)):
    v = db.query(Voucher).filter(Voucher.id == voucher_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Expense record not found.")

    try:
        # Find primary debit entry
        debit_entry = next((e for e in v.entries if e.entry_type == "Debit"), None)
        credit_entry = next((e for e in v.entries if e.entry_type == "Credit"), None)

        cur_category = debit_entry.account.name if (debit_entry and debit_entry.account) else "General"
        cur_payment_method = credit_entry.account.name if (credit_entry and credit_entry.account) else "Cash in Hand"
        cur_amount = v.total_amount or (debit_entry.amount if debit_entry else 0.0)

        new_category = expense_up.category.strip() if expense_up.category else cur_category
        new_payment_method = expense_up.payment_method.strip() if expense_up.payment_method else cur_payment_method
        new_amount = expense_up.amount if expense_up.amount is not None else cur_amount

        if new_amount <= 0:
            raise HTTPException(status_code=400, detail="Expense amount must be greater than zero.")

        # Reverse previous entries
        for e in list(v.entries):
            acc = db.query(Account).filter(Account.id == e.account_id).first()
            if acc:
                reverse_account_balance(acc, e.entry_type, e.amount)
            db.delete(e)
        db.flush()

        # Update voucher header
        if expense_up.date:
            v.date = expense_up.date
        if expense_up.reference_no is not None:
            v.reference_no = expense_up.reference_no.strip()
        if expense_up.narration is not None:
            v.narration = expense_up.narration.strip()
        v.total_amount = new_amount

        # Resolve accounts
        expense_acc = get_or_create_expense_account(db, new_category)
        payment_acc = get_or_create_payment_account(
            db,
            account_id=expense_up.payment_account_id,
            method_name=new_payment_method
        )

        party = None
        target_supplier_id = expense_up.supplier_id if expense_up.supplier_id is not None else (debit_entry.party_id if debit_entry else None)
        if target_supplier_id:
            party = db.query(Party).filter(Party.id == target_supplier_id).first()

        narration = expense_up.narration or expense_up.notes or v.narration or f"Expense for {expense_acc.name}"

        # Re-post debit entry
        new_debit = VoucherEntry(
            voucher_id=v.id,
            account_id=expense_acc.id,
            party_id=party.id if party else None,
            entry_type="Debit",
            amount=new_amount,
            narration=narration
        )
        db.add(new_debit)
        update_account_balance(expense_acc, "Debit", new_amount)

        # Re-post credit entry
        new_credit = VoucherEntry(
            voucher_id=v.id,
            account_id=payment_acc.id,
            party_id=party.id if party else None,
            entry_type="Credit",
            amount=new_amount,
            narration=narration
        )
        db.add(new_credit)
        update_account_balance(payment_acc, "Credit", new_amount)

        db.commit()
        db.refresh(v)
        db.refresh(new_debit)

        return ExpenseItemOut(
            id=new_debit.id,
            voucher_id=v.id,
            voucher_number=v.voucher_number,
            date=v.date,
            category=expense_acc.name,
            account_code=expense_acc.code,
            payment_method=payment_acc.name,
            amount=new_debit.amount,
            narration=new_debit.narration,
            reference_no=v.reference_no,
            supplier_id=party.id if party else None,
            supplier_name=party.name if party else None,
            notes=expense_up.notes
        )
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update expense: {str(e)}")

@router.delete("/{voucher_id}")
def delete_expense(voucher_id: int, db: Session = Depends(get_db)):
    v = db.query(Voucher).filter(Voucher.id == voucher_id).first()
    if not v:
        entry = db.query(VoucherEntry).filter(VoucherEntry.id == voucher_id).first()
        if entry:
            v = db.query(Voucher).filter(Voucher.id == entry.voucher_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Expense record not found.")

    try:
        # Reverse balances safely
        for e in list(v.entries):
            acc = db.query(Account).filter(Account.id == e.account_id).first()
            if acc:
                reverse_account_balance(acc, e.entry_type, e.amount)
            db.delete(e)

        v_num = v.voucher_number
        db.delete(v)
        db.commit()
        return {"success": True, "message": f"Expense {v_num} successfully deleted and reversed."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete expense: {str(e)}")
