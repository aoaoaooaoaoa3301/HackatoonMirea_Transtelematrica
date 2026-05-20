from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def inline_buttons(buttons: list[dict]) -> InlineKeyboardMarkup | None:
    if not buttons:
        return None
    rows = [
        [InlineKeyboardButton(text=button["label"], callback_data=button["callback_data"])]
        for button in buttons
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)
