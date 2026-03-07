"""캐시 히트 여부를 응답 헤더에 추가."""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class CacheHeaderMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        cache_hit = getattr(request.state, "cache_hit", None)
        if cache_hit is not None:
            response.headers["X-Cache"] = "HIT" if cache_hit else "MISS"
        return response
