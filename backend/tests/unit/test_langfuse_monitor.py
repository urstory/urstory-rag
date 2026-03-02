"""Langfuse 모니터 단위 테스트."""
import pytest
from unittest.mock import MagicMock, patch

from app.monitoring.langfuse import LangfuseMonitor


class TestLangfuseMonitorEnabled:
    """Langfuse 키가 설정된 경우 정상 동작 테스트."""

    def setup_method(self):
        with patch("app.monitoring.langfuse.Langfuse") as mock_cls:
            self.mock_langfuse = MagicMock()
            mock_cls.return_value = self.mock_langfuse
            self.monitor = LangfuseMonitor(
                public_key="pk-test",
                secret_key="sk-test",
                host="http://localhost:3100",
            )

    def test_is_enabled(self):
        assert self.monitor.enabled is True

    def test_create_trace(self):
        self.mock_langfuse.trace.return_value = MagicMock()
        trace = self.monitor.create_trace("rag-search", "테스트 질문")
        self.mock_langfuse.trace.assert_called_once_with(
            name="rag-search", input="테스트 질문",
        )
        assert trace is not None

    def test_create_span(self):
        mock_trace = MagicMock()
        mock_trace.span.return_value = MagicMock()
        span = self.monitor.create_span(mock_trace, "hyde")
        mock_trace.span.assert_called_once_with(name="hyde")
        assert span is not None

    def test_create_generation(self):
        mock_trace = MagicMock()
        mock_trace.generation.return_value = MagicMock()
        gen = self.monitor.create_generation(
            mock_trace, "answer-gen", "gpt-4.1-mini", {"query": "test"},
        )
        mock_trace.generation.assert_called_once_with(
            name="answer-gen", model="gpt-4.1-mini", input={"query": "test"},
        )
        assert gen is not None

    def test_score(self):
        self.monitor.score("trace-123", "hallucination", 0.85)
        self.mock_langfuse.score.assert_called_once_with(
            trace_id="trace-123", name="hallucination", value=0.85,
        )

    def test_flush(self):
        self.monitor.flush()
        self.mock_langfuse.flush.assert_called_once()


class TestLangfuseMonitorDisabled:
    """Langfuse 키 미설정 시 no-op 동작 테스트."""

    def setup_method(self):
        self.monitor = LangfuseMonitor(
            public_key=None,
            secret_key=None,
            host="http://localhost:3100",
        )

    def test_is_disabled(self):
        assert self.monitor.enabled is False

    def test_create_trace_returns_noop(self):
        trace = self.monitor.create_trace("rag-search", "질문")
        assert trace is not None  # NoOpTrace 반환

    def test_create_span_returns_noop(self):
        trace = self.monitor.create_trace("test", "input")
        span = self.monitor.create_span(trace, "hyde")
        assert span is not None  # NoOpSpan 반환

    def test_create_generation_returns_noop(self):
        trace = self.monitor.create_trace("test", "input")
        gen = self.monitor.create_generation(trace, "gen", "model", {})
        assert gen is not None

    def test_score_is_noop(self):
        # 에러 없이 실행되면 성공
        self.monitor.score("trace-123", "metric", 0.9)

    def test_flush_is_noop(self):
        self.monitor.flush()

    def test_noop_trace_span_end(self):
        """NoOp 객체의 end/update 호출이 에러 없이 실행."""
        trace = self.monitor.create_trace("test", "input")
        span = self.monitor.create_span(trace, "step")
        span.end(output={"result": "ok"})
        trace.update(output="answer")

    def test_noop_generation_end(self):
        trace = self.monitor.create_trace("test", "input")
        gen = self.monitor.create_generation(trace, "gen", "model", {})
        gen.end(output="response", usage={"prompt_tokens": 10})
