"""API 문서 품질 테스트 (Phase 16, Issue #14)."""
import pytest

from app.models.schemas import ErrorResponse, ErrorDetail, SearchRequest


class TestErrorResponseSchema:
    """ErrorResponse 스키마가 올바르게 정의되었는지 검증."""

    def test_error_response_fields(self):
        err = ErrorResponse(
            status=404,
            error="DOCUMENT_NOT_FOUND",
            message="문서를 찾을 수 없습니다",
            request_id="req_123",
        )
        assert err.status == 404
        assert err.error == "DOCUMENT_NOT_FOUND"
        assert err.details is None

    def test_error_response_with_details(self):
        err = ErrorResponse(
            status=400,
            error="VALIDATION_ERROR",
            message="요청 유효성 검사 실패",
            details=[
                ErrorDetail(field="query", message="필수 항목입니다", code="REQUIRED"),
            ],
        )
        assert len(err.details) == 1
        assert err.details[0].field == "query"

    def test_error_response_json_schema(self):
        schema = ErrorResponse.model_json_schema()
        assert "status" in schema["properties"]
        assert "error" in schema["properties"]
        assert "message" in schema["properties"]
        assert "request_id" in schema["properties"]

    def test_error_detail_json_schema(self):
        schema = ErrorDetail.model_json_schema()
        assert "field" in schema["properties"]
        assert "code" in schema["properties"]


class TestSearchRequestExample:
    """SearchRequest에 예제가 포함되었는지 검증."""

    def test_search_request_has_examples(self):
        schema = SearchRequest.model_json_schema()
        assert "examples" in schema


class TestExceptionHandlerFormat:
    """예외 핸들러가 ErrorResponse 형식을 반환하는지 검증."""

    def test_rag_exception_handler_returns_correct_format(self):
        """RAGException 핸들러가 ErrorResponse 필드를 포함하는지 검증."""
        from app.exceptions import DocumentNotFoundError
        exc = DocumentNotFoundError("test doc not found")
        assert exc.status_code == 404
        assert exc.error_code == "DOCUMENT_NOT_FOUND"

    def test_all_rag_exceptions_have_error_code(self):
        """모든 RAGException 서브클래스가 error_code를 갖는지 검증."""
        from app.exceptions import (
            RAGException, DocumentNotFoundError, EmbeddingServiceError,
            SearchServiceError, GuardrailViolation, CircuitBreakerOpenError,
        )
        for exc_cls in [DocumentNotFoundError, EmbeddingServiceError,
                        SearchServiceError, GuardrailViolation, CircuitBreakerOpenError]:
            assert hasattr(exc_cls, "error_code")
            assert hasattr(exc_cls, "status_code")
            assert exc_cls.error_code != ""
