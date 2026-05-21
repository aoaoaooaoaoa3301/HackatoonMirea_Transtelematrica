import json
import re
import uuid
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.task import Task
from app.models.telegram import TelegramSession
from app.models.user import User
from app.schemas.assistant import AssistantActionButton, AssistantResponse
from app.services import ai_service
from app.services import assistant_tools as tools
from app.services.llm import get_llm_provider
from app.services.llm.json_utils import extract_json_object

CONFIRM_BUTTONS = [
    AssistantActionButton(label="Да", callback_data="confirm"),
    AssistantActionButton(label="Отмена", callback_data="cancel"),
]

TOOL_NAMES = {
    "answer",
    "list_my_tasks",
    "list_week_tasks",
    "list_deadlines",
    "list_overdue",
    "task_details",
    "team_digest",
    "team_risks",
    "team_overload",
    "create_task",
    "add_comment",
    "update_progress",
    "complete_task",
}

ROUTER_PROMPT = """
Ты маршрутизатор AI-помощника системы задач. По сообщению пользователя и контексту диалога выбери один инструмент.

Инструменты:
- answer: обычный ответ без изменения БД.
- list_my_tasks: показать активные задачи пользователя.
- list_week_tasks: показать задачи пользователя на ближайшую неделю.
- list_deadlines: показать срочные дедлайны.
- list_overdue: показать просроченные задачи.
- task_details: показать детали конкретной задачи. args: {"task_ref": "..."}.
- team_digest: дать сводку по команде/доступной области.
- team_risks: показать задачи в зоне риска.
- team_overload: показать загрузку сотрудников.
- create_task: создать задачу/подзадачу или продолжить заполнение черновика. args: {"title": "...", "parent_ref": "...|null", "due_date": "YYYY-MM-DD|null", "assignee_or_department": "...|null", "assignment_empty": true|false, "priority": "LOW|MEDIUM|HIGH|CRITICAL|null", "comment": "...|null"}.
- add_comment: добавить комментарий к существующей задаче. args: {"task_ref": "...", "comment": "..."}.
- update_progress: изменить прогресс задачи. args: {"task_ref": "...", "progress": 0-100}.
- complete_task: завершить задачу. args: {"task_ref": "..."}.

Правила:
- Если пользователь просит "добавь/создай/поставь задачу", выбирай create_task, даже если внутри есть слово "комментарий".
- Если пользователь просит подзадачу, тоже выбирай create_task и заполни parent_ref. "для этой задачи" означает последнюю созданную или последнюю показанную задачу.
- Если есть незавершенный черновик create_task_draft, новые сообщения с дедлайном, приоритетом, исполнителем или комментарием обычно продолжают create_task.
- Для опасных изменений БД выбирай инструмент изменения, но не выполняй молча: backend покажет подтверждение.
- Если вопрос общий, про модель, возможности или контекст беседы, выбирай answer.

Ответь только JSON:
{"tool":"...", "args":{...}, "confidence":0.0-1.0}
"""


def _pending_action(action_type: str, **payload) -> dict:
    return {"type": action_type, "action_id": str(uuid.uuid4()), **payload}


def _format_tasks(title: str, tasks: list[Task], intent: str) -> AssistantResponse:
    if not tasks:
        return AssistantResponse(text=f"{title}\n\nЗадач не найдено.", intent=intent, task_ids=[])
    lines = [title, ""]
    for index, task in enumerate(tasks, 1):
        lines.append(tools.task_to_line(task, index))
    return AssistantResponse(text="\n".join(lines), intent=intent, task_ids=[task.id for task in tasks])


def _history_text(session: Optional[TelegramSession]) -> str:
    if not session or not session.chat_history:
        return ""
    rows = []
    for item in session.chat_history[-12:]:
        role = "Пользователь" if item.get("role") == "user" else "Ассистент"
        content = str(item.get("content") or "").strip()
        if content:
            rows.append(f"{role}: {content[:800]}")
    return "\n".join(rows)


def _pending_text(session: Optional[TelegramSession]) -> str:
    if not session or not session.pending_action:
        return "Нет."
    action = session.pending_action
    if action.get("type") == "create_task_draft":
        return "Есть незавершенный черновик создания задачи: " + json.dumps(action.get("draft") or {}, ensure_ascii=False)
    return "Есть действие на подтверждение: " + json.dumps(action, ensure_ascii=False)


def _last_tasks_text(session: Optional[TelegramSession]) -> str:
    if not session or not session.last_task_ids:
        return "Нет."
    return ", ".join(f"{index + 1}: {task_id}" for index, task_id in enumerate(session.last_task_ids[-10:]))


async def _llm_tool_call(message: str, session: Optional[TelegramSession]) -> Optional[dict[str, Any]]:
    prompt = "\n\n".join(
        part
        for part in [
            ROUTER_PROMPT,
            "Незавершенное действие:\n" + _pending_text(session),
            "Последние показанные задачи:\n" + _last_tasks_text(session),
            "История диалога:\n" + (_history_text(session) or "Нет."),
            "Сообщение пользователя:\n" + message,
        ]
        if part
    )
    try:
        raw = await get_llm_provider().generate(prompt, json_mode=True, temperature=0)
    except Exception:
        return None
    parsed = extract_json_object(raw or "")
    if not parsed:
        return None
    tool = parsed.get("tool")
    if tool not in TOOL_NAMES:
        return None
    args = parsed.get("args") if isinstance(parsed.get("args"), dict) else {}
    return {"tool": tool, "args": args, "confidence": parsed.get("confidence", 0)}


def _fallback_tool_call(message: str, session: Optional[TelegramSession]) -> dict[str, Any]:
    text = message.lower()
    if session and session.pending_action and session.pending_action.get("type") == "create_task_draft":
        return {"tool": "create_task", "args": {}, "confidence": 0}
    if "подзадач" in text and any(word in text for word in ("создай", "создать", "добавь", "добавить", "поставь")):
        return {"tool": "create_task", "args": {}, "confidence": 0}
    if re.search(r"\b(создай|создать|добавь|добавить|поставь)\s+(новую\s+)?(?:подзадачу|задачу)\b", text):
        return {"tool": "create_task", "args": {}, "confidence": 0}
    if "комментар" in text and any(word in text for word in ("добав", "остав", "напиш")):
        return {"tool": "add_comment", "args": {}, "confidence": 0}
    if "прогресс" in text or re.search(r"\b\d{1,3}\s*%", text):
        return {"tool": "update_progress", "args": {}, "confidence": 0}
    if any(word in text for word in ("заверши", "закрой", "готово")):
        return {"tool": "complete_task", "args": {}, "confidence": 0}
    if any(word in text for word in ("перегруж", "нагруз", "загруз")):
        return {"tool": "team_overload", "args": {}, "confidence": 0}
    if any(word in text for word in ("риск", "просроч")):
        return {"tool": "team_risks", "args": {}, "confidence": 0}
    if any(word in text for word in ("сводк", "отчет", "отчёт", "дайджест")):
        return {"tool": "team_digest", "args": {}, "confidence": 0}
    if any(word in text for word in ("дедлайн", "сроч", "горит")):
        return {"tool": "list_deadlines", "args": {}, "confidence": 0}
    if any(word in text for word in ("мои задачи", "что у меня")):
        return {"tool": "list_my_tasks", "args": {}, "confidence": 0}
    return {"tool": "answer", "args": {}, "confidence": 0}


def _is_cancel(message: str) -> bool:
    return message.lower().strip() in {"отмена", "отмени", "cancel", "/cancel"}


def _extract_ordinal_ref(message: str) -> Optional[str]:
    text = message.lower()
    for word in tools.ORDINALS:
        if re.search(rf"\b{re.escape(word)}\b", text):
            return word
    return None


def _extract_comment(message: str, args: dict[str, Any]) -> str:
    value = args.get("comment")
    if isinstance(value, str) and value.strip():
        return value.strip()
    comment = tools.extract_inline_comment(message)
    if comment:
        return comment
    if ":" in message:
        return message.split(":", 1)[1].strip()
    match = re.search(r"комментар(?:ий|ия|ий)?\s+(.+)$", message, re.IGNORECASE)
    return match.group(1).strip() if match else ""


def _task_ref(message: str, args: dict[str, Any]) -> Optional[str]:
    value = args.get("task_ref") or args.get("task") or args.get("title")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return _extract_ordinal_ref(message) or message


def _resolve_parent_task(
    db: Session,
    user: User,
    message: str,
    args: dict[str, Any],
    session: Optional[TelegramSession],
) -> Optional[Task]:
    parent_ref = args.get("parent_ref") or args.get("parent") or args.get("parent_task")
    lowered = message.lower()
    if not parent_ref and any(phrase in lowered for phrase in ("для этой задачи", "к этой задаче", "в этой задаче")):
        parent_ref = "__last__"
    if not parent_ref and "подзадач" in lowered:
        match = re.search(r"для\s+задачи\s+(.+?)(?:[.;]|$)", message, re.IGNORECASE)
        if match:
            parent_ref = match.group(1).strip()

    if parent_ref == "__last__":
        if session and session.last_task_ids:
            for task_id in reversed(session.last_task_ids):
                task = tools.resolve_task_ref(db, user, str(task_id), session)
                if task:
                    return task
        return None

    if isinstance(parent_ref, str) and parent_ref.strip():
        return tools.resolve_task_ref(db, user, parent_ref.strip(), session)

    return None


def _overlay_create_args(
    db: Session,
    user: User,
    draft: dict,
    args: dict[str, Any],
    message: str = "",
    session: Optional[TelegramSession] = None,
) -> dict:
    if isinstance(args.get("title"), str) and args["title"].strip():
        draft["title"] = args["title"].strip()

    if isinstance(args.get("due_date"), str) and args["due_date"].strip():
        try:
            draft["due_date"] = str(args["due_date"]).strip()
        except ValueError:
            pass

    if isinstance(args.get("priority"), str) and args["priority"].strip():
        value = args["priority"].strip().upper()
        if value in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}:
            draft["priority"] = value

    if isinstance(args.get("comment"), str) and args["comment"].strip():
        draft["comment"] = args["comment"].strip()

    if args.get("assignment_empty") is True:
        draft.update(
            {
                "assignee_id": None,
                "assignee_name": None,
                "department_id": None,
                "department_name": None,
                "assignment_empty": True,
            }
        )
    elif isinstance(args.get("assignee_or_department"), str) and args["assignee_or_department"].strip():
        assignee, department = tools.find_assignee_or_department(db, user, args["assignee_or_department"])
        if assignee or department:
            draft.update(
                {
                    "assignee_id": str(assignee.id) if assignee else None,
                    "assignee_name": assignee.full_name if assignee else None,
                    "department_id": str(department.id) if department else None,
                    "department_name": department.name if department else None,
                    "assignment_empty": False,
                }
            )

    parent = _resolve_parent_task(db, user, message, args, session)
    if parent:
        draft["parent_id"] = str(parent.id)
        draft["parent_title"] = parent.title
        draft["wants_subtask"] = True
    elif "подзадач" in message.lower() or args.get("parent_ref"):
        draft["wants_subtask"] = True

    draft["missing"] = tools._create_task_missing_fields(draft)
    return draft


async def _handle_answer(
    db: Session,
    user: User,
    message: str,
    args: dict[str, Any],
    session: Optional[TelegramSession],
) -> AssistantResponse:
    context = {}
    if session and session.chat_history:
        context["history"] = session.chat_history[-20:]
    result = await ai_service.chat(db, message, context=context, current_user=user)
    return AssistantResponse(text=result.get("reply", "Не удалось подготовить ответ."), intent="answer")


async def _handle_create_task(
    db: Session,
    user: User,
    message: str,
    args: dict[str, Any],
    session: Optional[TelegramSession],
) -> AssistantResponse:
    if _is_cancel(message):
        if session:
            session.pending_action = None
        return AssistantResponse(text="Создание задачи отменено.", intent="create_task")

    if session and session.pending_action and session.pending_action.get("type") == "create_task_draft":
        draft = await tools.merge_create_task_draft(db, user, session.pending_action.get("draft") or {}, message)
    else:
        draft = await tools.parse_create_task_draft(db, user, message)

    draft = _overlay_create_args(db, user, draft, args, message, session)
    if draft["missing"]:
        return AssistantResponse(
            text=tools.format_missing_create_task_fields(draft),
            pending_action=_pending_action("create_task_draft", draft=draft),
            intent="create_task",
        )

    return AssistantResponse(
        text=tools.format_create_task_draft(draft) + "\n\nСоздать задачу?",
        buttons=CONFIRM_BUTTONS,
        pending_action=_pending_action("create_task", draft=draft),
        intent="create_task",
    )


async def _handle_add_comment(
    db: Session,
    user: User,
    message: str,
    args: dict[str, Any],
    session: Optional[TelegramSession],
) -> AssistantResponse:
    task = tools.resolve_task_ref(db, user, _task_ref(message, args), session)
    if not task:
        return AssistantResponse(text="Не понял, к какой задаче добавить комментарий. Укажите задачу явно или номер из последнего списка.", intent="add_comment")
    comment = _extract_comment(message, args)
    if not comment:
        return AssistantResponse(text="Не хватает текста комментария. Напишите его после двоеточия.", intent="add_comment", task_ids=[task.id])
    return AssistantResponse(
        text="\n".join(
            [
                "Проверьте параметры действия:",
                "",
                "- Действие: добавить комментарий",
                f"- Задача: {task.title}",
                f"- Комментарий: {comment}",
                "",
                "Добавить комментарий?",
            ]
        ),
        buttons=CONFIRM_BUTTONS,
        task_ids=[task.id],
        pending_action=_pending_action("add_comment", task_id=str(task.id), comment=comment),
        intent="add_comment",
    )


async def _handle_update_progress(
    db: Session,
    user: User,
    message: str,
    args: dict[str, Any],
    session: Optional[TelegramSession],
) -> AssistantResponse:
    task = tools.resolve_task_ref(db, user, _task_ref(message, args), session)
    if not task:
        return AssistantResponse(text="Не понял, по какой задаче изменить прогресс.", intent="update_progress")
    progress = args.get("progress")
    if progress is None:
        match = re.search(r"(\d{1,3})\s*%", message)
        progress = int(match.group(1)) if match else None
    if progress is None:
        return AssistantResponse(text="Не хватает нового прогресса. Пример: `поставь прогресс 70% по второй`.", intent="update_progress", task_ids=[task.id])
    progress = max(0, min(100, int(progress)))
    return AssistantResponse(
        text="\n".join(
            [
                "Проверьте параметры действия:",
                "",
                "- Действие: изменить прогресс",
                f"- Задача: {task.title}",
                f"- Новый прогресс: {progress}%",
                "- Комментарий: не указан, это опционально",
                "",
                "Изменить прогресс?",
            ]
        ),
        buttons=CONFIRM_BUTTONS,
        task_ids=[task.id],
        pending_action=_pending_action("update_progress", task_id=str(task.id), progress=progress),
        intent="update_progress",
    )


async def _handle_complete_task(
    db: Session,
    user: User,
    message: str,
    args: dict[str, Any],
    session: Optional[TelegramSession],
) -> AssistantResponse:
    task = tools.resolve_task_ref(db, user, _task_ref(message, args), session)
    if not task:
        return AssistantResponse(text="Не нашёл задачу для завершения.", intent="complete_task")
    return AssistantResponse(
        text="\n".join(
            [
                "Проверьте параметры действия:",
                "",
                "- Действие: завершить задачу",
                f"- Задача: {task.title}",
                "- Новый статус: выполнена",
                "- Комментарий: не указан, это опционально",
                "",
                "Завершить задачу?",
            ]
        ),
        buttons=CONFIRM_BUTTONS,
        task_ids=[task.id],
        pending_action=_pending_action("complete_task", task_id=str(task.id)),
        intent="complete_task",
    )


async def _handle_task_details(
    db: Session,
    user: User,
    message: str,
    args: dict[str, Any],
    session: Optional[TelegramSession],
) -> AssistantResponse:
    task = tools.get_task_details(db, user, _task_ref(message, args) or message, session)
    if not task:
        return AssistantResponse(text="Не нашёл задачу в доступном вам контексте.", intent="task_details")
    body = tools.task_to_line(task)
    if task.description:
        body += f"\nОписание: {task.description}"
    return AssistantResponse(text=body, intent="task_details", task_ids=[task.id])


async def _handle_team_overload(db: Session, user: User, *_args) -> AssistantResponse:
    rows = tools.get_overload(db, user)
    if not rows:
        return AssistantResponse(text="Нет данных по загрузке в доступной вам области.", intent="team_overload")
    lines = ["Загрузка сотрудников:"]
    for row in rows[:8]:
        workload = row["workload"]
        lines.append(
            f"- {row['user'].full_name}: {workload['capacity_util']:.0f}%, "
            f"открытых задач {workload['open_tasks']}, просрочено {workload['overdue_count']}"
        )
    return AssistantResponse(text="\n".join(lines), intent="team_overload")


async def _handle_tool(
    db: Session,
    user: User,
    message: str,
    tool_call: dict[str, Any],
    session: Optional[TelegramSession],
) -> AssistantResponse:
    args = tool_call.get("args") or {}
    handlers = {
        "answer": _handle_answer,
        "create_task": _handle_create_task,
        "add_comment": _handle_add_comment,
        "update_progress": _handle_update_progress,
        "complete_task": _handle_complete_task,
        "task_details": _handle_task_details,
    }
    tool = tool_call["tool"]
    if tool in handlers:
        return await handlers[tool](db, user, message, args, session)
    if tool == "list_my_tasks":
        return _format_tasks("Ваши активные задачи:", tools.get_my_tasks(db, user), tool)
    if tool == "list_week_tasks":
        return _format_tasks("Ваши задачи на ближайшую неделю:", tools.get_my_tasks(db, user, period="week"), tool)
    if tool == "list_deadlines":
        return _format_tasks("Что горит на этой неделе:", tools.get_deadlines(db, user, days=7), tool)
    if tool == "list_overdue":
        return _format_tasks("Просроченные задачи:", tools.get_overdue_tasks(db, user), tool)
    if tool == "team_risks":
        return _format_tasks("Задачи в зоне риска:", tools.get_team_risks(db, user), tool)
    if tool == "team_digest":
        return AssistantResponse(text=tools.get_team_digest(db, user), intent=tool)
    if tool == "team_overload":
        return await _handle_team_overload(db, user)
    return await _handle_answer(db, user, message, args, session)


async def handle_message(
    db: Session,
    user: User,
    message: str,
    channel: str = "web",
    session: Optional[TelegramSession] = None,
) -> AssistantResponse:
    if _is_cancel(message) and session and session.pending_action:
        session.pending_action = None
        return AssistantResponse(text="Действие отменено.")

    tool_call = await _llm_tool_call(message, session)
    if not tool_call:
        tool_call = _fallback_tool_call(message, session)
    return await _handle_tool(db, user, message, tool_call, session)


async def execute_pending_action(db: Session, user: User, session: TelegramSession, callback_data: str) -> AssistantResponse:
    if callback_data == "cancel":
        if session.pending_action:
            session.pending_action = None
            db.add(session)
            db.commit()
        return AssistantResponse(text="Действие отменено.")

    if callback_data != "confirm" or not session.pending_action:
        return AssistantResponse(text="Нет действия, ожидающего подтверждения. Возможно, оно уже было выполнено или отменено.")

    action = dict(session.pending_action)
    action_type = action.get("type")

    session.pending_action = None
    db.add(session)
    db.commit()

    try:
        if action_type == "add_comment":
            task_id = UUID(str(action["task_id"]))
            tools.add_task_comment(db, user, task_id, action.get("comment", ""))
            text = "Комментарий добавлен."
            task_ids = [task_id]
        elif action_type == "update_progress":
            task = tools.update_task_progress(db, user, UUID(str(action["task_id"])), int(action.get("progress", 0)))
            text = f"Прогресс задачи «{task.title}» обновлён до {task.progress}%."
            task_ids = [task.id]
        elif action_type == "complete_task":
            task = tools.complete_task(db, user, UUID(str(action["task_id"])))
            text = f"Задача «{task.title}» завершена."
            task_ids = [task.id]
        elif action_type == "create_task":
            task = await tools.create_task_from_draft(db, user, action["draft"])
            text = f"Задача «{task.title}» создана."
            task_ids = [task.id]
        else:
            text = "Неизвестное действие."
            task_ids = []
    except PermissionError:
        text = "Нет прав на выполнение действия."
    except (KeyError, ValueError):
        text = "Не удалось выполнить действие: не хватает сохраненных параметров."

    return AssistantResponse(text=text, task_ids=task_ids if "task_ids" in locals() else [])
