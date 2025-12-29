"""
Gateway Request Forwarding Utility Module

This module provides utility functions for forwarding HTTP requests to upstream services.
It's used by the gateway router to proxy requests with proper header handling.

Since gateway_routes.py handles the main routing logic, this module provides
supporting utilities for request forwarding, header management, and error handling.
"""
import logging
from typing import Dict, Optional
from urllib.parse import urljoin

import httpx
from fastapi import Request, HTTPException, status

logger = logging.getLogger(__name__)

# Hop-by-hop headers that should not be forwarded
HOP_BY_HOP_HEADERS = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "host",
}


def prepare_forward_headers(request: Request) -> Dict[str, str]:
    """
    Prepare headers for forwarding to upstream service.
    
    This implements TokenRelay behavior from Spring Cloud Gateway:
    - Forward ALL headers including Authorization
    - Remove only hop-by-hop headers
    - Preserve request identity headers
    - Add correlation ID if available
    
    Args:
        request: Incoming FastAPI request
        
    Returns:
        Dictionary of headers to forward
    """
    forward_headers: Dict[str, str] = {}
    
    # Forward all headers except hop-by-hop
    for header_name, header_value in request.headers.items():
        if header_name.lower() not in HOP_BY_HOP_HEADERS:
            forward_headers[header_name] = header_value
    
    # Add correlation ID from request scope (from middleware)
    if "correlation_id" in request.scope:
        forward_headers["X-Correlation-ID"] = request.scope["correlation_id"]
    
    return forward_headers


def filter_response_headers(headers: Dict[str, str]) -> Dict[str, str]:
    """
    Filter response headers for returning to client.
    
    Removes hop-by-hop headers that should not be sent back to clients.
    
    Args:
        headers: Headers from upstream response
        
    Returns:
        Filtered headers safe to send to client
    """
    return {
        k: v for k, v in headers.items()
        if k.lower() not in HOP_BY_HOP_HEADERS
    }


async def get_request_body(request: Request) -> bytes:
    """
    Get request body for HTTP methods that have bodies.
    
    Args:
        request: Incoming request
        
    Returns:
        Request body as bytes (empty if no body)
    """
    if request.method.upper() in {"POST", "PUT", "PATCH"}:
        return await request.body()
    return b""


def build_upstream_url(
    base_url: str,
    path: str,
    query_string: Optional[str] = None,
) -> str:
    """
    Build complete upstream service URL.
    
    Args:
        base_url: Base URL of upstream service (e.g., "http://localhost:8001")
        path: Request path (e.g., "/login")
        query_string: Query string if present (e.g., "page=1&limit=10")
        
    Returns:
        Complete URL for upstream request
    """
    full_url = urljoin(base_url, path)
    if query_string:
        full_url = f"{full_url}?{query_string}"
    return full_url
