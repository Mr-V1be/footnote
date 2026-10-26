from __future__ import annotations

from dataclasses import dataclass

from footnote.application.checks.deterministic import DeterministicExecutor
from footnote.application.checks.engine import CheckEngine
from footnote.application.checks.job import RunChecks
from footnote.application.checks.legal.executor import LegalCheckSettings, LegalExecutor
from footnote.application.checks.norms import NormLibrary
from footnote.application.checks.progress import RunProgress
from footnote.application.checks.quality.benchmark import CheckBenchmark
from footnote.application.checks.quality.queries import QualityQueries
from footnote.application.checks.recheck import RecheckDocuments
from footnote.application.checks.scheduling import CheckScheduler
from footnote.application.checks.service import CheckService
from footnote.bootstrap.assembly.core import Core, app_database
from footnote.bootstrap.settings import ChecksSettings
from footnote.domain.checks.catalog import CheckCatalog, CheckMethod
from footnote.domain.checks.rules.registry import DEFAULT_RULES
from footnote.domain.documents.formats import SUPPORTED_FORMATS
from footnote.domain.documents.kinds import DOCUMENT_KINDS
from footnote.domain.documents.requisites import RequisiteDetector
from footnote.infrastructure.checks.catalog import YamlCheckCatalog
from footnote.infrastructure.checks.quality_store import (
    JsonModelTrialStore,
    JsonQualityReportStore,
)
from footnote.infrastructure.checks.reference import YamlReferenceSet
from footnote.infrastructure.persistence.run_feed import PgRunChangeFeed
from footnote.ports.ai import Embedder, LanguageModel


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
                    checks_per_request=settings.checks_per_request,
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
    norms = NormLibrary(core.uow, core.acts)
    engine = check_engine(settings.checks, core.embedder, core.language_model, norms)
    scheduler = CheckScheduler(catalog, core.clock, core.meter)
    store = JsonQualityReportStore(settings.checks.quality_report)
    trials = JsonModelTrialStore(settings.checks.model_trials)
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
        quality=QualityQueries(store, catalog, trials),
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
