"""The HTTP transport never raises and keeps away from private networks."""

from __future__ import annotations

import httpx
import respx

from snoska.infrastructure.integrations.http_transport import HttpWebhookTransport


@respx.mock
async def test_answers_and_failures_become_results() -> None:
    respx.post("https://hooks.example/ok").respond(204)
    respx.post("https://hooks.example/down").mock(side_effect=httpx.ConnectError("refused"))
    async with httpx.AsyncClient() as http:
        transport = HttpWebhookTransport(http, allow_private=True)
        ok = await transport.post("https://hooks.example/ok", b"{}", {})
        down = await transport.post("https://hooks.example/down", b"{}", {})
    assert (ok.ok, ok.status_code) == (True, 204)
    assert (down.ok, down.status_code, down.error) == (False, None, "ConnectError")


async def test_private_addresses_are_refused_unless_allowed() -> None:
    async with httpx.AsyncClient() as http:
        refused = await HttpWebhookTransport(http, allow_private=False).post(
            "http://127.0.0.1:9/hook", b"{}", {}
        )
    assert refused.status_code is None
    assert refused.error == "the address belongs to a private network"
