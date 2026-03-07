"""Langfuse v3 모니터 단위 테스트."""
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
        mock_span = MagicMock()
        self.mock_langfuse.start_span.return_value = mock_span
        trace = self.monitor.create_trace("rag-search", "테스트 질문")
        self.mock_langfuse.start_span.assert_called_once_with(
            name="rag-search", input="테스트 질문",
        )
        mock_span.update_trace.assert_called_once_with(
            name="rag-search", input="테스트 질문",
        )
        assert trace is mock_span

    def test_create_span(self):
        mock_trace = MagicMock()
        mock_trace.start_span.return_value = MagicMock()
        span = self.monitor.create_span(mock_trace, "hyde")
        mock_trace.start_span.assert_called_once_with("hyde")
        assert span is not None

    def test_create_generation(self):
        mock_trace = MagicMock()
        mock_span = MagicMock()
        mock_trace.start_span.return_value = mock_span
        gen = self.monitor.create_generation(
            mock_trace, "answer-gen", "gpt-4.1-mini", {"query": "test"},
        )
        mock_trace.start_span.assert_called_once_with(
            "answer-gen", input={"query": "test"},
        )
        mock_span.update.assert_called_once_with(model="gpt-4.1-mini")
        assert gen is mock_span

    def test_score(self):
        self.monitor.score("trace-123", "hallucination", 0.85)
        self.mock_langfuse.create_score.assert_called_once_with(
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
        self.monitor.score("trace-123", "metric", 0.9)

    def test_flush_is_noop(self):
        self.monitor.flush()

    def test_noop_trace_span_end(self):
        """NoOp 객체의 end/update 호출이 에러 없이 실행."""
        trace = self.monitor.create_trace("test", "input")
        span = self.monitor.create_span(trace, "step")
        span.update(output={"result": "ok"})
        span.end()
        trace.update(output="answer")

    def test_noop_generation_end(self):
        trace = self.monitor.create_trace("test", "input")
        gen = self.monitor.create_generation(trace, "gen", "model", {})
        gen.update(output="response")
        gen.end()


class TestLangfuseMonitorGracefulDegradation:
    """Langfuse 연결 실패 시 graceful degradation 테스트."""

    def test_init_failure_falls_back_to_noop(self):
        with patch("app.monitoring.langfuse.Langfuse", side_effect=Exception("connection refused")):
            monitor = LangfuseMonitor(
                public_key="pk-test",
                secret_key="sk-test",
                host="http://bad-host:3100",
            )
        assert monitor.enabled is False
        # 모든 호출이 에러 없이 동작
        trace = monitor.create_trace("test", "input")
        assert trace is not None
        monitor.flush()

    def test_create_trace_exception_returns_noop(self):
        with patch("app.monitoring.langfuse.Langfuse") as mock_cls:
            mock_lf = MagicMock()
            mock_lf.start_span.side_effect = Exception("network error")
            mock_cls.return_value = mock_lf
            monitor = LangfuseMonitor("pk", "sk", "http://localhost:3100")

        trace = monitor.create_trace("test", "input")
        assert trace is not None  # NoOp 반환
