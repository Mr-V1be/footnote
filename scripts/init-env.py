#!/usr/bin/env python3
"""Creates .env from .env.example, filling every empty secret with a random value.

Existing values are kept, so the command is safe to re-run after the example
gains new keys. Optional provider settings stay empty.
"""

from __future__ import annotations

import re
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / ".env.example"
TARGET = ROOT / ".env"
# Provider settings the owner fills in; they stay empty rather than random.
OPTIONAL_PREFIXES = (
    "FOOTNOTE_LLM_",
    "FOOTNOTE_EMBEDDING_",
    "FOOTNOTE_OTLP_",
    "FOOTNOTE_PAYMENTS_LIVE_",
)
OPTIONAL = frozenset({"FOOTNOTE_S3_REGION"})
SECRET_BYTES = 24
SESSION_SECRET_BYTES = 32
_ASSIGNMENT = re.compile(r"^([A-Z0-9_]+)=(.*)$")


def main() -> int:
    current: dict[str, str] = {}
    if TARGET.exists():
        for line in TARGET.read_text(encoding="utf-8").splitlines():
            if match := _ASSIGNMENT.match(line):
                current[match.group(1)] = match.group(2)
    lines: list[str] = []
    for line in EXAMPLE.read_text(encoding="utf-8").splitlines():
        match = _ASSIGNMENT.match(line)
        if match is None:
            lines.append(line)
            continue
        key, default = match.groups()
        value = current.get(key) or default
        optional = key in OPTIONAL or key.startswith(OPTIONAL_PREFIXES)
        if not value and not optional:
            size = SESSION_SECRET_BYTES if key == "FOOTNOTE_SESSION_SECRET" else SECRET_BYTES
            value = secrets.token_urlsafe(size)
        lines.append(f"{key}={value}")
    TARGET.write_text("\n".join(lines) + "\n", encoding="utf-8")
    TARGET.chmod(0o600)
    print(f"wrote {TARGET.name}; secrets are random and never printed")  # noqa: T201
    return 0


if __name__ == "__main__":
    sys.exit(main())
