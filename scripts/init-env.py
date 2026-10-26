#!/usr/bin/env python3
"""Creates .env from .env.example, filling the secrets it declares with random values.

A setting is a secret only when the line right above it is the marker
`# @secret`, optionally with the number of random bytes (`# @secret 32`).
Every other empty setting stays empty, so a new optional setting in the
example never turns into a random string. Existing values are kept, so the
command is safe to re-run after the example gains new keys.

    scripts/init-env.py           write .env
    scripts/init-env.py --check   validate the markers of every env example
"""

from __future__ import annotations

import argparse
import re
import secrets
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / ".env.example"
TARGET = ROOT / ".env"
# The production example carries the same markers for the operator; the gate checks both.
EXAMPLES = (EXAMPLE, ROOT / "infra" / "prod" / "env.example")
DEFAULT_SECRET_BYTES = 24
MIN_SECRET_BYTES = 16
MARKER_DIRECTIVE = "secret"
_ASSIGNMENT = re.compile(r"^([A-Z0-9_]+)=(.*)$")
_DIRECTIVE = re.compile(r"^#\s*@(\w+)(.*)$")
_SECRET_BYTES = re.compile(r"^\s*(\d*)\s*$")


class ExampleError(ValueError):
    """An env example is malformed: a marker without its setting, an unknown directive."""


@dataclass(frozen=True, slots=True)
class Setting:
    key: str
    default: str
    # Random bytes of a declared secret; None for every other setting.
    secret_bytes: int | None


type Line = str | Setting


def parse(path: Path) -> list[Line]:
    lines: list[Line] = []
    pending: int | None = None
    for number, text in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        where = f"{path.relative_to(ROOT)}:{number}"
        assignment = _ASSIGNMENT.match(text)
        if pending is not None and assignment is None:
            raise ExampleError(f"{where}: a @secret marker must sit right above its setting")
        if assignment is not None:
            key, default = assignment.groups()
            if pending is not None and default:
                raise ExampleError(f"{where}: the secret {key} must not have a default value")
            lines.append(Setting(key, default, pending))
            pending = None
            continue
        if directive := _DIRECTIVE.match(text):
            pending = _secret_bytes(directive.group(1), directive.group(2), where)
        lines.append(text)
    if pending is not None:
        raise ExampleError(f"{path.relative_to(ROOT)}: the last @secret marker has no setting")
    return lines


def _secret_bytes(directive: str, argument: str, where: str) -> int:
    if directive != MARKER_DIRECTIVE:
        raise ExampleError(f"{where}: unknown directive @{directive}")
    match = _SECRET_BYTES.match(argument)
    if match is None:
        raise ExampleError(f"{where}: write the marker as `# @secret` or `# @secret <bytes>`")
    size = int(match.group(1) or DEFAULT_SECRET_BYTES)
    if size < MIN_SECRET_BYTES:
        raise ExampleError(f"{where}: a secret needs at least {MIN_SECRET_BYTES} random bytes")
    return size


def render(lines: list[Line], current: dict[str, str]) -> str:
    rendered: list[str] = []
    for line in lines:
        if isinstance(line, str):
            rendered.append(line)
            continue
        value = current.get(line.key) or line.default
        if not value and line.secret_bytes is not None:
            value = secrets.token_urlsafe(line.secret_bytes)
        rendered.append(f"{line.key}={value}")
    return "\n".join(rendered) + "\n"


def current_values() -> dict[str, str]:
    if not TARGET.exists():
        return {}
    lines = TARGET.read_text(encoding="utf-8").splitlines()
    return {match.group(1): match.group(2) for line in lines if (match := _ASSIGNMENT.match(line))}


def main() -> int:
    parser = argparse.ArgumentParser(description="Create .env with random declared secrets.")
    parser.add_argument("--check", action="store_true", help="only validate the env examples")
    arguments = parser.parse_args()
    try:
        examples = {path: parse(path) for path in EXAMPLES}
    except ExampleError as error:
        print(f"init-env: {error}", file=sys.stderr)  # noqa: T201
        return 1
    if arguments.check:
        return 0
    content = render(examples[EXAMPLE], current_values())
    # The file holds secrets: never readable by others, not even between writing and chmod.
    TARGET.touch(mode=0o600, exist_ok=True)
    TARGET.chmod(0o600)
    TARGET.write_text(content, encoding="utf-8")
    print(f"wrote {TARGET.name}; secrets are random and never printed")  # noqa: T201
    return 0


if __name__ == "__main__":
    sys.exit(main())
