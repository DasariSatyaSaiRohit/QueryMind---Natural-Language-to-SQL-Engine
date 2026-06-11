from fastapi import APIRouter
from app.api.v1.endpoints import connections, query, health, sessions

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(query.router)
api_router.include_router(health.router)
api_router.include_router(connections.router)
api_router.include_router(sessions.router)
