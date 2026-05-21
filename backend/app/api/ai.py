import uuid
from typing import Optional

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
    AssistantMessageRequest, AssistantMessageResponse,
    AssistantConversationResponse, AssistantConfirmResponse,
    AssistantStoredMessage,
)
from app.services import ai_service
from app.services import assistant_agent

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
    result = await assistant_agent.process_message(
        db,
        current_user,
        body.message,
        channel="web",
        context=body.context or {},
    )
    return {"reply": result.text}


@router.get("/assistant/conversation", response_model=AssistantConversationResponse)
async def assistant_conversation(
    conversation_id: Optional[uuid.UUID] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conversation, messages = assistant_agent.get_conversation_messages(db, current_user, conversation_id, channel="web")
    return {
        "conversation_id": conversation.id,
        "messages": [AssistantStoredMessage(id=item.id, role=item.role, content=item.content) for item in messages],
        "mode": "degraded" if conversation.llm_status == "down" else "normal",
        "model": {
            "provider": assistant_agent.settings.LLM_PROVIDER,
            "name": assistant_agent._model_name(),
            "available": conversation.llm_status == "up",
        },
    }


@router.post("/assistant/message", response_model=AssistantMessageResponse)
async def assistant_message(
    body: AssistantMessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await assistant_agent.process_message(
        db,
        current_user,
        body.message,
        channel="web",
        conversation_id=body.conversation_id,
        external_chat_id="default",
        context=body.context or {},
    )
    return {
        "conversation_id": result.conversation_id,
        "message_id": result.message_id,
        "text": result.text,
        "buttons": result.buttons,
        "pending_action": result.pending_action,
        "referenced_task_ids": result.referenced_task_ids,
        "mode": result.mode,
        "model": result.model,
    }


@router.delete("/assistant/conversation", response_model=AssistantConversationResponse)
async def assistant_clear_conversation(
    conversation_id: Optional[uuid.UUID] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conversation = assistant_agent.clear_conversation(db, current_user, conversation_id, channel="web", external_chat_id="default")
    return {
        "conversation_id": conversation.id,
        "messages": [],
        "mode": "degraded" if conversation.llm_status == "down" else "normal",
        "model": {
            "provider": assistant_agent.settings.LLM_PROVIDER,
            "name": assistant_agent._model_name(),
            "available": conversation.llm_status == "up",
        },
    }


@router.post("/assistant/actions/{action_id}/confirm", response_model=AssistantConfirmResponse)
async def assistant_confirm_action(
    action_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await assistant_agent.confirm_action(db, current_user, action_id, confirm=True)
    return {"text": result.text, "buttons": result.buttons, "referenced_task_ids": result.referenced_task_ids}


@router.post("/assistant/actions/{action_id}/cancel", response_model=AssistantConfirmResponse)
async def assistant_cancel_action(
    action_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await assistant_agent.confirm_action(db, current_user, action_id, confirm=False)
    return {"text": result.text, "buttons": result.buttons, "referenced_task_ids": result.referenced_task_ids}


@router.post("/goal-summary", response_model=GoalSummaryResponse)
async def ai_goal_summary(
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    goal_id = uuid.UUID(str(body.get("goal_id")))
    result = await ai_service.goal_summary(db, goal_id, current_user)
    return result
