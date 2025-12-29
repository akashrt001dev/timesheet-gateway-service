"""
Gateway Router Module - Comprehensive Reverse Proxy Implementation

This module defines all gateway routes and integrates intelligent routing logic.
Routes requests to appropriate upstream services based on path prefixes.

Routing configuration:
- "/" and frontend paths → https://smmc-io-prod.timesmart.io
- "/user-management-service/**" → http://localhost:8001
- "/contract-managment-service/**" → http://localhost:8002
- "/entity-service/**" → http://localhost:8003
- "/timesheet-management-service/**" → http://localhost:8004

All HTTP methods are supported: GET, POST, PUT, PATCH, DELETE, OPTIONS, HEAD
"""
import logging
from typing import Dict, Optional, Tuple
from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import StreamingResponse, RedirectResponse
import httpx
from urllib.parse import urlparse, urljoin, quote

logger = logging.getLogger(__name__)
router = APIRouter()

# HTTP client configuration
HTTPX_TIMEOUT = 30.0
HTTPX_CLIENT_CONFIG = {
    "timeout": HTTPX_TIMEOUT,
    "follow_redirects": True,
    "limits": httpx.Limits(max_keepalive_connections=100, max_connections=100),
}

# Frontend configuration
FRONTEND_URL = "https://smmc-io-prod.timesmart.io"

# Static file extensions that bypass backend proxying
STATIC_EXTENSIONS = {
    '.js', '.css', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico',
    '.woff', '.woff2', '.ttf', '.eot', '.map', '.json', '.html',
    '.wav', '.mp3', '.mp4', '.webm', '.pdf', '.doc', '.docx'
}

# Upstream service mappings
UPSTREAM_SERVICES: Dict[str, str] = {
    "user-management-service": "http://localhost:8001",
    "contract-managment-service": "http://localhost:8002",
    "contract-management-service": "http://localhost:8002",
    "entity-service": "http://localhost:8003",
    "timesheet-management-service": "http://localhost:8004",
}

# Route predicates mapping path prefixes to service identifiers
ROUTE_PREDICATES: Dict[str, str] = {
    "/user-management-service": "user-management-service",
    "/auth": "user-management-service",
    "/user": "user-management-service",
    "/roles": "user-management-service",
    "/contract-managment-service": "contract-managment-service",
    "/contract-management-service": "contract-management-service",
    "/contracts": "contract-managment-service",
    "/entity-service": "entity-service",
    "/entity": "entity-service",
    "/app/entitySitePortal": "entity-service",
    "/timesheet-management-service": "timesheet-management-service",
    "/timesheet": "timesheet-management-service",
    "/activity": "timesheet-management-service",
}


def is_static_file(path: str) -> bool:
    """
    Check if a path represents a static file based on extension.
    
    Args:
        path: Request path
        
    Returns:
        True if path has a static file extension
    """
    return any(path.lower().endswith(ext) for ext in STATIC_EXTENSIONS)


def determine_target_service(path: str) -> Optional[Tuple[str, str]]:
    """
    Determine the target upstream service and base URL for a given path.
    
    Uses a priority-based matching system:
    1. Exact prefix matching from ROUTE_PREDICATES
    2. Falls back to frontend for root paths
    
    Args:
        path: Request path (e.g., "/user-management-service/api/users")
        
    Returns:
        Tuple of (service_identifier, service_url) or (None, None) if no match
    """
    # Check each route predicate in priority order
    # Sort by length descending to match longest prefix first
    sorted_predicates = sorted(
        ROUTE_PREDICATES.items(),
        key=lambda x: len(x[0]),
        reverse=True
    )
    
    for prefix, service_id in sorted_predicates:
        if path.startswith(prefix):
            service_url = UPSTREAM_SERVICES.get(service_id)
            if service_url:
                return service_id, service_url
    
    # Root path or unmatched paths → frontend
    if path == "/" or path.startswith("/"):
        return "frontend", FRONTEND_URL
    
    return None, None


def rewrite_path_for_upstream(path: str, service_id: str) -> str:
    """
    Rewrite the path for upstream service forwarding.
    
    Removes the service prefix from the path so the upstream service
    receives the correct resource path.
    
    Examples:
        /user-management-service/api/users → /api/users
        /auth/login → /login
        /contract-managment-service/v1/contracts → /v1/contracts
        
    Args:
        path: Original request path
        service_id: Target service identifier
        
    Returns:
        Rewritten path for upstream service
    """
    # Find the longest matching prefix to remove
    sorted_predicates = sorted(
        [(k, v) for k, v in ROUTE_PREDICATES.items() if v == service_id],
        key=lambda x: len(x[0]),
        reverse=True
    )
    
    for prefix, _ in sorted_predicates:
        if path.startswith(prefix):
            # Remove prefix and ensure path starts with /
            rewritten = path[len(prefix):]
            if not rewritten:
                return "/"
            if not rewritten.startswith("/"):
                rewritten = "/" + rewritten
            return rewritten
    
    # Fallback: return original path
    return path


async def proxy_request(
    request: Request,
    upstream_url: str,
    upstream_path: str,
    timeout: float = HTTPX_TIMEOUT
) -> Tuple[int, Dict[str, str], bytes]:
    """
    Forward an HTTP request to an upstream service.
    
    This is the core proxy helper function that handles:
    - All HTTP methods (GET, POST, PUT, PATCH, DELETE, OPTIONS, HEAD)
    - Header forwarding (excluding hop-by-hop headers)
    - Query parameter preservation
    - Request body forwarding
    - Response handling with proper headers
    
    Args:
        request: Incoming FastAPI request
        upstream_url: Base URL of upstream service (e.g., "http://localhost:8001")
        upstream_path: Path to forward (e.g., "/api/users")
        timeout: Request timeout in seconds
        
    Returns:
        Tuple of (status_code, headers_dict, response_body)
        
    Raises:
        HTTPException: If the request cannot be forwarded
    """
    # Build full upstream URL with query parameters
    target_url = urljoin(upstream_url, upstream_path)
    if request.url.query:
        target_url = f"{target_url}?{request.url.query}"
    
    # Prepare headers for forwarding
    # Exclude hop-by-hop and host headers
    hop_by_hop_headers = {
        "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
        "te", "trailers", "transfer-encoding", "upgrade", "host"
    }
    
    forward_headers: Dict[str, str] = {}
    for header_name, header_value in request.headers.items():
        if header_name.lower() not in hop_by_hop_headers:
            forward_headers[header_name] = header_value
    
    # Add correlation ID if present (from middleware)
    if "correlation_id" in request.scope:
        forward_headers["X-Correlation-ID"] = request.scope["correlation_id"]
    
    # Read request body if present
    body = b""
    if request.method.upper() in {"POST", "PUT", "PATCH"}:
        body = await request.body()
    
    try:
        logger.info(
            f"Proxying {request.method} {request.url.path} → {target_url}",
            extra={"correlation_id": request.scope.get("correlation_id", "N/A")}
        )
        
        # Create async HTTP client and forward request
        async with httpx.AsyncClient(**HTTPX_CLIENT_CONFIG) as client:
            response = await client.request(
                method=request.method.upper(),
                url=target_url,
                headers=forward_headers,
                content=body if body else None,
            )
        
        # Extract response headers (exclude hop-by-hop headers)
        response_headers = {
            k: v for k, v in response.headers.items()
            if k.lower() not in hop_by_hop_headers
        }
        
        logger.debug(
            f"Received {response.status_code} from upstream",
            extra={"correlation_id": request.scope.get("correlation_id", "N/A")}
        )
        
        return response.status_code, response_headers, response.content
        
    except httpx.TimeoutException as e:
        logger.error(
            f"Timeout proxying to {upstream_url}: {str(e)}",
            extra={"correlation_id": request.scope.get("correlation_id", "N/A")}
        )
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Gateway timeout - upstream service did not respond in time",
        )
    except httpx.ConnectError as e:
        logger.error(
            f"Connection error to {upstream_url}: {str(e)}",
            extra={"correlation_id": request.scope.get("correlation_id", "N/A")}
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service unavailable - cannot connect to upstream service",
        )
    except Exception as e:
        logger.exception(
            f"Error proxying request to {upstream_url}: {str(e)}",
            extra={"correlation_id": request.scope.get("correlation_id", "N/A")}
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Bad gateway - error forwarding request to upstream service",
        )


@router.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
    tags=["Gateway"],
)
async def gateway_route(request: Request, path: str = ""):
    """
    Universal gateway route handler.
    
    This is the catch-all route that handles ALL requests to the gateway.
    It determines the target upstream service based on the request path,
    forwards the request, and returns the upstream response.
    
    Supports all standard HTTP methods and properly handles:
    - JavaScript, CSS, and other static assets
    - Service worker requests
    - Frontend redirects
    - API request forwarding
    - Multipart form data
    - JSON payloads
    
    Args:
        request: Incoming HTTP request
        path: Request path (wildcard parameter)
        
    Returns:
        StreamingResponse with upstream service's response
        
    Raises:
        HTTPException: For routing failures or upstream errors
    """
    # Normalize path
    full_path = f"/{path}" if path else "/"
    
    try:
        # Determine target service
        service_id, service_url = determine_target_service(full_path)
        
        if not service_url:
            logger.warning(
                f"No route found for path: {full_path}",
                extra={"correlation_id": request.scope.get("correlation_id", "N/A")}
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No route found for {full_path}",
            )
        
        # Special handling for frontend root
        if service_id == "frontend":
            if full_path == "/" or is_static_file(full_path):
                # For root path, proxy to frontend
                upstream_path = full_path
            else:
                # Non-static paths at root also go to frontend
                upstream_path = full_path
        else:
            # Rewrite path for backend services (remove service prefix)
            upstream_path = rewrite_path_for_upstream(full_path, service_id)
        
        # Forward request to upstream service
        status_code, response_headers, response_body = await proxy_request(
            request=request,
            upstream_url=service_url,
            upstream_path=upstream_path,
        )
        
        # Return response from upstream service
        return StreamingResponse(
            iter([response_body]),
            status_code=status_code,
            headers=response_headers,
            media_type=response_headers.get("content-type", "application/octet-stream"),
        )
    
    except HTTPException:
        # Re-raise HTTP exceptions (already formatted)
        raise
    except Exception as exc:
        logger.exception(
            f"Unexpected error in gateway route handler: {str(exc)}",
            extra={"correlation_id": request.scope.get("correlation_id", "N/A")}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
