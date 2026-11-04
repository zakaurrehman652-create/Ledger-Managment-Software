from datetime import datetime, timedelta
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.database import get_db
from backend.models import Account, Party, Voucher, VoucherEntry, IncomeTransaction, PaymentAllocation
from backend.schemas import DashboardSummary, MonthlyCashFlowItem, VoucherOut, VoucherEntryOut
from backend.auth import get_current_user

router = APIRouter(prefix="/api/v1/dashboard", tags=["Dashboard"])

@router.get("/summary", response_model=DashboardSummary)
def get_dashboard_summary(db: Session = Depends(get_db)):
    accounts = db.query(Account).filter(Account.is_active == True).all()

    # Calculate financial metrics in PKR
    liquid_funds = sum(
        a.balance for a in accounts
        if a.type == "Asset" and ("Cash" in a.name or "Bank" in a.name or a.code in ["1010", "1020", "1030"])
    )

    receivables = sum(
        a.balance for a in accounts
        if a.code == "1200" or "Receivable" in a.name or "Debtor" in a.name
    )

    payables = sum(
        a.balance for a in accounts
        if a.type == "Liability" and ("Payable" in a.name or "Creditor" in a.name or a.code == "2010")
    )

    working_capital = (liquid_funds + receivables) - payables

    # -- Single Source of Truth for Income (double-counting bug fix) --------
    # Every income entry creates BOTH an IncomeTransaction AND a linked Voucher
    # (Sales/Receipt type). Adding both would double every rupee.
    # FIX: Use IncomeTransaction as the sole income source; only add Vouchers
    # that are NOT linked to any IncomeTransaction (pure manual vouchers).
    income_tx_total = db.query(func.sum(IncomeTransaction.amount)).filter(
        IncomeTransaction.is_voided == False
    ).scalar() or 0.0

    customer_receipts_total = db.query(func.sum(PaymentAllocation.amount)).filter(
        PaymentAllocation.is_voided == False,
        PaymentAllocation.payment_type.ilike("%receipt%")
    ).scalar() or 0.0

    supplier_payments_total = db.query(func.sum(PaymentAllocation.amount)).filter(
        PaymentAllocation.is_voided == False,
        PaymentAllocation.payment_type.ilike("%payment%")
    ).scalar() or 0.0

    # Voucher IDs already counted via IncomeTransaction -- exclude them
    linked_voucher_ids = db.query(IncomeTransaction.voucher_id).filter(
        IncomeTransaction.voucher_id.isnot(None),
        IncomeTransaction.is_voided == False
    )
    standalone_income_vouchers = db.query(func.sum(Voucher.total_amount)).filter(
        Voucher.voucher_type.in_(["Receipt", "Sales"]),
        Voucher.id.notin_(linked_voucher_ids)
    ).scalar() or 0.0

    standalone_expense_vouchers = db.query(func.sum(Voucher.total_amount)).filter(
        Voucher.voucher_type.in_(["Payment", "Purchase", "Expense"])
    ).scalar() or 0.0

    acc_revenue = sum(a.balance for a in accounts if a.type == "Revenue")
    acc_expense = sum(a.balance for a in accounts if a.type == "Expense")

    # Correct totals -- no double-counting
    total_revenue = income_tx_total + standalone_income_vouchers
    total_expense = supplier_payments_total + standalone_expense_vouchers
    amount_received = total_revenue + customer_receipts_total
    net_profit = amount_received - total_expense
    net_received_minus_expense = amount_received - total_expense

    # Dynamic Monthly Cash Flow series (Last 6 Months in PKR from real data)
    now = datetime.utcnow()
    monthly_flow = []
    for i in range(5, -1, -1):
        year = now.year
        month = now.month - i
        while month <= 0:
            month += 12
            year -= 1
        month_label = datetime(year, month, 1).strftime("%b %Y")
        ym_str = f"{year:04d}-{month:02d}"

        # IncomeTransaction = single source; exclude linked vouchers
        m_inc = db.query(func.sum(IncomeTransaction.amount)).filter(
            IncomeTransaction.is_voided == False,
            func.strftime('%Y-%m', IncomeTransaction.date) == ym_str
        ).scalar() or 0.0

        m_rcp = db.query(func.sum(PaymentAllocation.amount)).filter(
            PaymentAllocation.is_voided == False,
            PaymentAllocation.payment_type.ilike("%receipt%"),
            func.strftime('%Y-%m', PaymentAllocation.payment_date) == ym_str
        ).scalar() or 0.0

        # Only count standalone vouchers NOT linked to any IncomeTransaction
        linked_ids_m = db.query(IncomeTransaction.voucher_id).filter(
            IncomeTransaction.voucher_id.isnot(None),
            IncomeTransaction.is_voided == False,
            func.strftime('%Y-%m', IncomeTransaction.date) == ym_str
        )
        m_v_in = db.query(func.sum(Voucher.total_amount)).filter(
            Voucher.voucher_type.in_(["Receipt", "Sales"]),
            func.strftime('%Y-%m', Voucher.date) == ym_str,
            Voucher.id.notin_(linked_ids_m)
        ).scalar() or 0.0

        m_pay = db.query(func.sum(PaymentAllocation.amount)).filter(
            PaymentAllocation.is_voided == False,
            PaymentAllocation.payment_type.ilike("%payment%"),
            func.strftime('%Y-%m', PaymentAllocation.payment_date) == ym_str
        ).scalar() or 0.0

        m_v_out = db.query(func.sum(Voucher.total_amount)).filter(
            Voucher.voucher_type.in_(["Payment", "Purchase", "Expense"]),
            func.strftime('%Y-%m', Voucher.date) == ym_str
        ).scalar() or 0.0

        # inflow = IncomeTransactions + standalone vouchers + standalone receipts
        inflow_m = float(m_inc + m_v_in + m_rcp)
        outflow_m = float(m_pay + m_v_out)

        monthly_flow.append(MonthlyCashFlowItem(
            month=month_label,
            inflow_pkr=inflow_m,
            outflow_pkr=outflow_m,
            net_pkr=float(inflow_m - outflow_m)
        ))

    # Fetch recent vouchers
    vouchers = db.query(Voucher).order_by(Voucher.date.desc(), Voucher.id.desc()).limit(10).all()
    recent_vouchers = []
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
        recent_vouchers.append(VoucherOut(
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

    total_parties = db.query(Party).count()

    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_expense = db.query(Voucher).filter(
        Voucher.voucher_type == "Payment",
        Voucher.date >= today_start
    ).all()
    today_expense_pkr = sum(v.total_amount for v in today_expense)

    return DashboardSummary(
        currency="PKR",
        liquid_funds_pkr=liquid_funds,
        receivables_pkr=receivables,
        payables_pkr=payables,
        working_capital_pkr=working_capital,
        total_revenue_pkr=total_revenue,
        total_expense_pkr=total_expense,
        amount_received_pkr=amount_received,
        net_received_minus_expense_pkr=net_received_minus_expense,
        today_expense_pkr=today_expense_pkr,
        net_profit_pkr=net_profit,
        monthly_flow=monthly_flow,
        recent_vouchers=recent_vouchers,
        total_accounts=len(accounts),
        total_parties=total_parties
    )
