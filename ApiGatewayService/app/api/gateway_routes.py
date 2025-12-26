"""
Gateway Router Module
Defines all gateway routes and integrates routing logic
"""
import logging
from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import StreamingResponse
from app.services.gateway_forwarder import forward_request

logger = logging.getLogger(__name__)
router = APIRouter()


@router.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
    tags=["Gateway"],
)
async def gateway_route(request: Request, path: str):
    """
    Universal gateway route that forwards requests to appropriate upstream services

    Args:
        request: Incoming HTTP request
        path: Path parameter (wildcard)

    Returns:
        Response from upstream service
    """
    try:
        # Get configuration
        from app.core.config import get_settings

        settings = get_settings()

        # Forward request to appropriate service
        result = await forward_request(request, timeout=settings.request_timeout_seconds)

        # Stream response content
        return StreamingResponse(
            iter([result["content"]]),
            status_code=result["status_code"],
            headers=result["headers"],
            media_type=result["headers"].get("content-type", "application/json"),
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Unexpected error in gateway route: {str(exc)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
