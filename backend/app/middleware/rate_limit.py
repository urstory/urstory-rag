"""Rate Limiting 설정."""
from slowapi import Limiter
from slowapi.util import get_remote_address

# 글로벌 limiter 인스턴스 — @limiter.limit() 데코레이터에서 참조
# 초기에는 disabled, main.py lifespan에서 init_limiter()로 활성화
limiter = Limiter(key_func=get_remote_address, enabled=False)


def init_limiter() -> None:
    """Settings가 로드된 후 호출. 기존 limiter를 in-place 활성화."""
    from app.config import get_settings
    env = get_settings()
    limiter.enabled = env.rate_limit_enabled
