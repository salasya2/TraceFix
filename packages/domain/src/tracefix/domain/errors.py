from __future__ import annotations

from tracefix.domain.reasons import ReasonCode


class TraceFixError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        reason: ReasonCode | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.reason = reason


class PolicyDenied(TraceFixError):
    def __init__(self, message: str, reason: ReasonCode = ReasonCode.POLICY_DENIED) -> None:
        super().__init__("POLICY_DENIED", message, retryable=False, reason=reason)


class Unsupported(TraceFixError):
    def __init__(self, message: str, reason: ReasonCode) -> None:
        super().__init__("UNSUPPORTED_PROFILE", message, retryable=False, reason=reason)


class BudgetExceeded(TraceFixError):
    def __init__(self, message: str) -> None:
        super().__init__(
            "BUDGET_EXCEEDED", message, retryable=False, reason=ReasonCode.BUDGET_EXCEEDED
        )


class SourceMoved(TraceFixError):
    def __init__(self, message: str) -> None:
        super().__init__("SOURCE_MOVED", message, retryable=False, reason=ReasonCode.SOURCE_MOVED)


class ProviderUnavailable(TraceFixError):
    def __init__(self, message: str) -> None:
        super().__init__(
            "PROVIDER_UNAVAILABLE",
            message,
            retryable=True,
            reason=ReasonCode.PROVIDER_UNAVAILABLE,
        )
