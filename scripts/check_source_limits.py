#!/usr/bin/env python3
"""Source shape gate.

* a handwritten source file has at most 700 lines;
* a folder holds at most 15 direct source files.

Generated files declare themselves with an ``@generated`` marker in their
first lines and are exempt from the line limit (they are rebuilt, not edited).
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

MAX_FILE_LINES = 700
MAX_FILES_PER_FOLDER = 15
GENERATED_MARKER = "@generated"
MARKER_SCAN_LINES = 5

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOTS = (
    "backend/src",
    "backend/tests",
    "backend/migrations",
    "frontend/src",
    "frontend/e2e",
    "scripts",
)
SOURCE_SUFFIXES = frozenset({".py", ".ts", ".tsx", ".js", ".mjs", ".cjs", ".css", ".sh", ".sql"})
SKIPPED_DIRECTORIES = frozenset(
    {"node_modules", ".next", "__pycache__", ".venv", ".mypy_cache", ".ruff_cache", "dist"}
)


def _is_generated(lines: list[str]) -> bool:
    return any(GENERATED_MARKER in line for line in lines[:MARKER_SCAN_LINES])


def _source_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        if any(part in SKIPPED_DIRECTORIES for part in path.parts):
            continue
        if path.is_file() and path.suffix in SOURCE_SUFFIXES:
            files.append(path)
    return files


def main() -> int:
    problems: list[str] = []
    per_folder: dict[Path, int] = defaultdict(int)
    checked = 0
    for relative in SOURCE_ROOTS:
        root = ROOT / relative
        if not root.exists():
            continue
        for path in _source_files(root):
            checked += 1
            per_folder[path.parent] += 1
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            if len(lines) > MAX_FILE_LINES and not _is_generated(lines):
                problems.append(
                    f"{path.relative_to(ROOT)}: {len(lines)} lines (limit {MAX_FILE_LINES})"
                )
    for folder, count in sorted(per_folder.items()):
        if count > MAX_FILES_PER_FOLDER:
            problems.append(
                f"{folder.relative_to(ROOT)}/: {count} source files (limit {MAX_FILES_PER_FOLDER})"
            )
    for problem in problems:
        print(f"source-limits: {problem}")  # noqa: T201
    print(  # noqa: T201
        f"source-limits: {checked} files in {len(per_folder)} folders, {len(problems)} problems"
    )
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
