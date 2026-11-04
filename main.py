import os
import logging
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from backend.database import engine, Base, run_migrations
from backend.seed import seed_database
from backend.routes import (
    auth_routes,
    dashboard_routes,
    account_routes,
    party_routes,
    voucher_routes,
    report_routes,
    sync_routes,
    expense_routes,
    supplier_routes,
    customer_routes,
    custom_field_routes,
    income_routes,
    payment_routes,
    ledger_routes,
    gate_pass_routes,
    backup_routes,
    user_routes,
)

logger = logging.getLogger("ledger.api")

app = FastAPI(
    title="Tri Agro Farm - Ledger Management System API",
    description="Enterprise REST backend with PostgreSQL/SQLAlchemy, Double-Entry Accounting (PKR), Offline Sync, and Robust Data Safety.",
    version="2.1.0"
)

# ---------------------------------------------------------------------------
# Security Headers Middleware
# ---------------------------------------------------------------------------
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

app.add_middleware(SecurityHeadersMiddleware)

# ---------------------------------------------------------------------------
# CORS Configuration
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Global Safe Exception Handling (Prevents SQL/Internal Trace Leaks)
# ---------------------------------------------------------------------------
@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    logger.error(f"Database Integrity Error at {request.url.path}: {exc}")
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "detail": "Data integrity conflict. A record with identical unique constraints may already exist.",
            "path": request.url.path
        }
    )

@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError):
    logger.error(f"Database Error at {request.url.path}: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "A database operation error occurred. The transaction was safely rolled back.",
            "path": request.url.path
        }
    )

# ---------------------------------------------------------------------------
# Route Registration
# ---------------------------------------------------------------------------
app.include_router(auth_routes.router)
app.include_router(dashboard_routes.router)
app.include_router(account_routes.router)
app.include_router(party_routes.router)
app.include_router(voucher_routes.router)
app.include_router(report_routes.router)
app.include_router(sync_routes.router)
app.include_router(expense_routes.router)
app.include_router(supplier_routes.router)
app.include_router(customer_routes.router)
app.include_router(custom_field_routes.router)
app.include_router(income_routes.router)
app.include_router(payment_routes.router)
app.include_router(ledger_routes.router)
app.include_router(gate_pass_routes.router)
app.include_router(backup_routes.router)
app.include_router(user_routes.router)

@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    run_migrations()
    seed_database()

@app.get("/api/v1/health")
def health_check():
    return {
        "status": "healthy",
        "system": "Ledger Management System",
        "currency": "PKR",
        "engine": str(engine.url)
    }

# Mount frontend directory for static serving
current_dir = os.path.dirname(os.path.abspath(__file__))
frontend_dir = os.path.join(current_dir, "frontend")
app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    import socket

    local_ip = "127.0.0.1"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        pass

    print("\n" + "=" * 65)
    print("  TRI AGRO FARMS - LEDGER MANAGEMENT SYSTEM (PKR) - RUNNING")
    print("=" * 65)
    print("  Localhost Links:")
    print("    [1] Home / Login: http://localhost:8000")
    print("    [2] Dashboard:    http://localhost:8000/dashboard.html")
    print("    [3] API Docs:     http://localhost:8000/docs")
    if local_ip != "127.0.0.1":
        print("\n  Local Network (Farm Wi-Fi) Sharing:")
        print(f"    [1] Home / Login: http://{local_ip}:8000")
        print(f"    [2] Dashboard:    http://{local_ip}:8000/dashboard.html")
    print("=" * 65 + "\n")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)

