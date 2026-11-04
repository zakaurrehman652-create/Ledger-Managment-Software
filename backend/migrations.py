from .database import engine, Base
from . import models

def run_custom_migrations():
    """Create new tables for custom fields and customer custom values.
    This is safe to run on every startup because SQLAlchemy's create_all only
    creates missing tables/columns; it never drops or modifies existing ones.
    """
    # Ensure the Base metadata includes the CustomField model and the
    # association table `customer_custom_values`. They are imported via the
    # `models` module above.
    Base.metadata.create_all(bind=engine)
