from fastapi import APIRouter

from app.api.routes import health, login, principles, samples, users

api_router = APIRouter()
api_router.include_router(login.router)
api_router.include_router(users.router)
api_router.include_router(principles.router)
api_router.include_router(samples.router)
api_router.include_router(health.router)
