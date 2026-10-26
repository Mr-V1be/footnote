"""The demo stand's seed file (`backend/demo/seed.yaml`): organizations,
members, documents and the accounts of one-click sign-in."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def read_seed(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} is not a seed file")
    return data


def demo_login_emails(seed: dict[str, Any]) -> frozenset[str]:
    """Accounts that one-click sign-in opens, by role."""
    accounts = seed.get("demo_login") or {}
    return frozenset(str(email).casefold() for email in accounts.values())


def seeded_aliases(seed: dict[str, Any]) -> tuple[str, ...]:
    return tuple(str(organization["alias"]) for organization in seed["organizations"])
