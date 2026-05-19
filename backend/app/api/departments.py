import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user, require_role
from app.models.department import Department
from app.models.user import User
from app.models.enums import UserRole
from app.schemas.department import DepartmentCreate, DepartmentUpdate, DepartmentOut, DepartmentDetailOut

router = APIRouter(prefix="/departments", tags=["departments"])


def _dept_out(d: Department) -> dict:
    return {
        "id": d.id,
        "name": d.name,
        "parent_id": d.parent_id,
        "head_user_id": d.head_user_id,
        "head_user_name": d.head_user.full_name if d.head_user else None,
        "created_at": d.created_at,
        "updated_at": d.updated_at,
    }


@router.get("")
def list_departments(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    depts = db.query(Department).all()
    return [_dept_out(d) for d in depts]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_department(
    body: DepartmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    if db.query(Department).filter(Department.name == body.name).first():
        raise HTTPException(status_code=400, detail="Department name already exists")
    dept = Department(id=uuid.uuid4(), name=body.name, parent_id=body.parent_id, head_user_id=body.head_user_id)
    db.add(dept)
    db.commit()
    db.refresh(dept)
    return _dept_out(dept)


@router.get("/{dept_id}")
def get_department(dept_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    dept = db.get(Department, dept_id)
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")
    out = _dept_out(dept)
    out["members"] = [
        {
            "id": m.id,
            "email": m.email,
            "full_name": m.full_name,
            "role": m.role,
            "seniority": m.seniority,
            "skills": m.skills or [],
        }
        for m in (dept.members or [])
    ]
    out["children"] = [_dept_out(c) for c in (dept.children or [])]
    return out


@router.patch("/{dept_id}")
def update_department(
    dept_id: uuid.UUID,
    body: DepartmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dept = db.get(Department, dept_id)
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")

    # Permission: ADMIN or LEAD of this dept
    if current_user.role == UserRole.ADMIN:
        pass
    elif current_user.role == UserRole.LEAD and dept.head_user_id == current_user.id:
        pass
    else:
        raise HTTPException(status_code=403, detail="Forbidden")

    update_data = body.model_dump(exclude_unset=True)
    for key, val in update_data.items():
        setattr(dept, key, val)
    db.commit()
    db.refresh(dept)
    return _dept_out(dept)


@router.delete("/{dept_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_department(
    dept_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    dept = db.get(Department, dept_id)
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")
    db.delete(dept)
    db.commit()
