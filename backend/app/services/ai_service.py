"""AI service: local LLM client with rule-based fallbacks.

All public functions return deterministic results even when the LLM is unavailable.
"""
import re
import logging
from datetime import date, timedelta
from typing import Optional, List
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import apply_task_scope, user_can_access_task
from app.models.task import Task
from app.models.user import User
from app.models.department import Department
from app.models.enums import TaskStatus, TaskPriority, TaskType, UserRole, PRIORITY_WEIGHT
from app.services.llm import get_llm_provider
from app.services.llm.json_utils import extract_json_array, extract_json_object
from app.services.task_service import compute_user_workload, compute_period_bucket

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# LLM client
# ---------------------------------------------------------------------------

async def _ask_llm(
    prompt: str,
    system: str = "",
    json_mode: bool = False,
    temperature: float = 0.2,
) -> Optional[str]:
    """Call the configured LLM provider. Returns text or None on any failure."""
    try:
        return await get_llm_provider().generate(
            prompt=prompt,
            system=system,
            json_mode=json_mode,
            temperature=temperature,
        )
    except Exception as e:
        logger.warning("LLM call failed: %s", e)
    return None


# ---------------------------------------------------------------------------
# DIGEST
# ---------------------------------------------------------------------------

def _gather_tasks_for_scope(
    db: Session,
    scope: str,
    scope_id: Optional[UUID],
    current_user: Optional[User] = None,
) -> List[Task]:
    q = db.query(Task)
    if current_user:
        q = apply_task_scope(q, current_user, db)
    if scope == "department" and scope_id:
        q = q.filter(Task.assigned_department_id == scope_id)
    elif scope == "user" and scope_id:
        q = q.filter(Task.assignee_id == scope_id)
    return q.all()


def _build_stats_text(tasks: List[Task]) -> str:
    today = date.today()
    total = len(tasks)
    by_status = {}
    for t in tasks:
        by_status[t.status.value] = by_status.get(t.status.value, 0) + 1
    at_risk = sum(
        1 for t in tasks
        if t.due_date and 0 < (t.due_date - today).days <= 3 and t.status != TaskStatus.DONE
    )
    overdue = sum(
        1 for t in tasks
        if t.status == TaskStatus.OVERDUE or (t.due_date and t.due_date < today and t.status != TaskStatus.DONE)
    )
    done = by_status.get("DONE", 0)
    active = total - done
    lines = [
        f"Всего задач: {total}, активных: {active}, выполнено: {done}.",
        f"Просроченных: {overdue}, в зоне риска (<=3 дня): {at_risk}.",
        "По статусам: " + ", ".join(f"{k}: {v}" for k, v in by_status.items()) + ".",
    ]
    return "\n".join(lines)


async def digest(
    db: Session,
    scope: str,
    scope_id: Optional[UUID],
    period: str = "month",
    current_user: Optional[User] = None,
) -> dict:
    tasks = _gather_tasks_for_scope(db, scope, scope_id, current_user)
    stats_text = _build_stats_text(tasks)

    scope_label = "по всей организации"
    if scope == "department" and scope_id:
        dept = db.get(Department, scope_id)
        scope_label = f"в отделе {dept.name}" if dept else scope_label
    elif scope == "user" and scope_id:
        user = db.get(User, scope_id)
        scope_label = f"для {user.full_name}" if user else scope_label

    prompt = (
        f"Составь краткий дайджест {scope_label} за период {period}.\n"
        f"Статистика:\n{stats_text}\n"
        "Дай summary (2-3 предложения) и key_points (до 5 пунктов). "
        "Отвечай только на русском. Формат JSON: {{\"summary\": \"...\", \"key_points\": [\"...\"]}}."
    )
    system = "Ты ассистент руководителя в системе управления задачами. Отвечай кратко и по делу на русском."
    llm = await _ask_llm(prompt, system, json_mode=True)

    if llm:
        parsed = extract_json_object(llm)
        if parsed:
            return {"summary": parsed.get("summary", llm), "key_points": parsed.get("key_points", [])}
        return {"summary": llm, "key_points": []}

    # Fallback
    today = date.today()
    at_risk = sum(
        1 for t in tasks
        if t.due_date and 0 < (t.due_date - today).days <= 3 and t.status != TaskStatus.DONE
    )
    active = sum(1 for t in tasks if t.status != TaskStatus.DONE)
    overdue = sum(
        1 for t in tasks
        if t.status == TaskStatus.OVERDUE or (t.due_date and t.due_date < today and t.status != TaskStatus.DONE)
    )
    summary = (
        f"{scope_label.capitalize()} {active} активных задач, {overdue} просроченных, {at_risk} в риске просрочки."
    )
    key_points = []
    if overdue > 0:
        key_points.append(f"Необходимо обратить внимание на {overdue} просроченных задач.")
    if at_risk > 0:
        key_points.append(f"{at_risk} задач в зоне риска (дедлайн в ближайшие 3 дня).")
    high_prio = sum(1 for t in tasks if t.priority in (TaskPriority.HIGH, TaskPriority.CRITICAL) and t.status != TaskStatus.DONE)
    if high_prio > 0:
        key_points.append(f"{high_prio} задач с высоким/критическим приоритетом требуют внимания.")

    return {"summary": summary, "key_points": key_points}


# ---------------------------------------------------------------------------
# RISKS
# ---------------------------------------------------------------------------

async def risks(
    db: Session,
    scope: str,
    scope_id: Optional[UUID],
    current_user: Optional[User] = None,
) -> dict:
    tasks = _gather_tasks_for_scope(db, scope, scope_id, current_user)
    today = date.today()
    items = []

    for t in tasks:
        if t.status == TaskStatus.DONE:
            continue
        if t.due_date is None:
            continue
        days_left = (t.due_date - today).days
        if days_left <= 3:
            level = "high"
        elif days_left <= 7:
            level = "med"
        else:
            continue

        reason_fallback = (
            f"До дедлайна осталось {days_left} дн., статус: {t.status.value}, "
            f"прогресс: {t.progress}%."
        )
        items.append({
            "task_id": t.id,
            "title": t.title,
            "risk_level": level,
            "reason": reason_fallback,
        })

    # Try to enrich reasons via LLM
    if items:
        task_lines = "\n".join(
            f"- {i['title']} (риск: {i['risk_level']}, причина: {i['reason']})" for i in items
        )
        prompt = (
            f"Для каждой задачи ниже дай краткое пояснение риска на русском (1 предложение):\n{task_lines}\n"
            "Формат JSON: [{\"title\": \"...\", \"reason\": \"...\"}]"
        )
        llm = await _ask_llm(prompt, json_mode=True)
        if llm:
            enriched = extract_json_array(llm)
            if enriched:
                title_map = {e.get("title", ""): e.get("reason", "") for e in enriched}
                for item in items:
                    if item["title"] in title_map and title_map[item["title"]]:
                        item["reason"] = title_map[item["title"]]

    return {"items": items}


# ---------------------------------------------------------------------------
# OVERLOAD
# ---------------------------------------------------------------------------

async def overload(db: Session, current_user: Optional[User] = None) -> dict:
    if current_user:
        scoped_tasks = apply_task_scope(db.query(Task), current_user, db).all()
        user_ids = {task.assignee_id for task in scoped_tasks if task.assignee_id}
        if current_user.role != UserRole.ADMIN:
            user_ids.add(current_user.id)
        users = db.query(User).filter(User.active == True, User.id.in_(user_ids)).all() if user_ids else []
    else:
        users = db.query(User).filter(User.active == True).all()
    items = []
    for u in users:
        wl = compute_user_workload(db, u.id)
        util = wl["capacity_util"]
        if util > 120:
            status = "overload"
        elif util > 80:
            status = "warning"
        else:
            status = "ok"
        suggestion = ""
        if status == "overload":
            suggestion = f"Рекомендуется перераспределить задачи. Загрузка: {util:.0f}%."
        elif status == "warning":
            suggestion = f"Загрузка приближается к пределу ({util:.0f}%). Рассмотрите делегирование."

        items.append({
            "user_id": u.id,
            "full_name": u.full_name,
            "status": status,
            "suggestion": suggestion,
        })

    # Enrich overloaded users' suggestions via LLM
    overloaded = [i for i in items if i["status"] != "ok"]
    if overloaded:
        lines = "\n".join(f"- {i['full_name']}: {i['status']}, {i['suggestion']}" for i in overloaded)
        prompt = (
            f"Для каждого сотрудника дай краткую рекомендацию на русском:\n{lines}\n"
            "Формат JSON: [{{\"full_name\": \"...\", \"suggestion\": \"...\"}}]"
        )
        llm = await _ask_llm(prompt, json_mode=True)
        if llm:
            enriched = extract_json_array(llm)
            if enriched:
                name_map = {e.get("full_name", ""): e.get("suggestion", "") for e in enriched}
                for item in items:
                    if item["full_name"] in name_map and name_map[item["full_name"]]:
                        item["suggestion"] = name_map[item["full_name"]]

    return {"items": items}


# ---------------------------------------------------------------------------
# PARSE TASK
# ---------------------------------------------------------------------------

async def parse_task(text: str) -> dict:
    prompt = (
        f"Распознай задачу из текста: \"{text}\"\n"
        "Верни JSON: {\"title\": \"...\", \"description\": \"...или null\", "
        "\"due_date\": \"YYYY-MM-DD или null\", \"priority\": \"LOW|MEDIUM|HIGH|CRITICAL\", "
        "\"assignee_suggestion\": \"имя или null\", \"type\": \"GOAL|EPIC|TASK|SUBTASK\"}\n"
        "Отвечай только JSON."
    )
    llm = await _ask_llm(prompt, json_mode=True)
    if llm:
        parsed = extract_json_object(llm)
        if parsed:
            result = {
                "title": parsed.get("title", text),
                "description": parsed.get("description"),
                "due_date": parsed.get("due_date"),
                "priority": parsed.get("priority", "MEDIUM"),
                "assignee_suggestion": parsed.get("assignee_suggestion"),
                "type": parsed.get("type", "TASK"),
            }
            # Validate due_date format
            if result["due_date"]:
                try:
                    date.fromisoformat(result["due_date"])
                except ValueError:
                    result["due_date"] = None
            return result

    # Rule-based fallback
    result = {
        "title": text.strip(),
        "description": None,
        "due_date": None,
        "priority": "MEDIUM",
        "assignee_suggestion": None,
        "type": "TASK",
    }

    today = date.today()
    text_lower = text.lower()

    # Date heuristics
    if "завтра" in text_lower:
        result["due_date"] = (today + timedelta(days=1)).isoformat()
    elif "послезавтра" in text_lower:
        result["due_date"] = (today + timedelta(days=2)).isoformat()
    elif "к пятнице" in text_lower:
        days_ahead = 4 - today.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        result["due_date"] = (today + timedelta(days=days_ahead)).isoformat()
    elif "к понедельнику" in text_lower:
        days_ahead = 0 - today.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        result["due_date"] = (today + timedelta(days=days_ahead)).isoformat()
    else:
        # Try "15 мая", "20 июня" etc.
        months_ru = {
            "января": 1, "февраля": 2, "марта": 3, "апреля": 4,
            "мая": 5, "июня": 6, "июля": 7, "августа": 8,
            "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
        }
        for month_name, month_num in months_ru.items():
            pattern = rf"(\d{{1,2}})\s+{month_name}"
            m = re.search(pattern, text_lower)
            if m:
                day_num = int(m.group(1))
                try:
                    result["due_date"] = date(today.year, month_num, day_num).isoformat()
                except ValueError:
                    pass
                break

    # Priority heuristics
    if any(w in text_lower for w in ["срочно", "критично", "asap", "немедленно"]):
        result["priority"] = "CRITICAL"
    elif any(w in text_lower for w in ["важно", "высокий приоритет"]):
        result["priority"] = "HIGH"

    return result


# ---------------------------------------------------------------------------
# SUGGEST ASSIGNEE
# ---------------------------------------------------------------------------

async def suggest_assignee(
    db: Session,
    title: str,
    description: Optional[str],
    department_id: Optional[UUID],
    priority: Optional[str],
    due_date: Optional[date],
    current_user: Optional[User] = None,
) -> dict:
    q = db.query(User).filter(User.active == True)
    if department_id:
        q = q.filter(User.department_id == department_id)
    elif current_user and current_user.role == UserRole.EMPLOYEE and current_user.department_id:
        q = q.filter(User.department_id == current_user.department_id)
    users = q.all()

    if not users:
        return {"candidates": []}

    text_words = set()
    for w in (title + " " + (description or "")).lower().split():
        cleaned = re.sub(r"[^\w]", "", w)
        if len(cleaned) > 2:
            text_words.add(cleaned)

    candidates = []
    for u in users:
        wl = compute_user_workload(db, u.id)
        util = wl["capacity_util"]

        # Skill match
        skill_matches = 0
        for skill in u.skills:
            for sw in skill.lower().split():
                cleaned = re.sub(r"[^\w]", "", sw)
                if cleaned in text_words:
                    skill_matches += 1

        score = max(0, 100 - util) + skill_matches * 15

        reason_fallback = (
            f"Загрузка: {util:.0f}%, совпадений навыков: {skill_matches}, "
            f"открытых задач: {wl['open_tasks']}."
        )

        candidates.append({
            "user_id": u.id,
            "full_name": u.full_name,
            "score": round(score, 1),
            "reason": reason_fallback,
        })

    candidates.sort(key=lambda c: c["score"], reverse=True)
    top = candidates[:3]

    # Try LLM to enrich reasons
    if top:
        lines = "\n".join(
            f"- {c['full_name']}: score={c['score']}, {c['reason']}" for c in top
        )
        prompt = (
            f"Задача: \"{title}\"\n"
            f"Кандидаты на назначение:\n{lines}\n"
            "Для каждого кандидата дай краткое обоснование (1 предложение) на русском.\n"
            "Формат JSON: [{{\"full_name\": \"...\", \"reason\": \"...\"}}]"
        )
        llm = await _ask_llm(prompt, json_mode=True)
        if llm:
            enriched = extract_json_array(llm)
            if enriched:
                name_map = {e.get("full_name", ""): e.get("reason", "") for e in enriched}
                for c in top:
                    if c["full_name"] in name_map and name_map[c["full_name"]]:
                        c["reason"] = name_map[c["full_name"]]

    return {"candidates": top}


# ---------------------------------------------------------------------------
# CHAT
# ---------------------------------------------------------------------------

async def chat(db: Session, message: str, context: Optional[dict] = None) -> dict:
    system = (
        "Ты ассистент руководителя в системе управления задачами Транстелематика. "
        "Отвечай кратко и по делу на русском."
    )

    context_text = ""
    if context:
        if context.get("task_id"):
            task = db.get(Task, UUID(str(context["task_id"])))
            if task:
                context_text += (
                    f"\nКонтекст задачи: \"{task.title}\", статус: {task.status.value}, "
                    f"прогресс: {task.progress}%, приоритет: {task.priority.value}."
                )
        if context.get("department_id"):
            dept = db.get(Department, UUID(str(context["department_id"])))
            if dept:
                dept_tasks = db.query(Task).filter(Task.assigned_department_id == dept.id).all()
                active = sum(1 for t in dept_tasks if t.status != TaskStatus.DONE)
                context_text += f"\nОтдел: {dept.name}, активных задач: {active}."

    prompt = message
    if context_text:
        prompt = context_text + "\n\nВопрос пользователя: " + message

    llm = await _ask_llm(prompt, system)
    if llm:
        return {"reply": llm}

    # Fallback
    return {
        "reply": (
            "К сожалению, AI-ассистент временно недоступен. "
            "Попробуйте переформулировать вопрос или обратитесь позже."
        )
    }


# Context-aware chat implementation. Defined after the legacy chat function so
# this name is the one exported by the module.

def _chat_scope(db: Session, context: Optional[dict], current_user: Optional[User]) -> tuple[str, Optional[UUID], str]:
    department_id = UUID(str(context["department_id"])) if context and context.get("department_id") else None
    if department_id:
        dept = db.get(Department, department_id)
        return "department", department_id, f"отдел {dept.name}" if dept else "отдел"
    if current_user and current_user.department_id:
        dept = db.get(Department, current_user.department_id)
        return "department", current_user.department_id, f"моя команда ({dept.name})" if dept else "моя команда"
    return "all", None, "вся компания"


def _scoped_tasks(db: Session, scope: str, scope_id: Optional[UUID], current_user: Optional[User] = None) -> List[Task]:
    query = db.query(Task)
    if current_user:
        query = apply_task_scope(query, current_user, db)
    if scope == "department" and scope_id:
        query = query.filter(Task.assigned_department_id == scope_id)
    return query.all()


def _task_line(task: Task) -> str:
    assignee = task.assignee.full_name if task.assignee else "не назначен"
    due = task.due_date.isoformat() if task.due_date else "без срока"
    return (
        f"- {task.title}: {task.status.value}, прогресс {task.progress}%, "
        f"приоритет {task.priority.value}, срок {due}, исполнитель {assignee}"
    )


def _chat_digest_response(tasks: List[Task], scope_label: str) -> str:
    total = len(tasks)
    active = [t for t in tasks if t.status != TaskStatus.DONE]
    done = [t for t in tasks if t.status == TaskStatus.DONE]
    today = date.today()
    overdue = [t for t in active if t.status == TaskStatus.OVERDUE or (t.due_date and t.due_date < today)]
    risk = [t for t in active if t.due_date and 0 <= (t.due_date - today).days <= 7]
    critical = [t for t in active if t.priority in (TaskPriority.HIGH, TaskPriority.CRITICAL)]
    focus = sorted(
        set(overdue + risk + critical),
        key=lambda t: (0 if t in overdue else 1, t.due_date or date.max, -PRIORITY_WEIGHT.get(t.priority, 0)),
    )[:6]

    lines = [
        f"Сводка по области: {scope_label}.",
        f"Всего задач: {total}. Активных: {len(active)}. Завершено: {len(done)}.",
        f"Просрочено: {len(overdue)}. В зоне риска на ближайшие 7 дней: {len(risk)}. Высокий/критический приоритет: {len(critical)}.",
    ]
    if focus:
        lines.append("\nЧто требует внимания:")
        lines.extend(_task_line(t) for t in focus)
    else:
        lines.append("\nКритичных задач для немедленного внимания не найдено.")
    return "\n".join(lines)


def _chat_risks_response(tasks: List[Task], scope_label: str) -> str:
    today = date.today()
    risk_rows = []
    for task in tasks:
        if task.status == TaskStatus.DONE or not task.due_date:
            continue
        days_left = (task.due_date - today).days
        if task.status == TaskStatus.OVERDUE or days_left < 0:
            level = "высокий"
            reason = f"просрочена на {abs(days_left)} дн."
        elif days_left <= 3:
            level = "высокий"
            reason = f"до срока {days_left} дн."
        elif days_left <= 7:
            level = "средний"
            reason = f"до срока {days_left} дн."
        else:
            continue
        risk_rows.append((level, days_left, task, reason))

    risk_rows.sort(key=lambda r: (0 if r[0] == "высокий" else 1, r[1], -PRIORITY_WEIGHT.get(r[2].priority, 0)))
    if not risk_rows:
        return f"По области «{scope_label}» задач в зоне риска не найдено."

    lines = [f"Задачи в зоне риска по области: {scope_label}."]
    for level, _, task, reason in risk_rows[:10]:
        assignee = task.assignee.full_name if task.assignee else "не назначен"
        lines.append(
            f"- [{level}] {task.title}: {reason}, статус {task.status.value}, "
            f"прогресс {task.progress}%, исполнитель {assignee}."
        )
    return "\n".join(lines)


def _chat_overload_response(
    db: Session,
    scope: str,
    scope_id: Optional[UUID],
    scope_label: str,
    current_user: Optional[User] = None,
) -> str:
    query = db.query(User).filter(User.active == True)
    if scope == "department" and scope_id:
        query = query.filter(User.department_id == scope_id)
    users = query.all()
    allowed_user_ids = None
    if current_user:
        scoped_tasks = apply_task_scope(db.query(Task), current_user, db).all()
        allowed_user_ids = {task.assignee_id for task in scoped_tasks if task.assignee_id}
        allowed_user_ids.add(current_user.id)
    rows = []
    for user in users:
        if allowed_user_ids is not None and user.id not in allowed_user_ids:
            continue
        workload = compute_user_workload(db, user.id)
        rows.append((workload["capacity_util"], user, workload))
    rows.sort(key=lambda row: row[0], reverse=True)

    if not rows:
        return f"По области «{scope_label}» сотрудников не найдено."

    lines = [f"Сотрудники с наибольшей загрузкой по области: {scope_label}."]
    for util, user, workload in rows[:8]:
        status = "перегруз" if util > 120 else "риск перегруза" if util > 80 else "норма"
        lines.append(
            f"- {user.full_name}: {util:.0f}% ({status}), открытых задач: {workload['open_tasks']}, "
            f"просрочено: {workload['overdue_count']}, в риске: {workload['at_risk_count']}."
        )
    return "\n".join(lines)


def _chat_context_text(tasks: List[Task], scope_label: str) -> str:
    today = date.today()
    active = [t for t in tasks if t.status != TaskStatus.DONE]
    due_soon = [t for t in active if t.due_date and (t.due_date < today or 0 <= (t.due_date - today).days <= 14)]
    high_priority = [t for t in active if t.priority in (TaskPriority.HIGH, TaskPriority.CRITICAL)]
    sample = sorted(
        set(due_soon + high_priority),
        key=lambda t: (t.due_date or date.max, -PRIORITY_WEIGHT.get(t.priority, 0)),
    )[:20]

    status_counts = {}
    for task in tasks:
        status_counts[task.status.value] = status_counts.get(task.status.value, 0) + 1

    lines = [
        f"Область анализа: {scope_label}.",
        "Сводка по статусам: " + ", ".join(f"{k}: {v}" for k, v in status_counts.items()),
        "Задачи для анализа:",
    ]
    lines.extend(_task_line(t) for t in sample)
    return "\n".join(lines)


async def chat(db: Session, message: str, context: Optional[dict] = None, current_user: Optional[User] = None) -> dict:
    system = (
        "Ты ассистент руководителя в системе управления задачами Транстелематика. "
        "Отвечай кратко, по делу и только на основе переданного контекста задач. "
        "Если данных недостаточно, прямо скажи, каких данных не хватает."
    )

    scope, scope_id, scope_label = _chat_scope(db, context, current_user)
    message_lower = message.lower()

    if any(word in message_lower for word in ("перегруж", "загруз", "нагруз")):
        return {"reply": _chat_overload_response(db, scope, scope_id, scope_label, current_user)}

    tasks = _scoped_tasks(db, scope, scope_id, current_user)

    if any(word in message_lower for word in ("риск", "риска", "риске", "просроч")):
        return {"reply": _chat_risks_response(tasks, scope_label)}

    if any(word in message_lower for word in ("сводк", "отчет", "отчёт", "дайджест", "недел")):
        return {"reply": _chat_digest_response(tasks, scope_label)}

    context_text = _chat_context_text(tasks, scope_label)
    if context and context.get("task_id"):
        task = db.get(Task, UUID(str(context["task_id"])))
        if task:
            context_text += (
                f"\nКонтекст выбранной задачи: \"{task.title}\", статус: {task.status.value}, "
                f"прогресс: {task.progress}%, приоритет: {task.priority.value}."
            )

    prompt = context_text + "\n\nВопрос пользователя: " + message
    llm = await _ask_llm(prompt, system)
    if llm:
        return {"reply": llm}

    return {
        "reply": "AI-модель не ответила. Но данные проекта доступны: попробуйте спросить про сводку, риски или загрузку команды."
    }


# Final chat formatter. Kept near the end so it overrides the earlier chat
# implementation while preserving the rest of the AI service functions.

STATUS_LABELS = {
    TaskStatus.NEW: "Новая",
    TaskStatus.IN_PROGRESS: "В работе",
    TaskStatus.REVIEW: "На проверке",
    TaskStatus.DONE: "Готово",
    TaskStatus.OVERDUE: "Просрочена",
}

PRIORITY_LABELS = {
    TaskPriority.LOW: "низкий",
    TaskPriority.MEDIUM: "средний",
    TaskPriority.HIGH: "высокий",
    TaskPriority.CRITICAL: "критический",
}


def _display_name(user: Optional[User]) -> str:
    if not user or not user.full_name or "?" in user.full_name:
        return "не назначен"
    return user.full_name


def _status_label(status: TaskStatus) -> str:
    return STATUS_LABELS.get(status, status.value)


def _priority_label(priority: TaskPriority) -> str:
    return PRIORITY_LABELS.get(priority, priority.value.lower())


def _task_md(task: Task, note: str) -> str:
    due = task.due_date.strftime("%d.%m.%Y") if task.due_date else "без срока"
    return "\n".join([
        f"**{task.title}**",
        f"- Причина: {note}",
        f"- Статус: {_status_label(task.status)}, прогресс {task.progress}%",
        f"- Приоритет: {_priority_label(task.priority)}, срок: {due}",
        f"- Исполнитель: {_display_name(task.assignee)}",
    ])


def _final_chat_digest(tasks: List[Task], scope_label: str) -> str:
    today = date.today()
    active = [t for t in tasks if t.status != TaskStatus.DONE]
    done = [t for t in tasks if t.status == TaskStatus.DONE]
    overdue = [t for t in active if t.status == TaskStatus.OVERDUE or (t.due_date and t.due_date < today)]
    risk = [t for t in active if t.due_date and 0 <= (t.due_date - today).days <= 7]
    critical = [t for t in active if t.priority in (TaskPriority.HIGH, TaskPriority.CRITICAL)]
    focus = sorted(
        set(overdue + risk + critical),
        key=lambda t: (0 if t in overdue else 1, t.due_date or date.max, -PRIORITY_WEIGHT.get(t.priority, 0)),
    )[:5]

    lines = [
        "## Сводка по задачам",
        f"**Область:** {scope_label}",
        "",
        f"- Всего задач: **{len(tasks)}**",
        f"- Активных: **{len(active)}**",
        f"- Завершено: **{len(done)}**",
        f"- Просрочено: **{len(overdue)}**",
        f"- В зоне риска на 7 дней: **{len(risk)}**",
        f"- Высокий или критический приоритет: **{len(critical)}**",
    ]
    if focus:
        lines.extend(["", "### Что требует внимания"])
        for index, task in enumerate(focus, 1):
            if task in overdue:
                note = "просрочена"
            elif task in risk:
                days = (task.due_date - today).days if task.due_date else 0
                note = f"до срока {days} дн."
            else:
                note = "высокий приоритет"
            lines.extend(["", f"{index}. {_task_md(task, note)}"])
    return "\n".join(lines)


def _final_chat_risks(tasks: List[Task], scope_label: str) -> str:
    today = date.today()
    rows = []
    for task in tasks:
        if task.status == TaskStatus.DONE or not task.due_date:
            continue
        days_left = (task.due_date - today).days
        if task.status == TaskStatus.OVERDUE or days_left < 0:
            level = "высокий"
            note = f"просрочена на {abs(days_left)} дн."
        elif days_left <= 3:
            level = "высокий"
            note = f"до срока {days_left} дн."
        elif days_left <= 7:
            level = "средний"
            note = f"до срока {days_left} дн."
        else:
            continue
        rows.append((level, days_left, task, note))

    rows.sort(key=lambda row: (0 if row[0] == "высокий" else 1, row[1], -PRIORITY_WEIGHT.get(row[2].priority, 0)))
    if not rows:
        return f"## Задачи в зоне риска\n\n**Область:** {scope_label}\n\nЗадач в зоне риска не найдено."

    lines = [
        "## Задачи в зоне риска",
        f"**Область:** {scope_label}",
        "",
        f"Найдено задач: **{len(rows)}**. Ниже самые срочные.",
    ]
    for index, (level, _, task, note) in enumerate(rows[:8], 1):
        lines.extend(["", f"{index}. **Риск: {level}**", _task_md(task, note)])
    return "\n".join(lines)


def _final_chat_overload(
    db: Session,
    scope: str,
    scope_id: Optional[UUID],
    scope_label: str,
    current_user: Optional[User] = None,
) -> str:
    query = db.query(User).filter(User.active == True)
    if scope == "department" and scope_id:
        query = query.filter(User.department_id == scope_id)
    rows = []
    allowed_user_ids = None
    if current_user:
        scoped_tasks = apply_task_scope(db.query(Task), current_user, db).all()
        allowed_user_ids = {task.assignee_id for task in scoped_tasks if task.assignee_id}
        allowed_user_ids.add(current_user.id)
    for user in query.all():
        if allowed_user_ids is not None and user.id not in allowed_user_ids:
            continue
        workload = compute_user_workload(db, user.id)
        rows.append((workload["capacity_util"], user, workload))
    rows.sort(key=lambda row: row[0], reverse=True)

    lines = [
        "## Загрузка сотрудников",
        f"**Область:** {scope_label}",
        "",
    ]
    if not rows:
        lines.append("Сотрудников в выбранной области не найдено.")
        return "\n".join(lines)

    for index, (util, user, workload) in enumerate(rows[:8], 1):
        status = "перегруз" if util > 120 else "риск перегруза" if util > 80 else "норма"
        lines.extend([
            f"{index}. **{_display_name(user)}**",
            f"   - Загрузка: **{util:.0f}%** ({status})",
            f"   - Открытых задач: {workload['open_tasks']}",
            f"   - Просрочено: {workload['overdue_count']}",
            f"   - В зоне риска: {workload['at_risk_count']}",
        ])
    return "\n".join(lines)


async def chat(db: Session, message: str, context: Optional[dict] = None, current_user: Optional[User] = None) -> dict:
    scope, scope_id, scope_label = _chat_scope(db, context, current_user)
    message_lower = message.lower()

    if any(word in message_lower for word in ("перегруж", "загруз", "нагруз")):
        return {"reply": _final_chat_overload(db, scope, scope_id, scope_label, current_user)}

    tasks = _scoped_tasks(db, scope, scope_id, current_user)

    if any(word in message_lower for word in ("риск", "риска", "риске", "просроч")):
        return {"reply": _final_chat_risks(tasks, scope_label)}

    if any(word in message_lower for word in ("сводк", "отчет", "отчёт", "дайджест", "недел")):
        return {"reply": _final_chat_digest(tasks, scope_label)}

    system = (
        "Ты ассистент руководителя в системе управления задачами Транстелематика. "
        "Отвечай в Markdown: короткий заголовок, затем 3-6 пунктов. "
        "Используй только переданный контекст задач."
    )
    prompt = _chat_context_text(tasks, scope_label) + "\n\nВопрос пользователя: " + message
    llm = await _ask_llm(prompt, system)
    return {"reply": llm or "Не удалось получить ответ модели. Попробуйте спросить про сводку, риски или загрузку команды."}


# ---------------------------------------------------------------------------
# GOAL SUMMARY
# ---------------------------------------------------------------------------

def _collect_descendants(db: Session, task_id: UUID) -> List[Task]:
    """Collect all descendant tasks (BFS)."""
    result = []
    queue = [task_id]
    while queue:
        pid = queue.pop(0)
        children = db.query(Task).filter(Task.parent_id == pid).all()
        for c in children:
            result.append(c)
            queue.append(c.id)
    return result


async def goal_summary(db: Session, goal_id: UUID, current_user: Optional[User] = None) -> dict:
    goal = db.get(Task, goal_id)
    if not goal:
        return {"progress": 0, "risks": [], "summary": "Цель не найдена."}
    if current_user and not user_can_access_task(db, current_user, goal):
        return {"progress": 0, "risks": [], "summary": "Нет доступа к этой цели."}

    descendants = _collect_descendants(db, goal_id)
    if current_user:
        descendants = [task for task in descendants if user_can_access_task(db, current_user, task)]
    all_tasks = [goal] + descendants

    # Aggregate progress
    if descendants:
        avg_progress = sum(t.progress for t in descendants) / len(descendants)
    else:
        avg_progress = goal.progress

    # Risks
    today = date.today()
    risk_items = []
    for t in all_tasks:
        if t.status == TaskStatus.DONE or t.due_date is None:
            continue
        days_left = (t.due_date - today).days
        if days_left <= 3:
            level = "high"
        elif days_left <= 7:
            level = "med"
        else:
            continue
        risk_items.append({
            "task_id": t.id,
            "title": t.title,
            "risk_level": level,
            "reason": f"До дедлайна {days_left} дн., прогресс {t.progress}%.",
        })

    # LLM summary
    task_lines = "\n".join(
        f"- {t.title}: {t.status.value}, прогресс {t.progress}%"
        for t in all_tasks[:20]
    )
    prompt = (
        f"Цель: \"{goal.title}\", общий прогресс: {avg_progress:.0f}%.\n"
        f"Подзадачи:\n{task_lines}\n"
        "Дай краткое резюме по достижению цели (2-3 предложения) на русском."
    )
    llm = await _ask_llm(prompt)
    summary = llm if llm else (
        f"Цель \"{goal.title}\" выполнена на {avg_progress:.0f}%. "
        f"Всего подзадач: {len(descendants)}, из них в зоне риска: {len(risk_items)}."
    )

    return {
        "progress": round(avg_progress, 1),
        "risks": risk_items,
        "summary": summary,
    }


# The final chat implementation below intentionally overrides the earlier
# iterations in this module. It keeps deterministic DB answers for common
# task analytics, but also gives the LLM normal assistant context and memory.

CHAT_SYSTEM_PROMPT = (
    "Ты AI-помощник в системе управления задачами компании Транстелематика. "
    "Отвечай на русском, кратко и удобно: короткие абзацы, списки только когда они реально помогают. "
    "Если вопрос про задачи, сотрудников, сроки, риски или загрузку, опирайся на переданный контекст БД. "
    "Если вопрос общий или про тебя, отвечай как обычный ассистент и не требуй данные из БД. "
    "Не выдумывай факты о задачах, которых нет в контексте."
)


def _chat_model_name() -> str:
    provider = settings.LLM_PROVIDER
    if provider == "openai_compatible":
        return settings.OPENAI_COMPATIBLE_MODEL
    if provider in {"ollama", "docker_model"}:
        return settings.OLLAMA_MODEL
    return provider


def _looks_like_model_question(message: str) -> bool:
    text = message.lower()
    return any(word in text for word in ("модель", "model", "llm", "кто ты", "что ты такое"))


def _relevant_tasks_for_message(tasks: List[Task], message: str, limit: int = 12) -> List[Task]:
    words = [word for word in re.findall(r"[\w-]+", message.lower(), flags=re.UNICODE) if len(word) > 2]
    if not words:
        return []

    scored = []
    for task in tasks:
        assignee = task.assignee.full_name if task.assignee else ""
        department = task.assigned_department.name if task.assigned_department else ""
        haystack = " ".join([task.title or "", task.description or "", assignee, department]).lower()
        score = sum(1 for word in words if word in haystack)
        if score:
            scored.append((score, task.updated_at, task))

    scored.sort(key=lambda row: (row[0], row[1]), reverse=True)
    return [task for _, _, task in scored[:limit]]


def _history_text(history: list[dict]) -> str:
    rows = []
    for item in (history or [])[-12:]:
        role = "Пользователь" if item.get("role") == "user" else "Ассистент"
        content = str(item.get("content") or "").strip()
        if content:
            rows.append(f"{role}: {content[:1200]}")
    return "\n".join(rows)


def _task_context_for_chat(tasks: List[Task], scope_label: str, message: str) -> str:
    today = date.today()
    active = [task for task in tasks if task.status != TaskStatus.DONE]
    overdue = [task for task in active if task.status == TaskStatus.OVERDUE or (task.due_date and task.due_date < today)]
    risk = [task for task in active if task.due_date and 0 <= (task.due_date - today).days <= 7]
    high_priority = [task for task in active if task.priority in (TaskPriority.HIGH, TaskPriority.CRITICAL)]
    relevant = _relevant_tasks_for_message(tasks, message)

    focus = []
    for group in (relevant, overdue, risk, high_priority):
        for task in group:
            if task not in focus:
                focus.append(task)
            if len(focus) >= 30:
                break
        if len(focus) >= 30:
            break

    status_counts = {}
    for task in tasks:
        status_counts[task.status.value] = status_counts.get(task.status.value, 0) + 1

    lines = [
        f"Область данных: {scope_label}.",
        f"Всего задач в доступном контексте: {len(tasks)}; активных: {len(active)}; просроченных: {len(overdue)}; в зоне риска на 7 дней: {len(risk)}.",
        "Статусы: " + ", ".join(f"{key}: {value}" for key, value in status_counts.items()),
    ]
    if focus:
        lines.append("Релевантные и приоритетные задачи:")
        lines.extend(_task_line(task) for task in focus)
    else:
        lines.append("По словам из запроса точных совпадений в задачах не найдено.")
    return "\n".join(lines)


async def chat(db: Session, message: str, context: Optional[dict] = None, current_user: Optional[User] = None) -> dict:
    context = context or {}
    scope, scope_id, scope_label = _chat_scope(db, context, current_user)
    message_lower = message.lower()

    if _looks_like_model_question(message):
        return {
            "reply": (
                f"Я AI-помощник проекта Транстелематика. Сейчас backend настроен на провайдера "
                f"`{settings.LLM_PROVIDER}`, модель: `{_chat_model_name()}`."
            )
        }

    if any(word in message_lower for word in ("перегруж", "загруз", "нагруз")):
        return {"reply": _final_chat_overload(db, scope, scope_id, scope_label, current_user)}

    tasks = _scoped_tasks(db, scope, scope_id, current_user)

    if any(word in message_lower for word in ("риск", "риска", "риске", "просроч")):
        return {"reply": _final_chat_risks(tasks, scope_label)}

    if any(word in message_lower for word in ("сводк", "отчет", "отчёт", "дайджест", "недел")):
        return {"reply": _final_chat_digest(tasks, scope_label)}

    history = context.get("history") or []
    prompt_parts = [
        _task_context_for_chat(tasks, scope_label, message),
    ]
    if history:
        prompt_parts.append("Недавняя история диалога:\n" + _history_text(history))
    prompt_parts.append("Текущий вопрос пользователя: " + message)

    llm = await _ask_llm("\n\n".join(prompt_parts), CHAT_SYSTEM_PROMPT)
    if llm:
        return {"reply": llm}

    relevant = _relevant_tasks_for_message(tasks, message, limit=5)
    if relevant:
        return {"reply": "Нашёл похожие задачи:\n" + "\n".join(_task_line(task) for task in relevant)}

    return {
        "reply": (
            "Не удалось получить ответ модели. По данным задач я не нашёл прямого совпадения с запросом. "
            "Уточните название задачи, сотрудника, отдел или период."
        )
    }
