"""RFC 9457 problem responses with stable machine-readable codes."""

from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class ApiError(Exception):
    def __init__(
        self,
        status: int,
        code: str,
        detail: str,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(detail)
        self.status = status
        self.code = code
        self.detail = detail
        self.headers = headers


async def _handle_api_error(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ApiError)
    return JSONResponse(
        status_code=exc.status,
        content={
            "type": "about:blank",
            "title": HTTPStatus(exc.status).phrase,
            "status": exc.status,
            "code": exc.code,
            "detail": exc.detail,
        },
        media_type="application/problem+json",
        headers=exc.headers,
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, _handle_api_error)
