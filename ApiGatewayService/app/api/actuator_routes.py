"""
Health Check and Actuator Routes
Equivalent to Spring Boot actuator endpoints
"""
import logging
from fastapi import APIRouter, status
from pydantic import BaseModel
from datetime import datetime
from app.core.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/actuator", tags=["Actuator"])


class HealthResponse(BaseModel):
    """Health check response model"""

    status: str
    timestamp: str
    service: str
    version: str


class ServiceInfo(BaseModel):
    """Service information"""

    name: str
    port: int
    environment: str
    timestamp: str


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint
    Equivalent to Spring Boot /actuator/health
    """
    settings = get_settings()
    return HealthResponse(
        status="UP",
        timestamp=datetime.utcnow().isoformat(),
        service=settings.app_name,
        version="1.0.0",
    )


@router.get("/info", response_model=ServiceInfo)
async def service_info():
    """
    Service information endpoint
    Equivalent to Spring Boot /actuator/info
    """
    settings = get_settings()
    return ServiceInfo(
        name=settings.app_name,
        port=settings.server_port,
        environment=settings.environment,
        timestamp=datetime.utcnow().isoformat(),
    )
