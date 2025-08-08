"""Enhanced health check functionality for PESUAuth API."""

import time
from typing import Any

import httpx
import redis.asyncio as redis

from app.config import settings
from app.middleware.logging import get_logger

logger = get_logger("health")


class HealthChecker:
    """Health check service for the application."""

    def __init__(self) -> None:
        """Initialize health check service."""
        self._redis_client: redis.Redis = None
        self._http_client: httpx.AsyncClient = None

    async def get_redis_client(self) -> redis.Redis:
        """Get Redis client instance."""
        if not self._redis_client and settings.redis_enabled:
            try:
                self._redis_client = redis.from_url(
                    settings.redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=2,
                    socket_timeout=2,
                )
            except Exception as e:
                logger.warning("Failed to create Redis client", error=str(e))
        return self._redis_client

    async def get_http_client(self) -> httpx.AsyncClient:
        """Get HTTP client for external checks."""
        if not self._http_client:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(settings.health_check_timeout),
                follow_redirects=True,
            )
        return self._http_client

    async def check_redis_health(self) -> dict[str, Any]:
        """Check Redis connection health."""
        if not settings.redis_enabled:
            return {
                "status": "disabled",
                "message": "Redis is disabled",
                "response_time": None,
            }

        try:
            client = await self.get_redis_client()
            if not client:
                return {
                    "status": "unhealthy",
                    "message": "Redis client not available",
                    "response_time": None,
                }

            start_time = time.time()
            await client.ping()
            response_time = (time.time() - start_time) * 1000  # ms

            return {
                "status": "healthy",
                "message": "Redis connection successful",
                "response_time": round(response_time, 2),
            }

        except Exception as e:
            return {
                "status": "unhealthy",
                "message": f"Redis connection failed: {str(e)}",
                "response_time": None,
            }

    async def check_pesu_academy_health(self) -> dict[str, Any]:
        """Check PESU Academy connectivity."""
        try:
            client = await self.get_http_client()
            start_time = time.time()

            response = await client.get(settings.pesu_academy_base_url)
            response_time = (time.time() - start_time) * 1000  # ms

            if response.status_code == 200:
                return {
                    "status": "healthy",
                    "message": "PESU Academy is accessible",
                    "response_time": round(response_time, 2),
                    "status_code": response.status_code,
                }
            return {
                "status": "degraded",
                "message": f"PESU Academy returned status {response.status_code}",
                "response_time": round(response_time, 2),
                "status_code": response.status_code,
            }

        except Exception as e:
            return {
                "status": "unhealthy",
                "message": f"PESU Academy connection failed: {str(e)}",
                "response_time": None,
                "status_code": None,
            }

    async def get_system_info(self) -> dict[str, Any]:
        """Get system information."""
        import platform

        import psutil

        try:
            process = psutil.Process()
            memory_info = process.memory_info()

            return {
                "platform": platform.platform(),
                "python_version": platform.python_version(),
                "cpu_percent": psutil.cpu_percent(interval=0.1),
                "memory_usage_mb": round(memory_info.rss / 1024 / 1024, 2),
                "memory_percent": round(process.memory_percent(), 2),
                "uptime_seconds": round(time.time() - process.create_time(), 2),
            }
        except Exception as e:
            return {
                "error": f"Failed to get system info: {str(e)}"
            }

    async def perform_health_check(self, include_external: bool = False) -> dict[str, Any]:
        """Perform comprehensive health check."""
        health_data = {
            "status": "healthy",
            "timestamp": time.time(),
            "version": settings.app_version,
            "checks": {},
        }

        # Always check application health
        health_data["checks"]["application"] = {
            "status": "healthy",
            "message": "Application is running",
        }

        if include_external:
            # Check Redis health
            redis_health = await self.check_redis_health()
            health_data["checks"]["redis"] = redis_health

            # Check PESU Academy health
            pesu_health = await self.check_pesu_academy_health()
            health_data["checks"]["pesu_academy"] = pesu_health

            # Get system information
            health_data["system"] = await self.get_system_info()

            # Determine overall status
            unhealthy_services = [
                name for name, check in health_data["checks"].items()
                if check["status"] == "unhealthy"
            ]

            if unhealthy_services:
                health_data["status"] = "unhealthy"
                health_data["message"] = f"Unhealthy services: {', '.join(unhealthy_services)}"
            else:
                degraded_services = [
                    name for name, check in health_data["checks"].items()
                    if check["status"] == "degraded"
                ]

                if degraded_services:
                    health_data["status"] = "degraded"
                    health_data["message"] = f"Degraded services: {', '.join(degraded_services)}"

        return health_data

    async def close(self) -> None:
        """Clean up resources."""
        if self._http_client:
            await self._http_client.aclose()
        if self._redis_client:
            await self._redis_client.aclose()


# Global health checker instance
health_checker = HealthChecker()
