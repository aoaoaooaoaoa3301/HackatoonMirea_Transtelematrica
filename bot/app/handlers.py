import logging

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message

from app.backend_client import BackendClient
from app.keyboards import inline_buttons

logger = logging.getLogger(__name__)

router = Router()
client = BackendClient()

_ERROR_TEXT = "⚠️ Что-то пошло не так. Попробуйте ещё раз чуть позже."


async def _send_backend_response(message: Message, response: dict) -> None:
    await message.answer(
        response.get("text", "Нет ответа."),
        reply_markup=inline_buttons(
            response.get("buttons") or [],
            response.get("task_links") or [],
        ),
    )


async def _run_command(message: Message, text: str) -> None:
    """Run a backend command and always reply — never let an exception
    bubble up to aiogram (which would leave the update 'not handled' and
    the user without any response)."""
    try:
        response = await client.command(message.from_user.id, text)
        await _send_backend_response(message, response)
    except Exception:  # noqa: BLE001 — last-resort guard for any handler
        logger.exception("Telegram command failed: %s", text)
        await message.answer(_ERROR_TEXT)


@router.message(Command("start"))
async def start(message: Message, command: CommandObject) -> None:
    # Deep-link auth: opening https://t.me/<bot>?start=<code> (or scanning its
    # QR) launches the bot with the link code as the /start payload, so we link
    # the account automatically — no manual /link CODE needed.
    code = (command.args or "").strip()
    if code:
        try:
            response = await client.link(message.from_user, code)
            await _send_backend_response(message, response)
        except Exception:
            logger.exception("Telegram link failed")
            await message.answer(_ERROR_TEXT)
        return
    await message.answer(
        "Я Telegram-канал AI-помощника Транстелематики. "
        "Если аккаунт ещё не подключён, отсканируйте QR-код в веб-интерфейсе "
        "(страница «Telegram») или получите код и отправьте /link CODE."
    )


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    await message.answer(
        "Команды:\n"
        "/link CODE — привязать аккаунт\n"
        "/my — мои задачи\n"
        "/week — задачи на неделю\n"
        "/deadlines — ближайшие дедлайны\n"
        "/risks — задачи в зоне риска\n"
        "/team — сводка по команде\n"
        "/overload — кто перегружен\n"
        "/clear — очистить историю чата с AI\n\n"
        "Можно писать свободным текстом: например, «Что у меня горит на этой неделе?»."
    )


@router.message(Command("link"))
async def link(message: Message, command: CommandObject) -> None:
    code = (command.args or "").strip()
    if not code:
        await message.answer("Укажите код: /link CODE")
        return
    try:
        response = await client.link(message.from_user, code)
        await _send_backend_response(message, response)
    except Exception:
        logger.exception("Telegram link failed")
        await message.answer(_ERROR_TEXT)


@router.message(Command("my"))
async def my_tasks(message: Message) -> None:
    await _run_command(message, "/my")


@router.message(Command("week"))
async def week_tasks(message: Message) -> None:
    await _run_command(message, "/week")


@router.message(Command("deadlines"))
async def deadlines(message: Message) -> None:
    await _run_command(message, "/deadlines")


@router.message(Command("risks"))
async def risks(message: Message) -> None:
    await _run_command(message, "/risks")


@router.message(Command("team"))
async def team(message: Message) -> None:
    await _run_command(message, "/team")


@router.message(Command("overload"))
async def overload(message: Message) -> None:
    await _run_command(message, "/overload")


@router.message(Command("clear"))
async def clear(message: Message) -> None:
    # Backend recognises /clear and wipes the AI conversation history.
    await _run_command(message, "/clear")


@router.callback_query()
async def callback(query: CallbackQuery) -> None:
    try:
        response = await client.confirm_action(query.from_user.id, query.data or "")
        await query.message.answer(
            response.get("text", "Нет ответа."),
            reply_markup=inline_buttons(response.get("buttons") or [], response.get("task_links") or []),
        )
    except Exception:
        logger.exception("Telegram callback failed")
        await query.message.answer(_ERROR_TEXT)
    finally:
        await query.answer()


@router.message()
async def free_text(message: Message) -> None:
    await _run_command(message, message.text or "")
