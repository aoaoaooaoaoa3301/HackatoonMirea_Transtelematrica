import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_user, get_db
from app.models.telegram import TelegramAccount, TelegramLinkCode, TelegramSession
from app.models.user import User
from app.schemas.telegram import (
    TelegramCommandRequest,
    TelegramCommandResponse,
    TelegramConfirmActionRequest,
    TelegramLinkConfirmRequest,
    TelegramLinkStartResponse,
    TelegramStatusResponse,
)
from app.services import assistant_agent

router = APIRouter(prefix="/telegram", tags=["telegram"])


def require_telegram_internal_token(x_telegram_internal_token: str | None = Header(None)) -> None:
    expected = settings.TELEGRAM_INTERNAL_TOKEN
    if not expected:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Telegram internal token is not configured")
    if not secrets.compare_digest(x_telegram_internal_token or "", expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Telegram internal token")


def _new_link_code(db: Session) -> str:
    for _ in range(20):
        code = f"{secrets.randbelow(1_000_000):06d}"
        if not db.query(TelegramLinkCode).filter(TelegramLinkCode.code == code).first():
            return code
    raise HTTPException(status_code=500, detail="Cannot generate Telegram link code")


def _get_or_create_session(db: Session, telegram_user_id: int, user_id) -> TelegramSession:
    session = db.get(TelegramSession, telegram_user_id)
    if session:
        session.user_id = user_id
        return session
    session = TelegramSession(telegram_user_id=telegram_user_id, user_id=user_id, last_task_ids=[], chat_history=[])
    db.add(session)
    db.flush()
    return session


@router.get("/status", response_model=TelegramStatusResponse)
def telegram_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    account = (
        db.query(TelegramAccount)
        .filter(TelegramAccount.user_id == current_user.id, TelegramAccount.active == True)
        .order_by(TelegramAccount.updated_at.desc())
        .first()
    )
    if not account:
        return {"connected": False}
    return {
        "connected": True,
        "telegram_user_id": account.telegram_user_id,
        "telegram_username": account.telegram_username,
        "linked_at": account.linked_at,
    }


@router.post("/link/start", response_model=TelegramLinkStartResponse)
def start_telegram_link(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    code = _new_link_code(db)
    expires_at = datetime.utcnow() + timedelta(minutes=settings.TELEGRAM_LINK_CODE_TTL_MINUTES)
    entry = TelegramLinkCode(code=code, user_id=current_user.id, expires_at=expires_at)
    db.add(entry)
    db.commit()
    return {
        "code": code,
        "expires_at": expires_at,
        "instruction": f"Откройте Telegram-бота и отправьте /link {code}",
    }


@router.post("/link/confirm", response_model=TelegramCommandResponse, dependencies=[Depends(require_telegram_internal_token)])
def confirm_telegram_link(body: TelegramLinkConfirmRequest, db: Session = Depends(get_db)):
    now = datetime.utcnow()
    link_code = db.query(TelegramLinkCode).filter(TelegramLinkCode.code == body.code).first()
    if not link_code or link_code.used_at is not None:
        raise HTTPException(status_code=400, detail="Link code is invalid or already used")
    if link_code.expires_at < now:
        raise HTTPException(status_code=400, detail="Link code expired")

    account = db.query(TelegramAccount).filter(TelegramAccount.telegram_user_id == body.telegram_user_id).first()
    if not account:
        account = TelegramAccount(telegram_user_id=body.telegram_user_id, user_id=link_code.user_id)
        db.add(account)
    account.user_id = link_code.user_id
    account.telegram_username = body.username
    account.telegram_first_name = body.first_name
    account.telegram_last_name = body.last_name
    account.active = True
    link_code.used_at = now
    _get_or_create_session(db, body.telegram_user_id, link_code.user_id)
    db.commit()
    return {"text": "Telegram подключён к вашему аккаунту.", "buttons": []}


@router.post("/command", response_model=TelegramCommandResponse, dependencies=[Depends(require_telegram_internal_token)])
async def telegram_command(body: TelegramCommandRequest, db: Session = Depends(get_db)):
    account = (
        db.query(TelegramAccount)
        .filter(TelegramAccount.telegram_user_id == body.telegram_user_id, TelegramAccount.active == True)
        .first()
    )
    if not account:
        return {
            "text": "Telegram не привязан к аккаунту. Получите код в веб-интерфейсе и отправьте /link CODE.",
            "buttons": [],
        }

    user = db.get(User, account.user_id)
    if not user or not user.active:
        return {"text": "Связанный пользователь не найден или отключён.", "buttons": []}

    session = _get_or_create_session(db, body.telegram_user_id, user.id)
    response = await assistant_agent.process_message(
        db,
        user,
        body.message,
        channel="telegram",
        external_chat_id=str(body.telegram_user_id),
    )
    session.last_task_ids = [str(task_id) for task_id in response.referenced_task_ids]
    session.pending_action = response.pending_action
    session.last_intent = "assistant"
    session.last_scope = {"mode": response.mode}
    db.add(session)
    db.commit()
    return {"text": response.text, "buttons": response.buttons}


@router.post("/confirm-action", response_model=TelegramCommandResponse, dependencies=[Depends(require_telegram_internal_token)])
async def confirm_action(body: TelegramConfirmActionRequest, db: Session = Depends(get_db)):
    account = (
        db.query(TelegramAccount)
        .filter(TelegramAccount.telegram_user_id == body.telegram_user_id, TelegramAccount.active == True)
        .first()
    )
    if not account:
        return {"text": "Telegram не привязан к аккаунту.", "buttons": []}
    user = db.get(User, account.user_id)
    session = (
        db.query(TelegramSession)
        .filter(TelegramSession.telegram_user_id == body.telegram_user_id)
        .with_for_update()
        .first()
    )
    if not session:
        session = _get_or_create_session(db, body.telegram_user_id, account.user_id)

    callback_data = body.callback_data or ""
    confirm = not callback_data.startswith("cancel")
    action_id = None
    if ":" in callback_data:
        _, raw_id = callback_data.split(":", 1)
        try:
            import uuid

            action_id = uuid.UUID(raw_id)
        except ValueError:
            action_id = None
    if not action_id:
        conversation = assistant_agent._get_or_create_conversation(
            db,
            user,
            channel="telegram",
            external_chat_id=str(body.telegram_user_id),
        )
        pending = assistant_agent.latest_pending_action(db, conversation)
        action_id = pending.id if pending else None
    if not action_id:
        return {"text": "Нет действия, ожидающего подтверждения. Возможно, оно уже было выполнено или отменено.", "buttons": []}

    response = await assistant_agent.confirm_action(db, user, action_id, confirm=confirm)
    if response.referenced_task_ids:
        session.last_task_ids = [str(task_id) for task_id in response.referenced_task_ids]
        db.add(session)
        db.commit()
    return {"text": response.text, "buttons": response.buttons}
