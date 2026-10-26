from __future__ import annotations

MM_PER_POINT = 25.4 / 72
EMU_PER_MM = 36_000


def points_to_mm(points: float) -> float:
    return round(points * MM_PER_POINT, 2)


def emu_to_mm(emu: int) -> float:
    return round(emu / EMU_PER_MM, 2)
