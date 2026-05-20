import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.schemas.ai import (
    DigestRequest, DigestResponse,
    RisksRequest, RisksResponse,
    OverloadResponse,
    ParseTaskRequest, ParseTaskResponse,
    SuggestAssigneeRequest, SuggestAssigneeResponse,
    ChatRequest, ChatResponse,
    GoalSummaryResponse,
)
from app.services import ai_service

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/digest", response_model=DigestResponse)
async def ai_digest(body: DigestRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await ai_service.digest(db, body.scope, body.id, body.period or "month", current_user)
    return result


@router.post("/risks", response_model=RisksResponse)
async def ai_risks(body: RisksRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await ai_service.risks(db, body.scope, body.id, current_user)
    return result


@router.post("/overload", response_model=OverloadResponse)
async def ai_overload(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await ai_service.overload(db, current_user)
    return result


@router.post("/parse-task", response_model=ParseTaskResponse)
async def ai_parse_task(body: ParseTaskRequest, current_user: User = Depends(get_current_user)):
    result = await ai_service.parse_task(body.text)
    return result


@router.post("/suggest-assignee", response_model=SuggestAssigneeResponse)
async def ai_suggest_assignee(
    body: SuggestAssigneeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await ai_service.suggest_assignee(
        db, body.title, body.description, body.department_id, body.priority, body.due_date, current_user,
    )
    return result


@router.post("/chat", response_model=ChatResponse)
async def ai_chat(body: ChatRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await ai_service.chat(db, body.message, body.context, current_user)
    return result


@router.post("/goal-summary", response_model=GoalSummaryResponse)
async def ai_goal_summary(
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    goal_id = uuid.UUID(str(body.get("goal_id")))
    result = await ai_service.goal_summary(db, goal_id, current_user)
    return result
