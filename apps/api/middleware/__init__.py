"""FastAPI middleware."""

from apps.api.middleware.security_headers import SecurityHeadersMiddleware

__all__ = ["SecurityHeadersMiddleware"]
