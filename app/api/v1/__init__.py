from fastapi import APIRouter

from app.api.v1 import (
    chat,
    cities,
    compare,
    cost,
    emergency,
    health,
    livability,
    places,
    plans,
    providers,
    services,
    states,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router, tags=["health"])
api_router.include_router(states.router, tags=["states"])
api_router.include_router(emergency.router, tags=["emergency"])
api_router.include_router(compare.router, tags=["compare"])
api_router.include_router(chat.router, tags=["chat"])
api_router.include_router(plans.router, tags=["plans"])
api_router.include_router(places.router, tags=["places"])
api_router.include_router(cost.router, tags=["cost"])
api_router.include_router(services.router, tags=["services"])
api_router.include_router(livability.router, tags=["livability"])
api_router.include_router(cities.router, tags=["cities"])
api_router.include_router(providers.router, tags=["providers"])
