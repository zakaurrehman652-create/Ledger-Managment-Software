from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_email: Optional[str] = None
    user_role: Optional[str] = None

class TokenData(BaseModel):
    email: Optional[str] = None

class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    phone: Optional[str] = None
    address: Optional[str] = None
    company_name: Optional[str] = None
    is_active: bool
    access_token: Optional[str] = None

    class Config:
        from_attributes = True

class UserProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    company_name: Optional[str] = None
    password: Optional[str] = None

class PasswordResetRequest(BaseModel):
    email: str

class PasswordResetConfirm(BaseModel):
    email: str
    new_password: str

class EmployeeCreate(BaseModel):
    email: str = Field(..., min_length=4, max_length=255)
    password: str = Field(..., min_length=6, max_length=128)
    full_name: str = Field(..., min_length=2, max_length=255)
    role: str = "Accountant"
    phone: Optional[str] = None
    address: Optional[str] = None
    company_name: Optional[str] = "Tri Agro Farms"
    is_active: bool = True

class EmployeeUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None

class RolePermissionOut(BaseModel):
    role: str
    description: str
    permissions: List[str]

class AccountBase(BaseModel):
    code: str
    name: str
    type: str
    description: Optional[str] = None
    balance: float = 0.0
    is_active: bool = True

class AccountCreate(AccountBase):
    pass

class AccountUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    type: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

class AccountOut(AccountBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class PartyBase(BaseModel):
    name: str
    type: str
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = "Karachi"
    credit_limit: float = 0.0
    current_balance: float = 0.0
    opening_balance: float = 0.0
    balance_type: str = "Payable"  # Payable or Receivable


class PartyCreate(PartyBase):
    pass

class PartyUpdate(BaseModel):
    name: Optional[str] = None
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    credit_limit: Optional[float] = None

class PartyOut(PartyBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class SupplierBase(BaseModel):
    name: str
    type: str = "Supplier"
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = "Karachi"
    credit_limit: float = 0.0
    current_balance: float = 0.0
    opening_balance: float = 0.0
    balance_type: str = "Payable"
    notes: Optional[str] = None

class SupplierCreate(SupplierBase):
    pass

class SupplierUpdate(BaseModel):
    name: Optional[str] = None
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    credit_limit: Optional[float] = None
    opening_balance: Optional[float] = None
    balance_type: Optional[str] = None
    notes: Optional[str] = None

class SupplierOut(SupplierBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class VoucherEntryCreate(BaseModel):
    account_id: int
    party_id: Optional[int] = None
    entry_type: str
    amount: float = Field(gt=0)
    narration: Optional[str] = None

class VoucherEntryOut(BaseModel):
    id: int
    account_id: int
    party_id: Optional[int] = None
    entry_type: str
    amount: float
    narration: Optional[str] = None
    account_name: Optional[str] = None
    party_name: Optional[str] = None

    class Config:
        from_attributes = True

class VoucherCreate(BaseModel):
    voucher_number: Optional[str] = None
    voucher_type: str = "Journal"
    date: Optional[datetime] = None
    reference_no: Optional[str] = None
    narration: Optional[str] = None
    entries: List[VoucherEntryCreate]
    client_uuid: Optional[str] = None

class VoucherOut(BaseModel):
    id: int
    voucher_number: str
    date: datetime
    voucher_type: str
    reference_no: Optional[str] = None
    narration: Optional[str] = None
    total_amount: float
    created_by: str
    is_synced: bool
    client_uuid: Optional[str] = None
    entries: List[VoucherEntryOut] = []
    created_at: datetime

    class Config:
        from_attributes = True

class MonthlyCashFlowItem(BaseModel):
    month: str
    inflow_pkr: float
    outflow_pkr: float
    net_pkr: float

class DashboardSummary(BaseModel):
    currency: str = "PKR"
    liquid_funds_pkr: float
    receivables_pkr: float
    payables_pkr: float
    working_capital_pkr: float
    total_revenue_pkr: float
    total_expense_pkr: float
    amount_received_pkr: float = 0.0
    net_received_minus_expense_pkr: float = 0.0
    today_expense_pkr: float = 0.0
    net_profit_pkr: float
    monthly_flow: List[MonthlyCashFlowItem]
    recent_vouchers: List[VoucherOut]
    total_accounts: int
    total_parties: int

class SyncPayload(BaseModel):
    vouchers: List[VoucherCreate]

class SyncResult(BaseModel):
    synced_count: int
    duplicates_skipped: int
    message: str

class TrialBalanceItem(BaseModel):
    account_code: str
    account_name: str
    account_type: str
    debit_pkr: float
    credit_pkr: float

class TrialBalanceReport(BaseModel):
    currency: str = "PKR"
    items: List[TrialBalanceItem]
    total_debit_pkr: float
    total_credit_pkr: float
    is_balanced: bool
    difference_pkr: float

class ProfitLossReport(BaseModel):
    currency: str = "PKR"
    revenues: List[Dict[str, Any]]
    total_revenue_pkr: float
    expenses: List[Dict[str, Any]]
    total_expense_pkr: float
    net_profit_pkr: float

class ExpenseCreate(BaseModel):
    date: Optional[datetime] = None
    category: Optional[str] = "General"
    payment_account_id: Optional[int] = None
    payment_method: Optional[str] = "Cash in Hand"
    amount: float = Field(gt=0)
    narration: Optional[str] = None
    reference_no: Optional[str] = None
    supplier_id: Optional[int] = None
    notes: Optional[str] = None

class ExpenseUpdate(BaseModel):
    category: Optional[str] = None
    payment_method: Optional[str] = None
    payment_account_id: Optional[int] = None
    amount: Optional[float] = Field(None, gt=0)
    date: Optional[datetime] = None
    narration: Optional[str] = None
    reference_no: Optional[str] = None
    supplier_id: Optional[int] = None
    notes: Optional[str] = None

class ExpenseItemOut(BaseModel):
    id: int
    voucher_id: int
    voucher_number: str
    date: datetime
    category: str
    account_code: str
    payment_method: str
    amount: float
    narration: Optional[str] = None
    reference_no: Optional[str] = None
    supplier_id: Optional[int] = None
    supplier_name: Optional[str] = None
    notes: Optional[str] = None

class ExpenseListOut(BaseModel):
    total_all_time_pkr: float
    today_pkr: float
    filtered_total_pkr: float
    items: List[ExpenseItemOut]

# --- Custom Field Schemas ----------------------------------------------------

class CustomFieldBase(BaseModel):
    name: str = Field(..., description="Internal identifier, unique")
    label: str = Field(..., description="Human readable label")
    field_type: str = Field(..., description="One of: text, long_text, number, date, dropdown, checkbox")
    required: bool = False
    enabled: bool = True
    order: int = 0
    options: Optional[List[str]] = None  # Used when field_type == 'dropdown'

class CustomFieldCreate(CustomFieldBase):
    pass

class CustomFieldUpdate(BaseModel):
    label: Optional[str] = None
    field_type: Optional[str] = None
    required: Optional[bool] = None
    enabled: Optional[bool] = None
    order: Optional[int] = None
    options: Optional[List[str]] = None

class CustomFieldOut(CustomFieldBase):
    id: int

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Income Transaction Schemas
# ---------------------------------------------------------------------------
class IncomeCreate(BaseModel):
    date: Optional[datetime] = None
    income_category: str = "General Income"
    party_id: Optional[int] = None            # Customer (optional)
    amount: float = Field(gt=0)
    payment_method: str = "Cash"              # Cash, Bank Transfer, Card, Cheque, Other
    reference_no: Optional[str] = None
    description: Optional[str] = None
    notes: Optional[str] = None
    is_customer_receipt: bool = False         # True = collecting existing receivable

class IncomeUpdate(BaseModel):
    date: Optional[datetime] = None
    income_category: Optional[str] = None
    party_id: Optional[int] = None
    amount: Optional[float] = None
    payment_method: Optional[str] = None
    description: Optional[str] = None
    notes: Optional[str] = None
    reference_no: Optional[str] = None
    is_customer_receipt: Optional[bool] = None

class IncomeOut(BaseModel):
    id: int
    transaction_number: str
    date: datetime
    income_category: str
    party_id: Optional[int] = None
    party_name: Optional[str] = None
    amount: float
    payment_method: str
    reference_no: Optional[str] = None
    description: Optional[str] = None
    notes: Optional[str] = None
    created_by: str
    created_at: datetime
    voucher_id: Optional[int] = None
    is_customer_receipt: bool = False
    is_voided: bool = False
    void_reason: Optional[str] = None

    class Config:
        from_attributes = True

class IncomeListOut(BaseModel):
    total_income_pkr: float
    total_receipts_pkr: float
    today_pkr: float
    filtered_total_pkr: float
    items: List[IncomeOut]


# ---------------------------------------------------------------------------
# Payment Allocation Schemas (Customer Receipts & Supplier Payments)
# ---------------------------------------------------------------------------
class PaymentCreate(BaseModel):
    payment_date: Optional[datetime] = None
    payment_type: str                         # CustomerReceipt or SupplierPayment
    party_id: int
    amount: float = Field(gt=0)
    payment_method: str = "Cash"
    reference_no: Optional[str] = None
    notes: Optional[str] = None

class PaymentOut(BaseModel):
    id: int
    payment_number: str
    payment_date: datetime
    payment_type: str
    party_id: int
    party_name: Optional[str] = None
    party_type: Optional[str] = None
    amount: float
    payment_method: str
    reference_no: Optional[str] = None
    notes: Optional[str] = None
    created_by: str
    created_at: datetime
    voucher_id: Optional[int] = None
    is_voided: bool = False
    void_reason: Optional[str] = None
    original_balance_pkr: Optional[float] = 0.0
    remaining_balance_pkr: Optional[float] = 0.0

    class Config:
        from_attributes = True

class PaymentListOut(BaseModel):
    total_receipts_pkr: float
    total_supplier_payments_pkr: float
    today_pkr: float
    items: List[PaymentOut]


# ---------------------------------------------------------------------------
# Unified Ledger Schemas
# ---------------------------------------------------------------------------
class LedgerRowOut(BaseModel):
    id: str
    transaction_date: datetime
    transaction_type: str
    transaction_number: str
    reference_no: Optional[str] = None
    description: Optional[str] = None
    party_name: Optional[str] = None
    account_name: Optional[str] = None
    debit_pkr: float = 0.0
    credit_pkr: float = 0.0
    running_balance_pkr: Optional[float] = None
    created_by: Optional[str] = None
    voucher_id: Optional[int] = None
    is_voided: bool = False

class UnifiedLedgerOut(BaseModel):
    total_debit_pkr: float
    total_credit_pkr: float
    net_pkr: float
    total_records: int
    items: List[LedgerRowOut]


# ---------------------------------------------------------------------------
# Gate Pass Schemas
# ---------------------------------------------------------------------------
class GatePassItem(BaseModel):
    item_name: str
    quality: Optional[str] = "Fresh Flowers"
    quantity: float = 0.0
    unit: str = "Bunches"
    rate: Optional[float] = 0.0
    amount: Optional[float] = 0.0
    weight: Optional[str] = None
    remarks: Optional[str] = None

class GatePassCreate(BaseModel):
    pass_number: Optional[str] = None
    date: Optional[datetime] = None
    pass_type: str = "Outward"
    party_name: Optional[str] = None
    vehicle_number: Optional[str] = None
    driver_name: Optional[str] = None
    driver_phone: Optional[str] = None
    bilty_number: Optional[str] = None
    reference_no: Optional[str] = None
    items: List[GatePassItem] = []
    total_amount: Optional[float] = 0.0
    payment_type: Optional[str] = "Debit (Customer Ledger / Receivable)"
    remarks: Optional[str] = None
    prepared_by: Optional[str] = None
    gate_incharge: Optional[str] = None
    authorized_by: Optional[str] = None

class GatePassOut(BaseModel):
    id: int
    pass_number: str
    date: datetime
    pass_type: str
    party_name: Optional[str] = None
    vehicle_number: Optional[str] = None
    driver_name: Optional[str] = None
    driver_phone: Optional[str] = None
    bilty_number: Optional[str] = None
    reference_no: Optional[str] = None
    items: List[GatePassItem] = []
    total_amount: Optional[float] = 0.0
    payment_type: Optional[str] = "Debit (Customer Ledger / Receivable)"
    remarks: Optional[str] = None
    prepared_by: Optional[str] = "Tri Agro Farms Dispatch"
    gate_incharge: Optional[str] = "Security Officer"
    authorized_by: Optional[str] = "Farm General Manager"
    created_at: datetime

    class Config:
        from_attributes = True
