from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def _truncate(text: str, limit: int = 40) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def inline_buttons(
    buttons: list[dict] | None = None,
    task_links: list[dict] | None = None,
) -> InlineKeyboardMarkup | None:
    """Build the inline keyboard for a bot reply.

    - `buttons` are callback buttons (e.g. confirm/cancel a pending action).
    - `task_links` are URL buttons that open a referenced task in the web app,
      so any task the assistant created or mentioned is one tap away.
    """
    rows: list[list[InlineKeyboardButton]] = []

    for button in buttons or []:
        rows.append(
            [InlineKeyboardButton(text=button["label"], callback_data=button["callback_data"])]
        )

    for link in task_links or []:
        url = link.get("url")
        if not url:
            continue
        rows.append(
            [InlineKeyboardButton(text=f"🔗 {_truncate(link.get('title', 'Открыть задачу'))}", url=url)]
        )

    if not rows:
        return None
    return InlineKeyboardMarkup(inline_keyboard=rows)
