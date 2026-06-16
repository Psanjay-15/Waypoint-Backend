from fastapi import APIRouter, Query

from app.api.v1.deps import DeviceDep, SessionDep
from app.domain.schemas.chat import ChatRequest, ChatResponse, ChatSuggestionsResponse
from app.domain.services.chat_service import chat_service

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest, db: SessionDep, device_id: DeviceDep) -> ChatResponse:
    return await chat_service.ask(db, body, device_id)


@router.get("/chat/suggestions", response_model=ChatSuggestionsResponse)
async def suggestions(
    from_state: str | None = Query(None, min_length=2, max_length=2),
    to_state: str | None = Query(None, min_length=2, max_length=2),
) -> ChatSuggestionsResponse:
    f = (from_state or "my current state").upper() if from_state else "my current state"
    t = (to_state or "my new state").upper() if to_state else "my new state"
    return ChatSuggestionsResponse(
        suggestions=[
            f"Do I need a new driver's license when moving from {f} to {t}, and how long do I have?",
            f"How will my income taxes change moving from {f} to {t}?",
            f"What happens to my health insurance when I move to {t}?",
            f"When and how do I register my car in {t}?",
            f"When can I register to vote in {t}?",
            f"What surprising laws should I know about before moving to {t}?",
        ]
    )
