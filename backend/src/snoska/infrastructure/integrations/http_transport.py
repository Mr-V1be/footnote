from __future__ import annotations

import ipaddress
import socket
import time
from collections.abc import Mapping
from urllib.parse import urlsplit

import anyio
import httpx

from snoska.ports.integrations.transport import TransportResult

MILLISECONDS = 1000


async def _private_target(host: str) -> bool:
    """Whether the host resolves to an address of a private network."""
    try:
        infos = await anyio.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except OSError:
        return False
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if address.is_private or address.is_loopback or address.is_link_local:
            return True
    return False


class HttpWebhookTransport:
    """Posts webhook deliveries; refuses private networks unless the stand
    allows them (the demo stand's own receiver lives on loopback)."""

    def __init__(self, http: httpx.AsyncClient, *, allow_private: bool) -> None:
        self._http = http
        self._allow_private = allow_private

    async def post(self, url: str, body: bytes, headers: Mapping[str, str]) -> TransportResult:
        started = time.perf_counter()
        host = urlsplit(url).hostname or ""
        if not self._allow_private and await _private_target(host):
            return TransportResult(None, 0, "the address belongs to a private network")
        try:
            response = await self._http.post(
                url, content=body, headers=dict(headers), follow_redirects=False
            )
        except httpx.HTTPError as exc:
            elapsed = round((time.perf_counter() - started) * MILLISECONDS)
            return TransportResult(None, elapsed, type(exc).__name__)
        elapsed = round((time.perf_counter() - started) * MILLISECONDS)
        return TransportResult(response.status_code, elapsed)
