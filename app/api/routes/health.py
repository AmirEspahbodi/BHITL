"""
Health check endpoint for Docker health checks and monitoring.
Add this to your FastAPI routes.
"""

from fastapi import APIRouter, status
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    service: str


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    tags=["health"],
)
async def health_check() -> HealthResponse:
    """
    Health check endpoint.
    Returns 200 OK if the service is running.
    """
    return HealthResponse(status="healthy", service="cogniloop-api")
