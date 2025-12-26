"""
Health Check and Actuator Routes
Equivalent to Spring Boot actuator endpoints
"""
import logging
from fastapi import APIRouter
from app.core.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/actuator", tags=["Actuator"])
