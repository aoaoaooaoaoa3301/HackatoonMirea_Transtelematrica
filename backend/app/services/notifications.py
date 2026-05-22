"""Best-effort Telegram notifications for task events.

Design constraints:
- Completely non-blocking: every send is wrapped in a broad try/except that
  swallows ALL exceptions and logs a warning.  A notification failure must
  never break or slow down the core API.
- Skips silently when TELEGRAM_BOT_TOKEN is empty or the target user has no
  linked Telegram account.
- Uses a SHORT httpx timeout (5 s connect + read) so an unreachable Telegram
  API never stalls a request.
- Must be called AFTER db.commit() in every endpoint so a notification error
  cannot roll back the database transaction.
"""

from __future__ import annotations

import logging
import uuid

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.telegram import TelegramAccount

logger = logging.getLogger(__name__)

_TELEGRAM_TIMEOUT = httpx.Timeout(5.0, connect=5.0)


def task_link(task_id: uuid.UUID | str) -> str:
    """Return a full URL to the task in the web app."""
    base = (settings.APP_PUBLIC_URL or "http://localhost").rstrip("/")
    return f"{base}/tasks/{task_id}"


def _get_chat_id(db: Session, user_id: uuid.UUID) -> int | None:
    """Look up the Telegram chat_id for a user via their linked account.

    For private Telegram chats the chat_id equals the telegram_user_id, so we
    reuse the value stored in TelegramAccount during the linking flow.
    Returns None if the user has no active linked Telegram account.
    """
    account = (
        db.query(TelegramAccount)
        .filter(
            TelegramAccount.user_id == user_id,
            TelegramAccount.active == True,  # noqa: E712
        )
        .first()
    )
    if account is None:
        return None
    return account.telegram_user_id


def _send_telegram_message(chat_id: int, text: str) -> None:
    """POST to the Telegram Bot API sendMessage endpoint (sync httpx).

    Swallows all exceptions so that the caller is never affected.
    """
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        with httpx.Client(timeout=_TELEGRAM_TIMEOUT) as client:
            resp = client.post(url, json=payload)
            if resp.status_code != 200:
                logger.warning(
                    "Telegram sendMessage returned %s: %s",
                    resp.status_code,
                    resp.text[:300],
                )
    except Exception:
        logger.warning("Telegram notification failed for chat_id=%s", chat_id, exc_info=True)


def notify_task_assignee(db: Session, user_id: uuid.UUID, text: str) -> None:
    """Send a best-effort Telegram notification to a user.

    - Returns immediately if TELEGRAM_BOT_TOKEN is not set.
    - Returns immediately if the user has no linked Telegram account.
    - Swallows ALL exceptions (logs a warning, never raises).
    """
    try:
        if not settings.TELEGRAM_BOT_TOKEN:
            return
        chat_id = _get_chat_id(db, user_id)
        if chat_id is None:
            return
        _send_telegram_message(chat_id, text)
    except Exception:
        logger.warning(
            "notify_task_assignee failed for user_id=%s", user_id, exc_info=True
        )
