from fastapi import APIRouter
from app.api.v1.endpoints import auth, users, knowledge, dashboard, ai, assets, stats, reservations, guests, whatsapp

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(knowledge.router, prefix="/knowledge", tags=["knowledge"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(ai.router, prefix="/ai", tags=["ai"])
api_router.include_router(assets.router, prefix="/assets", tags=["assets"])
api_router.include_router(stats.router, prefix="/stats", tags=["stats"])
api_router.include_router(reservations.router, prefix="/reservations", tags=["reservations"])
api_router.include_router(guests.router, prefix="/guests", tags=["guests"])
api_router.include_router(whatsapp.router, prefix="/whatsapp", tags=["whatsapp"])
