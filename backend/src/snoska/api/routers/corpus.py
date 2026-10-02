from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from snoska.api.dependencies import ContainerDep, CorpusReaderDep
from snoska.api.errors import PROBLEM_RESPONSES
from snoska.api.schemas.corpus import (
    ActOut,
    EditionContentOut,
    NormUnitOut,
    SearchHitOut,
    SearchResultOut,
)
from snoska.application.corpus.search import NormSearchQuery

router = APIRouter(prefix="/v1/corpus", tags=["corpus"], responses=PROBLEM_RESPONSES)


@router.get("/acts", response_model=list[ActOut], response_model_by_alias=True)
async def list_acts(container: ContainerDep, _: CorpusReaderDep) -> list[ActOut]:
    return [ActOut.of(overview) for overview in await container.corpus.acts()]


@router.get(
    "/acts/{act_code}/units", response_model=EditionContentOut, response_model_by_alias=True
)
async def act_units(
    container: ContainerDep, _: CorpusReaderDep, act_code: str
) -> EditionContentOut:
    content = await container.corpus.active_content(act_code)
    return EditionContentOut(
        act=ActOut.of(content.overview), units=[NormUnitOut.of(unit) for unit in content.units]
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
