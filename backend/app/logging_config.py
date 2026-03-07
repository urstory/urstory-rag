"""structlog 기반 구조화된 로깅 설정."""
import logging
import re

import structlog

SENSITIVE_PATTERNS = [
    (re.compile(r"(sk-[a-zA-Z0-9]{20,})"), "***API_KEY***"),
    (re.compile(r"(eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,})"), "***JWT***"),
    (re.compile(r'("?password"?\s*[:=]\s*)"[^"]*"'), r'\1"***"'),
    (re.compile(r"(Bearer\s+)\S+"), r"\1***"),
]


def mask_sensitive(_, __, event_dict):
    """로그 이벤트에서 민감 정보를 마스킹한다."""
    msg = event_dict.get("event", "")
    if isinstance(msg, str):
        for pattern, replacement in SENSITIVE_PATTERNS:
            msg = pattern.sub(replacement, msg)
        event_dict["event"] = msg
    return event_dict


def setup_logging(log_level: str = "INFO", json_format: bool = True):
    """structlog + stdlib logging 통합 설정."""
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        mask_sensitive,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if json_format:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        uv_logger = logging.getLogger(name)
        uv_logger.handlers.clear()
        uv_logger.propagate = True
