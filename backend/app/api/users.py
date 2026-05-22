import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.core.deps import get_db, get_current_user, require_role, scoped_user_query
from app.core.security import hash_password
from app.models.user import User
from app.models.enums import UserRole
from app.schemas.user import UserCreate, UserUpdate, UserOut, WorkloadOut
from app.services.task_service import compute_user_workload

router = APIRouter(prefix="/users", tags=["users"])


def _user_out(u: User) -> dict:
    return {
        "id": u.id,
        "email": u.email,
        "full_name": u.full_name,
        "role": u.role,
        "department_id": u.department_id,
        "department_name": u.department.name if u.department else None,
        "skills": u.skills or [],
        "seniority": u.seniority,
        "capacity_hours_per_week": u.capacity_hours_per_week,
        "active": u.active,
        "created_at": u.created_at,
        "updated_at": u.updated_at,
    }


@router.get("")
def list_users(
    department_id: Optional[uuid.UUID] = None,
    role: Optional[UserRole] = None,
    q: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Scope the directory by role: ADMIN sees everyone, LEAD their dept
    # subtree, EMPLOYEE their own department (+ themselves). Prevents the
    # whole org chart leaking to every user.
    query = scoped_user_query(db.query(User), current_user, db)
    if department_id:
        query = query.filter(User.department_id == department_id)
    if role:
        query = query.filter(User.role == role)
    if q:
        pattern = f"%{q}%"
        query = query.filter(or_(User.full_name.ilike(pattern), User.email.ilike(pattern)))
    users = query.all()
    return [_user_out(u) for u in users]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_user(
    body: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        id=uuid.uuid4(),
        email=body.email,
        full_name=body.full_name,
        password_hash=hash_password(body.password),
        role=body.role,
        department_id=body.department_id,
        skills=body.skills,
        seniority=body.seniority,
        capacity_hours_per_week=body.capacity_hours_per_week,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _user_out(user)


@router.get("/{user_id}")
def get_user(user_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    out = _user_out(user)
    out["workload"] = compute_user_workload(db, user.id)
    return out


@router.patch("/{user_id}")
def update_user(
    user_id: uuid.UUID,
    body: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Permission check
    if current_user.role != UserRole.ADMIN and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    # EMPLOYEE self-edit: limited fields
    allowed_self = {"full_name", "skills", "seniority", "password"}
    update_data = body.model_dump(exclude_unset=True)

    if current_user.role != UserRole.ADMIN and current_user.id == user_id:
        for key in list(update_data.keys()):
            if key not in allowed_self:
                del update_data[key]

    for key, val in update_data.items():
        if key == "password":
            user.password_hash = hash_password(val)
        else:
            setattr(user, key, val)

    db.commit()
    db.refresh(user)
    return _user_out(user)


@router.get("/{user_id}/workload")
def get_workload(user_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return compute_user_workload(db, user_id)
