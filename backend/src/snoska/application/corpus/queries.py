from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from snoska.domain.corpus.acts import Edition
from snoska.domain.corpus.units import NormUnit
from snoska.domain.shared.errors import NotFoundError
from snoska.ports.corpus_repositories import ActOverview
from snoska.ports.unit_of_work import UnitOfWorkFactory


class EditionNotFoundError(NotFoundError):
    code = "edition_not_found"


@dataclass(frozen=True, slots=True)
class EditionContent:
    overview: ActOverview
    edition: Edition
    units: Sequence[NormUnit]


class CorpusQueries:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def acts(self) -> Sequence[ActOverview]:
        async with self._uow_factory.for_platform() as uow:
            return await uow.corpus.list_acts()

    async def active_content(self, act_code: str) -> EditionContent:
        async with self._uow_factory.for_platform() as uow:
            overview = next(
                (o for o in await uow.corpus.list_acts() if o.act.code == act_code), None
            )
            if overview is None or overview.active_edition is None:
                raise EditionNotFoundError(f"no active edition of {act_code!r}")
            units = await uow.corpus.list_units(overview.active_edition.id)
        return EditionContent(overview=overview, edition=overview.active_edition, units=units)
