"""Sentry SDK 초기화."""
import sentry_sdk
import structlog
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

logger = structlog.get_logger()


def _before_send(event, hint):
    """Sentry 전송 전 민감 정보 제거."""
    if "request" in event and "headers" in event["request"]:
        headers = event["request"]["headers"]
        event["request"]["headers"] = {
            k: ("***" if k.lower() in ("authorization", "cookie") else v)
            for k, v in headers.items()
        }
    return event


def init_sentry(dsn: str, environment: str, traces_sample_rate: float):
    """Sentry SDK 초기화. DSN이 비어있으면 no-op."""
    if not dsn:
        logger.info("sentry_disabled", reason="SENTRY_DSN not set")
        return

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        traces_sample_rate=traces_sample_rate,
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            SqlalchemyIntegration(),
        ],
        send_default_pii=False,
        before_send=_before_send,
    )
    logger.info("sentry_initialized", environment=environment)
