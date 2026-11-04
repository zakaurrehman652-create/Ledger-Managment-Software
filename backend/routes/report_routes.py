"""
Financial Reports — General Ledger, Trial Balance, Profit & Loss, Party Statements
All date filters are string-based (YYYY-MM-DD) for FastAPI Query compatibility.
Timezone: UTC stored; display timezone is PKT (UTC+5) — dates accepted in local PKT.
"""
from datetime import datetime, date, timedelta
from calendar import monthrange
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.database import get_db
from backend.models import Account, VoucherEntry, Voucher, Party, IncomeTransaction, PaymentAllocation
from backend.schemas import TrialBalanceReport, TrialBalanceItem, ProfitLossReport

router = APIRouter(prefix="/api/v1/reports", tags=["Financial Reports"])

PKT_OFFSET_HOURS = 5  # Pakistan Standard Time = UTC+5


# ---------------------------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------------------------

def _parse_date(date_str: Optional[str], default: Optional[datetime] = None) -> Optional[datetime]:
    """Parse YYYY-MM-DD string into datetime at midnight."""
    if not date_str or not isinstance(date_str, str):
        return default
    try:
        return datetime.strptime(date_str.strip(), "%Y-%m-%d")
    except ValueError:
        return default


def _parse_date_end(date_str: Optional[str]) -> Optional[datetime]:
    """Parse YYYY-MM-DD string into datetime at 23:59:59."""
    if not date_str or not isinstance(date_str, str):
        return None
    try:
        return datetime.strptime(f"{date_str.strip()} 23:59:59", "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def _date_filter_label(date_filter: Optional[str], from_date: Optional[str], to_date: Optional[str]) -> tuple:
    """
    Resolve named date filters (today/yesterday/this_week/this_month)
    or fall back to explicit from_date/to_date strings.
    Returns (start_dt, end_dt) as datetime objects or (None, None).
    """
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    # Adjust for PKT: PKT midnight = UTC 19:00 previous day, but we store in UTC.
    # We keep it simple: treat "today" as UTC calendar day for backend consistency.

    if date_filter and isinstance(date_filter, str):
        df = date_filter.lower().replace("-", "_")
        if df == "today":
            return today, today.replace(hour=23, minute=59, second=59)
        elif df == "yesterday":
            yd = today - timedelta(days=1)
            return yd, yd.replace(hour=23, minute=59, second=59)
        elif df in ("this_week", "week"):
            week_start = today - timedelta(days=today.weekday())
            return week_start, today.replace(hour=23, minute=59, second=59)
        elif df in ("this_month", "month"):
            month_start = today.replace(day=1)
            return month_start, today.replace(hour=23, minute=59, second=59)
        elif df in ("last_month",):
            first_of_this = today.replace(day=1)
            last_of_prev = first_of_this - timedelta(days=1)
            first_of_prev = last_of_prev.replace(day=1)
            return first_of_prev, last_of_prev.replace(hour=23, minute=59, second=59)
        elif df in ("this_year", "year"):
            year_start = today.replace(month=1, day=1)
            return year_start, today.replace(hour=23, minute=59, second=59)

    start = _parse_date(from_date)
    end = _parse_date_end(to_date)
    return start, end


def _fmt_date(dt: Optional[datetime]) -> Optional[str]:
    return dt.strftime("%Y-%m-%d") if dt else None


# ---------------------------------------------------------------------------
# TRIAL BALANCE
# ---------------------------------------------------------------------------
@router.get("/trial-balance", response_model=TrialBalanceReport)
def get_trial_balance(db: Session = Depends(get_db)):
    accounts = db.query(Account).filter(Account.is_active == True).order_by(Account.code.asc()).all()

    items = []
    total_debit = 0.0
    total_credit = 0.0

    for acc in accounts:
        debit = 0.0
        credit = 0.0

        if acc.type in ["Asset", "Expense"]:
            if acc.balance >= 0:
                debit = acc.balance
            else:
                credit = abs(acc.balance)
        else:
            if acc.balance >= 0:
                credit = acc.balance
            else:
                debit = abs(acc.balance)

        total_debit += debit
        total_credit += credit

        items.append(TrialBalanceItem(
            account_code=acc.code,
            account_name=acc.name,
            account_type=acc.type,
            debit_pkr=debit,
            credit_pkr=credit
        ))

    diff = abs(total_debit - total_credit)
    is_balanced = diff < 0.05

    return TrialBalanceReport(
        currency="PKR",
        items=items,
        total_debit_pkr=total_debit,
        total_credit_pkr=total_credit,
        is_balanced=is_balanced,
        difference_pkr=diff
    )


# ---------------------------------------------------------------------------
# PROFIT & LOSS
# ---------------------------------------------------------------------------
@router.get("/profit-loss", response_model=ProfitLossReport)
def get_profit_loss(db: Session = Depends(get_db)):
    revenues = db.query(Account).filter(Account.type == "Revenue", Account.is_active == True).all()
    expenses = db.query(Account).filter(Account.type == "Expense", Account.is_active == True).all()

    rev_list = [{"code": r.code, "name": r.name, "amount_pkr": r.balance} for r in revenues]
    exp_list = [{"code": e.code, "name": e.name, "amount_pkr": e.balance} for e in expenses]

    total_rev = sum(r.balance for r in revenues)
    total_exp = sum(e.balance for e in expenses)
    net_profit = total_rev - total_exp

    return ProfitLossReport(
        currency="PKR",
        revenues=rev_list,
        total_revenue_pkr=total_rev,
        expenses=exp_list,
        total_expense_pkr=total_exp,
        net_profit_pkr=net_profit
    )


# ---------------------------------------------------------------------------
# BALANCE SHEET
# ---------------------------------------------------------------------------
@router.get("/balance-sheet")
def get_balance_sheet(db: Session = Depends(get_db)):
    assets = db.query(Account).filter(Account.type == "Asset", Account.is_active == True).all()
    liabilities = db.query(Account).filter(Account.type == "Liability", Account.is_active == True).all()
    equities = db.query(Account).filter(Account.type == "Equity", Account.is_active == True).all()

    total_assets = sum(a.balance for a in assets)
    total_liabilities = sum(l.balance for l in liabilities)
    total_equity = sum(eq.balance for eq in equities)

    return {
        "currency": "PKR",
        "total_assets": total_assets,
        "total_liabilities": total_liabilities,
        "total_equity": total_equity,
        "assets": [{"code": a.code, "name": a.name, "balance_pkr": a.balance} for a in assets],
        "liabilities": [{"code": l.code, "name": l.name, "balance_pkr": l.balance} for l in liabilities],
        "equity": [{"code": eq.code, "name": eq.name, "balance_pkr": eq.balance} for eq in equities]
    }


# ---------------------------------------------------------------------------
# GENERAL LEDGER (Account Statement)  — FIX: date params as strings
# ---------------------------------------------------------------------------
@router.get("/general-ledger/{account_id}")
def get_account_statement(
    account_id: int,
    from_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    to_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    db: Session = Depends(get_db)
):
    acc = db.query(Account).filter(Account.id == account_id).first()
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found.")

    query = db.query(VoucherEntry).join(Voucher).filter(VoucherEntry.account_id == account_id)

    start_dt = _parse_date(from_date)
    end_dt = _parse_date_end(to_date)

    if start_dt:
        query = query.filter(Voucher.date >= start_dt)
    if end_dt:
        query = query.filter(Voucher.date <= end_dt)

    entries = query.order_by(Voucher.date.asc(), Voucher.id.asc()).all()

    statement_rows = []
    running_bal = 0.0

    for e in entries:
        debit = e.amount if e.entry_type == "Debit" else 0.0
        credit = e.amount if e.entry_type == "Credit" else 0.0

        if acc.type in ["Asset", "Expense"]:
            running_bal += (debit - credit)
        else:
            running_bal += (credit - debit)

        statement_rows.append({
            "voucher_id": e.voucher.id,
            "voucher_number": e.voucher.voucher_number,
            "date": e.voucher.date.strftime("%Y-%m-%d"),
            "narration": e.narration or e.voucher.narration,
            "debit_pkr": debit,
            "credit_pkr": credit,
            "running_balance_pkr": running_bal
        })

    return {
        "account_id": acc.id,
        "account_code": acc.code,
        "account_name": acc.name,
        "account_type": acc.type,
        "current_balance_pkr": acc.balance,
        "currency": "PKR",
        "from_date": _fmt_date(start_dt),
        "to_date": _fmt_date(end_dt),
        "statement": statement_rows
    }


# ---------------------------------------------------------------------------
# PARTY STATEMENT (Customer / Supplier)  — FIX: date params as strings
# ---------------------------------------------------------------------------
@router.get("/party-statement/{party_id}")
def get_party_statement(
    party_id: int,
    from_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    to_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    db: Session = Depends(get_db)
):
    party = db.query(Party).filter(Party.id == party_id).first()
    if not party:
        raise HTTPException(status_code=404, detail="Commercial party not found.")

    start_dt = _parse_date(from_date)
    end_dt = _parse_date_end(to_date)

    query = db.query(VoucherEntry).join(Voucher).filter(VoucherEntry.party_id == party_id)
    if start_dt:
        query = query.filter(Voucher.date >= start_dt)
    if end_dt:
        query = query.filter(Voucher.date <= end_dt)

    entries = query.order_by(Voucher.date.asc(), Voucher.id.asc()).all()

    opening_bal = float(party.opening_balance or 0.0)
    # If from_date / start_dt is given, add transactions prior to start_dt into opening_bal
    if start_dt:
        pre_entries = db.query(VoucherEntry).join(Voucher).filter(
            VoucherEntry.party_id == party_id,
            Voucher.date < start_dt
        ).all()
        bal_type = getattr(party, "balance_type", None) or ("Receivable" if party.type == "Customer" else "Payable")
        for pe in pre_entries:
            pe_deb = float(pe.amount) if pe.entry_type == "Debit" else 0.0
            pe_cred = float(pe.amount) if pe.entry_type == "Credit" else 0.0
            if party.type == "Customer" or bal_type == "Receivable":
                opening_bal += (pe_deb - pe_cred)
            else:
                opening_bal += (pe_cred - pe_deb)

    running_bal = opening_bal

    statement_rows = []
    total_debit = 0.0
    total_credit = 0.0

    for e in entries:
        # Ignore contra cash/asset entries on receipt/payment vouchers
        vtype = e.voucher.voucher_type if e.voucher else ""
        if vtype == "Receipt" and (party.type == "Customer" or getattr(party, "balance_type", None) == "Receivable") and e.entry_type == "Debit":
            continue
        if vtype == "Payment" and (party.type in ["Supplier", "Vendor"] or getattr(party, "balance_type", None) == "Payable") and e.entry_type == "Credit":
            continue

        debit = float(e.amount) if e.entry_type == "Debit" else 0.0
        credit = float(e.amount) if e.entry_type == "Credit" else 0.0
        total_debit += debit
        total_credit += credit

        # Customer (Receivable): Debit = charge, Credit = payment received
        # Supplier (Payable): Credit = liability, Debit = payment made
        balance_type = getattr(party, "balance_type", None)
        if party.type == "Customer" or balance_type == "Receivable":
            running_bal += (debit - credit)
        else:
            running_bal += (credit - debit)

        statement_rows.append({
            "voucher_id": e.voucher.id,
            "voucher_number": e.voucher.voucher_number,
            "date": e.voucher.date.strftime("%Y-%m-%d"),
            "voucher_type": e.voucher.voucher_type or "Journal",
            "reference_no": e.voucher.reference_no or "-",
            "narration": e.narration or e.voucher.narration or "-",
            "debit_pkr": debit,
            "credit_pkr": credit,
            "running_balance_pkr": running_bal
        })

    return {
        "party_id": party.id,
        "party_name": party.name,
        "party_type": party.type,
        "contact_person": party.contact_person,
        "phone": party.phone,
        "email": party.email,
        "city": party.city,
        "address": party.address,
        "credit_limit_pkr": float(party.credit_limit or 0.0),
        "opening_balance_pkr": opening_bal,
        "current_balance_pkr": float(party.current_balance or 0.0),
        "total_debit_pkr": total_debit,
        "total_credit_pkr": total_credit,
        "closing_balance_pkr": running_bal,
        "from_date": _fmt_date(start_dt),
        "to_date": _fmt_date(end_dt),
        "currency": "PKR",
        "statement": statement_rows
    }


# ---------------------------------------------------------------------------
# ANNUAL REPORT — Full Year Month-by-Month Breakdown
# ---------------------------------------------------------------------------
@router.get("/annual-report")
def get_annual_report(
    year: int = Query(..., description="Fiscal year, e.g. 2026"),
    db: Session = Depends(get_db)
):
    """
    Returns a month-by-month summary for the given year:
      - total inflow (receipts/sales), outflow (payments/purchases), voucher count
      - per-account-type totals
      - yearly grand totals and net profit
    """
    if year < 1900 or year > 9999:
        raise HTTPException(status_code=400, detail="Invalid year. Must be between 1900 and 9999.")

    year_start = datetime(year, 1, 1)
    year_end = datetime(year, 12, 31, 23, 59, 59)

    vouchers = (
        db.query(Voucher)
        .filter(Voucher.date >= year_start, Voucher.date <= year_end)
        .order_by(Voucher.date.asc())
        .all()
    )

    month_names = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]

    months = []
    for m in range(1, 13):
        months.append({
            "month": m,
            "month_name": month_names[m - 1],
            "inflow_pkr": 0.0,
            "outflow_pkr": 0.0,
            "journal_pkr": 0.0,
            "voucher_count": 0,
            "net_pkr": 0.0,
        })

    grand_inflow = 0.0
    grand_outflow = 0.0
    grand_journal = 0.0
    grand_voucher_count = 0

    # Exclude income-linked vouchers from inflow (already counted via IncomeTransaction)
    _linked_annual = set(
        r[0] for r in db.query(IncomeTransaction.voucher_id)
        .filter(IncomeTransaction.voucher_id.isnot(None), IncomeTransaction.is_voided == False)
        .all() if r[0] is not None
    )
    # Also add IncomeTransaction amounts per month to inflow
    _inc_by_month = {}
    for _t in db.query(IncomeTransaction).filter(
        IncomeTransaction.is_voided == False,
        IncomeTransaction.date >= year_start,
        IncomeTransaction.date <= year_end
    ).all():
        _m = _t.date.month - 1
        _inc_by_month[_m] = _inc_by_month.get(_m, 0.0) + float(_t.amount or 0.0)
        grand_inflow += float(_t.amount or 0.0)

    for _m_idx, _amt in _inc_by_month.items():
        months[_m_idx]["inflow_pkr"] += _amt

    for v in vouchers:
        m_idx = v.date.month - 1
        months[m_idx]["voucher_count"] += 1
        grand_voucher_count += 1

        if v.voucher_type in ("Receipt", "Sales") and v.id not in _linked_annual:
            # Standalone income voucher (manual, not from Income module)
            months[m_idx]["inflow_pkr"] += v.total_amount
            grand_inflow += v.total_amount
        elif v.voucher_type in ("Payment", "Purchase"):
            months[m_idx]["outflow_pkr"] += v.total_amount
            grand_outflow += v.total_amount
        elif v.voucher_type not in ("Receipt", "Sales"):
            months[m_idx]["journal_pkr"] += v.total_amount
            grand_journal += v.total_amount

    for m in months:
        m["net_pkr"] = m["inflow_pkr"] - m["outflow_pkr"]

    accounts = db.query(Account).filter(Account.is_active == True).all()
    type_summary = {}
    for acc in accounts:
        t = acc.type
        if t not in type_summary:
            type_summary[t] = {"type": t, "total_balance_pkr": 0.0, "account_count": 0}
        type_summary[t]["total_balance_pkr"] += acc.balance
        type_summary[t]["account_count"] += 1

    total_revenue = sum(a.balance for a in accounts if a.type == "Revenue")
    total_expense = sum(a.balance for a in accounts if a.type == "Expense")

    return {
        "year": year,
        "currency": "PKR",
        "months": months,
        "grand_inflow_pkr": grand_inflow,
        "grand_outflow_pkr": grand_outflow,
        "amount_received_pkr": grand_inflow,
        "total_expense_pkr": grand_outflow,
        "net_received_minus_expense_pkr": grand_inflow - grand_outflow,
        "grand_journal_pkr": grand_journal,
        "grand_voucher_count": grand_voucher_count,
        "grand_net_pkr": grand_inflow - grand_outflow,
        "total_revenue_pkr": total_revenue,
        "net_profit_pkr": total_revenue - total_expense,
        "account_type_summary": list(type_summary.values()),
    }


# ---------------------------------------------------------------------------
# MONTHLY REPORT — 1st to last day of any month
# ---------------------------------------------------------------------------
@router.get("/monthly-report")
def get_monthly_report(
    year: int = Query(..., description="Year, e.g. 2026"),
    month: int = Query(..., ge=1, le=12, description="Month number 1-12"),
    db: Session = Depends(get_db)
):
    """
    Returns a day-by-day voucher summary for a specific month.
    """
    last_day = monthrange(year, month)[1]
    month_start = datetime(year, month, 1)
    month_end = datetime(year, month, last_day, 23, 59, 59)

    month_names = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]

    vouchers = (
        db.query(Voucher)
        .filter(Voucher.date >= month_start, Voucher.date <= month_end)
        .order_by(Voucher.date.asc(), Voucher.id.asc())
        .all()
    )

    daily_map = {}
    voucher_rows = []
    total_inflow = 0.0
    total_outflow = 0.0
    total_journal = 0.0
    type_breakdown = {}

    # Exclude income-linked vouchers (already counted via IncomeTransaction)
    _linked_monthly = set(
        r[0] for r in db.query(IncomeTransaction.voucher_id)
        .filter(IncomeTransaction.voucher_id.isnot(None), IncomeTransaction.is_voided == False)
        .all() if r[0] is not None
    )
    # Add IncomeTransaction amounts directly to inflow
    for _t in db.query(IncomeTransaction).filter(
        IncomeTransaction.is_voided == False,
        IncomeTransaction.date >= month_start,
        IncomeTransaction.date <= month_end
    ).all():
        _day = _t.date.strftime("%Y-%m-%d")
        if _day not in daily_map:
            daily_map[_day] = {"date": _day, "inflow_pkr": 0.0, "outflow_pkr": 0.0, "journal_pkr": 0.0, "count": 0}
        daily_map[_day]["inflow_pkr"] += float(_t.amount or 0.0)
        total_inflow += float(_t.amount or 0.0)

    for v in vouchers:
        day_key = v.date.strftime("%Y-%m-%d")
        if day_key not in daily_map:
            daily_map[day_key] = {"date": day_key, "inflow_pkr": 0.0, "outflow_pkr": 0.0, "journal_pkr": 0.0, "count": 0}

        daily_map[day_key]["count"] += 1

        if v.voucher_type in ("Receipt", "Sales") and v.id not in _linked_monthly:
            # Standalone income voucher only
            daily_map[day_key]["inflow_pkr"] += v.total_amount
            total_inflow += v.total_amount
        elif v.voucher_type in ("Payment", "Purchase"):
            daily_map[day_key]["outflow_pkr"] += v.total_amount
            total_outflow += v.total_amount
        elif v.voucher_type not in ("Receipt", "Sales"):
            daily_map[day_key]["journal_pkr"] += v.total_amount
            total_journal += v.total_amount

        vt = v.voucher_type or "Journal"
        if vt not in type_breakdown:
            type_breakdown[vt] = {"type": vt, "count": 0, "total_pkr": 0.0}
        type_breakdown[vt]["count"] += 1
        type_breakdown[vt]["total_pkr"] += v.total_amount

        entries_out = []
        for e in v.entries:
            entries_out.append({
                "account_name": e.account.name if e.account else "N/A",
                "party_name": e.party.name if e.party else None,
                "entry_type": e.entry_type,
                "amount": e.amount,
                "narration": e.narration,
            })

        voucher_rows.append({
            "id": v.id,
            "voucher_number": v.voucher_number,
            "date": v.date.strftime("%Y-%m-%d"),
            "voucher_type": v.voucher_type,
            "reference_no": v.reference_no,
            "narration": v.narration,
            "total_amount": v.total_amount,
            "created_by": v.created_by,
            "entries": entries_out,
        })

    return {
        "year": year,
        "month": month,
        "month_name": month_names[month - 1],
        "period": f"1 {month_names[month - 1]} {year} to {last_day} {month_names[month - 1]} {year}",
        "currency": "PKR",
        "total_inflow_pkr": total_inflow,
        "total_outflow_pkr": total_outflow,
        "amount_received_pkr": total_inflow,
        "total_expense_pkr": total_outflow,
        "net_received_minus_expense_pkr": total_inflow - total_outflow,
        "total_journal_pkr": total_journal,
        "net_pkr": total_inflow - total_outflow,
        "voucher_count": len(vouchers),
        "daily_summary": list(daily_map.values()),
        "type_breakdown": list(type_breakdown.values()),
        "vouchers": voucher_rows,
    }


# ===========================================================================
# TRANSACTION & BALANCE REPORT ENDPOINTS
# ===========================================================================

# ---------------------------------------------------------------------------
# INCOME REPORT — with date filters
# ---------------------------------------------------------------------------
@router.get("/income")
def get_income_report(
    date_filter: Optional[str] = Query(None, description="today|yesterday|this_week|this_month|last_month"),
    from_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    to_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    category: Optional[str] = Query(None),
    party_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Income Report: all IncomeTransaction records (excluding voided) with date filters.
    Also includes Revenue-type voucher totals for completeness.
    """
    start_dt, end_dt = _date_filter_label(date_filter, from_date, to_date)

    # --- Income Transactions ---
    q = db.query(IncomeTransaction).filter(IncomeTransaction.is_voided == False)
    if start_dt:
        q = q.filter(IncomeTransaction.date >= start_dt)
    if end_dt:
        q = q.filter(IncomeTransaction.date <= end_dt)
    if category:
        q = q.filter(IncomeTransaction.income_category.ilike(f"%{category}%"))
    if party_id:
        q = q.filter(IncomeTransaction.party_id == party_id)

    txns = q.order_by(IncomeTransaction.date.desc()).all()

    items = []
    total_income = 0.0
    total_receipts = 0.0

    for t in txns:
        amt = float(t.amount or 0.0)
        if t.is_customer_receipt:
            total_receipts += amt
        else:
            total_income += amt

        items.append({
            "id": t.id,
            "transaction_number": t.transaction_number,
            "date": t.date.strftime("%Y-%m-%d") if t.date else None,
            "income_category": t.income_category,
            "party_name": t.party.name if t.party else None,
            "amount_pkr": amt,
            "payment_method": t.payment_method,
            "reference_no": t.reference_no,
            "description": t.description,
            "is_customer_receipt": t.is_customer_receipt,
            "voucher_id": t.voucher_id,
        })

    # --- Only standalone Sales/Receipt vouchers (not linked to any IncomeTransaction) ---
    linked_v_ids = db.query(IncomeTransaction.voucher_id).filter(
        IncomeTransaction.voucher_id.isnot(None),
        IncomeTransaction.is_voided == False
    )
    sales_q = db.query(Voucher).filter(
        Voucher.voucher_type.in_(["Sales", "Receipt"]),
        Voucher.id.notin_(linked_v_ids)
    )
    if start_dt:
        sales_q = sales_q.filter(Voucher.date >= start_dt)
    if end_dt:
        sales_q = sales_q.filter(Voucher.date <= end_dt)
    voucher_total = sum(float(v.total_amount or 0.0) for v in sales_q.all())

    return {
        "currency": "PKR",
        "period": {
            "from_date": _fmt_date(start_dt),
            "to_date": _fmt_date(end_dt),
            "filter": date_filter or "custom",
        },
        "summary": {
            "total_income_pkr": total_income,
            "total_customer_receipts_pkr": total_receipts,
            "grand_total_pkr": total_income + total_receipts,
            "voucher_inflow_pkr": voucher_total,
            "transaction_count": len(items),
        },
        "items": items,
    }


# ---------------------------------------------------------------------------
# EXPENSE REPORT — with date filters
# ---------------------------------------------------------------------------
@router.get("/expense")
def get_expense_report(
    date_filter: Optional[str] = Query(None, description="today|yesterday|this_week|this_month|last_month"),
    from_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    to_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    category: Optional[str] = Query(None),
    party_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Expense Report: Vouchers of type Payment/Purchase, filtered by date.
    """
    start_dt, end_dt = _date_filter_label(date_filter, from_date, to_date)

    q = db.query(Voucher).filter(Voucher.voucher_type.in_(["Payment", "Purchase"]))
    if start_dt:
        q = q.filter(Voucher.date >= start_dt)
    if end_dt:
        q = q.filter(Voucher.date <= end_dt)

    vouchers = q.order_by(Voucher.date.desc()).all()

    items = []
    total_expense = 0.0
    category_breakdown: Dict[str, float] = {}

    for v in vouchers:
        amt = float(v.total_amount or 0.0)
        total_expense += amt

        # Determine category from entries
        cat = "General"
        party_name = None
        for e in v.entries:
            if e.account and e.account.type == "Expense":
                cat = e.account.name
            if e.party:
                party_name = e.party.name

        if category and category.lower() not in cat.lower():
            continue
        if party_id:
            linked_party_ids = [e.party_id for e in v.entries if e.party_id]
            if party_id not in linked_party_ids:
                continue

        category_breakdown[cat] = category_breakdown.get(cat, 0.0) + amt

        items.append({
            "id": v.id,
            "voucher_number": v.voucher_number,
            "date": v.date.strftime("%Y-%m-%d") if v.date else None,
            "voucher_type": v.voucher_type,
            "category": cat,
            "party_name": party_name,
            "amount_pkr": amt,
            "narration": v.narration,
            "reference_no": v.reference_no,
        })

    return {
        "currency": "PKR",
        "period": {
            "from_date": _fmt_date(start_dt),
            "to_date": _fmt_date(end_dt),
            "filter": date_filter or "custom",
        },
        "summary": {
            "total_expense_pkr": total_expense,
            "transaction_count": len(items),
            "category_breakdown": [{"category": k, "total_pkr": v} for k, v in sorted(category_breakdown.items())],
        },
        "items": items,
    }


# ---------------------------------------------------------------------------
# PAYMENTS & RECEIPTS REPORT — with date filters
# ---------------------------------------------------------------------------
@router.get("/payments")
def get_payments_report(
    date_filter: Optional[str] = Query(None, description="today|yesterday|this_week|this_month|last_month"),
    from_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    to_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    payment_type: Optional[str] = Query(None, description="CustomerReceipt|SupplierPayment"),
    party_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Payments & Receipts Report: all PaymentAllocation records with date filters.
    """
    start_dt, end_dt = _date_filter_label(date_filter, from_date, to_date)

    q = db.query(PaymentAllocation).filter(PaymentAllocation.is_voided == False)
    if start_dt:
        q = q.filter(PaymentAllocation.payment_date >= start_dt)
    if end_dt:
        q = q.filter(PaymentAllocation.payment_date <= end_dt)
    if payment_type:
        q = q.filter(PaymentAllocation.payment_type.ilike(f"%{payment_type}%"))
    if party_id:
        q = q.filter(PaymentAllocation.party_id == party_id)

    payments = q.order_by(PaymentAllocation.payment_date.desc()).all()

    items = []
    total_receipts = 0.0
    total_supplier_payments = 0.0

    for p in payments:
        amt = float(p.amount or 0.0)
        is_receipt = "receipt" in (p.payment_type or "").lower() or "customer" in (p.payment_type or "").lower()
        if is_receipt:
            total_receipts += amt
        else:
            total_supplier_payments += amt

        items.append({
            "id": p.id,
            "payment_number": p.payment_number,
            "date": p.payment_date.strftime("%Y-%m-%d") if p.payment_date else None,
            "payment_type": p.payment_type,
            "party_name": p.party.name if p.party else None,
            "party_type": p.party.type if p.party else None,
            "amount_pkr": amt,
            "payment_method": p.payment_method,
            "reference_no": p.reference_no,
            "notes": p.notes,
            "voucher_id": p.voucher_id,
        })

    return {
        "currency": "PKR",
        "period": {
            "from_date": _fmt_date(start_dt),
            "to_date": _fmt_date(end_dt),
            "filter": date_filter or "custom",
        },
        "summary": {
            "total_receipts_pkr": total_receipts,
            "total_supplier_payments_pkr": total_supplier_payments,
            "grand_total_pkr": total_receipts + total_supplier_payments,
            "transaction_count": len(items),
        },
        "items": items,
    }


# ---------------------------------------------------------------------------
# CUSTOMER OUTSTANDING BALANCES REPORT
# ---------------------------------------------------------------------------
@router.get("/customer-balances")
def get_customer_balances(
    search: Optional[str] = Query(None),
    min_balance: Optional[float] = Query(None, description="Minimum outstanding balance"),
    db: Session = Depends(get_db)
):
    """
    Customer Ledger and Outstanding Balances Report.
    Lists all customers with their opening balance, total debits (charges),
    total credits (payments received), and current outstanding balance.
    """
    q = db.query(Party).filter(Party.type == "Customer")
    if search:
        q = q.filter(Party.name.ilike(f"%{search}%"))

    customers = q.order_by(Party.name.asc()).all()

    items = []
    grand_opening = 0.0
    grand_debits = 0.0
    grand_credits = 0.0
    grand_outstanding = 0.0

    for c in customers:
        opening = float(c.opening_balance or 0.0)

        # Compute from voucher entries
        entries = db.query(VoucherEntry).join(Voucher).filter(
            VoucherEntry.party_id == c.id
        ).all()

        total_debit = sum(float(e.amount) for e in entries if e.entry_type == "Debit")
        total_credit = sum(float(e.amount) for e in entries if e.entry_type == "Credit")

        # Outstanding = opening + debits - credits (for Receivable-type)
        balance_type = getattr(c, "balance_type", "Receivable") or "Receivable"
        if balance_type == "Receivable":
            outstanding = opening + total_debit - total_credit
        else:
            outstanding = opening + total_credit - total_debit

        if min_balance is not None and outstanding < min_balance:
            continue

        grand_opening += opening
        grand_debits += total_debit
        grand_credits += total_credit
        grand_outstanding += outstanding

        items.append({
            "party_id": c.id,
            "party_name": c.name,
            "phone": c.phone,
            "city": c.city,
            "balance_type": balance_type,
            "opening_balance_pkr": opening,
            "total_debit_pkr": total_debit,
            "total_credit_pkr": total_credit,
            "outstanding_balance_pkr": outstanding,
            "current_balance_pkr": float(c.current_balance or 0.0),
            "credit_limit_pkr": float(c.credit_limit or 0.0),
        })

    return {
        "currency": "PKR",
        "report_date": date.today().isoformat(),
        "summary": {
            "total_customers": len(items),
            "grand_opening_balance_pkr": grand_opening,
            "grand_total_debit_pkr": grand_debits,
            "grand_total_credit_pkr": grand_credits,
            "grand_outstanding_pkr": grand_outstanding,
        },
        "items": items,
    }


# ---------------------------------------------------------------------------
# SUPPLIER OUTSTANDING BALANCES REPORT
# ---------------------------------------------------------------------------
@router.get("/supplier-balances")
def get_supplier_balances(
    search: Optional[str] = Query(None),
    min_balance: Optional[float] = Query(None, description="Minimum outstanding balance"),
    db: Session = Depends(get_db)
):
    """
    Supplier Ledger and Outstanding Balances Report.
    Lists all suppliers with opening balance, total credits (liabilities),
    total debits (payments made), and current outstanding payable.
    """
    q = db.query(Party).filter(Party.type.in_(["Supplier", "Vendor"]))
    if search:
        q = q.filter(Party.name.ilike(f"%{search}%"))

    suppliers = q.order_by(Party.name.asc()).all()

    items = []
    grand_opening = 0.0
    grand_debits = 0.0
    grand_credits = 0.0
    grand_outstanding = 0.0

    for s in suppliers:
        opening = float(s.opening_balance or 0.0)

        entries = db.query(VoucherEntry).join(Voucher).filter(
            VoucherEntry.party_id == s.id
        ).all()

        total_debit = sum(float(e.amount) for e in entries if e.entry_type == "Debit")
        total_credit = sum(float(e.amount) for e in entries if e.entry_type == "Credit")

        # Supplier (Payable): opening payable + credits (new liabilities) - debits (payments made)
        balance_type = getattr(s, "balance_type", "Payable") or "Payable"
        if balance_type == "Payable":
            outstanding = opening + total_credit - total_debit
        else:
            outstanding = opening + total_debit - total_credit

        if min_balance is not None and outstanding < min_balance:
            continue

        grand_opening += opening
        grand_debits += total_debit
        grand_credits += total_credit
        grand_outstanding += outstanding

        items.append({
            "party_id": s.id,
            "party_name": s.name,
            "phone": s.phone,
            "balance_type": balance_type,
            "opening_balance_pkr": opening,
            "total_debit_pkr": total_debit,
            "total_credit_pkr": total_credit,
            "outstanding_balance_pkr": outstanding,
            "current_balance_pkr": float(s.current_balance or 0.0),
        })

    return {
        "currency": "PKR",
        "report_date": date.today().isoformat(),
        "summary": {
            "total_suppliers": len(items),
            "grand_opening_balance_pkr": grand_opening,
            "grand_total_debit_pkr": grand_debits,
            "grand_total_credit_pkr": grand_credits,
            "grand_outstanding_pkr": grand_outstanding,
        },
        "items": items,
    }


# ---------------------------------------------------------------------------
# TRANSACTION REPORT — all vouchers with date filters
# ---------------------------------------------------------------------------
@router.get("/transactions")
def get_transaction_report(
    date_filter: Optional[str] = Query(None, description="today|yesterday|this_week|this_month|last_month"),
    from_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    to_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    voucher_type: Optional[str] = Query(None, description="Sales|Receipt|Payment|Purchase|Journal"),
    party_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(200, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """
    Full Transaction Report: all double-entry voucher entries with date filters.
    Groups by voucher for a clean transaction view.
    """
    start_dt, end_dt = _date_filter_label(date_filter, from_date, to_date)

    q = db.query(Voucher)
    if start_dt:
        q = q.filter(Voucher.date >= start_dt)
    if end_dt:
        q = q.filter(Voucher.date <= end_dt)
    if voucher_type:
        q = q.filter(Voucher.voucher_type.ilike(f"%{voucher_type}%"))
    if search:
        s = f"%{search}%"
        q = q.filter(
            Voucher.voucher_number.ilike(s) |
            Voucher.reference_no.ilike(s) |
            Voucher.narration.ilike(s)
        )
    if party_id:
        q = q.join(Voucher.entries).filter(VoucherEntry.party_id == party_id)

    total_count = q.count()
    vouchers = q.order_by(Voucher.date.desc(), Voucher.id.desc()).offset(offset).limit(limit).all()

    items = []
    grand_inflow = 0.0
    grand_outflow = 0.0

    for v in vouchers:
        amt = float(v.total_amount or 0.0)
        vtype = v.voucher_type or "Journal"
        if vtype in ("Receipt", "Sales"):
            grand_inflow += amt
        elif vtype in ("Payment", "Purchase"):
            grand_outflow += amt

        entries_out = []
        party_names = []
        for e in v.entries:
            if e.party and e.party.name not in party_names:
                party_names.append(e.party.name)
            entries_out.append({
                "account_name": e.account.name if e.account else "N/A",
                "account_type": e.account.type if e.account else None,
                "party_name": e.party.name if e.party else None,
                "entry_type": e.entry_type,
                "amount_pkr": float(e.amount or 0.0),
                "narration": e.narration,
            })

        items.append({
            "id": v.id,
            "voucher_number": v.voucher_number,
            "date": v.date.strftime("%Y-%m-%d") if v.date else None,
            "voucher_type": vtype,
            "reference_no": v.reference_no,
            "narration": v.narration,
            "total_amount_pkr": amt,
            "parties": party_names,
            "created_by": v.created_by,
            "entries": entries_out,
        })

    return {
        "currency": "PKR",
        "period": {
            "from_date": _fmt_date(start_dt),
            "to_date": _fmt_date(end_dt),
            "filter": date_filter or "custom",
        },
        "summary": {
            "total_transactions": total_count,
            "page_count": len(items),
            "grand_inflow_pkr": grand_inflow,
            "grand_outflow_pkr": grand_outflow,
            "net_pkr": grand_inflow - grand_outflow,
        },
        "pagination": {
            "limit": limit,
            "offset": offset,
            "total": total_count,
        },
        "items": items,
    }


# ---------------------------------------------------------------------------
# CASH FLOW REPORT — inflows vs outflows by date range
# ---------------------------------------------------------------------------
@router.get("/cash-flow")
def get_cash_flow_report(
    date_filter: Optional[str] = Query(None, description="today|yesterday|this_week|this_month|last_month"),
    from_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    to_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    db: Session = Depends(get_db)
):
    """
    Cash Flow Report: inflows (Receipts + Sales) vs outflows (Payments + Purchases).
    """
    start_dt, end_dt = _date_filter_label(date_filter, from_date, to_date)

    q = db.query(Voucher)
    if start_dt:
        q = q.filter(Voucher.date >= start_dt)
    if end_dt:
        q = q.filter(Voucher.date <= end_dt)

    vouchers = q.order_by(Voucher.date.asc()).all()

    inflow_items = []
    outflow_items = []
    total_inflow = 0.0
    total_outflow = 0.0

    for v in vouchers:
        amt = float(v.total_amount or 0.0)
        row = {
            "date": v.date.strftime("%Y-%m-%d") if v.date else None,
            "voucher_number": v.voucher_number,
            "voucher_type": v.voucher_type,
            "narration": v.narration,
            "amount_pkr": amt,
        }
        if v.voucher_type in ("Receipt", "Sales"):
            total_inflow += amt
            inflow_items.append(row)
        elif v.voucher_type in ("Payment", "Purchase"):
            total_outflow += amt
            outflow_items.append(row)

    return {
        "currency": "PKR",
        "period": {
            "from_date": _fmt_date(start_dt),
            "to_date": _fmt_date(end_dt),
            "filter": date_filter or "custom",
        },
        "summary": {
            "total_inflow_pkr": total_inflow,
            "total_outflow_pkr": total_outflow,
            "net_cash_flow_pkr": total_inflow - total_outflow,
        },
        "inflows": inflow_items,
        "outflows": outflow_items,
    }
