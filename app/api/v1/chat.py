from datetime import datetime, timezone

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app import llm
from app.core.exceptions import UnknownStateError
from app.db import chat_logs_col, states_col
from app.domain.dataset import chat_context, chat_sources, mentioned_states, suggestions

router = APIRouter()


class ChatRequest(BaseModel):
    question: str
    fromState: str | None = None
    toState: str | None = None
    city: str | None = None


@router.post("/chat")
async def chat(body: ChatRequest) -> dict:
    to_code = (body.toState or "TX").strip().upper()
    to_doc = await states_col().find_one({"_id": to_code})
    if to_doc is None:
        raise UnknownStateError(f"No data for state '{to_code}'")

    from_doc = None
    if body.fromState:
        from_doc = await states_col().find_one({"_id": body.fromState.strip().upper()})
    from_name = from_doc["name"] if from_doc else "your current state"

    state_docs = await states_col().find({}).to_list(length=100)
    prompt_states = mentioned_states(body.question, state_docs)
    context = chat_context(to_doc, from_name, body.city, prompt_states)
    answer = await llm.ask(body.question, context)  # raises LLMError -> 502
    sources = chat_sources(body.question, to_doc["name"], [s["name"] for s in prompt_states])

    await chat_logs_col().insert_one(
        {
            "question": body.question,
            "from_state": body.fromState,
            "to_state": to_code,
            "city": body.city,
            "prompt_states": [s["code"] for s in prompt_states],
            "answer": answer,
            "created_at": datetime.now(timezone.utc),
        }
    )
    return {"answer": answer, "sources": sources}


@router.get("/chat/suggestions")
async def chat_suggestions(to: str = Query("TX")) -> dict:
    doc = await states_col().find_one({"_id": to.strip().upper()})
    name = doc["name"] if doc else "your new state"
    return {"suggestions": suggestions(name)}
