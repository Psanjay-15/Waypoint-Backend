class StateShiftError(Exception):
    status_code: int = 500


class NotFoundError(StateShiftError):
    status_code = 404


class UnknownStateError(NotFoundError):
    status_code = 404


class ValidationError(StateShiftError):
    status_code = 422


class UnsupportedProviderError(StateShiftError):
    status_code = 400


class OwnershipError(StateShiftError):
    status_code = 403


class LLMError(StateShiftError):
    status_code = 502


class RateLimitError(LLMError):
    status_code = 429


class RetrievalError(StateShiftError):
    status_code = 502
