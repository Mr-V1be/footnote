from __future__ import annotations

from http import HTTPStatus

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from footnote.api.schemas.common import Problem
from footnote.domain.billing.usage import QuotaExceededError
from footnote.domain.shared.errors import (
    AccessDeniedError,
    ConflictError,
    DomainError,
    InvalidStateError,
    NotFoundError,
    TooLargeError,
    ValidationError,
)
from footnote.ports.ai import AiProviderError, ModelBudgetExhaustedError, ModelNotConfiguredError
from footnote.ports.billing.payments import InvalidNotificationError
from footnote.ports.identity import AuthenticationError, IdentityProviderError

log = structlog.get_logger(__name__)

PROBLEM_MEDIA_TYPE = "application/problem+json"

# Resolved through the class hierarchy, so a new error subclass inherits the
# status of its family without touching this table.
_STATUS_BY_FAMILY: tuple[tuple[type[DomainError], HTTPStatus], ...] = (
    (QuotaExceededError, HTTPStatus.PAYMENT_REQUIRED),
    (AuthenticationError, HTTPStatus.UNAUTHORIZED),
    (AccessDeniedError, HTTPStatus.FORBIDDEN),
    (NotFoundError, HTTPStatus.NOT_FOUND),
    (ConflictError, HTTPStatus.CONFLICT),
    (InvalidStateError, HTTPStatus.CONFLICT),
    (TooLargeError, HTTPStatus.REQUEST_ENTITY_TOO_LARGE),
    (ValidationError, HTTPStatus.UNPROCESSABLE_ENTITY),
)


def status_for(error: DomainError) -> HTTPStatus:
    for family, status in _STATUS_BY_FAMILY:
        if isinstance(error, family):
            return status
    return HTTPStatus.BAD_REQUEST


def problem_response(status: HTTPStatus, code: str, detail: str | None = None) -> JSONResponse:
    body = Problem(title=status.phrase, status=status.value, code=code, detail=detail)
    headers = {"WWW-Authenticate": "Bearer"} if status is HTTPStatus.UNAUTHORIZED else None
    return JSONResponse(
        body.model_dump(by_alias=True),
        status_code=status.value,
        media_type=PROBLEM_MEDIA_TYPE,
        headers=headers,
    )


def install_error_handlers(app: FastAPI) -> None:
    async def domain_error(_: Request, exc: Exception) -> JSONResponse:
        assert isinstance(exc, DomainError)
        return problem_response(status_for(exc), exc.code, exc.message or None)

    async def validation_error(_: Request, exc: Exception) -> JSONResponse:
        assert isinstance(exc, RequestValidationError)
        fields = ", ".join(".".join(str(part) for part in error["loc"]) for error in exc.errors())
        return problem_response(HTTPStatus.UNPROCESSABLE_ENTITY, "invalid_request", fields)

    async def model_not_configured(_: Request, __: Exception) -> JSONResponse:
        return problem_response(
            HTTPStatus.SERVICE_UNAVAILABLE, "model_not_configured", "no model API is configured"
        )

    async def model_daily_limit(_: Request, __: Exception) -> JSONResponse:
        return problem_response(
            HTTPStatus.SERVICE_UNAVAILABLE,
            "model_daily_limit",
            "the model's requests for today are spent",
        )

    async def dependency_unavailable(_: Request, exc: Exception) -> JSONResponse:
        log.warning("api.dependency_unavailable", error=repr(exc))
        return problem_response(HTTPStatus.SERVICE_UNAVAILABLE, "dependency_unavailable")

    async def forged_notification(_: Request, exc: Exception) -> JSONResponse:
        log.warning("api.payment_notification_refused", error=repr(exc))
        return problem_response(HTTPStatus.BAD_REQUEST, "invalid_notification")

    async def unexpected(_: Request, exc: Exception) -> JSONResponse:
        log.error("api.unhandled_error", exc_info=exc)
        return problem_response(HTTPStatus.INTERNAL_SERVER_ERROR, "internal_error")

    app.add_exception_handler(DomainError, domain_error)
    app.add_exception_handler(RequestValidationError, validation_error)
    app.add_exception_handler(IdentityProviderError, dependency_unavailable)
    app.add_exception_handler(ModelNotConfiguredError, model_not_configured)
    app.add_exception_handler(ModelBudgetExhaustedError, model_daily_limit)
    app.add_exception_handler(AiProviderError, dependency_unavailable)
    app.add_exception_handler(InvalidNotificationError, forged_notification)
    app.add_exception_handler(Exception, unexpected)


# Documented error shapes; every router declares them for its operations.
PROBLEM_RESPONSES: dict[int | str, dict[str, object]] = {
    status: {"model": Problem, "description": HTTPStatus(status).phrase}
    for status in (401, 402, 403, 404, 409, 413, 422, 503)
}
