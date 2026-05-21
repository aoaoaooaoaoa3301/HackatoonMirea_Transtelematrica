from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message

from app.backend_client import BackendClient
from app.keyboards import inline_buttons

router = Router()
client = BackendClient()


async def _send_backend_response(message: Message, response: dict) -> None:
    await message.answer(
        response.get("text", "Нет ответа."),
        reply_markup=inline_buttons(
            response.get("buttons") or [],
            response.get("task_links") or [],
        ),
    )


@router.message(Command("start"))
async def start(message: Message, command: CommandObject) -> None:
    # Deep-link auth: opening https://t.me/<bot>?start=<code> (or scanning its
    # QR) launches the bot with the link code as the /start payload, so we link
    # the account automatically — no manual /link CODE needed.
    code = (command.args or "").strip()
    if code:
        response = await client.link(message.from_user, code)
        await _send_backend_response(message, response)
        return
    await message.answer(
        "Я Telegram-канал AI-помощника Транстелематики. "
        "Если аккаунт ещё не подключён, отсканируйте QR-код в веб-интерфейсе "
        "(страница «Telegram») или получите код и отправьте /link CODE."
    )


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    await message.answer(
        "Команды: /link CODE, /my, /week, /deadlines, /risks, /team, /overload. "
        "Можно писать свободным текстом: например, «Что у меня горит на этой неделе?»."
    )


@router.message(Command("link"))
async def link(message: Message, command: CommandObject) -> None:
    code = (command.args or "").strip()
    if not code:
        await message.answer("Укажите код: /link CODE")
        return
    response = await client.link(message.from_user, code)
    await _send_backend_response(message, response)


@router.message(Command("my"))
async def my_tasks(message: Message) -> None:
    await _send_backend_response(message, await client.command(message.from_user.id, "/my"))


@router.message(Command("week"))
async def week_tasks(message: Message) -> None:
    await _send_backend_response(message, await client.command(message.from_user.id, "/week"))


@router.message(Command("deadlines"))
async def deadlines(message: Message) -> None:
    await _send_backend_response(message, await client.command(message.from_user.id, "/deadlines"))


@router.message(Command("risks"))
async def risks(message: Message) -> None:
    await _send_backend_response(message, await client.command(message.from_user.id, "/risks"))


@router.message(Command("team"))
async def team(message: Message) -> None:
    await _send_backend_response(message, await client.command(message.from_user.id, "/team"))


@router.message(Command("overload"))
async def overload(message: Message) -> None:
    await _send_backend_response(message, await client.command(message.from_user.id, "/overload"))


@router.callback_query()
async def callback(query: CallbackQuery) -> None:
    response = await client.confirm_action(query.from_user.id, query.data or "")
    await query.message.answer(response.get("text", "Нет ответа."), reply_markup=inline_buttons(response.get("buttons") or []))
    await query.answer()


@router.message()
async def free_text(message: Message) -> None:
    await _send_backend_response(message, await client.command(message.from_user.id, message.text or ""))
