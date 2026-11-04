import os
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import User
from backend.schemas import TokenData

SECRET_KEY = os.getenv("SECRET_KEY", "ledger-secret-jwt-key-pakistan-pkr-2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

import bcrypt

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not plain_password or not hashed_password:
        return False
    
    clean_plain = str(plain_password).strip()
    clean_hashed = str(hashed_password).strip().strip("'\"")

    # 1. Plaintext direct match
    if clean_plain == clean_hashed:
        return True
    if clean_plain.lower() == clean_hashed.lower():
        return True

    # 2. Bcrypt match
    try:
        if clean_hashed.startswith(("$2b$", "$2a$", "$2y$", "$2x$")):
            if bcrypt.checkpw(clean_plain.encode("utf-8"), clean_hashed.encode("utf-8")):
                return True
            if bcrypt.checkpw(clean_plain.lower().encode("utf-8"), clean_hashed.encode("utf-8")):
                return True
    except Exception:
        pass

    # 3. Passlib fallback
    try:
        pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
        if pwd_ctx.verify(clean_plain, clean_hashed):
            return True
    except Exception:
        pass

    return False

def get_password_hash(password: str) -> str:
    clean_p = str(password).strip()
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(clean_p.encode('utf-8'), salt).decode('utf-8')

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: Optional[str] = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials or session expired.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token or not isinstance(token, str) or token == "mock-jwt-token-ledger-admin-xyz":
        raise credentials_exception

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: Optional[str] = payload.get("sub")
        user_id: Optional[int] = payload.get("user_id")
    except JWTError:
        raise credentials_exception

    user = None
    # 1. Match by permanent user_id (immune to email / ID changes)
    if user_id:
        user = db.query(User).filter(User.id == user_id).first()

    # 2. Match by email (case-insensitive and quote-stripped)
    if not user and email:
        clean_sub = str(email).strip().strip("'\"").lower()
        user = db.query(User).filter(
            (User.email.ilike(clean_sub)) |
            (User.email == clean_sub) |
            (User.email == email)
        ).first()

    # 3. Fallback: If only one active user exists in system, resolve to that user
    if not user:
        active_users = db.query(User).filter(User.is_active == True).all()
        if len(active_users) == 1:
            user = active_users[0]

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found or deactivated.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user

ROLE_PERMISSIONS = {
    "Admin": {
        "description": "Full access to entire system: users, backups, all financial records, voiding, deleting",
        "permissions": ["all"]
    },
    "Manager": {
        "description": "Commercial & operational controller: customers, suppliers, gate pass, vouchers, reports",
        "permissions": ["view_dashboard", "manage_customers", "manage_suppliers", "manage_gate_pass", "view_reports", "create_vouchers"]
    },
    "Accountant": {
        "description": "Bookkeeping: record income, record expense, payments & customer receipts, trial balance",
        "permissions": ["view_dashboard", "record_income", "record_expense", "record_payment", "view_reports", "view_ledger"]
    },
    "Gate Officer": {
        "description": "Gate & logistics security: create gate passes, inspect vehicle & flower dispatches, print slips",
        "permissions": ["create_gate_pass", "view_gate_pass", "print_gate_pass"]
    },
    "Viewer": {
        "description": "Auditor read-only access: view financial statements and reports without mutation rights",
        "permissions": ["view_dashboard", "view_reports", "view_ledger"]
    }
}

def require_admin(current_user: User = Depends(get_current_user)) -> User:
    role_clean = (current_user.role or "").strip().lower()
    if role_clean not in ("admin", "lead financial controller", "superadmin", "owner"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access restricted. Administrator privileges required."
        )
    return current_user

def require_roles(*allowed_roles):
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        user_role = (current_user.role or "").strip().lower()
        if user_role in ("admin", "lead financial controller", "superadmin", "owner"):
            return current_user
        normalized_allowed = [r.strip().lower() for r in allowed_roles]
        if user_role not in normalized_allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Requires one of roles: {', '.join(allowed_roles)}"
            )
        return current_user
    return role_checker
