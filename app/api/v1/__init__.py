from fastapi import APIRouter

from app.api.v1 import chat, compare, cost, health, plans, states

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router, tags=["health"])
api_router.include_router(states.router, tags=["states"])
api_router.include_router(compare.router, tags=["compare"])
api_router.include_router(chat.router, tags=["chat"])
api_router.include_router(plans.router, tags=["plans"])
api_router.include_router(cost.router, tags=["cost"])
