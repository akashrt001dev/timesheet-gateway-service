"""
Gateway Service Module
Handles request forwarding to upstream services
Equivalent to Spring Cloud Gateway routing logic
"""
import logging
import re
from typing import Dict, Optional, Any
from urllib.parse import urljoin, quote
import httpx
from fastapi import Request, HTTPException, status
from app.core.config import GATEWAY_ROUTES

logger = logging.getLogger(__name__)


class GatewayForwarder:
    """
    Gateway Request Forwarder
    Routes requests to appropriate upstream services and forwards responses
    """

    def __init__(self, timeout: int = 30):
        """
        Initialize gateway forwarder

        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout
        self.routes = GATEWAY_ROUTES
        self._client: Optional[httpx.AsyncClient] = None

    async def get_client(self) -> httpx.AsyncClient:
        """
        Get or create async HTTP client

        Returns:
            httpx.AsyncClient instance
        """
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def close(self):
        """Close HTTP client connection"""
        if self._client is not None:
            await self._client.aclose()

    def get_target_service(self, path: str) -> Optional[Dict[str, Any]]:
        """
        Get target upstream service for given path

        Args:
            path: Request path

        Returns:
            Route configuration or None if no match
        """
        for route_id, route_config in self.routes.items():
            predicates = route_config.get("predicates", [])

            for predicate in predicates:
                # Convert Spring Cloud Gateway predicate to regex
                # /auth/** -> /auth/.*
                pattern = predicate.replace("/**", "/.*").replace("**", ".*")
                pattern = f"^{pattern}$"

                if re.match(pattern, path):
                    logger.debug(f"Matched route: {route_id} for path: {path}")
                    return route_config

        return None

    def rewrite_path(self, path: str, route_config: Dict[str, Any]) -> str:
        """
        Rewrite path according to route configuration

        Args:
            path: Original request path
            route_config: Route configuration with rewrites

        Returns:
            Rewritten path
        """
        rewrites = route_config.get("rewrites", {})

        for pattern, replacement in rewrites.items():
            # Convert Spring Cloud Gateway rewrite to regex
            # /auth/(?<path>.*) -> /auth/(.*)
            pattern = pattern.replace("(?<path>", "(").replace("(?<.*?>", "(")

            regex = re.compile(f"^{pattern}$")
            match = regex.match(path)

            if match:
                # Replace {path} in replacement with captured group
                rewritten = replacement.replace("${path}", match.group(1))
                logger.debug(f"Rewritten path: {path} -> {rewritten}")
                return rewritten

        return path

    def get_target_url(self, service_uri: str, rewritten_path: str) -> str:
        """
        Construct target URL from service URI and rewritten path

        Args:
            service_uri: Service URI (e.g., lb://user-management-service)
            rewritten_path: Rewritten request path

        Returns:
            Full target URL
        """
        # For load-balanced URIs (lb://service-name), use the service name
        # In production, this would be resolved by a service registry (Eureka)
        if service_uri.startswith("lb://"):
            service_name = service_uri[5:]  # Remove "lb://" prefix
            # In this implementation, we would use Eureka to resolve service name
            # For now, we use environment variable mapping
            target_url = self._resolve_service_url(service_name)
        else:
            target_url = service_uri

        return urljoin(target_url, rewritten_path)

    def _resolve_service_url(self, service_name: str) -> str:
        """
        Resolve service name to URL (from config or environment)

        Args:
            service_name: Service name to resolve

        Returns:
            Service URL
        """
        from app.core.config import get_settings

        settings = get_settings()

        # Map service names to configured URLs
        service_map = {
            "user-management-service": settings.user_service_url,
            "contract-management-service": settings.contract_service_url,
            "entity-service": settings.entity_service_url,
            "timesheet-management-service": settings.timesheet_service_url,
        }

        url = service_map.get(service_name)
        if not url:
            logger.error(f"Unknown service: {service_name}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Service {service_name} not found",
            )

        return url

    def prepare_headers(self, request: Request) -> Dict[str, str]:
        """
        Prepare headers for forwarding to upstream service

        Args:
            request: Incoming request

        Returns:
            Dictionary of headers to forward
        """
        headers = {}

        # Forward relevant headers, excluding hop-by-hop headers
        hop_by_hop_headers = {
            "connection",
            "keep-alive",
            "proxy-authenticate",
            "proxy-authorization",
            "te",
            "trailers",
            "transfer-encoding",
            "upgrade",
            "content-length",  # Will be calculated
        }

        for header_name, header_value in request.headers.items():
            if header_name.lower() not in hop_by_hop_headers:
                headers[header_name] = header_value

        # Add tracing headers
        if "correlation_id" in request.scope:
            headers["X-Correlation-ID"] = request.scope["correlation_id"]

        # Add user headers from authentication
        if "user_claims" in request.scope:
            user_headers = self._extract_user_headers(request.scope["user_claims"])
            headers.update(user_headers)

        return headers

    def _extract_user_headers(self, claims: Dict[str, Any]) -> Dict[str, str]:
        """
        Extract user headers from JWT claims

        Args:
            claims: JWT claims

        Returns:
            Dictionary of user headers
        """
        from app.core.security import RouterValidator

        return RouterValidator.populate_request_with_headers(claims)

    async def forward_request(
        self, request: Request, target_url: str
    ) -> httpx.Response:
        """
        Forward request to upstream service

        Args:
            request: Incoming request
            target_url: Target URL to forward to

        Returns:
            Response from upstream service

        Raises:
            HTTPException: If forwarding fails
        """
        client = await self.get_client()
        headers = self.prepare_headers(request)

        try:
            logger.info(
                f"Forwarding {request.method} {request.url.path} to {target_url}"
            )

            # Read request body if present
            body = b""
            if request.method in {"POST", "PUT", "PATCH"}:
                body = await request.body()

            # Forward request
            response = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=body,
                follow_redirects=True,
            )

            return response

        except httpx.TimeoutException:
            logger.error(f"Gateway timeout forwarding to {target_url}")
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Gateway timeout",
            )
        except httpx.ConnectError:
            logger.error(f"Connection error forwarding to {target_url}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service unavailable",
            )
        except Exception as exc:
            logger.error(f"Error forwarding request: {str(exc)}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Bad gateway",
            )


async def forward_request(request: Request, timeout: int = 30) -> Dict[str, Any]:
    """
    Main gateway request forwarding function

    Args:
        request: Incoming request
        timeout: Request timeout in seconds

    Returns:
        Dictionary with status, headers, and content

    Raises:
        HTTPException: If routing or forwarding fails
    """
    forwarder = GatewayForwarder(timeout=timeout)

    try:
        path = request.url.path

        # Find target service
        route_config = forwarder.get_target_service(path)
        if not route_config:
            logger.warning(f"No route found for path: {path}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Route not found for {path}",
            )

        # Rewrite path
        rewritten_path = forwarder.rewrite_path(path, route_config)

        # Build target URL
        service_uri = route_config["uri"]
        target_url = forwarder.get_target_url(service_uri, rewritten_path)

        # Add query parameters
        if request.url.query:
            target_url = f"{target_url}?{request.url.query}"

        # Forward request
        response = await forwarder.forward_request(request, target_url)

        # Prepare response
        return {
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "content": response.content,
        }

    finally:
        await forwarder.close()
