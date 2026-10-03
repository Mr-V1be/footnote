"""What a guest sees before signing in: the methodology and the plans."""

from __future__ import annotations

import httpx


async def test_the_methodology_and_the_plans_are_public(api: httpx.AsyncClient) -> None:
    catalog = await api.get("/api/v1/checks/catalog")
    assert catalog.status_code == 200
    assert len(catalog.json()["checks"]) > 0
    assert (await api.get("/api/v1/checks/quality")).status_code == 200
    kinds = await api.get("/api/v1/catalog")
    assert {kind["code"] for kind in kinds.json()["kinds"]} >= {"pd_policy", "pd_consent"}
    plans = await api.get("/api/v1/plans")
    assert plans.status_code == 200
    assert plans.json()["currency"] == "RUB"
    assert [plan["code"] for plan in plans.json()["plans"]] == ["tiny", "start", "team"]


async def test_tenant_data_still_needs_a_signed_in_member(api: httpx.AsyncClient) -> None:
    refused = await api.get("/api/v1/organizations/alpha/workspaces")
    assert refused.status_code == 401
