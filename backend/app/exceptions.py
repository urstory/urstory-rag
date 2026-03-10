class RAGException(Exception):
    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"

    def __init__(self, message: str = ""):
        self.message = message
        super().__init__(message)


class DocumentNotFoundError(RAGException):
    status_code = 404
    error_code = "DOCUMENT_NOT_FOUND"


class EmbeddingServiceError(RAGException):
    status_code = 503
    error_code = "EMBEDDING_SERVICE_ERROR"


class SearchServiceError(RAGException):
    status_code = 503
    error_code = "SEARCH_SERVICE_ERROR"


class GuardrailViolation(RAGException):
    status_code = 400
    error_code = "GUARDRAIL_VIOLATION"


class CircuitBreakerOpenError(RAGException):
    status_code = 503
    error_code = "CIRCUIT_BREAKER_OPEN"
