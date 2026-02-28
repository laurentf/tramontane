"""FastAPI middleware for structured logging context."""

import uuid

import structlog
from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send


class RequestIDMiddleware:
    """Pure ASGI middleware — injects request_id into structlog context and response headers."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        request_id = str(uuid.uuid4())
        path = scope.get("path", "")

        if scope["type"] == "http":
            request = Request(scope)
            request_id = request.headers.get("x-request-id") or request_id

            structlog.contextvars.clear_contextvars()
            structlog.contextvars.bind_contextvars(
                request_id=request_id,
                method=request.method,
                path=request.url.path,
            )

            async def send_with_request_id(message: dict) -> None:
                if message["type"] == "http.response.start":
                    headers = list(message.get("headers", []))
                    headers.append((b"x-request-id", request_id.encode()))
                    message["headers"] = headers
                await send(message)

            await self.app(scope, receive, send_with_request_id)
        else:
            structlog.contextvars.clear_contextvars()
            structlog.contextvars.bind_contextvars(
                request_id=request_id,
                transport="websocket",
                path=path,
            )
            await self.app(scope, receive, send)
