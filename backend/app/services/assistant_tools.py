import re
import uuid
from datetime import date, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.deps import apply_task_scope, user_can_access_task
from app.models.department import Department
from app.models.enums import PRIORITY_WEIGHT, TaskPriority, TaskStatus
from app.models.task import Task, TaskComment
from app.models.user import User
from app.services import ai_service
from app.services.task_service import compute_user_workload, log_history, recompute_parent_progress

ORDINALS = {
    "первая": 1,
    "первую": 1,
    "первый": 1,
    "1": 1,
    "вторая": 2,
    "вторую": 2,
    "второй": 2,
    "2": 2,
    "третья": 3,
    "третью": 3,
    "третий": 3,
    "3": 3,
    "четвертая": 4,
    "четвертую": 4,
    "четвертый": 4,
    "4": 4,
    "пятая": 5,
    "пятую": 5,
    "пятый": 5,
    "5": 5,
}


def scoped_task_query(db: Session, user: User):
    return apply_task_scope(db.query(Task), user, db)


def task_to_line(task: Task, index: Optional[int] = None) -> str:
    prefix = f"{index}. " if index else "- "
    due = task.due_date.strftime("%d.%m.%Y") if task.due_date else "без срока"
    assignee = task.assignee.full_name if task.assignee else "не назначен"
    return (
        f"{prefix}{task.title} — статус {task.status.value}, прогресс {task.progress}%, "
        f"срок {due}, исполнитель {assignee}"
    )


def parse_priority(text: str) -> Optional[TaskPriority]:
    lowered = text.lower()
    if any(word in lowered for word in ("крит", "срочно", "asap", "немедленно")):
        return TaskPriority.CRITICAL
    if any(word in lowered for word in ("высок", "важно", "важная")):
        return TaskPriority.HIGH
    if any(word in lowered for word in ("средн", "обычн")):
        return TaskPriority.MEDIUM
    if any(word in lowered for word in ("низк", "не срочно", "несрочно")):
        return TaskPriority.LOW
    return None


def parse_due_date(text: str) -> Optional[date]:
    lowered = text.lower()
    today = date.today()
    if "сегодня" in lowered:
        return today
    if "завтра" in lowered and "послезавтра" not in lowered:
        return today + timedelta(days=1)
    if "послезавтра" in lowered:
        return today + timedelta(days=2)

    weekdays = {
        "понедельник": 0,
        "понедельнику": 0,
        "вторник": 1,
        "вторнику": 1,
        "среду": 2,
        "среда": 2,
        "среде": 2,
        "четверг": 3,
        "четвергу": 3,
        "пятницу": 4,
        "пятница": 4,
        "пятнице": 4,
        "субботу": 5,
        "суббота": 5,
        "субботе": 5,
        "воскресенье": 6,
        "воскресенью": 6,
    }
    for word, weekday in weekdays.items():
        if f"к {word}" in lowered or f"до {word}" in lowered:
            days_ahead = weekday - today.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            return today + timedelta(days=days_ahead)

    iso_match = re.search(r"\b(20\d{2})-(\d{2})-(\d{2})\b", lowered)
    if iso_match:
        return date.fromisoformat(iso_match.group(0))

    dotted_match = re.search(r"\b(\d{1,2})\.(\d{1,2})(?:\.(20\d{2}))?\b", lowered)
    if dotted_match:
        day = int(dotted_match.group(1))
        month = int(dotted_match.group(2))
        year = int(dotted_match.group(3) or today.year)
        return date(year, month, day)

    return None


def extract_inline_comment(text: str) -> Optional[str]:
    match = re.search(r"комментар(?:ий|ием)?\s*[:\-]\s*(.+)$", text, re.IGNORECASE)
    return match.group(1).strip() if match else None


def find_assignee_or_department(db: Session, user: User, text: str) -> tuple[Optional[User], Optional[Department]]:
    lowered = text.lower()
    if any(part in lowered for part in ("на меня", "мне ", "для меня", "себе")):
        return user, user.department

    users = db.query(User).filter(User.active == True).all()
    for candidate in users:
        names = [candidate.full_name.lower(), candidate.email.lower()]
        names.extend(part.lower() for part in candidate.full_name.split() if len(part) > 2)
        if any(name and name in lowered for name in names):
            return candidate, candidate.department

    departments = db.query(Department).all()
    for department in departments:
        if department.name.lower() in lowered:
            return None, department

    return None, None


async def parse_create_task_draft(db: Session, user: User, text: str) -> dict:
    parsed = await ai_service.parse_task(text)
    assignee, department = find_assignee_or_department(db, user, text)
    priority = parse_priority(text)
    comment = extract_inline_comment(text)
    title = (parsed.get("title") or "").strip()
    if title.lower().startswith(("создай задачу", "создать задачу", "поставь задачу")):
        title = re.sub(r"^(создай|создать|поставь)\s+задачу", "", title, flags=re.IGNORECASE).strip(" :.-")

    due_date = parsed.get("due_date")
    if isinstance(due_date, str) and due_date:
        due_date = date.fromisoformat(due_date)
    due_date = due_date or parse_due_date(text)

    draft = {
        "title": title,
        "due_date": due_date.isoformat() if due_date else None,
        "priority": priority.value if priority else None,
        "assignee_id": str(assignee.id) if assignee else None,
        "assignee_name": assignee.full_name if assignee else None,
        "department_id": str(department.id) if department else None,
        "department_name": department.name if department else None,
        "comment": comment,
        "source_text": text,
    }
    missing = []
    if not draft["title"]:
        missing.append("название")
    if not draft["due_date"]:
        missing.append("дедлайн")
    if not draft["assignee_id"] and not draft["department_id"]:
        missing.append("отдел или сотрудник")
    if not draft["priority"]:
        missing.append("приоритет")
    draft["missing"] = missing
    return draft


def format_create_task_draft(draft: dict) -> str:
    lines = [
        "Проверьте параметры новой задачи:",
        "",
        f"- Название: {draft.get('title') or 'не указано'}",
        f"- Дедлайн: {draft.get('due_date') or 'не указан'}",
        f"- Отдел/сотрудник: {draft.get('assignee_name') or draft.get('department_name') or 'не указан'}",
        f"- Приоритет: {draft.get('priority') or 'не указан'}",
        f"- Комментарий: {draft.get('comment') or 'не указан, это опционально'}",
    ]
    return "\n".join(lines)


def format_missing_create_task_fields(draft: dict) -> str:
    missing = ", ".join(draft.get("missing") or [])
    return (
        "Не хватает обязательных параметров для создания задачи: "
        f"{missing}.\n\n"
        "Укажите: название, дедлайн, отдел или сотрудника, приоритет. "
        "Комментарий можно добавить опционально, например: `комментарий: нужна проверка`."
    )


def get_my_tasks(db: Session, user: User, period: Optional[str] = None) -> list[Task]:
    query = scoped_task_query(db, user).filter(Task.status != TaskStatus.DONE)
    query = query.filter(or_(Task.assignee_id == user.id, Task.created_by_id == user.id))
    if period == "week":
        query = query.filter(Task.due_date <= date.today() + timedelta(days=7))
    return query.order_by(Task.due_date.asc().nullslast(), Task.created_at.desc()).limit(10).all()


def get_deadlines(db: Session, user: User, days: int = 7) -> list[Task]:
    today = date.today()
    return (
        scoped_task_query(db, user)
        .filter(Task.status != TaskStatus.DONE)
        .filter(Task.due_date.isnot(None))
        .filter(Task.due_date <= today + timedelta(days=days))
        .order_by(Task.due_date.asc(), Task.priority.desc())
        .limit(10)
        .all()
    )


def get_overdue_tasks(db: Session, user: User) -> list[Task]:
    today = date.today()
    return (
        scoped_task_query(db, user)
        .filter(Task.status != TaskStatus.DONE)
        .filter(or_(Task.status == TaskStatus.OVERDUE, Task.due_date < today))
        .order_by(Task.due_date.asc())
        .limit(10)
        .all()
    )


def resolve_task_ref(db: Session, user: User, task_ref: Optional[str], session=None) -> Optional[Task]:
    if not task_ref:
        return None

    raw_ref = task_ref.strip().lower()
    try:
        task_id = UUID(str(raw_ref))
        task = db.get(Task, task_id)
        return task if task and user_can_access_task(db, user, task) else None
    except ValueError:
        pass

    ordinal = None
    for word, number in ORDINALS.items():
        if re.search(rf"\b{re.escape(word)}\b", raw_ref):
            ordinal = number
            break
    if ordinal and session and session.last_task_ids and len(session.last_task_ids) >= ordinal:
        task = db.get(Task, UUID(str(session.last_task_ids[ordinal - 1])))
        return task if task and user_can_access_task(db, user, task) else None

    pattern = f"%{raw_ref}%"
    return scoped_task_query(db, user).filter(Task.title.ilike(pattern)).order_by(Task.updated_at.desc()).first()


def get_task_details(db: Session, user: User, task_ref: str, session=None) -> Optional[Task]:
    return resolve_task_ref(db, user, task_ref, session)


def add_task_comment(db: Session, user: User, task_id: UUID, comment: str) -> TaskComment:
    task = db.get(Task, task_id)
    if not task or not user_can_access_task(db, user, task):
        raise PermissionError("No access to task")
    entry = TaskComment(id=uuid.uuid4(), task_id=task.id, author_id=user.id, body=comment)
    db.add(entry)
    log_history(db, task.id, "comment_added", user.id, {"body": comment[:200], "channel": "telegram"})
    db.commit()
    db.refresh(entry)
    return entry


def update_task_progress(db: Session, user: User, task_id: UUID, progress: int) -> Task:
    task = db.get(Task, task_id)
    if not task or not user_can_access_task(db, user, task):
        raise PermissionError("No access to task")
    old_progress = task.progress
    task.progress = max(0, min(100, progress))
    if task.progress == 100:
        task.status = TaskStatus.DONE
    log_history(db, task.id, "progress_updated", user.id, {"old": old_progress, "new": task.progress, "channel": "telegram"})
    db.commit()
    db.refresh(task)
    recompute_parent_progress(db, task)
    db.commit()
    return task


def complete_task(db: Session, user: User, task_id: UUID) -> Task:
    task = db.get(Task, task_id)
    if not task or not user_can_access_task(db, user, task):
        raise PermissionError("No access to task")
    old_status = task.status.value
    task.status = TaskStatus.DONE
    task.progress = 100
    log_history(db, task.id, "status_changed", user.id, {"old": old_status, "new": TaskStatus.DONE.value, "channel": "telegram"})
    db.commit()
    db.refresh(task)
    recompute_parent_progress(db, task)
    db.commit()
    return task


def get_team_digest(db: Session, user: User, department_id: Optional[UUID] = None, period: str = "week") -> str:
    tasks = scoped_task_query(db, user)
    if department_id:
        tasks = tasks.filter(Task.assigned_department_id == department_id)
    rows = tasks.all()
    active = [task for task in rows if task.status != TaskStatus.DONE]
    overdue = [task for task in active if task.status == TaskStatus.OVERDUE or (task.due_date and task.due_date < date.today())]
    risk = [task for task in active if task.due_date and 0 <= (task.due_date - date.today()).days <= 7]
    return (
        f"Сводка команды за {period}: всего задач {len(rows)}, активных {len(active)}, "
        f"просроченных {len(overdue)}, в зоне риска {len(risk)}."
    )


def get_team_risks(db: Session, user: User, department_id: Optional[UUID] = None) -> list[Task]:
    query = scoped_task_query(db, user).filter(Task.status != TaskStatus.DONE).filter(Task.due_date.isnot(None))
    if department_id:
        query = query.filter(Task.assigned_department_id == department_id)
    today = date.today()
    tasks = query.all()
    return sorted(
        [task for task in tasks if task.due_date < today or (task.due_date - today).days <= 7],
        key=lambda task: (task.due_date or date.max, -PRIORITY_WEIGHT.get(task.priority, 0)),
    )[:10]


def get_overload(db: Session, user: User, department_id: Optional[UUID] = None) -> list[dict]:
    query = scoped_task_query(db, user)
    if department_id:
        query = query.filter(Task.assigned_department_id == department_id)
    user_ids = {task.assignee_id for task in query.all() if task.assignee_id}
    if not user_ids:
        user_ids = {user.id}

    rows = []
    for assignee in db.query(User).filter(User.id.in_(user_ids), User.active == True).all():
        workload = compute_user_workload(db, assignee.id)
        rows.append({"user": assignee, "workload": workload})
    return sorted(rows, key=lambda row: row["workload"]["capacity_util"], reverse=True)


async def create_task_from_draft(db: Session, user: User, draft: dict) -> Task:
    due_date = date.fromisoformat(draft["due_date"]) if draft.get("due_date") else None
    priority = TaskPriority(draft.get("priority") or TaskPriority.MEDIUM.value)
    task = Task(
        id=uuid.uuid4(),
        title=draft["title"],
        description=draft.get("comment"),
        due_date=due_date,
        priority=priority,
        status=TaskStatus.NEW,
        progress=0,
        assigned_department_id=UUID(str(draft["department_id"])) if draft.get("department_id") else None,
        assignee_id=UUID(str(draft["assignee_id"])) if draft.get("assignee_id") else None,
        created_by_id=user.id,
    )
    db.add(task)
    db.flush()
    log_history(db, task.id, "created", user.id, {"title": task.title, "channel": "telegram"})
    if draft.get("comment"):
        comment = TaskComment(id=uuid.uuid4(), task_id=task.id, author_id=user.id, body=draft["comment"])
        db.add(comment)
        log_history(db, task.id, "comment_added", user.id, {"body": draft["comment"][:200], "channel": "telegram"})
    db.commit()
    db.refresh(task)
    return task
