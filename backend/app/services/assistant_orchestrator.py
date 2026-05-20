import re
import uuid
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.telegram import TelegramSession
from app.models.task import Task
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


def _pending_action(action_type: str, **payload) -> dict:
    return {"type": action_type, "action_id": str(uuid.uuid4()), **payload}


def _detect_intent(message: str) -> Optional[str]:
    text = message.lower().strip()
    command_map = {
        "/my": "my_tasks",
        "/week": "week_tasks",
        "/deadlines": "deadlines",
        "/risks": "risks",
        "/team": "team_digest",
        "/overload": "overload",
    }
    if text in command_map:
        return command_map[text]
    if any(part in text for part in ("мои задачи", "что у меня", "что делать")):
        return "my_tasks"
    if any(part in text for part in ("на неделю", "этой неделе")):
        return "deadlines" if any(word in text for word in ("горит", "дедлайн", "сроч")) else "week_tasks"
    if any(part in text for part in ("что горит", "дедлайн", "срочн")):
        return "deadlines"
    if "комментар" in text and any(word in text for word in ("добав", "напиш", "остав")):
        return "add_comment"
    if "прогресс" in text or re.search(r"\b\d{1,3}\s*%", text):
        return "update_progress"
    if any(part in text for part in ("заверши", "закрой", "закрыть задачу", "готово")):
        return "complete_task"
    if any(part in text for part in ("подробнее", "детали", "покажи задачу")):
        return "task_details"
    if any(part in text for part in ("создай задачу", "создать задачу", "поставь задачу")):
        return "create_task"
    if any(part in text for part in ("сводка", "дайджест", "отчет", "отчёт")):
        return "team_digest"
    if any(part in text for part in ("риск", "сорваться", "просроч")):
        return "risks"
    if any(part in text for part in ("перегруж", "нагрузка", "загрузка сотрудников")):
        return "overload"
    return None


async def _llm_intent(message: str) -> Optional[str]:
    prompt = (
        "Определи intent сообщения пользователя для системы задач. "
        "Верни JSON {\"intent\":\"...\"}. Возможные intent: my_tasks, week_tasks, deadlines, "
        "add_comment, update_progress, complete_task, task_details, team_digest, risks, overload, "
        "overdue, create_task, unknown.\n"
        f"Сообщение: {message}"
    )
    response = await get_llm_provider().generate(prompt, json_mode=True, temperature=0)
    parsed = extract_json_object(response or "")
    intent = (parsed or {}).get("intent")
    return intent if intent and intent != "unknown" else None


def _extract_ordinal_ref(message: str) -> Optional[str]:
    text = message.lower()
    for word in tools.ORDINALS:
        if re.search(rf"\b{re.escape(word)}\b", text):
            return word
    return None


def _extract_comment(message: str) -> str:
    comment = tools.extract_inline_comment(message)
    if comment:
        return comment
    if ":" in message:
        return message.split(":", 1)[1].strip()
    match = re.search(r"комментар(?:ий|ия|ий)?\s+(.+)$", message, re.IGNORECASE)
    return match.group(1).strip() if match else ""


def _format_tasks(title: str, tasks: list[Task], intent: str) -> AssistantResponse:
    if not tasks:
        return AssistantResponse(text=f"{title}\n\nЗадач не найдено.", intent=intent, task_ids=[])
    lines = [title, ""]
    for index, task in enumerate(tasks, 1):
        lines.append(tools.task_to_line(task, index))
    return AssistantResponse(text="\n".join(lines), intent=intent, task_ids=[task.id for task in tasks])


def _missing_action_param(message: str, intent: str, task_ids: Optional[list[UUID]] = None) -> AssistantResponse:
    return AssistantResponse(text=message, intent=intent, task_ids=task_ids or [])


async def handle_message(
    db: Session,
    user: User,
    message: str,
    channel: str = "web",
    session: Optional[TelegramSession] = None,
) -> AssistantResponse:
    intent = _detect_intent(message) or await _llm_intent(message)

    if intent == "my_tasks":
        return _format_tasks("Ваши активные задачи:", tools.get_my_tasks(db, user), intent)

    if intent == "week_tasks":
        return _format_tasks("Ваши задачи на ближайшую неделю:", tools.get_my_tasks(db, user, period="week"), intent)

    if intent == "deadlines":
        return _format_tasks("Что горит на этой неделе:", tools.get_deadlines(db, user, days=7), intent)

    if intent == "overdue":
        return _format_tasks("Просроченные задачи:", tools.get_overdue_tasks(db, user), intent)

    if intent == "task_details":
        task = tools.get_task_details(db, user, _extract_ordinal_ref(message) or message, session)
        if not task:
            return AssistantResponse(text="Не нашёл задачу в доступном вам контексте.", intent=intent)
        body = tools.task_to_line(task)
        if task.description:
            body += f"\nОписание: {task.description}"
        return AssistantResponse(text=body, intent=intent, task_ids=[task.id])

    if intent == "risks":
        tasks = tools.get_team_risks(db, user)
        return _format_tasks("Задачи в зоне риска:", tasks, intent)

    if intent == "team_digest":
        digest = tools.get_team_digest(db, user)
        overload = ""
        if any(word in message.lower() for word in ("перегруж", "нагруз", "загруз")):
            rows = tools.get_overload(db, user)[:5]
            if rows:
                overload_lines = ["", "Загрузка сотрудников:"]
                for row in rows:
                    workload = row["workload"]
                    overload_lines.append(
                        f"- {row['user'].full_name}: {workload['capacity_util']:.0f}%, "
                        f"открытых задач {workload['open_tasks']}, в риске {workload['at_risk_count']}"
                    )
                overload = "\n".join(overload_lines)
        return AssistantResponse(text=digest + overload, intent=intent)

    if intent == "overload":
        rows = tools.get_overload(db, user)
        if not rows:
            return AssistantResponse(text="Нет данных по загрузке в доступной вам области.", intent=intent)
        lines = ["Загрузка сотрудников:"]
        for row in rows[:8]:
            workload = row["workload"]
            lines.append(
                f"- {row['user'].full_name}: {workload['capacity_util']:.0f}%, "
                f"открытых задач {workload['open_tasks']}, просрочено {workload['overdue_count']}"
            )
        return AssistantResponse(text="\n".join(lines), intent=intent)

    if intent == "add_comment":
        comment = _extract_comment(message)
        task = tools.resolve_task_ref(db, user, _extract_ordinal_ref(message) or message, session)
        if not task:
            return _missing_action_param(
                "Не понял, к какой задаче добавить комментарий. Укажите задачу явно или используйте номер из последнего списка: `добавь комментарий ко второй: текст`.",
                intent,
            )
        if not comment:
            return _missing_action_param(
                "Не хватает текста комментария. Напишите его после двоеточия: `добавь комментарий ко второй: жду согласование`.",
                intent,
                [task.id],
            )
        text = "\n".join([
            "Проверьте параметры действия:",
            "",
            "- Действие: добавить комментарий",
            f"- Задача: {task.title}",
            f"- Комментарий: {comment}",
            "",
            "Добавить комментарий?",
        ])
        return AssistantResponse(
            text=text,
            buttons=CONFIRM_BUTTONS,
            task_ids=[task.id],
            pending_action=_pending_action("add_comment", task_id=str(task.id), comment=comment),
            intent=intent,
        )

    if intent == "update_progress":
        progress_match = re.search(r"(\d{1,3})\s*%", message)
        task = tools.resolve_task_ref(db, user, _extract_ordinal_ref(message) or message, session)
        if not task:
            return _missing_action_param("Не понял, по какой задаче изменить прогресс. Укажите задачу или номер из последнего списка.", intent)
        if not progress_match:
            return _missing_action_param("Не хватает нового прогресса. Пример: `поставь прогресс 70% по второй`.", intent, [task.id])
        progress = max(0, min(100, int(progress_match.group(1))))
        text = "\n".join([
            "Проверьте параметры действия:",
            "",
            "- Действие: изменить прогресс",
            f"- Задача: {task.title}",
            f"- Новый прогресс: {progress}%",
            "- Комментарий: не указан, это опционально",
            "",
            "Изменить прогресс?",
        ])
        return AssistantResponse(
            text=text,
            buttons=CONFIRM_BUTTONS,
            task_ids=[task.id],
            pending_action=_pending_action("update_progress", task_id=str(task.id), progress=progress),
            intent=intent,
        )

    if intent == "complete_task":
        task = tools.resolve_task_ref(db, user, _extract_ordinal_ref(message) or message, session)
        if not task:
            return _missing_action_param("Не нашёл задачу для завершения. Укажите задачу явно или номер из последнего списка.", intent)
        text = "\n".join([
            "Проверьте параметры действия:",
            "",
            "- Действие: завершить задачу",
            f"- Задача: {task.title}",
            "- Новый статус: DONE",
            "- Комментарий: не указан, это опционально",
            "",
            "Завершить задачу?",
        ])
        return AssistantResponse(
            text=text,
            buttons=CONFIRM_BUTTONS,
            task_ids=[task.id],
            pending_action=_pending_action("complete_task", task_id=str(task.id)),
            intent=intent,
        )

    if intent == "create_task":
        text = re.sub(r"^(создай|создать|поставь)\s+задачу", "", message, flags=re.IGNORECASE).strip(" :.-") or message
        draft = await tools.parse_create_task_draft(db, user, text)
        if draft["missing"]:
            return AssistantResponse(text=tools.format_missing_create_task_fields(draft), intent=intent)
        confirmation_text = tools.format_create_task_draft(draft) + "\n\nСоздать задачу?"
        return AssistantResponse(
            text=confirmation_text,
            buttons=CONFIRM_BUTTONS,
            pending_action=_pending_action("create_task", draft=draft),
            intent=intent,
        )

    fallback = await ai_service.chat(db, message, current_user=user)
    return AssistantResponse(text=fallback.get("reply", "Не удалось подготовить ответ."), intent="fallback")


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

    # Clear before executing. This makes repeated Telegram button clicks idempotent.
    session.pending_action = None
    db.add(session)
    db.commit()

    try:
        if action_type == "add_comment":
            task_id = UUID(str(action["task_id"]))
            tools.add_task_comment(db, user, task_id, action.get("comment", ""))
            text = "Комментарий добавлен."
        elif action_type == "update_progress":
            task = tools.update_task_progress(db, user, UUID(str(action["task_id"])), int(action.get("progress", 0)))
            text = f"Прогресс задачи «{task.title}» обновлён до {task.progress}%."
        elif action_type == "complete_task":
            task = tools.complete_task(db, user, UUID(str(action["task_id"])))
            text = f"Задача «{task.title}» завершена."
        elif action_type == "create_task":
            task = await tools.create_task_from_draft(db, user, action["draft"])
            text = f"Задача «{task.title}» создана."
        else:
            text = "Неизвестное действие."
    except PermissionError:
        text = "Нет прав на выполнение действия."
    except (KeyError, ValueError):
        text = "Не удалось выполнить действие: не хватает сохраненных параметров."

    return AssistantResponse(text=text)
