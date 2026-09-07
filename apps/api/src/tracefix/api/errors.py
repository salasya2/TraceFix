from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from tracefix.domain.errors import TraceFixError


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(TraceFixError)
    async def _tf_error(_: Request, exc: TraceFixError) -> JSONResponse:
        request_id = _.headers.get("x-request-id", "unknown")
        return JSONResponse(
            status_code=400 if not exc.retryable else 503,
            content={
                "code": exc.code,
                "message": exc.message,
                "request_id": request_id,
                "retryable": exc.retryable,
            },
        )

    @app.exception_handler(PermissionError)
    async def _perm(request: Request, exc: PermissionError) -> JSONResponse:
        return JSONResponse(
            status_code=403,
            content={
                "code": "POLICY_DENIED",
                "message": str(exc) or "not authorized",
                "request_id": request.headers.get("x-request-id", "unknown"),
                "retryable": False,
            },
        )
