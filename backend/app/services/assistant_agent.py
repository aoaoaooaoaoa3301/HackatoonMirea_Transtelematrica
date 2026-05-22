import asyncio
import hashlib
import json
import re
import time
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import _get_subdepartment_ids, apply_task_scope, user_can_access_task
from app.models.assistant import AssistantConversation, AssistantMessage, AssistantPendingAction
from app.models.department import Department
from app.models.enums import TaskPriority, TaskStatus, TaskType
from app.models.task import Task, TaskComment
from app.models.user import User
from app.schemas.assistant import AssistantActionButton
from app.services import assistant_tools as legacy_tools
from app.services.llm import get_llm_provider
from app.services.llm.base import NullLLMProvider
from app.services.llm.json_utils import extract_json_object
from app.services.task_service import infer_child_type, log_history, recompute_parent_progress


MAX_TOOL_ROUNDS = 2
READ_TOOLS = {
    "search_tasks",
    "get_task_details",
    "list_departments",
    "list_users",
    "get_team_risks",
    "get_team_overload",
    "get_task_tree",
    "get_recent_context",
}
WRITE_ACTIONS = {
    "create_task",
    "create_subtask",
    "update_task_assignment",
    "update_task_progress",
    "complete_task",
    "delete_task",
    "add_task_comment",
}

STATUS_LABELS = {
    TaskStatus.NEW: "новая",
    TaskStatus.IN_PROGRESS: "в работе",
    TaskStatus.REVIEW: "на согласовании",
    TaskStatus.DONE: "выполнена",
    TaskStatus.OVERDUE: "просрочена",
}

PRIORITY_LABELS = {
    TaskPriority.LOW: "низкий",
    TaskPriority.MEDIUM: "средний",
    TaskPriority.HIGH: "высокий",
    TaskPriority.CRITICAL: "критический",
}

TASK_TYPE_LABELS = {
    TaskType.GOAL: "цель",
    TaskType.EPIC: "эпик",
    TaskType.TASK: "задача",
    TaskType.SUBTASK: "подзадача",
}

ROLE_LABELS = {
    "EMPLOYEE": "сотрудник",
    "LEAD": "руководитель",
    "ADMIN": "администратор",
}

CODE_LABELS = {
    "NEW": "новая",
    "IN_PROGRESS": "в работе",
    "REVIEW": "на согласовании",
    "DONE": "выполнена",
    "OVERDUE": "просрочена",
    "LOW": "низкий",
    "MEDIUM": "средний",
    "HIGH": "высокий",
    "CRITICAL": "критический",
    "GOAL": "цель",
    "EPIC": "эпик",
    "TASK": "задача",
    "SUBTASK": "подзадача",
    "EMPLOYEE": "сотрудник",
    "LEAD": "руководитель",
    "ADMIN": "администратор",
}


def _localize_enum_codes(text: str) -> str:
    result = text
    for code, label in sorted(CODE_LABELS.items(), key=lambda item: len(item[0]), reverse=True):
        result = re.sub(rf"\b{re.escape(code)}\b", label, result)
    return result


def _status_label(status: TaskStatus | str | None) -> str:
    if isinstance(status, TaskStatus):
        return STATUS_LABELS.get(status, status.value)
    if isinstance(status, str):
        try:
            return STATUS_LABELS.get(TaskStatus(status), status.lower())
        except ValueError:
            return status
    return str(status or "не указан")


def _priority_label(priority: TaskPriority | str | None) -> str:
    if isinstance(priority, TaskPriority):
        return PRIORITY_LABELS.get(priority, priority.value.lower())
    if isinstance(priority, str):
        try:
            return PRIORITY_LABELS.get(TaskPriority(priority), priority.lower())
        except ValueError:
            return priority
    return "не указан"


def _task_type_label(task_type: TaskType | str | None) -> str:
    if isinstance(task_type, TaskType):
        return TASK_TYPE_LABELS.get(task_type, task_type.value.lower())
    if isinstance(task_type, str):
        try:
            return TASK_TYPE_LABELS.get(TaskType(task_type), task_type.lower())
        except ValueError:
            return task_type
    return "не указан"

AGENT_SYSTEM_PROMPT = """
Ты AI-помощник в системе управления задачами компании Транстелематика.

Главная задача: понимать свободный русский текст пользователя, поддерживать диалог, пользоваться инструментами и помогать с задачами. Ты не простой маршрутизатор.

Правила:
- Если вопрос общий, про тебя, модель, возможности, формулировки или объяснения, отвечай напрямую.
- Если вопрос требует фактов из БД, сначала вызывай read-tool, если нужных данных нет в контексте.
- Если пользователь хочет изменить БД, подготовь action_proposal. Backend покажет подтверждение.
- Если данных для действия не хватает, задай короткий уточняющий вопрос и сохрани уже известные данные в memory_patch.
- Не выдумывай задачи, сотрудников, отделы и дедлайны. Используй только контекст или инструменты.
- Не проси пользователя заново вводить уже известные данные.
- Если пользователь говорит "эта задача", "её", "для неё", используй active_task или последние показанные задачи.
- Для подзадачи обязательно нужен parent_id или понятная ссылка на родительскую задачу.
- В пользовательских ответах показывай статусы, приоритеты, роли и типы задач русскими словами, а не техническими кодами вроде HIGH или IN_PROGRESS.

Read tools:
- search_tasks: {"query": "строка", "limit": 10}
- get_task_details: {"task_ref": "id, номер из списка или название"}
- list_departments: {}
- list_users: {}
- get_team_risks: {}
- get_team_overload: {}
- get_task_tree: {"root_ref": "опционально"}
- get_recent_context: {}

Write actions:
- create_task: {"title": "...", "due_date": "YYYY-MM-DD|null", "priority": "LOW|MEDIUM|HIGH|CRITICAL|null", "assignee_id": "uuid|null", "department_id": "uuid|null", "assignment_empty": false, "comment": "optional"}
- create_subtask: как create_task плюс {"parent_id": "uuid|null", "parent_ref": "optional"}
- update_task_assignment: {"task_id": "uuid|null", "task_ref": "optional", "assignee_id": "uuid|null", "department_id": "uuid|null", "assignment_empty": false}
- update_task_progress: {"task_id": "uuid|null", "task_ref": "optional", "progress": 0-100, "comment": "optional"}
- complete_task: {"task_id": "uuid|null", "task_ref": "optional", "comment": "optional"}
- delete_task: {"task_id": "uuid|null", "task_ref": "optional", "comment": "optional"}. Доступно только администратору для любых задач и руководителю для задач своего отдела. Сотрудник не может удалять задачи.
- add_task_comment: {"task_id": "uuid|null", "task_ref": "optional", "comment": "..."}

Отвечай строго JSON:
{
  "mode": "answer|tool_call|action_proposal|clarification",
  "message": "текст для пользователя",
  "tool_call": {"name": "tool_name", "arguments": {}},
  "action": {"type": "action_name", "payload": {}},
  "memory_patch": {},
  "confidence": 0.0
}
"""


@dataclass
class AgentResult:
    conversation_id: UUID
    text: str
    buttons: list[AssistantActionButton]
    pending_action: Optional[dict]
    referenced_task_ids: list[UUID]
    mode: str
    model: dict[str, Any]
    message_id: Optional[UUID] = None


def _model_name() -> str:
    if settings.LLM_PROVIDER == "openai_compatible":
        return settings.OPENAI_COMPATIBLE_MODEL
    if settings.LLM_PROVIDER in {"ollama", "docker_model"}:
        return settings.OLLAMA_MODEL
    return settings.LLM_PROVIDER or "none"


def _model_state(available: bool) -> dict[str, Any]:
    return {"provider": settings.LLM_PROVIDER, "name": _model_name(), "available": available}


# Cached, real provider health. Replaces deriving "available" from a single
# conversation's stored llm_status — which made a brand-new conversation report
# the model as down, and made availability differ per user/conversation. The
# result is cached so we don't ping the provider on every page load.
_LLM_HEALTH: dict[str, Any] = {"ok": None, "ts": 0.0}


async def check_llm_available(ttl: float = 30.0) -> bool:
    """Whether the configured LLM provider currently answers. None provider →
    not available. Otherwise a short, cached ping (so the conversation status
    reflects reality rather than per-conversation state)."""
    provider = get_llm_provider()
    if isinstance(provider, NullLLMProvider):
        return False
    now = time.monotonic()
    if _LLM_HEALTH["ok"] is not None and (now - _LLM_HEALTH["ts"]) < ttl:
        return bool(_LLM_HEALTH["ok"])
    try:
        res = await asyncio.wait_for(
            provider.generate("ping", system="Ответь одним словом: OK", temperature=0.0),
            timeout=8.0,
        )
        ok = bool(res and str(res).strip())
    except Exception:
        ok = False
    _LLM_HEALTH["ok"] = ok
    _LLM_HEALTH["ts"] = now
    return ok


def _system_prompt() -> str:
    """System prompt + the assistant's *real* model identity, so it stops
    hallucinating things like "GPT-4" when asked what model it is."""
    return (
        AGENT_SYSTEM_PROMPT
        + f"\n\nФАКТ О СЕБЕ: ты работаешь на модели «{_model_name()}» "
        f"через провайдера «{settings.LLM_PROVIDER}». "
        "Если спрашивают, какая ты модель или на чём построена — назови ИМЕННО это "
        "значение модели. Никогда не выдумывай другое имя (например, GPT-4), "
        "если оно не совпадает с указанным выше."
    )


def _json_default(value: Any) -> str:
    if isinstance(value, (UUID, date, datetime)):
        return str(value)
    return str(value)


def _compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=_json_default, separators=(",", ":"))


def _get_or_create_conversation(
    db: Session,
    user: User,
    channel: str,
    conversation_id: Optional[UUID] = None,
    external_chat_id: Optional[str] = None,
) -> AssistantConversation:
    if conversation_id:
        conversation = db.get(AssistantConversation, conversation_id)
        if conversation and conversation.user_id == user.id:
            return conversation

    external = str(external_chat_id or "default")
    conversation = (
        db.query(AssistantConversation)
        .filter(
            AssistantConversation.user_id == user.id,
            AssistantConversation.channel == channel,
            AssistantConversation.external_chat_id == external,
        )
        .first()
    )
    if conversation:
        return conversation

    conversation = AssistantConversation(
        id=uuid.uuid4(),
        user_id=user.id,
        channel=channel,
        external_chat_id=external,
        working_memory={},
        llm_status="unknown",
    )
    db.add(conversation)
    db.flush()
    return conversation


def _store_message(
    db: Session,
    conversation: AssistantConversation,
    role: str,
    content: str,
    metadata: Optional[dict] = None,
) -> AssistantMessage:
    message = AssistantMessage(
        id=uuid.uuid4(),
        conversation_id=conversation.id,
        role=role,
        content=content,
        metadata_json=metadata or {},
    )
    db.add(message)
    db.flush()
    return message


def _recent_messages(db: Session, conversation: AssistantConversation, limit: int = 14) -> list[dict[str, str]]:
    rows = (
        db.query(AssistantMessage)
        .filter(AssistantMessage.conversation_id == conversation.id)
        .order_by(AssistantMessage.created_at.desc())
        .limit(limit)
        .all()
    )
    rows.reverse()
    return [{"role": row.role, "content": row.content} for row in rows]


def _task_dict(task: Task) -> dict[str, Any]:
    return {
        "id": str(task.id),
        "type": _task_type_label(task.type),
        "type_code": task.type.value,
        "title": task.title,
        "description": task.description,
        "parent_id": str(task.parent_id) if task.parent_id else None,
        "status": _status_label(task.status),
        "status_code": task.status.value,
        "progress": task.progress,
        "priority": _priority_label(task.priority),
        "priority_code": task.priority.value,
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "assignee_id": str(task.assignee_id) if task.assignee_id else None,
        "assignee_name": task.assignee.full_name if task.assignee else None,
        "department_id": str(task.assigned_department_id) if task.assigned_department_id else None,
        "department_name": task.assigned_department.name if task.assigned_department else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
    }


def _user_dict(user: User) -> dict[str, Any]:
    return {
        "id": str(user.id),
        "name": user.full_name,
        "email": user.email,
        "role": ROLE_LABELS.get(user.role.value, user.role.value),
        "role_code": user.role.value,
        "department_id": str(user.department_id) if user.department_id else None,
        "department_name": user.department.name if user.department else None,
    }


def _department_dict(department: Department) -> dict[str, Any]:
    aliases = [department.name]
    lowered = department.name.lower()
    if lowered == "ит-инфраструктура":
        aliases += ["ИТ", "IT", "айти", "инфраструктура"]
    elif lowered == "тех. поддержка":
        aliases += ["техподдержка", "техническая поддержка", "поддержка"]
    elif lowered == "отдел продаж":
        aliases += ["продажи", "sales"]
    return {
        "id": str(department.id),
        "name": department.name,
        "parent_id": str(department.parent_id) if department.parent_id else None,
        "aliases": aliases,
    }


def _scoped_tasks(db: Session, user: User) -> list[Task]:
    return apply_task_scope(db.query(Task), user, db).order_by(Task.updated_at.desc().nullslast(), Task.created_at.desc()).limit(400).all()


def _search_tasks(db: Session, user: User, query: str = "", limit: int = 10) -> list[Task]:
    query = (query or "").strip()
    base = apply_task_scope(db.query(Task), user, db)
    if not query:
        return base.order_by(Task.updated_at.desc().nullslast(), Task.created_at.desc()).limit(limit).all()

    exact_pattern = f"%{query}%"
    exact = (
        base.filter(or_(Task.title.ilike(exact_pattern), Task.description.ilike(exact_pattern)))
        .order_by(Task.updated_at.desc().nullslast(), Task.created_at.desc())
        .limit(limit)
        .all()
    )
    if len(exact) >= limit:
        return exact

    words = [word for word in re.findall(r"[\w-]+", query.lower(), flags=re.UNICODE) if len(word) > 2]
    candidates = base.order_by(Task.updated_at.desc().nullslast(), Task.created_at.desc()).limit(400).all()
    scored = []
    seen = {task.id for task in exact}
    for task in candidates:
        if task.id in seen:
            continue
        haystack = " ".join(
            part
            for part in [
                task.title or "",
                task.description or "",
                task.assignee.full_name if task.assignee else "",
                task.assigned_department.name if task.assigned_department else "",
            ]
            if part
        ).lower()
        score = sum(1 for word in words if word in haystack)
        if score:
            scored.append((score, task.updated_at or task.created_at, task))
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [*exact, *[task for _, _, task in scored[: max(0, limit - len(exact))]]]


def _memory_task_ids(conversation: AssistantConversation) -> list[str]:
    memory = conversation.working_memory or {}
    return [str(item) for item in (memory.get("last_task_ids") or []) if item]


class _SessionRef:
    def __init__(self, last_task_ids: list[str]):
        self.last_task_ids = last_task_ids


def _resolve_task(db: Session, user: User, conversation: AssistantConversation, task_id: Optional[str] = None, task_ref: Optional[str] = None) -> Optional[Task]:
    if task_id:
        try:
            task = db.get(Task, UUID(str(task_id)))
            return task if task and user_can_access_task(db, user, task) else None
        except ValueError:
            pass
    ref = task_ref or (conversation.working_memory or {}).get("active_task_id")
    return legacy_tools.resolve_task_ref(db, user, str(ref), _SessionRef(_memory_task_ids(conversation))) if ref else None


def _can_delete_task(db: Session, user: User, task: Task) -> bool:
    if user.role.value == "ADMIN":
        return True
    if user.role.value != "LEAD" or not user.department_id or not task.assigned_department_id:
        return False
    department_ids = _get_subdepartment_ids(db, user.department_id)
    return task.assigned_department_id in department_ids


def _conversation_context(db: Session, user: User, conversation: AssistantConversation, message: str, tool_results: list[dict]) -> dict[str, Any]:
    memory = conversation.working_memory or {}
    tasks = _scoped_tasks(db, user)
    relevant = _search_tasks(db, user, message, limit=16)
    if not relevant:
        relevant = tasks[:12]

    today = date.today()
    active = [task for task in tasks if task.status != TaskStatus.DONE]
    overdue = [task for task in active if task.status == TaskStatus.OVERDUE or (task.due_date and task.due_date < today)]
    risk = [task for task in active if task.due_date and 0 <= (task.due_date - today).days <= 7]

    return {
        "current_user": _user_dict(user),
        "today": today.isoformat(),
        "departments": [_department_dict(item) for item in db.query(Department).order_by(Department.name.asc()).all()],
        "users": [_user_dict(item) for item in db.query(User).filter(User.active == True).order_by(User.full_name.asc()).limit(100).all()],
        "task_stats": {"visible": len(tasks), "active": len(active), "overdue": len(overdue), "risk_7d": len(risk)},
        "working_memory": memory,
        "recent_messages": _recent_messages(db, conversation),
        "relevant_tasks": [_task_dict(task) for task in relevant],
        "tool_results": tool_results[-4:],
    }


def _apply_memory_patch(conversation: AssistantConversation, patch: Any) -> None:
    if not isinstance(patch, dict):
        return
    memory = dict(conversation.working_memory or {})
    for key, value in patch.items():
        if value is None:
            memory.pop(key, None)
        else:
            memory[key] = value
    conversation.working_memory = memory


def _set_last_tasks(conversation: AssistantConversation, tasks: list[Task]) -> None:
    if not tasks:
        return
    memory = dict(conversation.working_memory or {})
    task_ids = [str(task.id) for task in tasks]
    memory["last_task_ids"] = task_ids[:20]
    memory["active_task_id"] = task_ids[0]
    memory["active_task_title"] = tasks[0].title
    conversation.working_memory = memory


async def _ask_agent(prompt: str) -> tuple[Optional[dict[str, Any]], bool]:
    try:
        raw = await get_llm_provider().generate(prompt, system=_system_prompt(), json_mode=True, temperature=0.1)
    except Exception:
        return None, False
    if not raw:
        return None, False
    parsed = extract_json_object(raw)
    if not isinstance(parsed, dict):
        return None, False
    return parsed, True


def _build_agent_prompt(context: dict[str, Any], message: str) -> str:
    return (
        "Контекст ассистента:\n"
        + _compact_json(context)
        + "\n\nСообщение пользователя:\n"
        + message
        + "\n\nВерни следующий шаг строго JSON по системному протоколу."
    )


def _execute_read_tool(db: Session, user: User, conversation: AssistantConversation, name: str, args: dict[str, Any]) -> dict[str, Any]:
    args = args or {}
    if name == "search_tasks":
        tasks = _search_tasks(db, user, str(args.get("query") or ""), int(args.get("limit") or 10))
        _set_last_tasks(conversation, tasks)
        return {"tool": name, "tasks": [_task_dict(task) for task in tasks]}
    if name == "get_task_details":
        task = _resolve_task(db, user, conversation, task_ref=args.get("task_ref"))
        if task:
            _set_last_tasks(conversation, [task])
        return {"tool": name, "task": _task_dict(task) if task else None}
    if name == "list_departments":
        return {"tool": name, "departments": [_department_dict(item) for item in db.query(Department).order_by(Department.name.asc()).all()]}
    if name == "list_users":
        users = db.query(User).filter(User.active == True).order_by(User.full_name.asc()).limit(100).all()
        return {"tool": name, "users": [_user_dict(item) for item in users]}
    if name == "get_team_risks":
        tasks = legacy_tools.get_team_risks(db, user)
        _set_last_tasks(conversation, tasks)
        return {"tool": name, "tasks": [_task_dict(task) for task in tasks]}
    if name == "get_team_overload":
        rows = legacy_tools.get_overload(db, user)
        return {
            "tool": name,
            "items": [
                {
                    "user": _user_dict(row["user"]),
                    "workload": row["workload"],
                }
                for row in rows
            ],
        }
    if name == "get_task_tree":
        root = _resolve_task(db, user, conversation, task_ref=args.get("root_ref")) if args.get("root_ref") else None
        from app.services.task_service import build_tree

        return {"tool": name, "tree": build_tree(db, root.id if root else None, current_user=user)}
    if name == "get_recent_context":
        memory = conversation.working_memory or {}
        return {"tool": name, "memory": memory, "messages": _recent_messages(db, conversation)}
    return {"tool": name, "error": "unknown_tool"}


def _normalize_priority(value: Any) -> Optional[str]:
    if not value:
        return None
    text = str(value).strip().upper()
    aliases = {
        "LOW": "LOW",
        "НИЗКИЙ": "LOW",
        "MEDIUM": "MEDIUM",
        "СРЕДНИЙ": "MEDIUM",
        "HIGH": "HIGH",
        "ВЫСОКИЙ": "HIGH",
        "CRITICAL": "CRITICAL",
        "КРИТИЧЕСКИЙ": "CRITICAL",
        "КРИТ": "CRITICAL",
    }
    return aliases.get(text)


def _normalize_date(value: Any) -> Optional[str]:
    if not value:
        return None
    text = str(value).strip()
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError:
        parsed = legacy_tools.parse_due_date(text)
        return parsed.isoformat() if parsed else None


def _resolve_user_or_department(
    db: Session,
    user: User,
    payload: dict[str, Any],
) -> tuple[Optional[UUID], Optional[UUID]]:
    assignee_id = payload.get("assignee_id")
    department_id = payload.get("department_id")
    try:
        assignee_uuid = UUID(str(assignee_id)) if assignee_id else None
    except ValueError:
        assignee_uuid = None
    try:
        department_uuid = UUID(str(department_id)) if department_id else None
    except ValueError:
        department_uuid = None

    if assignee_uuid and db.get(User, assignee_uuid):
        assignee = db.get(User, assignee_uuid)
        return assignee_uuid, assignee.department_id if assignee and not department_uuid else department_uuid
    if department_uuid and db.get(Department, department_uuid):
        return None, department_uuid

    text = " ".join(str(payload.get(key) or "") for key in ("assignee", "assignee_name", "department", "department_name", "assignee_or_department"))
    if text.strip():
        assignee, department = legacy_tools.find_assignee_or_department(db, user, text)
        return (assignee.id if assignee else None), (department.id if department else (assignee.department_id if assignee else None))
    return None, None


def _missing_action_fields(action_type: str, payload: dict[str, Any]) -> list[str]:
    missing = []
    if action_type in {"create_task", "create_subtask"}:
        if not payload.get("title"):
            missing.append("название")
        if not payload.get("due_date"):
            missing.append("дедлайн")
        if not payload.get("priority"):
            missing.append("приоритет")
        if not payload.get("assignment_empty") and not payload.get("assignee_id") and not payload.get("department_id"):
            missing.append("отдел или сотрудник")
        if action_type == "create_subtask" and not payload.get("parent_id"):
            missing.append("родительская задача")
    elif action_type == "add_task_comment":
        if not payload.get("task_id"):
            missing.append("задача")
        if not payload.get("comment"):
            missing.append("комментарий")
    elif action_type == "update_task_progress":
        if not payload.get("task_id"):
            missing.append("задача")
        if payload.get("progress") is None:
            missing.append("прогресс")
    elif action_type in {"complete_task", "update_task_assignment", "delete_task"}:
        if not payload.get("task_id"):
            missing.append("задача")
    if action_type == "update_task_assignment" and not payload.get("assignment_empty") and not payload.get("assignee_id") and not payload.get("department_id"):
        missing.append("новый отдел или сотрудник")
    return missing


def _validated_action_payload(
    db: Session,
    user: User,
    conversation: AssistantConversation,
    action_type: str,
    raw_payload: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    payload = dict(raw_payload or {})

    if action_type in {"create_task", "create_subtask"}:
        payload["title"] = str(payload.get("title") or "").strip()
        payload["due_date"] = _normalize_date(payload.get("due_date"))
        payload["priority"] = _normalize_priority(payload.get("priority"))
        assignee_id, department_id = _resolve_user_or_department(db, user, payload)
        if assignee_id:
            payload["assignee_id"] = str(assignee_id)
            assignee = db.get(User, assignee_id)
            if assignee:
                payload["assignee_name"] = assignee.full_name
        if department_id:
            payload["department_id"] = str(department_id)
            department = db.get(Department, department_id)
            if department:
                payload["department_name"] = department.name
        payload["assignment_empty"] = bool(payload.get("assignment_empty"))
        if action_type == "create_subtask":
            parent = _resolve_task(db, user, conversation, task_id=payload.get("parent_id"), task_ref=payload.get("parent_ref"))
            if parent:
                payload["parent_id"] = str(parent.id)
                payload["parent_title"] = parent.title

    if action_type in {"add_task_comment", "update_task_progress", "complete_task", "update_task_assignment", "delete_task"}:
        task = _resolve_task(db, user, conversation, task_id=payload.get("task_id"), task_ref=payload.get("task_ref"))
        if task:
            payload["task_id"] = str(task.id)
            payload["task_title"] = task.title

    if action_type == "update_task_progress":
        try:
            payload["progress"] = max(0, min(100, int(payload.get("progress"))))
        except (TypeError, ValueError):
            payload["progress"] = None

    if action_type == "update_task_assignment":
        assignee_id, department_id = _resolve_user_or_department(db, user, payload)
        payload["assignment_empty"] = bool(payload.get("assignment_empty"))
        payload["assignee_id"] = str(assignee_id) if assignee_id else None
        payload["department_id"] = str(department_id) if department_id else None
        assignee = db.get(User, assignee_id) if assignee_id else None
        department = db.get(Department, department_id) if department_id else None
        payload["assignee_name"] = assignee.full_name if assignee else None
        payload["department_name"] = department.name if department else None

    if action_type == "add_task_comment":
        payload["comment"] = str(payload.get("comment") or "").strip()

    return payload, _missing_action_fields(action_type, payload)


def _action_idempotency_key(conversation: AssistantConversation, action_type: str, payload: dict[str, Any]) -> str:
    raw = _compact_json({"conversation_id": str(conversation.id), "type": action_type, "payload": payload})
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _format_action_confirmation(action_type: str, payload: dict[str, Any]) -> str:
    if action_type in {"create_task", "create_subtask"}:
        title = "Проверьте параметры новой подзадачи:" if action_type == "create_subtask" else "Проверьте параметры новой задачи:"
        assignment = "не назначать" if payload.get("assignment_empty") else payload.get("assignee_name") or payload.get("department_name")
        if not assignment:
            assignment = payload.get("assignee_id") or payload.get("department_id") or "не указано"
        lines = [
            title,
            "",
            f"- Название: {payload.get('title') or 'не указано'}",
            f"- Родительская задача: {payload.get('parent_title') or 'нет'}",
            f"- Дедлайн: {payload.get('due_date') or 'не указан'}",
            f"- Отдел/сотрудник: {assignment}",
            f"- Приоритет: {_priority_label(payload.get('priority'))}",
            f"- Комментарий: {payload.get('comment') or 'не указан, это опционально'}",
            "",
            "Создать?",
        ]
        return "\n".join(lines)
    if action_type == "add_task_comment":
        return f"Добавить комментарий к задаче «{payload.get('task_title')}»?\n\nКомментарий: {payload.get('comment')}"
    if action_type == "update_task_progress":
        return f"Изменить прогресс задачи «{payload.get('task_title')}» на {payload.get('progress')}%?"
    if action_type == "complete_task":
        return f"Завершить задачу «{payload.get('task_title')}»?"
    if action_type == "delete_task":
        return f"Удалить задачу «{payload.get('task_title')}»? Это действие нельзя отменить."
    if action_type == "update_task_assignment":
        target = (
            payload.get("assignee_name")
            or payload.get("department_name")
            or payload.get("assignee_id")
            or payload.get("department_id")
            or "оставить без назначения"
        )
        return f"Изменить назначение задачи «{payload.get('task_title')}» на {target}?"
    return "Подтвердить действие?"


def _create_pending_action(db: Session, conversation: AssistantConversation, action_type: str, payload: dict[str, Any]) -> AssistantPendingAction:
    key = _action_idempotency_key(conversation, action_type, payload)
    existing = (
        db.query(AssistantPendingAction)
        .filter(
            AssistantPendingAction.conversation_id == conversation.id,
            AssistantPendingAction.idempotency_key == key,
            AssistantPendingAction.status == "pending",
        )
        .order_by(AssistantPendingAction.created_at.desc())
        .first()
    )
    if existing:
        return existing
    action = AssistantPendingAction(
        id=uuid.uuid4(),
        conversation_id=conversation.id,
        action_type=action_type,
        payload=payload,
        status="pending",
        idempotency_key=key,
        expires_at=datetime.utcnow() + timedelta(hours=6),
    )
    db.add(action)
    db.flush()
    return action


def _buttons_for_action(action_id: UUID) -> list[AssistantActionButton]:
    return [
        AssistantActionButton(label="Да", callback_data=f"confirm:{action_id}"),
        AssistantActionButton(label="Отмена", callback_data=f"cancel:{action_id}"),
    ]


def _degraded_response(db: Session, user: User, conversation: AssistantConversation, message: str) -> AgentResult:
    text = message.lower().strip()
    referenced: list[UUID] = []
    if text in {"отмена", "отмени", "cancel", "/cancel"}:
        (
            db.query(AssistantPendingAction)
            .filter(AssistantPendingAction.conversation_id == conversation.id, AssistantPendingAction.status == "pending")
            .update({"status": "cancelled"})
        )
        reply = "Действие отменено. ИИ-модель сейчас недоступна, поэтому я работаю в ограниченном режиме."
    elif text in {"/my", "мои задачи"} or "мои задачи" in text:
        tasks = legacy_tools.get_my_tasks(db, user)
        _set_last_tasks(conversation, tasks)
        referenced = [task.id for task in tasks]
        reply = legacy_tools.task_to_line(tasks[0]) if len(tasks) == 1 else "\n".join(["Ваши активные задачи:", *[legacy_tools.task_to_line(task, idx + 1) for idx, task in enumerate(tasks)]])
    elif text in {"/risks", "/deadlines"} or any(word in text for word in ("риск", "просроч", "дедлайн")):
        tasks = legacy_tools.get_team_risks(db, user)
        _set_last_tasks(conversation, tasks)
        referenced = [task.id for task in tasks]
        reply = "\n".join(["Задачи в зоне риска:", *[legacy_tools.task_to_line(task, idx + 1) for idx, task in enumerate(tasks)]]) if tasks else "Задач в зоне риска не найдено."
    elif text in {"/overload"} or any(word in text for word in ("загруз", "перегруж")):
        rows = legacy_tools.get_overload(db, user)
        reply = "\n".join(
            ["Загрузка сотрудников:", *[f"- {row['user'].full_name}: {row['workload']['capacity_util']:.0f}%, открытых задач {row['workload']['open_tasks']}" for row in rows[:8]]]
        )
    else:
        reply = (
            "ИИ-модель временно недоступна, поэтому я перешёл в ограниченный режим. "
            "Сейчас доступны только простые команды: «мои задачи», «риски», «дедлайны», «загрузка» и отмена действия."
        )
    reply = _localize_enum_codes(reply)
    assistant_message = _store_message(db, conversation, "assistant", reply, {"mode": "degraded"})
    conversation.llm_status = "down"
    conversation.llm_recovered_notice_pending = True
    return AgentResult(conversation.id, reply, [], None, referenced, "degraded", _model_state(False), assistant_message.id)


async def process_message(
    db: Session,
    user: User,
    message: str,
    channel: str = "web",
    conversation_id: Optional[UUID] = None,
    external_chat_id: Optional[str] = None,
    context: Optional[dict] = None,
) -> AgentResult:
    conversation = _get_or_create_conversation(db, user, channel, conversation_id, external_chat_id)
    _store_message(db, conversation, "user", message, {"channel": channel, "context": context or {}})

    tool_results: list[dict[str, Any]] = []
    parsed: Optional[dict[str, Any]] = None
    llm_available = False

    for _ in range(MAX_TOOL_ROUNDS + 1):
        agent_context = _conversation_context(db, user, conversation, message, tool_results)
        if context:
            agent_context["ui_context"] = context
        parsed, llm_available = await _ask_agent(_build_agent_prompt(agent_context, message))
        if not parsed:
            break
        _apply_memory_patch(conversation, parsed.get("memory_patch"))
        mode = parsed.get("mode")
        tool_call = parsed.get("tool_call") if isinstance(parsed.get("tool_call"), dict) else {}
        tool_name = tool_call.get("name")
        if mode == "tool_call" and tool_name in READ_TOOLS:
            result = _execute_read_tool(db, user, conversation, tool_name, tool_call.get("arguments") or {})
            tool_results.append(result)
            _store_message(db, conversation, "tool", _compact_json(result), {"tool": tool_name})
            continue
        break

    if not parsed or not llm_available:
        result = _degraded_response(db, user, conversation, message)
        db.add(conversation)
        db.commit()
        return result

    recovered_prefix = ""
    if conversation.llm_status == "down" or conversation.llm_recovered_notice_pending:
        recovered_prefix = "Вам помогает ИИ-помощник. Ранее был включён ограниченный режим из-за недоступности модели.\n\n"
    conversation.llm_status = "up"
    conversation.llm_recovered_notice_pending = False

    mode = parsed.get("mode")
    if mode == "action_proposal":
        action = parsed.get("action") if isinstance(parsed.get("action"), dict) else {}
        action_type = action.get("type")
        if action_type not in WRITE_ACTIONS:
            text = recovered_prefix + (parsed.get("message") or "Не понял, какое действие нужно подготовить.")
            text = _localize_enum_codes(text)
            assistant_message = _store_message(db, conversation, "assistant", text, {"mode": "clarification"})
            db.commit()
            return AgentResult(conversation.id, text, [], None, [], "normal", _model_state(True), assistant_message.id)
        raw_payload = action.get("payload") or {}
        active_draft = (conversation.working_memory or {}).get("active_draft") or {}
        if active_draft.get("type") == action_type and isinstance(active_draft.get("payload"), dict):
            raw_payload = {**active_draft["payload"], **raw_payload}
        payload, missing = _validated_action_payload(db, user, conversation, action_type, raw_payload)
        if missing:
            memory = dict(conversation.working_memory or {})
            memory["active_draft"] = {"type": action_type, "payload": payload, "missing": missing}
            conversation.working_memory = memory
            text = recovered_prefix + f"Не хватает данных: {', '.join(missing)}. Укажите только эти параметры, остальные я уже запомнил."
            text = _localize_enum_codes(text)
            assistant_message = _store_message(db, conversation, "assistant", text, {"mode": "clarification", "missing": missing})
            db.commit()
            return AgentResult(conversation.id, text, [], None, [], "normal", _model_state(True), assistant_message.id)
        if action_type == "delete_task":
            task = db.get(Task, UUID(str(payload["task_id"]))) if payload.get("task_id") else None
            if not task or not _can_delete_task(db, user, task):
                text = recovered_prefix + "У вас нет прав на удаление этой задачи. Администратор может удалять любые задачи, руководитель — только задачи своего отдела, сотрудник не может удалять задачи."
                text = _localize_enum_codes(text)
                assistant_message = _store_message(db, conversation, "assistant", text, {"mode": "permission_denied"})
                db.commit()
                return AgentResult(conversation.id, text, [], None, [], "normal", _model_state(True), assistant_message.id)
        pending = _create_pending_action(db, conversation, action_type, payload)
        memory = dict(conversation.working_memory or {})
        memory.pop("active_draft", None)
        conversation.working_memory = memory
        text = recovered_prefix + _format_action_confirmation(action_type, payload)
        text = _localize_enum_codes(text)
        assistant_message = _store_message(db, conversation, "assistant", text, {"mode": "action_proposal", "action_id": str(pending.id)})
        db.commit()
        return AgentResult(
            conversation.id,
            text,
            _buttons_for_action(pending.id),
            {"id": str(pending.id), "type": action_type, "payload": payload},
            [UUID(str(payload["task_id"]))] if payload.get("task_id") else [],
            "normal",
            _model_state(True),
            assistant_message.id,
        )

    text = recovered_prefix + str(parsed.get("message") or "Готов помочь. Уточните, что нужно сделать.")
    text = _localize_enum_codes(text)
    referenced_tasks = []
    for result in tool_results:
        for task_data in result.get("tasks") or []:
            if task_data.get("id"):
                referenced_tasks.append(UUID(str(task_data["id"])))
        task_data = result.get("task")
        if isinstance(task_data, dict) and task_data.get("id"):
            referenced_tasks.append(UUID(str(task_data["id"])))
    assistant_message = _store_message(db, conversation, "assistant", text, {"mode": mode or "answer"})
    db.add(conversation)
    db.commit()
    return AgentResult(conversation.id, text, [], None, referenced_tasks[:20], "normal", _model_state(True), assistant_message.id)


def _execute_action(db: Session, user: User, action: AssistantPendingAction) -> tuple[str, list[UUID]]:
    payload = dict(action.payload or {})
    action_type = action.action_type
    task_ids: list[UUID] = []

    if action.status == "executed":
        result = action.result or {}
        return "Действие уже было выполнено, повторно ничего не создавалось.", [UUID(str(item)) for item in result.get("task_ids") or []]
    if action.status != "pending":
        return "Это действие уже не ожидает подтверждения.", []

    if action.expires_at and action.expires_at < datetime.utcnow():
        action.status = "expired"
        db.add(action)
        db.commit()
        return "Срок подтверждения действия истёк. Повторите команду.", []

    if action_type in {"create_task", "create_subtask"}:
        parent_id = UUID(str(payload["parent_id"])) if action_type == "create_subtask" and payload.get("parent_id") else None
        parent = db.get(Task, parent_id) if parent_id else None
        if parent_id and (not parent or not user_can_access_task(db, user, parent)):
            raise PermissionError("No access to parent task")
        assignee_id = UUID(str(payload["assignee_id"])) if payload.get("assignee_id") else None
        department_id = UUID(str(payload["department_id"])) if payload.get("department_id") else None
        if assignee_id and not department_id:
            assignee = db.get(User, assignee_id)
            department_id = assignee.department_id if assignee else None
        task = Task(
            id=uuid.uuid4(),
            type=infer_child_type(parent.type) if parent else TaskType.TASK,
            title=payload["title"],
            description=payload.get("comment"),
            parent_id=parent_id,
            due_date=date.fromisoformat(payload["due_date"]) if payload.get("due_date") else None,
            priority=TaskPriority(payload.get("priority") or TaskPriority.MEDIUM.value),
            status=TaskStatus.NEW,
            progress=0,
            assigned_department_id=department_id,
            assignee_id=assignee_id,
            created_by_id=user.id,
        )
        db.add(task)
        db.flush()
        log_history(db, task.id, "created", user.id, {"title": task.title, "channel": "assistant"})
        if payload.get("comment"):
            db.add(TaskComment(id=uuid.uuid4(), task_id=task.id, author_id=user.id, body=payload["comment"]))
            log_history(db, task.id, "comment_added", user.id, {"body": payload["comment"][:200], "channel": "assistant"})
        if task.parent_id:
            recompute_parent_progress(db, task)
        text = f"Задача «{task.title}» создана."
        task_ids = [task.id]
    elif action_type == "add_task_comment":
        task = db.get(Task, UUID(str(payload["task_id"])))
        if not task or not user_can_access_task(db, user, task):
            raise PermissionError("No access to task")
        db.add(TaskComment(id=uuid.uuid4(), task_id=task.id, author_id=user.id, body=payload["comment"]))
        log_history(db, task.id, "comment_added", user.id, {"body": payload["comment"][:200], "channel": "assistant"})
        text = "Комментарий добавлен."
        task_ids = [task.id]
    elif action_type == "update_task_progress":
        task = db.get(Task, UUID(str(payload["task_id"])))
        if not task or not user_can_access_task(db, user, task):
            raise PermissionError("No access to task")
        old = task.progress
        task.progress = int(payload["progress"])
        if task.progress == 100:
            task.status = TaskStatus.DONE
        log_history(db, task.id, "progress_updated", user.id, {"old": old, "new": task.progress, "channel": "assistant"})
        recompute_parent_progress(db, task)
        text = f"Прогресс задачи «{task.title}» обновлён до {task.progress}%."
        task_ids = [task.id]
    elif action_type == "complete_task":
        task = db.get(Task, UUID(str(payload["task_id"])))
        if not task or not user_can_access_task(db, user, task):
            raise PermissionError("No access to task")
        old = _status_label(task.status)
        task.status = TaskStatus.DONE
        task.progress = 100
        log_history(db, task.id, "status_changed", user.id, {"old": old, "new": _status_label(TaskStatus.DONE), "channel": "assistant"})
        recompute_parent_progress(db, task)
        text = f"Задача «{task.title}» завершена."
        task_ids = [task.id]
    elif action_type == "delete_task":
        task = db.get(Task, UUID(str(payload["task_id"])))
        if not task or not user_can_access_task(db, user, task) or not _can_delete_task(db, user, task):
            raise PermissionError("No access to delete task")
        task_title = task.title
        task_id = task.id
        parent = task.parent
        db.delete(task)
        db.flush()
        if parent:
            children = db.query(Task).filter(Task.parent_id == parent.id).all()
            parent.progress = int(sum(child.progress for child in children) / len(children)) if children else 0
            db.add(parent)
            recompute_parent_progress(db, parent)
        text = f"Задача «{task_title}» удалена."
        task_ids = []
    elif action_type == "update_task_assignment":
        task = db.get(Task, UUID(str(payload["task_id"])))
        if not task or not user_can_access_task(db, user, task):
            raise PermissionError("No access to task")
        task.assignee_id = UUID(str(payload["assignee_id"])) if payload.get("assignee_id") else None
        task.assigned_department_id = UUID(str(payload["department_id"])) if payload.get("department_id") else None
        log_history(db, task.id, "assignment_changed", user.id, {"channel": "assistant", "payload": payload})
        text = f"Назначение задачи «{task.title}» обновлено."
        task_ids = [task.id]
    else:
        text = "Неизвестное действие."
        task_ids = []

    action.status = "executed"
    action.result = {"text": text, "task_ids": [str(task_id) for task_id in task_ids]}
    db.add(action)
    db.commit()
    return text, task_ids


async def confirm_action(
    db: Session,
    user: User,
    action_id: UUID,
    confirm: bool,
) -> AgentResult:
    # Lock the pending-action row so two concurrent confirmations can't both
    # read status="pending" and execute the same write twice (idempotency at
    # the DB level). The second request blocks here until the first commits,
    # then sees the terminal status below and returns the stored result.
    action = (
        db.query(AssistantPendingAction)
        .filter(AssistantPendingAction.id == action_id)
        .with_for_update()
        .first()
    )
    if not action:
        return AgentResult(uuid.uuid4(), "Действие не найдено.", [], None, [], "normal", _model_state(True))
    conversation = db.get(AssistantConversation, action.conversation_id)
    if not conversation or conversation.user_id != user.id:
        return AgentResult(action.conversation_id, "Нет доступа к этому действию.", [], None, [], "normal", _model_state(True))

    # Already processed by a previous (or concurrent) confirmation.
    if action.status and action.status != "pending":
        if action.status == "executed" and isinstance(action.result, dict):
            cached = action.result.get("text", "Действие уже выполнено.")
            task_ids = [UUID(t) for t in action.result.get("task_ids", []) if t]
            return AgentResult(conversation.id, cached, [], None, task_ids, "normal", _model_state(conversation.llm_status == "up"))
        if action.status == "cancelled":
            return AgentResult(conversation.id, "Действие уже отменено.", [], None, [], "normal", _model_state(conversation.llm_status == "up"))
        return AgentResult(conversation.id, "Действие уже обработано.", [], None, [], "normal", _model_state(conversation.llm_status == "up"))

    if not confirm:
        action.status = "cancelled"
        db.add(action)
        text = "Действие отменено."
        text = _localize_enum_codes(text)
        assistant_message = _store_message(db, conversation, "assistant", text, {"mode": "cancel_action", "action_id": str(action.id)})
        db.commit()
        return AgentResult(conversation.id, text, [], None, [], "normal", _model_state(conversation.llm_status == "up"), assistant_message.id)
    try:
        text, task_ids = _execute_action(db, user, action)
        text = _localize_enum_codes(text)
        memory = dict(conversation.working_memory or {})
        if task_ids:
            memory["last_task_ids"] = [str(task_id) for task_id in task_ids]
            memory["active_task_id"] = str(task_ids[0])
            task = db.get(Task, task_ids[0])
            if task:
                memory["active_task_title"] = task.title
        memory.pop("active_draft", None)
        conversation.working_memory = memory
        assistant_message = _store_message(db, conversation, "assistant", text, {"mode": "execute_action", "action_id": str(action.id)})
        db.add(conversation)
        db.commit()
        return AgentResult(conversation.id, text, [], None, task_ids, "normal", _model_state(conversation.llm_status == "up"), assistant_message.id)
    except PermissionError:
        db.rollback()
        text = "Нет прав на выполнение действия."
    except (KeyError, ValueError):
        db.rollback()
        text = "Не удалось выполнить действие: не хватает сохранённых параметров."
    text = _localize_enum_codes(text)
    assistant_message = _store_message(db, conversation, "assistant", text, {"mode": "execute_action_error", "action_id": str(action.id)})
    db.commit()
    return AgentResult(conversation.id, text, [], None, [], "normal", _model_state(conversation.llm_status == "up"), assistant_message.id)


def latest_pending_action(db: Session, conversation: AssistantConversation) -> Optional[AssistantPendingAction]:
    return (
        db.query(AssistantPendingAction)
        .filter(AssistantPendingAction.conversation_id == conversation.id, AssistantPendingAction.status == "pending")
        .order_by(AssistantPendingAction.created_at.desc())
        .first()
    )


def clear_conversation(
    db: Session,
    user: User,
    conversation_id: Optional[UUID] = None,
    channel: str = "web",
    external_chat_id: Optional[str] = "default",
) -> AssistantConversation:
    conversation = _get_or_create_conversation(db, user, channel, conversation_id, external_chat_id)
    db.query(AssistantPendingAction).filter(AssistantPendingAction.conversation_id == conversation.id).delete(synchronize_session=False)
    db.query(AssistantMessage).filter(AssistantMessage.conversation_id == conversation.id).delete(synchronize_session=False)
    conversation.working_memory = {}
    conversation.llm_recovered_notice_pending = False
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def get_conversation_messages(db: Session, user: User, conversation_id: Optional[UUID] = None, channel: str = "web") -> tuple[AssistantConversation, list[AssistantMessage]]:
    conversation = _get_or_create_conversation(db, user, channel, conversation_id, "default")
    db.commit()
    messages = (
        db.query(AssistantMessage)
        .filter(AssistantMessage.conversation_id == conversation.id, AssistantMessage.role.in_(("user", "assistant")))
        .order_by(AssistantMessage.created_at.asc())
        .limit(80)
        .all()
    )
    return conversation, messages
