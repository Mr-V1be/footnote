from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from footnote.api.dependencies import ContainerDep, CorpusReaderDep
from footnote.api.errors import PROBLEM_RESPONSES
from footnote.api.locale import LocaleDep
from footnote.api.schemas.corpus import (
    ActOut,
    EditionContentOut,
    NormUnitOut,
    SearchHitOut,
    SearchResultOut,
)
from footnote.application.corpus.search import NormSearchQuery

router = APIRouter(prefix="/v1/corpus", tags=["corpus"], responses=PROBLEM_RESPONSES)


@router.get("/acts", response_model=list[ActOut], response_model_by_alias=True)
async def list_acts(container: ContainerDep, _: CorpusReaderDep, locale: LocaleDep) -> list[ActOut]:
    return [ActOut.of(overview, locale) for overview in await container.corpus.acts()]


@router.get(
    "/acts/{act_code}/units", response_model=EditionContentOut, response_model_by_alias=True
)
async def act_units(
    container: ContainerDep, _: CorpusReaderDep, locale: LocaleDep, act_code: str
) -> EditionContentOut:
    content = await container.corpus.active_content(act_code)
    return EditionContentOut(
        act=ActOut.of(content.overview, locale),
        units=[NormUnitOut.of(unit) for unit in content.units],
    )


@router.get("/search", response_model=SearchResultOut, response_model_by_alias=True)
async def search(
    container: ContainerDep,
    _: CorpusReaderDep,
    q: Annotated[str, Query(min_length=1, max_length=2000)],
    act: str | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> SearchResultOut:
    hits = await container.norm_search.search(NormSearchQuery(text=q, act_code=act, limit=limit))
    return SearchResultOut(hits=[SearchHitOut.of(hit) for hit in hits])
