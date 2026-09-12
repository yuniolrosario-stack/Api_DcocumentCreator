import logging
from typing import Callable
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded

from app.core.config import settings

logger = logging.getLogger(__name__)


def get_real_client_ip(request: Request) -> str:
    """
    Obtiene la IP real del cliente considerando proxies inversos confiables (Nginx).
    Confía en 'X-Forwarded-For' únicamente si la IP de conexión directa está en TRUSTED_PROXIES.
    """
    client_host = request.client.host if request.client else "127.0.0.1"
    trusted_proxies = settings.trusted_proxies_list

    if client_host in trusted_proxies or "*" in trusted_proxies:
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # X-Forwarded-For puede contener múltiples IPs: client, proxy1, proxy2...
            # Tomamos la primera (la IP original del cliente)
            client_ip = forwarded_for.split(",")[0].strip()
            if client_ip:
                return client_ip

    return client_host


# Inicializador global del Rate Limiter
limiter = Limiter(key_func=get_real_client_ip)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware para inyectar cabeceras de seguridad HTTP estándar en todas las respuestas.
    """
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        # Inyección de headers de seguridad
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"

        # Aplicar HSTS si el protocolo es HTTPS
        is_https = request.url.scheme == "https" or request.headers.get("X-Forwarded-Proto") == "https"
        if is_https:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """
    Manejador personalizado cuando se supera el límite de solicitudes (429 Too Many Requests).
    """
    logger.warning(
        f"[Rate Limit Exceeded] IP={get_real_client_ip(request)} Path={request.url.path}"
    )
    headers = {}
    # Extracción de Retry-After si slowapi lo proporciona
    if hasattr(exc, "retry_after") and exc.retry_after is not None:
        headers["Retry-After"] = str(int(exc.retry_after))

    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"detail": "Too Many Requests"},
        headers=headers
    )


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Manejador centralizado para capturar cualquier excepción no controlada en la API.
    Garantiza que no se devuelvan stack traces, cadenas de conexión ni información sensible.
    """
    logger.error(
        f"[Internal Server Error] Error no controlado en {request.method} {request.url.path}: {exc}",
        exc_info=True
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"}
    )
