from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_

from backend.database import get_db
from backend.models import Voucher, VoucherEntry, Account, Party
from backend.schemas import UnifiedLedgerOut, LedgerRowOut

router = APIRouter(prefix="/api/v1/ledger", tags=["Unified Ledger Transactions"])


@router.get("", response_model=UnifiedLedgerOut)
def get_unified_ledger(
    transaction_type: Optional[str] = Query(None, description="Income, Expense, Receipt, Payment, Journal, Sales, Purchase"),
    account_id: Optional[int] = Query(None),
    party_id: Optional[int] = Query(None),
    from_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    to_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    search: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """
    Unified authoritative double-entry transaction history across all transactions:
    Income, Expenses, Customer Receipts, Supplier Payments, and Journals.
    """
    query = db.query(VoucherEntry, Voucher, Account, Party).join(
        Voucher, VoucherEntry.voucher_id == Voucher.id
    ).join(
        Account, VoucherEntry.account_id == Account.id
    ).outerjoin(
        Party, VoucherEntry.party_id == Party.id
    )

    if from_date and isinstance(from_date, str):
        try:
            fd = datetime.strptime(from_date, "%Y-%m-%d")
            query = query.filter(Voucher.date >= fd)
        except ValueError:
            pass

    if to_date and isinstance(to_date, str):
        try:
            td = datetime.strptime(f"{to_date} 23:59:59", "%Y-%m-%d %H:%M:%S")
            query = query.filter(Voucher.date <= td)
        except ValueError:
            pass

    if account_id and isinstance(account_id, int):
        query = query.filter(VoucherEntry.account_id == account_id)

    if party_id and isinstance(party_id, int):
        query = query.filter(VoucherEntry.party_id == party_id)

    if transaction_type and isinstance(transaction_type, str):
        tt = transaction_type.lower()
        if tt == "income":
            query = query.filter(Voucher.voucher_type.in_(["Sales", "Receipt"]))
        elif tt == "expense":
            query = query.filter(Voucher.voucher_type.in_(["Payment", "Purchase"]))
        elif tt == "receipt":
            query = query.filter(Voucher.voucher_type == "Receipt")
        elif tt == "payment":
            query = query.filter(Voucher.voucher_type == "Payment")
        else:
            query = query.filter(Voucher.voucher_type.ilike(f"%{transaction_type}%"))

    if search and isinstance(search, str):
        s = f"%{search}%"
        query = query.filter(
            or_(
                Voucher.voucher_number.ilike(s),
                Voucher.reference_no.ilike(s),
                Voucher.narration.ilike(s),
                VoucherEntry.narration.ilike(s),
                Account.name.ilike(s),
                Party.name.ilike(s)
            )
        )

    lim = limit if isinstance(limit, int) else 100
    off = offset if isinstance(offset, int) else 0

    # Order chronologically for running balance calculation
    all_results = query.order_by(Voucher.date.asc(), Voucher.id.asc(), VoucherEntry.id.asc()).all()

    total_debit = 0.0
    total_credit = 0.0
    prior_balance = 0.0

    if from_date and isinstance(from_date, str):
        try:
            fd = datetime.strptime(from_date, "%Y-%m-%d")
            prior_query = db.query(VoucherEntry, Voucher).join(
                Voucher, VoucherEntry.voucher_id == Voucher.id
            ).filter(Voucher.date < fd)
            if account_id:
                prior_query = prior_query.filter(VoucherEntry.account_id == account_id)
            if party_id:
                prior_query = prior_query.filter(VoucherEntry.party_id == party_id)
            for pe, pv in prior_query.all():
                p_deb = pe.amount if pe.entry_type == "Debit" else 0.0
                p_cred = pe.amount if pe.entry_type == "Credit" else 0.0
                prior_balance += (p_deb - p_cred)
        except ValueError:
            pass

    running_balance = prior_balance
    items = []

    for entry, voucher, account, party in all_results:
        debit = entry.amount if entry.entry_type == "Debit" else 0.0
        credit = entry.amount if entry.entry_type == "Credit" else 0.0
        total_debit += debit
        total_credit += credit

        # Net cash movement: Debit increases asset/inflow, Credit decreases
        running_balance += (debit - credit)

        # Derive human friendly transaction type
        v_type = voucher.voucher_type or "Journal"
        if v_type == "Sales":
            tx_type = "Income"
        elif v_type == "Receipt":
            tx_type = "Customer Receipt" if party else "Receipt"
        elif v_type == "Payment":
            tx_type = "Supplier Payment" if (party and party.type in ["Supplier", "Vendor"]) else "Expense"
        else:
            tx_type = v_type

        items.append(LedgerRowOut(
            id=f"VE-{entry.id}",
            transaction_date=voucher.date,
            transaction_type=tx_type,
            transaction_number=voucher.voucher_number,
            reference_no=voucher.reference_no,
            description=entry.narration or voucher.narration or "-",
            party_name=party.name if party else None,
            account_name=account.name if account else "N/A",
            debit_pkr=debit,
            credit_pkr=credit,
            running_balance_pkr=running_balance,
            created_by=voucher.created_by,
            voucher_id=voucher.id,
            is_voided=False
        ))

    # Paginate from latest if requested or keep chronological
    # For user display, standard reverse chronological view:
    total_count = len(items)
    display_items = list(reversed(items))[off:off + lim]

    return UnifiedLedgerOut(
        total_debit_pkr=total_debit,
        total_credit_pkr=total_credit,
        net_pkr=total_debit - total_credit,
        total_records=total_count,
        items=display_items
    )
