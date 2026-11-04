from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime,
    ForeignKey, Text, Table, UniqueConstraint, Numeric
)
from sqlalchemy.orm import relationship
from backend.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), default="Muhammad Haris")
    role = Column(String(100), default="Lead Financial Controller")
    phone = Column(String(100), default="+92 300 1234567")
    address = Column(Text, default="Plot 42, Commercial Avenue, I.I. Chundrigar Road, Karachi")
    company_name = Column(String(255), default="Tri Agro Farm")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(255), index=True, nullable=False)
    type = Column(String(50), index=True, nullable=False)
    description = Column(Text, nullable=True)
    balance = Column(Float, default=0.0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    entries = relationship("VoucherEntry", back_populates="account")


class Party(Base):
    __tablename__ = "parties"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), index=True, nullable=False)
    type = Column(String(50), index=True, nullable=False)  # Customer, Vendor, Supplier
    contact_person = Column(String(255), nullable=True)   # also used as business_name for Supplier
    phone = Column(String(50), nullable=True)
    email = Column(String(255), nullable=True)
    address = Column(Text, nullable=True)
    city = Column(String(100), default="Karachi")
    credit_limit = Column(Float, default=0.0)
    current_balance = Column(Float, default=0.0)
    opening_balance = Column(Float, default=0.0)
    balance_type = Column(String(20), default="Payable")   # Payable or Receivable
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    entries = relationship("VoucherEntry", back_populates="party")


class Voucher(Base):
    __tablename__ = "vouchers"

    id = Column(Integer, primary_key=True, index=True)
    voucher_number = Column(String(100), unique=True, index=True, nullable=False)
    date = Column(DateTime, default=datetime.utcnow, index=True)
    voucher_type = Column(String(50), index=True, default="Journal")
    reference_no = Column(String(100), nullable=True)
    narration = Column(Text, nullable=True)
    total_amount = Column(Float, default=0.0)
    created_by = Column(String(255), default="System Admin")
    is_synced = Column(Boolean, default=True)
    client_uuid = Column(String(100), unique=True, index=True, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    entries = relationship("VoucherEntry", back_populates="voucher", cascade="all, delete-orphan")


class VoucherEntry(Base):
    __tablename__ = "voucher_entries"

    id = Column(Integer, primary_key=True, index=True)
    voucher_id = Column(Integer, ForeignKey("vouchers.id", ondelete="CASCADE"), nullable=False)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    party_id = Column(Integer, ForeignKey("parties.id"), nullable=True)
    entry_type = Column(String(20), nullable=False)
    amount = Column(Float, default=0.0)
    narration = Column(Text, nullable=True)

    voucher = relationship("Voucher", back_populates="entries")
    account = relationship("Account", back_populates="entries")
    party = relationship("Party", back_populates="entries")


# ---------------------------------------------------------------------------
# Customer Custom Fields (original — do NOT change)
# ---------------------------------------------------------------------------
customer_custom_values = Table(
    "customer_custom_values",
    Base.metadata,
    Column("id", Integer, primary_key=True, index=True),
    Column("customer_id", Integer, ForeignKey("parties.id"), nullable=False),
    Column("field_id", Integer, ForeignKey("custom_fields.id"), nullable=False),
    Column("value", Text, nullable=True),
    UniqueConstraint("customer_id", "field_id", name="uq_customer_field"),
)


class CustomField(Base):
    __tablename__ = "custom_fields"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, index=True, nullable=False)
    label = Column(String(100), nullable=False)
    field_type = Column(String(20), nullable=False)
    required = Column(Boolean, default=False)
    enabled = Column(Boolean, default=True)
    order = Column(Integer, default=0)
    options = Column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<CustomField {self.name} ({self.field_type})>"


# ---------------------------------------------------------------------------
# Supplier Custom Fields (separate tables — do not affect customers)
# ---------------------------------------------------------------------------
class SupplierCustomField(Base):
    __tablename__ = "supplier_custom_fields"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, index=True, nullable=False)
    label = Column(String(100), nullable=False)
    field_type = Column(String(20), nullable=False)
    required = Column(Boolean, default=False)
    enabled = Column(Boolean, default=True)
    order = Column(Integer, default=0)
    options = Column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<SupplierCustomField {self.name} ({self.field_type})>"


supplier_custom_values = Table(
    "supplier_custom_values",
    Base.metadata,
    Column("id", Integer, primary_key=True, index=True),
    Column("supplier_id", Integer, ForeignKey("parties.id"), nullable=False),
    Column("field_id", Integer, ForeignKey("supplier_custom_fields.id"), nullable=False),
    Column("value", Text, nullable=True),
    UniqueConstraint("supplier_id", "field_id", name="uq_supplier_field"),
)


# ---------------------------------------------------------------------------
# Income Transactions — standalone income records (not just vouchers)
# ---------------------------------------------------------------------------
class IncomeTransaction(Base):
    __tablename__ = "income_transactions"

    id = Column(Integer, primary_key=True, index=True)
    transaction_number = Column(String(100), unique=True, index=True, nullable=False)
    date = Column(DateTime, default=datetime.utcnow, index=True)
    income_category = Column(String(255), nullable=False, default="General Income")
    party_id = Column(Integer, ForeignKey("parties.id"), nullable=True)   # optional customer
    amount = Column(Float, nullable=False)
    payment_method = Column(String(100), default="Cash")  # Cash, Bank Transfer, Card, Cheque, Other
    reference_no = Column(String(200), nullable=True)
    description = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    created_by = Column(String(255), default="System")
    created_at = Column(DateTime, default=datetime.utcnow)
    # Link to double-entry voucher
    voucher_id = Column(Integer, ForeignKey("vouchers.id"), nullable=True)
    is_customer_receipt = Column(Boolean, default=False)   # True = collecting receivable (NOT new income)
    is_voided = Column(Boolean, default=False)
    void_reason = Column(Text, nullable=True)
    voided_at = Column(DateTime, nullable=True)
    voided_by = Column(String(255), nullable=True)

    party = relationship("Party", foreign_keys=[party_id])
    voucher = relationship("Voucher", foreign_keys=[voucher_id])


# ---------------------------------------------------------------------------
# Payment Allocations — link payments to outstanding balances
# ---------------------------------------------------------------------------
class PaymentAllocation(Base):
    __tablename__ = "payment_allocations"

    id = Column(Integer, primary_key=True, index=True)
    payment_number = Column(String(100), unique=True, index=True, nullable=False)
    payment_date = Column(DateTime, default=datetime.utcnow, index=True)
    payment_type = Column(String(50), nullable=False)   # CustomerReceipt, SupplierPayment
    party_id = Column(Integer, ForeignKey("parties.id"), nullable=False)
    amount = Column(Float, nullable=False)
    payment_method = Column(String(100), default="Cash")
    reference_no = Column(String(200), nullable=True)
    notes = Column(Text, nullable=True)
    created_by = Column(String(255), default="System")
    created_at = Column(DateTime, default=datetime.utcnow)
    # Link to double-entry voucher
    voucher_id = Column(Integer, ForeignKey("vouchers.id"), nullable=True)
    is_voided = Column(Boolean, default=False)
    void_reason = Column(Text, nullable=True)
    voided_at = Column(DateTime, nullable=True)

    party = relationship("Party", foreign_keys=[party_id])
    voucher = relationship("Voucher", foreign_keys=[voucher_id])


# ---------------------------------------------------------------------------
# Gate Pass Management — Inward & Outward Farm Gate Passes
# ---------------------------------------------------------------------------
class GatePass(Base):
    __tablename__ = "gate_passes"

    id = Column(Integer, primary_key=True, index=True)
    pass_number = Column(String(100), unique=True, index=True, nullable=False)
    date = Column(DateTime, default=datetime.utcnow, index=True)
    pass_type = Column(String(50), default="Outward")   # Outward (Dispatch) / Inward (Receiving)
    party_name = Column(String(255), nullable=True)     # Customer / Supplier / Transporter
    vehicle_number = Column(String(100), nullable=True)
    driver_name = Column(String(100), nullable=True)
    driver_phone = Column(String(50), nullable=True)
    bilty_number = Column(String(100), nullable=True)
    reference_no = Column(String(100), nullable=True)
    items_json = Column(Text, nullable=True)            # JSON list of items
    remarks = Column(Text, nullable=True)
    total_amount = Column(Float, default=0.0)
    payment_type = Column(String(100), default="Debit (Customer Ledger / Receivable)")
    prepared_by = Column(String(255), default="Muhammad Haris")
    gate_incharge = Column(String(255), default="Security Office")
    authorized_by = Column(String(255), default="Farm General Manager")
    created_at = Column(DateTime, default=datetime.utcnow)

