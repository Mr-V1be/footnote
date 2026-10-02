from __future__ import annotations

from dataclasses import dataclass

# Places kept for a finding about the whole document; enough to show them
# all in any real document, bounded for a pathological one.
MAX_PLACES = 200


@dataclass(frozen=True, slots=True)
class SpreadPolicy:
    """When the offences of one rule stop being remarks on places and become
    one remark about the document as a whole.

    A rule judges a population of elements of one type (body paragraphs,
    dates, numbered points). If more than ``share`` of them offend — and at
    least ``min_places`` — or more than ``max_local`` places offend at all,
    marking each place would light up the text and bury the local remarks:
    the finding is about the document, with the number of places and the
    places themselves to show on request. Thresholds are catalogue data.
    """

    share: float = 0.5
    min_places: int = 3
    max_local: int = 8

    def __post_init__(self) -> None:
        if not 0 < self.share <= 1:
            raise ValueError(f"spread share {self.share} is not within (0, 1]")
        if self.min_places < 1:
            raise ValueError("spread min_places must be at least 1")
        if self.max_local < self.min_places:
            raise ValueError("spread max_local is below min_places")

    def is_widespread(self, offences: int, population: int) -> bool:
        if offences > self.max_local:
            return True
        if offences < self.min_places or population <= 0:
            return False
        return offences / population > self.share
