import uuid
from datetime import date, datetime, timezone
from typing import Optional, List

from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.task import Task, TaskComment, TaskHistory
from app.models.enums import (
    TaskType, TaskStatus, TaskPriority, TASK_TYPE_HIERARCHY, PRIORITY_WEIGHT,
)


def compute_period_bucket(start_date: Optional[date], due_date: Optional[date]) -> Optional[str]:
    if due_date is None:
        return None
    if start_date:
        delta = (due_date - start_date).days
    else:
        delta = (due_date - date.today()).days
    if delta <= 8:
        return "week"
    elif delta <= 32:
        return "month"
    elif delta <= 95:
        return "quarter"
    else:
        return "year"


def infer_child_type(parent_type: TaskType) -> TaskType:
    idx = TASK_TYPE_HIERARCHY.index(parent_type)
    if idx < len(TASK_TYPE_HIERARCHY) - 1:
        return TASK_TYPE_HIERARCHY[idx + 1]
    return TaskType.SUBTASK


def log_history(
    db: Session,
    task_id: uuid.UUID,
    event_type: str,
    actor_id: Optional[uuid.UUID] = None,
    payload: Optional[dict] = None,
) -> TaskHistory:
    entry = TaskHistory(
        id=uuid.uuid4(),
        task_id=task_id,
        actor_id=actor_id,
        event_type=event_type,
        payload=payload or {},
    )
    db.add(entry)
    return entry


def recompute_parent_progress(db: Session, task: Task):
    """Recompute progress of parent as average of children."""
    if task.parent_id is None:
        return
    parent = db.get(Task, task.parent_id)
    if parent is None:
        return
    children = db.query(Task).filter(Task.parent_id == parent.id).all()
    if children:
        avg = sum(c.progress for c in children) / len(children)
        parent.progress = int(avg)
        db.add(parent)
        # Recurse upward
        recompute_parent_progress(db, parent)


def get_parent_chain(db: Session, task: Task) -> List[dict]:
    """Walk from root to immediate parent."""
    chain = []
    current = task
    while current.parent_id is not None:
        current = db.get(Task, current.parent_id)
        if current is None:
            break
        chain.append({"id": current.id, "type": current.type, "title": current.title})
    chain.reverse()
    return chain


def compute_user_workload(db: Session, user_id: uuid.UUID) -> dict:
    open_statuses = [TaskStatus.NEW, TaskStatus.IN_PROGRESS, TaskStatus.REVIEW, TaskStatus.OVERDUE]
    tasks = db.query(Task).filter(
        Task.assignee_id == user_id,
        Task.status.in_(open_statuses),
    ).all()

    today = date.today()
    overdue_count = 0
    at_risk_count = 0
    weighted_load = 0.0

    for t in tasks:
        if t.due_date:
            days_left = (t.due_date - today).days
            if days_left < 0 or t.status == TaskStatus.OVERDUE:
                overdue_count += 1
            if days_left <= 3 and t.status != TaskStatus.DONE:
                at_risk_count += 1
            urgency = max(0.0, 1.0 - days_left / 14.0) + 0.3
        else:
            urgency = 0.3
        pw = PRIORITY_WEIGHT.get(t.priority, 2)
        weighted_load += pw * urgency

    from app.models.user import User
    user = db.get(User, user_id)
    cap = user.capacity_hours_per_week if user else 40
    capacity_util = (weighted_load / cap * 10.0) if cap > 0 else 0.0

    return {
        "open_tasks": len(tasks),
        "weighted_load": round(weighted_load, 2),
        "overdue_count": overdue_count,
        "at_risk_count": at_risk_count,
        "capacity_util": round(capacity_util * 100, 1),
    }


def build_tree(db: Session, root_id: Optional[uuid.UUID] = None, max_depth: int = 4, current_user=None) -> List[dict]:
    """Build task tree(s). If root_id given, single tree; else all GOAL roots."""
    from app.core.deps import apply_task_scope, user_can_access_task

    if root_id:
        root = db.get(Task, root_id)
        if root is None or (current_user and not user_can_access_task(db, current_user, root)):
            return []
        return [_tree_node(db, root, 0, max_depth, current_user)]
    else:
        query = db.query(Task)
        if current_user:
            query = apply_task_scope(query, current_user, db)
        roots = query.filter(
            Task.parent_id.is_(None),
            Task.type == TaskType.GOAL,
        ).all()
        return [_tree_node(db, r, 0, max_depth, current_user) for r in roots]


def _tree_node(db: Session, task: Task, depth: int, max_depth: int, current_user=None) -> dict:
    node = {
        "id": task.id,
        "type": task.type,
        "title": task.title,
        "status": task.status,
        "priority": task.priority,
        "progress": task.progress,
        "assignee_id": task.assignee_id,
        "assignee_name": task.assignee.full_name if task.assignee else None,
        "assigned_department_name": task.assigned_department.name if task.assigned_department else None,
        "due_date": task.due_date,
        "period_bucket": compute_period_bucket(task.start_date, task.due_date),
        "children": [],
    }
    if depth < max_depth:
        query = db.query(Task).filter(Task.parent_id == task.id)
        if current_user:
            from app.core.deps import apply_task_scope
            query = apply_task_scope(query, current_user, db)
        children = query.all()
        node["children"] = [_tree_node(db, c, depth + 1, max_depth, current_user) for c in children]
    return node
