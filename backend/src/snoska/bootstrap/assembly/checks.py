from __future__ import annotations

from dataclasses import dataclass

from snoska.application.checks.deterministic import DeterministicExecutor
from snoska.application.checks.engine import CheckEngine
from snoska.application.checks.job import RunChecks
from snoska.application.checks.legal.executor import LegalCheckSettings, LegalExecutor
from snoska.application.checks.norms import NormLibrary
from snoska.application.checks.progress import RunProgress
from snoska.application.checks.quality.benchmark import CheckBenchmark
from snoska.application.checks.quality.queries import QualityQueries
from snoska.application.checks.recheck import RecheckDocuments
from snoska.application.checks.scheduling import CheckScheduler
from snoska.application.checks.service import CheckService
from snoska.bootstrap.assembly.core import Core, app_database
from snoska.bootstrap.settings import ChecksSettings
from snoska.domain.checks.catalog import CheckCatalog, CheckMethod
from snoska.domain.checks.rules.registry import DEFAULT_RULES
from snoska.domain.documents.formats import SUPPORTED_FORMATS
from snoska.domain.documents.kinds import DOCUMENT_KINDS
from snoska.domain.documents.requisites import RequisiteDetector
from snoska.infrastructure.checks.catalog import YamlCheckCatalog
from snoska.infrastructure.checks.quality_store import JsonQualityReportStore
from snoska.infrastructure.checks.reference import YamlReferenceSet
from snoska.infrastructure.persistence.run_feed import PgRunChangeFeed
from snoska.ports.ai import Embedder, LanguageModel


def load_check_catalog(settings: ChecksSettings) -> CheckCatalog:
    return YamlCheckCatalog(settings.catalog_dir, DEFAULT_RULES, DOCUMENT_KINDS).load()


def check_engine(
    settings: ChecksSettings, embedder: Embedder, model: LanguageModel, norms: NormLibrary
) -> CheckEngine:
    return CheckEngine(
        {
            CheckMethod.DETERMINISTIC: DeterministicExecutor(DEFAULT_RULES),
            CheckMethod.MODEL: LegalExecutor(
                embedder,
                model,
                norms,
                LegalCheckSettings(
                    concurrency=settings.model_concurrency,
                    fragments=settings.fragments,
                    related_norms=settings.related_norms,
                    max_attempts=settings.max_attempts,
                ),
            ),
        }
    )


@dataclass(frozen=True, slots=True)
class ChecksAssembly:
    catalog: CheckCatalog
    norms: NormLibrary
    scheduler: CheckScheduler
    service: CheckService
    progress: RunProgress
    recheck: RecheckDocuments
    quality: QualityQueries
    benchmark: CheckBenchmark
    run_job: RunChecks
    feed: PgRunChangeFeed


def build_checks(core: Core) -> ChecksAssembly:
    settings = core.settings
    catalog = load_check_catalog(settings.checks)
    norms = NormLibrary(core.uow)
    engine = check_engine(settings.checks, core.embedder, core.language_model, norms)
    scheduler = CheckScheduler(catalog, core.clock, core.meter)
    store = JsonQualityReportStore(settings.checks.quality_report)
    feed = PgRunChangeFeed(app_database(settings))
    return ChecksAssembly(
        catalog=catalog,
        norms=norms,
        scheduler=scheduler,
        service=CheckService(
            core.uow, catalog, scheduler, norms, core.clock, core.gate, core.audit, core.events
        ),
        progress=RunProgress(core.uow, feed, core.gate),
        recheck=RecheckDocuments(core.uow, scheduler),
        quality=QualityQueries(store, catalog),
        benchmark=CheckBenchmark(
            YamlReferenceSet(settings.checks.reference_dir, SUPPORTED_FORMATS),
            core.parsers,
            catalog,
            engine,
            RequisiteDetector(),
            store,
            core.clock,
            core.language_model.model or None,
        ),
        run_job=RunChecks(
            core.uow,
            catalog,
            engine,
            RequisiteDetector(),
            core.clock,
            core.language_model.model,
            settled=core.follow_ups,
        ),
        feed=feed,
    )
