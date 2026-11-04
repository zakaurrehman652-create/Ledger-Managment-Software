import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

logger = logging.getLogger("ledger.database")
logging.basicConfig(level=logging.INFO)

DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)

# Support explicit sqlite:/// path in DATABASE_URL (e.g. for alternate drive)
_CUSTOM_SQLITE = DATABASE_URL and DATABASE_URL.startswith("sqlite:///")
SQLITE_URL = DATABASE_URL if _CUSTOM_SQLITE else "sqlite:///./ledger.db"
if _CUSTOM_SQLITE:
    DATABASE_URL = None  # treat as local sqlite, skip PostgreSQL path


def get_engine_and_session():
    if DATABASE_URL:
        try:
            engine = create_engine(DATABASE_URL, pool_pre_ping=True)
            with engine.connect():
                logger.info("Connected successfully to PostgreSQL database.")
            return engine, sessionmaker(autocommit=False, autoflush=False, bind=engine)
        except Exception as e:
            logger.warning(
                f"Could not connect to PostgreSQL ({e}). "
                "Falling back to local SQLite engine (ledger.db) for development."
            )

    engine = create_engine(SQLITE_URL, connect_args={"check_same_thread": False})
    # Database Security & Concurrency: Enable WAL mode and foreign keys for SQLite
    from sqlalchemy import event
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=DELETE")
        cursor.close()
    return engine, sessionmaker(autocommit=False, autoflush=False, bind=engine)

engine, SessionLocal = get_engine_and_session()
Base = declarative_base()

# Import custom migration helper
from .migrations import run_custom_migrations


def run_migrations():
    """Ensure database schema has updated columns for existing SQLite tables.
    Only creates a backup if missing columns need to be added.
    """
    # 1. Run custom migrations (creates custom_fields and association table)
    try:
        run_custom_migrations()
    except Exception as e:
        logger.warning(f"Custom migrations warning: {e}")

    # 2. Existing SQLite schema adjustments
    try:
        with engine.begin() as conn:
            if "sqlite" in str(engine.url):
                res = conn.exec_driver_sql("PRAGMA table_info(users);").fetchall()
                existing_cols = [r[1] for r in res] if res else []
                user_missing = [c for c in ["phone", "address", "company_name"] if c not in existing_cols]

                res2 = conn.exec_driver_sql("PRAGMA table_info(parties);").fetchall()
                party_cols = [r[1] for r in res2] if res2 else []
                party_missing = [c for c in ["opening_balance", "balance_type", "notes"] if c not in party_cols]

                res3 = conn.exec_driver_sql("PRAGMA table_info(gate_passes);").fetchall()
                gp_cols = [r[1] for r in res3] if res3 else []
                gp_missing = [c for c in ["total_amount", "payment_type"] if c not in gp_cols]

                # Only create pre-migration backup if table schema actually needs altering
                if user_missing or party_missing or gp_missing:
                    try:
                        from backend.utils.backup import create_database_backup
                        create_database_backup(tag="pre-migration")
                    except Exception as e:
                        logger.warning(f"Pre-migration backup warning: {e}")

                if "phone" not in existing_cols:
                    conn.exec_driver_sql(
                        "ALTER TABLE users ADD COLUMN phone VARCHAR(100) DEFAULT '+92 300 1234567';"
                    )
                if "address" not in existing_cols:
                    conn.exec_driver_sql(
                        "ALTER TABLE users ADD COLUMN address TEXT DEFAULT 'Plot 42, Commercial Avenue, I.I. Chundrigar Road, Karachi';"
                    )
                if "company_name" not in existing_cols:
                    conn.exec_driver_sql(
                        "ALTER TABLE users ADD COLUMN company_name VARCHAR(255) DEFAULT 'Tri Agro Farm';"
                    )
                if "opening_balance" not in party_cols:
                    conn.exec_driver_sql("ALTER TABLE parties ADD COLUMN opening_balance REAL DEFAULT 0.0;")
                if "balance_type" not in party_cols:
                    conn.exec_driver_sql("ALTER TABLE parties ADD COLUMN balance_type TEXT DEFAULT 'Payable';")
                if "notes" not in party_cols:
                    conn.exec_driver_sql("ALTER TABLE parties ADD COLUMN notes TEXT;")
                if "total_amount" not in gp_cols:
                    conn.exec_driver_sql("ALTER TABLE gate_passes ADD COLUMN total_amount REAL DEFAULT 0.0;")
                if "payment_type" not in gp_cols:
                    conn.exec_driver_sql("ALTER TABLE gate_passes ADD COLUMN payment_type TEXT DEFAULT 'Debit (Customer Ledger / Receivable)';")
    except Exception as e:
        logger.warning(f"Schema migration warning: {e}")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
