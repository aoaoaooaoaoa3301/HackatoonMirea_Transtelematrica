"""AI service: local LLM client with rule-based fallbacks.

All public functions return deterministic results even when the LLM is unavailable.
"""
import json
import re
import logging
from datetime import date, timedelta
from typing import Optional, List
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.task import Task
from app.models.user import User
from app.models.department import Department
from app.models.enums import TaskStatus, TaskPriority, TaskType, PRIORITY_WEIGHT
from app.services.task_service import compute_user_workload, compute_period_bucket

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# LLM client
# ---------------------------------------------------------------------------

async def _ask_llm(prompt: str, system: str = "") -> Optional[str]:
    """Call the configured local LLM. Returns text or None on any failure."""
    try:
        async with httpx.AsyncClient(timeout=settings.OLLAMA_TIMEOUT) as client:
            if settings.LLM_PROVIDER == "docker_model":
                messages = []
                if system:
                    messages.append({"role": "system", "content": system})
                messages.append({"role": "user", "content": prompt})
                resp = await client.post(
                    f"{settings.DOCKER_MODEL_URL}/v1/chat/completions",
                    json={"model": settings.OLLAMA_MODEL, "messages": messages, "stream": False},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    choices = data.get("choices") or []
                    if choices:
                        return choices[0].get("message", {}).get("content", "").strip()
                logger.warning("Docker Model Runner returned status %d: %s", resp.status_code, resp.text[:500])
                return None

            body = {
                "model": settings.OLLAMA_MODEL,
                "prompt": prompt,
                "system": system,
                "stream": False,
            }
            resp = await client.post(f"{settings.OLLAMA_URL}/api/generate", json=body)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("response", "").strip()
            logger.warning("Ollama returned status %d: %s", resp.status_code, resp.text[:500])
    except Exception as e:
        logger.warning("LLM call failed: %s", e)
    return None


# ---------------------------------------------------------------------------
# DIGEST
# ---------------------------------------------------------------------------

def _gather_tasks_for_scope(db: Session, scope: str, scope_id: Optional[UUID]) -> List[Task]:
    q = db.query(Task)
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


async def digest(db: Session, scope: str, scope_id: Optional[UUID], period: str = "month") -> dict:
    tasks = _gather_tasks_for_scope(db, scope, scope_id)
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
    llm = await _ask_llm(prompt, system)

    if llm:
        try:
            parsed = json.loads(llm)
            return {"summary": parsed.get("summary", llm), "key_points": parsed.get("key_points", [])}
        except json.JSONDecodeError:
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

async def risks(db: Session, scope: str, scope_id: Optional[UUID]) -> dict:
    tasks = _gather_tasks_for_scope(db, scope, scope_id)
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
        llm = await _ask_llm(prompt)
        if llm:
            try:
                enriched = json.loads(llm)
                title_map = {e.get("title", ""): e.get("reason", "") for e in enriched}
                for item in items:
                    if item["title"] in title_map and title_map[item["title"]]:
                        item["reason"] = title_map[item["title"]]
            except (json.JSONDecodeError, TypeError):
                pass

    return {"items": items}


# ---------------------------------------------------------------------------
# OVERLOAD
# ---------------------------------------------------------------------------

async def overload(db: Session) -> dict:
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
        llm = await _ask_llm(prompt)
        if llm:
            try:
                enriched = json.loads(llm)
                name_map = {e.get("full_name", ""): e.get("suggestion", "") for e in enriched}
                for item in items:
                    if item["full_name"] in name_map and name_map[item["full_name"]]:
                        item["suggestion"] = name_map[item["full_name"]]
            except (json.JSONDecodeError, TypeError):
                pass

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
    llm = await _ask_llm(prompt)
    if llm:
        try:
            parsed = json.loads(llm)
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
        except (json.JSONDecodeError, TypeError):
            pass

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
) -> dict:
    q = db.query(User).filter(User.active == True)
    if department_id:
        q = q.filter(User.department_id == department_id)
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
        llm = await _ask_llm(prompt)
        if llm:
            try:
                enriched = json.loads(llm)
                name_map = {e.get("full_name", ""): e.get("reason", "") for e in enriched}
                for c in top:
                    if c["full_name"] in name_map and name_map[c["full_name"]]:
                        c["reason"] = name_map[c["full_name"]]
            except (json.JSONDecodeError, TypeError):
                pass

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


def _scoped_tasks(db: Session, scope: str, scope_id: Optional[UUID]) -> List[Task]:
    query = db.query(Task)
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


def _chat_overload_response(db: Session, scope: str, scope_id: Optional[UUID], scope_label: str) -> str:
    query = db.query(User).filter(User.active == True)
    if scope == "department" and scope_id:
        query = query.filter(User.department_id == scope_id)
    users = query.all()
    rows = []
    for user in users:
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
        return {"reply": _chat_overload_response(db, scope, scope_id, scope_label)}

    tasks = _scoped_tasks(db, scope, scope_id)

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


def _final_chat_overload(db: Session, scope: str, scope_id: Optional[UUID], scope_label: str) -> str:
    query = db.query(User).filter(User.active == True)
    if scope == "department" and scope_id:
        query = query.filter(User.department_id == scope_id)
    rows = []
    for user in query.all():
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
        return {"reply": _final_chat_overload(db, scope, scope_id, scope_label)}

    tasks = _scoped_tasks(db, scope, scope_id)

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


async def goal_summary(db: Session, goal_id: UUID) -> dict:
    goal = db.get(Task, goal_id)
    if not goal:
        return {"progress": 0, "risks": [], "summary": "Цель не найдена."}

    descendants = _collect_descendants(db, goal_id)
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
