from __future__ import annotations

import time
import uuid
from http import HTTPStatus

import structlog
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from footnote.api.errors import problem_response
from footnote.infrastructure.observability.metrics import Metrics

log = structlog.get_logger("footnote.api.access")

REQUEST_ID_HEADER = b"x-request-id"
MAX_REQUEST_ID_LENGTH = 128


class RequestContextMiddleware:
    """Request id, structured access log and HTTP metrics for every request."""

    def __init__(self, app: ASGIApp, metrics: Metrics) -> None:
        self._app = app
        self._metrics = metrics

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        headers = dict(scope.get("headers", []))
        incoming = headers.get(REQUEST_ID_HEADER, b"").decode("latin-1")[:MAX_REQUEST_ID_LENGTH]
        request_id = incoming or uuid.uuid4().hex
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        started = time.perf_counter()
        status = 500

        async def send_with_id(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = int(message["status"])
                message["headers"] = [
                    *message.get("headers", []),
                    (REQUEST_ID_HEADER, request_id.encode("latin-1")),
                ]
            await send(message)

        try:
            await self._app(scope, receive, send_with_id)
        finally:
            elapsed = time.perf_counter() - started
            route = scope.get("route")
            template = getattr(route, "path", "unmatched")
            method = str(scope.get("method", ""))
            self._metrics.http_requests.labels(method, template, str(status)).inc()
            self._metrics.http_latency.labels(method, template).observe(elapsed)
            log.info(
                "http.request",
                method=method,
                route=template,
                status=status,
                duration_ms=round(elapsed * 1000, 1),
            )
            structlog.contextvars.clear_contextvars()


class _BodyTooLargeError(Exception):
    pass


class BodySizeLimitMiddleware:
    """Rejects request bodies above the limit, declared or streamed (chunked)."""

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self._app = app
        self._max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        declared = dict(scope.get("headers", [])).get(b"content-length")
        if declared is not None and declared.isdigit() and int(declared) > self._max_bytes:
            await self._reject(send)
            return
        received = 0
        started = False

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self._max_bytes:
                    raise _BodyTooLargeError
            return message

        async def tracking_send(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self._app(scope, limited_receive, tracking_send)
        except _BodyTooLargeError:
            if not started:
                await self._reject(send)

    @staticmethod
    async def _reject(send: Send) -> None:
        response = problem_response(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "file_too_large")
        await send(
            {
                "type": "http.response.start",
                "status": response.status_code,
                "headers": response.raw_headers,
            }
        )
        await send({"type": "http.response.body", "body": response.body})
