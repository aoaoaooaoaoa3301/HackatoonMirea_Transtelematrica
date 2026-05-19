from datetime import date, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import func as sqlfunc

from app.models.task import Task
from app.models.department import Department
from app.models.user import User
from app.models.enums import TaskStatus, TaskPriority, TaskType
from app.services.task_service import compute_user_workload


def get_overview(db: Session) -> dict:
    today = date.today()
    tasks = db.query(Task).all()
    total = len(tasks)

    by_status = {}
    for s in TaskStatus:
        by_status[s.value] = 0
    by_priority = {}
    for p in TaskPriority:
        by_priority[p.value] = 0
    by_type = {}
    for t in TaskType:
        by_type[t.value] = 0

    overdue_count = 0
    at_risk_count = 0
    done_count = 0

    for t in tasks:
        by_status[t.status.value] = by_status.get(t.status.value, 0) + 1
        by_priority[t.priority.value] = by_priority.get(t.priority.value, 0) + 1
        by_type[t.type.value] = by_type.get(t.type.value, 0) + 1
        if t.status == TaskStatus.DONE:
            done_count += 1
        if t.status == TaskStatus.OVERDUE or (t.due_date and t.due_date < today and t.status != TaskStatus.DONE):
            overdue_count += 1
        if t.due_date and 0 < (t.due_date - today).days <= 3 and t.status != TaskStatus.DONE:
            at_risk_count += 1

    departments = db.query(Department).all()
    by_department = []
    for dept in departments:
        dept_tasks = [t for t in tasks if t.assigned_department_id == dept.id]
        dept_done = sum(1 for t in dept_tasks if t.status == TaskStatus.DONE)
        dept_overdue = sum(
            1 for t in dept_tasks
            if t.status == TaskStatus.OVERDUE or (t.due_date and t.due_date < today and t.status != TaskStatus.DONE)
        )
        dept_at_risk = sum(
            1 for t in dept_tasks
            if t.due_date and 0 < (t.due_date - today).days <= 3 and t.status != TaskStatus.DONE
        )
        by_department.append({
            "id": dept.id,
            "name": dept.name,
            "count": len(dept_tasks),
            "done": dept_done,
            "overdue": dept_overdue,
            "at_risk": dept_at_risk,
        })

    completion_rate = round(done_count / total * 100, 1) if total else 0.0

    return {
        "total": total,
        "by_status": by_status,
        "by_priority": by_priority,
        "by_type": by_type,
        "by_department": by_department,
        "overdue_count": overdue_count,
        "at_risk_count": at_risk_count,
        "completion_rate": completion_rate,
    }


def get_workload_list(db: Session) -> list:
    users = db.query(User).filter(User.active == True).all()
    result = []
    for u in users:
        wl = compute_user_workload(db, u.id)
        result.append({
            "user_id": u.id,
            "full_name": u.full_name,
            "department_name": u.department.name if u.department else None,
            **wl,
        })
    return result


def get_completion_buckets(db: Session, period: str = "month") -> list:
    today = date.today()
    tasks = db.query(Task).all()

    def bucket_key(d: date) -> str:
        if period == "week":
            iso = d.isocalendar()
            return f"{iso[0]}-W{iso[1]:02d}"
        elif period == "month":
            return f"{d.year}-{d.month:02d}"
        elif period == "quarter":
            q = (d.month - 1) // 3 + 1
            return f"{d.year}-Q{q}"
        else:
            return str(d.year)

    buckets: dict = {}
    for t in tasks:
        key_date = t.due_date or t.start_date or t.created_at.date() if t.created_at else today
        if key_date is None:
            key_date = today
        bk = bucket_key(key_date)
        if bk not in buckets:
            buckets[bk] = {"bucket_key": bk, "total": 0, "done": 0}
        buckets[bk]["total"] += 1
        if t.status == TaskStatus.DONE:
            buckets[bk]["done"] += 1

    result = []
    for bk in sorted(buckets.keys()):
        b = buckets[bk]
        b["completion_pct"] = round(b["done"] / b["total"] * 100, 1) if b["total"] else 0.0
        result.append(b)

    return result


def get_delegation_flow(db: Session) -> dict:
    """Build sankey nodes + links: who created tasks for whom."""
    tasks = db.query(Task).all()
    users = db.query(User).filter(User.active == True).all()
    departments = db.query(Department).all()

    user_map = {u.id: u for u in users}
    dept_map = {d.id: d for d in departments}

    nodes = []
    node_ids = set()

    for d in departments:
        nid = f"dept-{d.id}"
        if nid not in node_ids:
            nodes.append({"id": nid, "name": d.name, "type": "department"})
            node_ids.add(nid)

    for u in users:
        nid = f"user-{u.id}"
        if nid not in node_ids:
            nodes.append({"id": nid, "name": u.full_name, "type": "user"})
            node_ids.add(nid)

    link_counts: dict = {}
    for t in tasks:
        if t.created_by_id and t.assignee_id and t.created_by_id != t.assignee_id:
            source = f"user-{t.created_by_id}"
            target = f"user-{t.assignee_id}"
            key = (source, target)
            link_counts[key] = link_counts.get(key, 0) + 1

    links = [
        {"source": s, "target": tg, "value": c}
        for (s, tg), c in link_counts.items()
    ]

    return {"nodes": nodes, "links": links}
