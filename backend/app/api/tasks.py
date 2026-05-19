import uuid
from typing import Optional, List
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.core.deps import get_db, get_current_user, require_task_access
from app.models.task import Task, TaskComment
from app.models.user import User
from app.models.enums import TaskType, TaskPriority, TaskStatus, UserRole
from app.schemas.task import TaskCreate, TaskUpdate, CommentCreate, TaskOut, TaskDetailOut
from app.services.task_service import (
    compute_period_bucket, infer_child_type, log_history,
    recompute_parent_progress, get_parent_chain, build_tree,
)

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _task_out(t: Task) -> dict:
    children_count = len(t.children) if t.children else 0
    return {
        "id": t.id,
        "type": t.type,
        "title": t.title,
        "description": t.description,
        "parent_id": t.parent_id,
        "start_date": t.start_date,
        "due_date": t.due_date,
        "priority": t.priority,
        "status": t.status,
        "progress": t.progress,
        "assigned_department_id": t.assigned_department_id,
        "assigned_department_name": t.assigned_department.name if t.assigned_department else None,
        "assignee_id": t.assignee_id,
        "assignee_name": t.assignee.full_name if t.assignee else None,
        "created_by_id": t.created_by_id,
        "created_by_name": t.created_by.full_name if t.created_by else None,
        "period_bucket": compute_period_bucket(t.start_date, t.due_date),
        "children_count": children_count,
        "created_at": t.created_at,
        "updated_at": t.updated_at,
    }


@router.get("/tree")
def get_tree(
    root_id: Optional[uuid.UUID] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return build_tree(db, root_id)


@router.get("")
def list_tasks(
    type: Optional[TaskType] = None,
    department_id: Optional[uuid.UUID] = None,
    assignee_id: Optional[uuid.UUID] = None,
    created_by_id: Optional[uuid.UUID] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    priority_filter: Optional[str] = Query(None, alias="priority"),
    parent_id: Optional[str] = None,
    q: Optional[str] = None,
    due_before: Optional[date] = None,
    due_after: Optional[date] = None,
    limit: int = Query(200, le=1000),
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Task)

    if type:
        query = query.filter(Task.type == type)
    if department_id:
        query = query.filter(Task.assigned_department_id == department_id)
    if assignee_id:
        query = query.filter(Task.assignee_id == assignee_id)
    if created_by_id:
        query = query.filter(Task.created_by_id == created_by_id)
    if status_filter:
        statuses = [s.strip() for s in status_filter.split(",") if s.strip()]
        query = query.filter(Task.status.in_(statuses))
    if priority_filter:
        priorities = [p.strip() for p in priority_filter.split(",") if p.strip()]
        query = query.filter(Task.priority.in_(priorities))
    if parent_id is not None:
        if parent_id == "null":
            query = query.filter(Task.parent_id.is_(None))
        else:
            query = query.filter(Task.parent_id == uuid.UUID(parent_id))
    if q:
        pattern = f"%{q}%"
        query = query.filter(or_(Task.title.ilike(pattern), Task.description.ilike(pattern)))
    if due_before:
        query = query.filter(Task.due_date <= due_before)
    if due_after:
        query = query.filter(Task.due_date >= due_after)

    query = query.order_by(Task.created_at.desc())
    tasks = query.offset(offset).limit(limit).all()
    return [_task_out(t) for t in tasks]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_task(
    body: TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task_type = body.type or TaskType.TASK
    if body.parent_id:
        parent = db.get(Task, body.parent_id)
        if not parent:
            raise HTTPException(status_code=400, detail="Parent task not found")
        task_type = infer_child_type(parent.type)

    # Auto-set department from assignee if not provided
    dept_id = body.assigned_department_id
    if not dept_id and body.assignee_id:
        assignee = db.get(User, body.assignee_id)
        if assignee and assignee.department_id:
            dept_id = assignee.department_id

    task = Task(
        id=uuid.uuid4(),
        type=task_type,
        title=body.title,
        description=body.description,
        parent_id=body.parent_id,
        start_date=body.start_date,
        due_date=body.due_date,
        priority=body.priority,
        status=body.status,
        progress=body.progress,
        assigned_department_id=dept_id,
        assignee_id=body.assignee_id,
        created_by_id=current_user.id,
    )
    db.add(task)
    db.flush()

    log_history(db, task.id, "created", current_user.id, {"title": task.title, "type": task.type.value})
    if task.assignee_id and task.assignee_id != current_user.id:
        assignee = db.get(User, task.assignee_id)
        log_history(db, task.id, "delegated", current_user.id, {
            "assignee_id": str(task.assignee_id),
            "assignee_name": assignee.full_name if assignee else None,
        })

    db.commit()
    db.refresh(task)
    return _task_out(task)


@router.get("/{task_id}")
def get_task(
    task_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    out = _task_out(task)
    out["children"] = [_task_out(c) for c in (task.children or [])]
    out["parent_chain"] = get_parent_chain(db, task)
    out["comments"] = [
        {
            "id": c.id,
            "task_id": c.task_id,
            "author_id": c.author_id,
            "author_name": c.author.full_name if c.author else None,
            "body": c.body,
            "created_at": c.created_at,
        }
        for c in (task.comments or [])[:50]
    ]
    out["history"] = [
        {
            "id": h.id,
            "task_id": h.task_id,
            "actor_id": h.actor_id,
            "actor_name": h.actor.full_name if h.actor else None,
            "event_type": h.event_type,
            "payload": h.payload,
            "at": h.at,
        }
        for h in (task.history or [])[:50]
    ]
    return out


@router.patch("/{task_id}")
def update_task(
    task_id: uuid.UUID,
    body: TaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # RBAC: EMPLOYEE can only update status/progress on own tasks
    if current_user.role == UserRole.EMPLOYEE:
        if task.assignee_id != current_user.id and task.assigned_department_id != current_user.department_id:
            raise HTTPException(status_code=403, detail="Forbidden")
        allowed = {"status", "progress"}
        update_data = body.model_dump(exclude_unset=True)
        for key in list(update_data.keys()):
            if key not in allowed:
                del update_data[key]
    elif current_user.role == UserRole.LEAD:
        # Check dept access
        from app.core.deps import _get_subdepartment_ids
        if current_user.department_id:
            dept_ids = _get_subdepartment_ids(db, current_user.department_id)
            has_access = (
                task.assigned_department_id in dept_ids
                or task.assignee_id == current_user.id
                or task.created_by_id == current_user.id
            )
        else:
            has_access = task.assignee_id == current_user.id or task.created_by_id == current_user.id
        if not has_access:
            raise HTTPException(status_code=403, detail="Forbidden")
        update_data = body.model_dump(exclude_unset=True)
    else:
        update_data = body.model_dump(exclude_unset=True)

    old_status = task.status
    old_assignee = task.assignee_id
    old_progress = task.progress

    for key, val in update_data.items():
        setattr(task, key, val)

    # Status → DONE ⇒ progress = 100
    if task.status == TaskStatus.DONE and old_status != TaskStatus.DONE:
        task.progress = 100

    # Log changes
    if "status" in update_data and update_data["status"] != old_status:
        log_history(db, task.id, "status_changed", current_user.id, {
            "old": old_status.value if old_status else None,
            "new": task.status.value,
        })

    if "assignee_id" in update_data and update_data.get("assignee_id") != old_assignee:
        new_assignee = db.get(User, task.assignee_id) if task.assignee_id else None
        log_history(db, task.id, "assignee_changed", current_user.id, {
            "old_assignee_id": str(old_assignee) if old_assignee else None,
            "new_assignee_id": str(task.assignee_id) if task.assignee_id else None,
            "new_assignee_name": new_assignee.full_name if new_assignee else None,
        })

    if "progress" in update_data and update_data["progress"] != old_progress:
        log_history(db, task.id, "progress_updated", current_user.id, {
            "old": old_progress,
            "new": task.progress,
        })

    db.commit()
    db.refresh(task)

    # Recompute parent progress
    recompute_parent_progress(db, task)
    db.commit()

    return _task_out(task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if current_user.role != UserRole.ADMIN and task.created_by_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    db.delete(task)
    db.commit()


@router.post("/{task_id}/comments", status_code=status.HTTP_201_CREATED)
def add_comment(
    task_id: uuid.UUID,
    body: CommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    comment = TaskComment(
        id=uuid.uuid4(),
        task_id=task_id,
        author_id=current_user.id,
        body=body.body,
    )
    db.add(comment)
    log_history(db, task_id, "comment_added", current_user.id, {"body": body.body[:200]})
    db.commit()
    db.refresh(comment)

    return {
        "id": comment.id,
        "task_id": comment.task_id,
        "author_id": comment.author_id,
        "author_name": current_user.full_name,
        "body": comment.body,
        "created_at": comment.created_at,
    }
