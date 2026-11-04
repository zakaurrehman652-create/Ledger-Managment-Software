from sqlalchemy.orm import Session
from backend.database import SessionLocal, Base, engine
from backend.models import User, Account
from backend.auth import get_password_hash

def seed_database():
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()

    try:
        # Only seed the admin user if no user exists in database
        admin = db.query(User).first()
        if not admin:
            admin = User(
                email="admin123@gmail.com",
                hashed_password=get_password_hash("admin123"),
                full_name="Muhammad Saad",
                role="Lead Financial Controller",
                phone="+92300000000",
                address="al hafeez cgarden",
                company_name="Tri Agro Farms",
                is_active=True
            )
            db.add(admin)
            db.commit()

        # Seed core Chart of Accounts if empty
        if db.query(Account).count() == 0:
            default_accounts = [
                Account(code="1010", name="Cash in Hand", type="Asset", description="Physical cash in register / farm vault", balance=0.0, is_active=True),
                Account(code="1020", name="Bank Account - HBL", type="Asset", description="Habib Bank Ltd Primary Current Account", balance=0.0, is_active=True),
                Account(code="1030", name="Accounts Receivable", type="Asset", description="Amounts due from flower customers", balance=0.0, is_active=True),
                Account(code="2010", name="Accounts Payable", type="Liability", description="Amounts due to suppliers and vendors", balance=0.0, is_active=True),
                Account(code="3010", name="Owner Equity & Capital", type="Equity", description="Proprietor equity and initial capital", balance=0.0, is_active=True),
                Account(code="4010", name="Flower & Crop Sales Revenue", type="Revenue", description="Revenue from flower cut dispatch and crops", balance=0.0, is_active=True),
                Account(code="5010", name="Farm Operational Expenses", type="Expense", description="Daily farm operational expenditures", balance=0.0, is_active=True),
                Account(code="5020", name="Fertilizer & Seed Expense", type="Expense", description="Cost of fertilizers, seeds, and agrochemicals", balance=0.0, is_active=True),
                Account(code="5030", name="Labor & Wages Expense", type="Expense", description="Daily wages and labor charges", balance=0.0, is_active=True),
            ]
            db.add_all(default_accounts)
            db.commit()

    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
    print("Database seeding completed.")
