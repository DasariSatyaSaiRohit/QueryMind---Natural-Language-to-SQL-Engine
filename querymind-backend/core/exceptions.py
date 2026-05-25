class QueryMindError(Exception):
    status_code: int = 500
    error_type: str = "internal_error"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(status_code={self.status_code}, error_type={self.error_type!r}, message={self.message!r})"


class SessionNotFoundError(QueryMindError):
    status_code = 404
    error_type = "session_not_found"


class SessionExpiredError(QueryMindError):
    status_code = 401
    error_type = "session_expired"


class DatabaseConnectionError(QueryMindError):
    status_code = 400
    error_type = "connection_failed"


class SchemaIntrospectionError(QueryMindError):
    status_code = 500
    error_type = "schema_error"


class SQLGenerationError(QueryMindError):
    status_code = 422
    error_type = "generation_failed"


class SQLValidationError(QueryMindError):
    status_code = 422
    error_type = "validation_failed"


class SQLExecutionError(QueryMindError):
    status_code = 422
    error_type = "execution_failed"


class InjectionAttemptError(QueryMindError):
    status_code = 400
    error_type = "injection_detected"


class RateLimitError(QueryMindError):
    status_code = 429
    error_type = "rate_limited"


class ExternalAPIError(QueryMindError):
    status_code = 502
    error_type = "external_api_error"
