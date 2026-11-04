from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from datetime import datetime

from backend.database import get_db
from backend.models import User
from backend.schemas import UserOut, EmployeeCreate, EmployeeUpdate, RolePermissionOut
from backend.auth import (
    get_current_user,
    require_admin,
    require_roles,
    get_password_hash,
    ROLE_PERMISSIONS
)

router = APIRouter(prefix="/api/v1/users", tags=["Employee Accounts & Permissions"])


@router.get("", response_model=List[UserOut])
@router.get("/", response_model=List[UserOut])
def list_employees(
    role: Optional[str] = Query(None, description="Filter by role"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    search: Optional[str] = Query(None, description="Search by name, email, or phone"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all staff and employee accounts with roles and active status.
    Requires authentication.
    """
    query = db.query(User)

    if role:
        query = query.filter(User.role.ilike(f"%{role.strip()}%"))

    if is_active is not None:
        query = query.filter(User.is_active == is_active)

    if search:
        s = f"%{search.strip()}%"
        query = query.filter(
            (User.full_name.ilike(s)) |
            (User.email.ilike(s)) |
            (User.phone.ilike(s))
        )

    return query.order_by(User.id.asc()).all()


@router.get("/roles", response_model=List[RolePermissionOut])
def get_roles_and_permissions(current_user: User = Depends(get_current_user)):
    """
    List all system roles and their assigned access permissions.
    """
    result = []
    for role_name, data in ROLE_PERMISSIONS.items():
        result.append(RolePermissionOut(
            role=role_name,
            description=data["description"],
            permissions=data["permissions"]
        ))
    return result


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_employee(
    emp_in: EmployeeCreate,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin)
):
    """
    Register a new staff/employee account with defined role and permissions.
    Requires Administrator privileges.
    """
    clean_email = emp_in.email.strip().lower()
    existing = db.query(User).filter(User.email == clean_email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"An account with email '{clean_email}' already exists."
        )

    # Validate role against canonical roles
    clean_role = emp_in.role.strip()
    valid_roles = list(ROLE_PERMISSIONS.keys())
    matched_role = next((r for r in valid_roles if r.lower() == clean_role.lower()), clean_role)

    new_user = User(
        email=clean_email,
        hashed_password=get_password_hash(emp_in.password.strip()),
        full_name=emp_in.full_name.strip(),
        role=matched_role,
        phone=emp_in.phone.strip() if emp_in.phone else None,
        address=emp_in.address.strip() if emp_in.address else None,
        company_name=emp_in.company_name or "Tri Agro Farms",
        is_active=emp_in.is_active,
        created_at=datetime.utcnow()
    )

    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return new_user
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create employee account: {str(e)}"
        )


@router.get("/{user_id}", response_model=UserOut)
def get_employee(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get detailed information of a specific staff member.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Employee account not found.")
    return user


@router.put("/{user_id}", response_model=UserOut)
def update_employee(
    user_id: int,
    emp_up: EmployeeUpdate,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin)
):
    """
    Update staff member role, active status, contact details, or reset password.
    Requires Administrator privileges.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Employee account not found.")

    if emp_up.full_name is not None and emp_up.full_name.strip():
        user.full_name = emp_up.full_name.strip()

    if emp_up.role is not None and emp_up.role.strip():
        user.role = emp_up.role.strip()

    if emp_up.phone is not None:
        user.phone = emp_up.phone.strip()

    if emp_up.address is not None:
        user.address = emp_up.address.strip()

    if emp_up.is_active is not None:
        # Prevent admin from deactivating themselves
        if user.id == admin_user.id and not emp_up.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot deactivate your own active Administrator account."
            )
        user.is_active = emp_up.is_active

    if emp_up.password and len(emp_up.password.strip()) >= 6:
        user.hashed_password = get_password_hash(emp_up.password.strip())

    try:
        db.commit()
        db.refresh(user)
        return user
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update employee account: {str(e)}"
        )


@router.delete("/{user_id}")
def delete_employee(
    user_id: int,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin)
):
    """
    Permanently delete an employee account.
    Requires Administrator privileges. Admins cannot delete their own account.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Employee account not found.")

    if user.id == admin_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own Administrator account."
        )

    try:
        user_name = user.full_name
        db.delete(user)
        db.commit()
        return {
            "success": True,
            "message": f"Employee account '{user_name}' successfully removed."
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete employee account: {str(e)}"
        )
