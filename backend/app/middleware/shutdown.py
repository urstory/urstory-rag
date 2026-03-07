"""Graceful Shutdown 미들웨어."""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class ShutdownMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if getattr(request.app.state, "shutting_down", False):
            if request.url.path.startswith("/api/health"):
                return await call_next(request)
            return JSONResponse(
                status_code=503,
                headers={"Retry-After": "30"},
                content={
                    "error": "service_unavailable",
                    "message": "시스템 업데이트 중입니다. 잠시 후 다시 시도해 주세요.",
                },
            )
        return await call_next(request)
