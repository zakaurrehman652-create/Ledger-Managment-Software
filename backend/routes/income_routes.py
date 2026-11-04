from datetime import datetime, date

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query

from sqlalchemy.orm import Session

from sqlalchemy import func



from backend.database import get_db

from backend.models import (

    IncomeTransaction, Voucher, VoucherEntry, Account, Party, User

)

from backend.schemas import (

    IncomeCreate, IncomeUpdate, IncomeOut, IncomeListOut

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

from backend.auth import get_current_user



router = APIRouter(prefix="/api/v1/income", tags=["Income Management"])





def generate_income_number(db: Session, target_date: Optional[datetime] = None) -> str:

    """

    Format: TA-INC-YYYY-MMM-000001

    Sequentially numbered by year and month.

    """

    if not target_date:

        target_date = datetime.utcnow()



    year = target_date.year

    month_abbr = target_date.strftime("%b").upper()

    prefix = f"TA-INC-{year}-{month_abbr}-"



    records = db.query(IncomeTransaction).filter(

        IncomeTransaction.transaction_number.like(f"{prefix}%")

    ).all()



    max_seq = 0

    for r in records:

        tnum = (r.transaction_number or "").strip()

        if tnum.startswith(prefix):

            suffix = tnum[len(prefix):].strip()

            if suffix.isdigit():

                max_seq = max(max_seq, int(suffix))



    return f"{prefix}{max_seq + 1:06d}"





def get_or_create_revenue_account(db: Session, category_name: str) -> Account:

    clean_name = (category_name or "General Income").strip()

    acc = db.query(Account).filter(

        Account.name.ilike(clean_name),

        Account.type == "Revenue"

    ).first()

    if acc:

        return acc



    # Generate next 4xxx code for Revenue

    rev_accounts = db.query(Account).filter(Account.type == "Revenue").all()

    codes = []

    for a in rev_accounts:

        try:

            if a.code.isdigit():

                codes.append(int(a.code))

        except ValueError:

            pass



    next_code = max(codes) + 10 if codes else 4010

    new_acc = Account(

        code=str(next_code),

        name=clean_name,

        type="Revenue",

        description=f"Revenue account for {clean_name}",

        balance=0.0,

        is_active=True

    )

    db.add(new_acc)

    db.flush()

    return new_acc





def get_accounts_receivable_account(db: Session) -> Account:

    acc = db.query(Account).filter(Account.code == "1200").first()

    if acc:

        return acc

    acc = db.query(Account).filter(

        Account.type == "Asset",

        Account.name.ilike("%Receivable%")

    ).first()

    if acc:

        return acc

    acc = Account(

        code="1200",

        name="Accounts Receivable",

        type="Asset",

        description="Trade Debtors / Customer Balances",

        balance=0.0,

        is_active=True

    )

    db.add(acc)

    db.flush()

    return acc





@router.get("/next-number")

def get_next_number(date_str: Optional[str] = Query(None), db: Session = Depends(get_db)):

    target_date = datetime.utcnow()

    if date_str:

        try:

            target_date = datetime.strptime(date_str, "%Y-%m-%d")

        except ValueError:

            pass

    return {

        "next_transaction_number": generate_income_number(db, target_date),

        "next_reference_no": generate_reference_number(db)

    }





@router.get("", response_model=IncomeListOut)

def list_income(

    date_filter: Optional[str] = Query(None, alias="date", description="YYYY-MM-DD"),

    start_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),

    end_date: Optional[str] = Query(None, description="End date YYYY-MM-DD"),

    category: Optional[str] = Query(None),

    customer_id: Optional[int] = Query(None),

    search: Optional[str] = Query(None),

    is_receipt: Optional[bool] = Query(None),

    db: Session = Depends(get_db)

):

    query = db.query(IncomeTransaction).order_by(

        IncomeTransaction.date.desc(), IncomeTransaction.id.desc()

    )



    all_txns = query.all()



    today_str = date.today().isoformat()

    total_income_all = 0.0

    total_receipts_all = 0.0

    today_total = 0.0



    for t in all_txns:

        if not t.is_voided:

            if t.is_customer_receipt:

                total_receipts_all += t.amount

            else:

                total_income_all += t.amount



            t_date_str = t.date.strftime("%Y-%m-%d") if t.date else ""

            if t_date_str == today_str:

                today_total += t.amount



    filtered_items = []

    for t in all_txns:

        t_date_str = t.date.strftime("%Y-%m-%d") if t.date else ""



        if date_filter and t_date_str != date_filter:

            continue

        if start_date and t_date_str < start_date:

            continue

        if end_date and t_date_str > end_date:

            continue

        if category and category.lower() not in (t.income_category or "").lower():

            continue

        if customer_id and t.party_id != customer_id:

            continue

        if is_receipt is not None and t.is_customer_receipt != is_receipt:

            continue

        if search:

            s = search.lower()

            party_name = t.party.name.lower() if t.party else ""

            num = (t.transaction_number or "").lower()

            ref = (t.reference_no or "").lower()

            desc = (t.description or "").lower()

            if s not in party_name and s not in num and s not in ref and s not in desc:

                continue



        filtered_items.append(IncomeOut(

            id=t.id,

            transaction_number=t.transaction_number,

            date=t.date,

            income_category=t.income_category,

            party_id=t.party_id,

            party_name=t.party.name if t.party else None,

            amount=t.amount,

            payment_method=t.payment_method,

            reference_no=t.reference_no,

            description=t.description,

            notes=t.notes,

            created_by=t.created_by,

            created_at=t.created_at,

            voucher_id=t.voucher_id,

            is_customer_receipt=t.is_customer_receipt,

            is_voided=t.is_voided,

            void_reason=t.void_reason

        ))



    filtered_total = sum(x.amount for x in filtered_items if not x.is_voided)



    return IncomeListOut(

        total_income_pkr=total_income_all,

        total_receipts_pkr=total_receipts_all,

        today_pkr=today_total,

        filtered_total_pkr=filtered_total,

        items=filtered_items

    )





@router.post("", response_model=IncomeOut, status_code=status.HTTP_201_CREATED)

def create_income(

    income_in: IncomeCreate,

    db: Session = Depends(get_db)

):

    if income_in.amount <= 0:

        raise HTTPException(

            status_code=status.HTTP_400_BAD_REQUEST,

            detail="Income amount must be greater than zero."

        )



    t_date = income_in.date or datetime.utcnow()

    t_num = generate_income_number(db, t_date)

    ref_no = income_in.reference_no.strip() if income_in.reference_no and income_in.reference_no.strip() else generate_reference_number(db)



    party = None

    if income_in.party_id:

        party = db.query(Party).filter(Party.id == income_in.party_id).first()

        if not party:

            raise HTTPException(

                status_code=status.HTTP_404_NOT_FOUND,

                detail=f"Customer with id {income_in.party_id} not found."

            )



    user = db.query(User).first()

    creator_name = user.full_name if user and user.full_name else "Muhammad Haris"



    # Guard: A customer receipt REQUIRES a specific customer party.

    # If no party is selected (Walk-in / Cash), it must be recorded as Direct Revenue.

    is_cust_rcp = bool(income_in.is_customer_receipt and party)



    # --- Double-Entry Accounting Posting ---

    payment_acc = get_or_create_payment_account(db, method_name=income_in.payment_method)



    v_num = generate_voucher_number(db, v_date=t_date)

    v_type = "Receipt" if is_cust_rcp else "Sales"

    narration = income_in.description or f"Income - {income_in.income_category}"



    voucher = Voucher(

        voucher_number=v_num,

        date=t_date,

        voucher_type=v_type,

        reference_no=ref_no,

        narration=narration,

        total_amount=income_in.amount,

        created_by=creator_name,

        is_synced=True,

        client_uuid=f"inc-{int(datetime.utcnow().timestamp() * 1000)}"

    )

    db.add(voucher)

    db.flush()



    # Entry 1: Debit to Cash/Bank (Inflow)

    e_debit = VoucherEntry(

        voucher_id=voucher.id,

        account_id=payment_acc.id,

        party_id=party.id if party else None,

        entry_type="Debit",

        amount=income_in.amount,

        narration=narration

    )

    db.add(e_debit)

    update_account_balance(payment_acc, "Debit", income_in.amount)



    if is_cust_rcp:

        # Credit to Accounts Receivable

        ar_acc = get_accounts_receivable_account(db)

        e_credit = VoucherEntry(

            voucher_id=voucher.id,

            account_id=ar_acc.id,

            party_id=party.id if party else None,

            entry_type="Credit",

            amount=income_in.amount,

            narration=f"Receipt from customer {party.name if party else ''} - settles receivable"

        )

        db.add(e_credit)

        update_account_balance(ar_acc, "Credit", income_in.amount)

        if party:

            update_party_balance(party, "Credit", income_in.amount)

    else:

        # Credit to Revenue Account (Genuine new revenue)

        rev_acc = get_or_create_revenue_account(db, income_in.income_category)

        e_credit = VoucherEntry(

            voucher_id=voucher.id,

            account_id=rev_acc.id,

            party_id=party.id if party else None,

            entry_type="Credit",

            amount=income_in.amount,

            narration=narration

        )

        db.add(e_credit)

        update_account_balance(rev_acc, "Credit", income_in.amount)



    # 3. Create IncomeTransaction record

    income_tx = IncomeTransaction(

        transaction_number=t_num,

        date=t_date,

        income_category=income_in.income_category,

        party_id=party.id if party else None,

        amount=income_in.amount,

        payment_method=income_in.payment_method,

        reference_no=ref_no,

        description=income_in.description,

        notes=income_in.notes,

        created_by=creator_name,

        created_at=datetime.utcnow(),

        voucher_id=voucher.id,

        is_customer_receipt=is_cust_rcp,

        is_voided=False

    )

    db.add(income_tx)



    db.commit()

    db.refresh(income_tx)



    return IncomeOut(

        id=income_tx.id,

        transaction_number=income_tx.transaction_number,

        date=income_tx.date,

        income_category=income_tx.income_category,

        party_id=income_tx.party_id,

        party_name=party.name if party else None,

        amount=income_tx.amount,

        payment_method=income_tx.payment_method,

        reference_no=income_tx.reference_no,

        description=income_tx.description,

        notes=income_tx.notes,

        created_by=income_tx.created_by,

        created_at=income_tx.created_at,

        voucher_id=income_tx.voucher_id,

        is_customer_receipt=income_tx.is_customer_receipt,

        is_voided=income_tx.is_voided

    )





@router.get("/{income_id}", response_model=IncomeOut)

def get_income_detail(income_id: int, db: Session = Depends(get_db)):

    tx = db.query(IncomeTransaction).filter(IncomeTransaction.id == income_id).first()

    if not tx:

        raise HTTPException(status_code=404, detail="Income transaction not found.")

    return IncomeOut(

        id=tx.id,

        transaction_number=tx.transaction_number,

        date=tx.date,

        income_category=tx.income_category,

        party_id=tx.party_id,

        party_name=tx.party.name if tx.party else None,

        amount=tx.amount,

        payment_method=tx.payment_method,

        reference_no=tx.reference_no,

        description=tx.description,

        notes=tx.notes,

        created_by=tx.created_by,

        created_at=tx.created_at,

        voucher_id=tx.voucher_id,

        is_customer_receipt=tx.is_customer_receipt,

        is_voided=tx.is_voided,

        void_reason=tx.void_reason

    )





@router.put("/{income_id}", response_model=IncomeOut)

def update_income(

    income_id: int,

    income_up: IncomeUpdate,

    db: Session = Depends(get_db)

):

    tx = db.query(IncomeTransaction).filter(IncomeTransaction.id == income_id).first()

    if not tx:

        raise HTTPException(status_code=404, detail="Income transaction not found.")

    if tx.is_voided:

        raise HTTPException(

            status_code=400,

            detail="Cannot edit a voided income transaction."

        )



    new_amount = income_up.amount if income_up.amount is not None else tx.amount

    if new_amount <= 0:

        raise HTTPException(status_code=400, detail="Amount must be greater than zero.")



    new_date = income_up.date if income_up.date is not None else tx.date

    new_method = income_up.payment_method if income_up.payment_method is not None else tx.payment_method

    new_category = income_up.income_category.strip() if income_up.income_category is not None else tx.income_category

    new_party_id = income_up.party_id if income_up.party_id is not None else tx.party_id

    new_desc = income_up.description if income_up.description is not None else tx.description

    new_ref = income_up.reference_no if income_up.reference_no is not None else tx.reference_no

    new_notes = income_up.notes if income_up.notes is not None else tx.notes



    new_party = None

    if new_party_id:

        new_party = db.query(Party).filter(Party.id == new_party_id).first()



    raw_is_rcp = income_up.is_customer_receipt if income_up.is_customer_receipt is not None else tx.is_customer_receipt

    new_is_rcp = bool(raw_is_rcp and new_party)



    fin_changed = any([

        income_up.amount is not None and income_up.amount != tx.amount,

        income_up.payment_method is not None and income_up.payment_method != tx.payment_method,

        income_up.party_id is not None and income_up.party_id != tx.party_id,

        new_is_rcp != tx.is_customer_receipt,

        income_up.income_category is not None and income_up.income_category != tx.income_category,

        income_up.date is not None and income_up.date != tx.date

    ])



    if fin_changed and tx.voucher_id:

        v = db.query(Voucher).filter(Voucher.id == tx.voucher_id).first()

        if v:

            # 1. Reverse previous entries

            for entry in list(v.entries):

                if entry.account_id:

                    acc = db.query(Account).filter(Account.id == entry.account_id).first()

                    if acc:

                        reverse_account_balance(acc, entry.entry_type, entry.amount)

                if entry.party_id:

                    p = db.query(Party).filter(Party.id == entry.party_id).first()

                    if p:

                        reverse_party_balance(p, entry.entry_type, entry.amount)

                db.delete(entry)

            db.flush()



            # 2. Re-create entries with updated values

            payment_acc = get_or_create_payment_account(db, method_name=new_method)

            v.voucher_type = "Receipt" if new_is_rcp else "Sales"

            v.date = new_date

            v.total_amount = new_amount

            v.reference_no = new_ref

            v.narration = new_desc or f"Income - {new_category}"



            e_debit = VoucherEntry(

                voucher_id=v.id,

                account_id=payment_acc.id,

                party_id=new_party.id if new_party else None,

                entry_type="Debit",

                amount=new_amount,

                narration=v.narration

            )

            db.add(e_debit)

            update_account_balance(payment_acc, "Debit", new_amount)



            if new_is_rcp:

                ar_acc = get_accounts_receivable_account(db)

                e_credit = VoucherEntry(

                    voucher_id=v.id,

                    account_id=ar_acc.id,

                    party_id=new_party.id if new_party else None,

                    entry_type="Credit",

                    amount=new_amount,

                    narration=f"Receipt from customer {new_party.name if new_party else ''} - settles receivable"

                )

                db.add(e_credit)

                update_account_balance(ar_acc, "Credit", new_amount)

                if new_party:

                    update_party_balance(new_party, "Credit", new_amount)

            else:

                rev_acc = get_or_create_revenue_account(db, new_category)

                e_credit = VoucherEntry(

                    voucher_id=v.id,

                    account_id=rev_acc.id,

                    party_id=new_party.id if new_party else None,

                    entry_type="Credit",

                    amount=new_amount,

                    narration=v.narration

                )

                db.add(e_credit)

                update_account_balance(rev_acc, "Credit", new_amount)



    tx.date = new_date

    tx.income_category = new_category

    tx.party_id = new_party_id if new_party else None

    tx.amount = new_amount

    tx.payment_method = new_method

    tx.reference_no = new_ref

    tx.description = new_desc

    tx.notes = new_notes

    tx.is_customer_receipt = new_is_rcp



    db.commit()

    db.refresh(tx)

    return IncomeOut(

        id=tx.id,

        transaction_number=tx.transaction_number,

        date=tx.date,

        income_category=tx.income_category,

        party_id=tx.party_id,

        party_name=tx.party.name if tx.party else None,

        amount=tx.amount,

        payment_method=tx.payment_method,

        reference_no=tx.reference_no,

        description=tx.description,

        notes=tx.notes,

        created_by=tx.created_by,

        created_at=tx.created_at,

        voucher_id=tx.voucher_id,

        is_customer_receipt=tx.is_customer_receipt,

        is_voided=tx.is_voided,

        void_reason=tx.void_reason

    )





@router.post("/{income_id}/void")

def void_income(

    income_id: int,

    reason: str = Query("Voided by user"),

    db: Session = Depends(get_db)

):

    """

    Void and reverse the financial impact of the transaction.

    Instead of hard deleting, marks transaction as voided and reverses journal balances.

    """

    tx = db.query(IncomeTransaction).filter(IncomeTransaction.id == income_id).first()

    if not tx:

        raise HTTPException(status_code=404, detail="Income transaction not found.")

    if tx.is_voided:

        raise HTTPException(status_code=400, detail="Transaction is already voided.")



    # Reverse the associated double-entry voucher

    if tx.voucher_id:

        v = db.query(Voucher).filter(Voucher.id == tx.voucher_id).first()

        if v:

            for entry in v.entries:

                if entry.account_id:

                    acc = db.query(Account).filter(Account.id == entry.account_id).first()

                    if acc:

                        reverse_account_balance(acc, entry.entry_type, entry.amount)

                if entry.party_id:

                    party = db.query(Party).filter(Party.id == entry.party_id).first()

                    if party:

                        reverse_party_balance(party, entry.entry_type, entry.amount)



    tx.is_voided = True

    tx.void_reason = reason

    tx.voided_at = datetime.utcnow()

    tx.voided_by = "Lead Financial Controller"



    db.commit()

    return {

        "success": True,

        "message": f"Income transaction {tx.transaction_number} voided and reversed successfully."

    }





@router.delete("/{income_id}")

def delete_income_transaction(income_id: int, db: Session = Depends(get_db)):

    tx = db.query(IncomeTransaction).filter(IncomeTransaction.id == income_id).first()

    if not tx:

        raise HTTPException(status_code=404, detail="Income transaction not found.")



    tx_num = tx.transaction_number or f"#{income_id}"



    # If linked to a double-entry voucher, reverse balances and delete the voucher

    if tx.voucher_id:

        v = db.query(Voucher).filter(Voucher.id == tx.voucher_id).first()

        if v:

            if not tx.is_voided:

                for entry in v.entries:

                    if entry.account_id:

                        acc = db.query(Account).filter(Account.id == entry.account_id).first()

                        if acc:

                            reverse_account_balance(acc, entry.entry_type, entry.amount)

                    if entry.party_id:

                        party = db.query(Party).filter(Party.id == entry.party_id).first()

                        if party:

                            reverse_party_balance(party, entry.entry_type, entry.amount)

                    db.delete(entry)

            else:

                for entry in v.entries:

                    db.delete(entry)

            db.delete(v)



    db.delete(tx)

    db.commit()

    return {

        "success": True,

        "message": f"Income transaction {tx_num} deleted and reversed successfully."

    }

