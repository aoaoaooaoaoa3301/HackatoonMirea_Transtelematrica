from typing import Generator, Callable, List
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.core.db import SessionLocal
from app.core.security import decode_access_token
from app.models.user import User
from app.models.task import Task
from app.models.enums import UserRole

bearer_scheme = HTTPBearer(auto_error=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    db: Session = Depends(get_db),
    cred: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> User:
    if cred is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    user_id = decode_access_token(cred.credentials)
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = db.get(User, UUID(user_id))
    if user is None or not user.active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    return user


def require_role(*roles: UserRole) -> Callable:
    def checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return current_user
    return checker


def _get_subdepartment_ids(db: Session, dept_id: UUID) -> List[UUID]:
    """Get all descendant department IDs (BFS)."""
    from app.models.department import Department
    result = [dept_id]
    queue = [dept_id]
    while queue:
        parent = queue.pop(0)
        children = db.query(Department.id).filter(Department.parent_id == parent).all()
        for (cid,) in children:
            result.append(cid)
            queue.append(cid)
    return result


def apply_task_scope(query, current_user: User, db: Session):
    """Limit a Task query to rows visible for the current user."""
    if current_user.role == UserRole.ADMIN:
        return query

    own_task_filter = or_(
        Task.assignee_id == current_user.id,
        Task.created_by_id == current_user.id,
    )

    if current_user.role == UserRole.LEAD:
        if current_user.department_id:
            dept_ids = _get_subdepartment_ids(db, current_user.department_id)
            return query.filter(or_(Task.assigned_department_id.in_(dept_ids), own_task_filter))
        return query.filter(own_task_filter)

    if current_user.department_id:
        return query.filter(or_(Task.assigned_department_id == current_user.department_id, own_task_filter))

    return query.filter(own_task_filter)


def visible_department_ids(db: Session, current_user: User):
    """Department IDs the user may see. None == all (ADMIN).

    LEAD → their department subtree; EMPLOYEE → only their own department;
    a user without a department → empty set.
    """
    if current_user.role == UserRole.ADMIN:
        return None
    if current_user.department_id is None:
        return set()
    if current_user.role == UserRole.LEAD:
        return set(_get_subdepartment_ids(db, current_user.department_id))
    return {current_user.department_id}


def scoped_user_query(query, current_user: User, db: Session):
    """Limit a User query to users the current user may see.

    Mirrors task scoping: ADMIN → everyone, LEAD → their dept subtree,
    EMPLOYEE → their own department; always includes the user themselves.
    """
    if current_user.role == UserRole.ADMIN:
        return query
    dept_ids = visible_department_ids(db, current_user)
    if not dept_ids:
        return query.filter(User.id == current_user.id)
    return query.filter(or_(User.department_id.in_(dept_ids), User.id == current_user.id))


def can_delete_task(db: Session, current_user: User, task: Task) -> bool:
    """Delete matrix: ADMIN any task; LEAD tasks within their department
    subtree; EMPLOYEE none. (Creator-based deletion was wrong — it let
    employees delete and blocked leads on their own department's tasks.)"""
    if current_user.role == UserRole.ADMIN:
        return True
    if current_user.role == UserRole.LEAD:
        dept_ids = visible_department_ids(db, current_user)
        if dept_ids and task.assigned_department_id in dept_ids:
            return True
        return task.created_by_id == current_user.id
    return False


def user_can_access_task(db: Session, current_user: User, task: Task) -> bool:
    if task is None:
        return False
    if current_user.role == UserRole.ADMIN:
        return True
    return apply_task_scope(db.query(Task).filter(Task.id == task.id), current_user, db).first() is not None


def require_task_access(task_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> Task:
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    if user_can_access_task(db, current_user, task):
        return task
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this task")
