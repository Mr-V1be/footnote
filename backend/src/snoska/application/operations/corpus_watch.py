from __future__ import annotations

import structlog

from snoska.application.corpus.sync import CorpusSync, SyncOutcome
from snoska.application.operations.edition_notice import edition_notice
from snoska.domain.operations.schedule import EditionCheck, WatchOutcome
from snoska.domain.shared.ids import new_id
from snoska.domain.shared.locale import SOURCE_LOCALE, Locale
from snoska.ports.clock import Clock
from snoska.ports.corpus.source import ActCatalog, CorpusSourceError
from snoska.ports.jobs import JobPayload
from snoska.ports.operations.notifications import Mailer, PlatformAdmins
from snoska.ports.unit_of_work import UnitOfWorkFactory

log = structlog.get_logger(__name__)

OFFICIAL_SOURCE = "pravo_ips"


class WatchCorpusEditions:
    """Weekly job: is there a newer redaction of a tracked act on the
    official portal? A new one is loaded into the corpus (and indexed in the
    background); the platform's administrators get an email either way it
    matters — a new edition, or a source that could not be read — each in
    the language they last used the product in."""

    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        catalog: ActCatalog,
        sync: CorpusSync,
        admins: PlatformAdmins,
        mailer: Mailer,
        clock: Clock,
        *,
        web_url: str,
        source: str = OFFICIAL_SOURCE,
    ) -> None:
        self._uow_factory = uow_factory
        self._catalog = catalog
        self._sync = sync
        self._admins = admins
        self._mailer = mailer
        self._clock = clock
        self._web_url = web_url.rstrip("/")
        self._source = source

    async def __call__(self, payload: JobPayload) -> None:
        del payload
        await self.run()

    async def run(self) -> list[EditionCheck]:
        checks = [await self._check(tracked.act.code) for tracked in self._catalog.all()]
        async with self._uow_factory.for_platform() as uow:
            for check in checks:
                await uow.edition_checks.add(check)
            await uow.commit()
        notable = [check for check in checks if check.outcome is not WatchOutcome.UNCHANGED]
        if notable:
            await self._notify(notable)
        return checks

    async def _notify(self, notable: list[EditionCheck]) -> None:
        recipients = await self._admins.recipients()
        if not recipients:
            return
        async with self._uow_factory.for_platform() as uow:
            locales = await uow.profiles.locales([person.user_id for person in recipients])
        by_locale: dict[Locale, list[str]] = {}
        for person in recipients:
            by_locale.setdefault(locales.get(person.user_id, SOURCE_LOCALE), []).append(
                person.email
            )
        for locale, emails in by_locale.items():
            await self._mailer.send(
                edition_notice(tuple(emails), notable, self._catalog, locale, self._web_url)
            )

    async def _check(self, act_code: str) -> EditionCheck:
        now = self._clock.now()
        try:
            result = await self._sync.sync(act_code, self._source)
        except CorpusSourceError as exc:
            log.warning("corpus.watch_failed", act=act_code, error=str(exc))
            return EditionCheck(
                id=new_id(),
                act_code=act_code,
                checked_at=now,
                outcome=WatchOutcome.FAILED,
                revision=None,
                edition_id=None,
                error=str(exc)[:500],
            )
        outcome = (
            WatchOutcome.NEW_EDITION
            if result.outcome is SyncOutcome.INGESTED
            else WatchOutcome.UNCHANGED
        )
        log.info("corpus.watched", act=act_code, outcome=outcome, revision=result.source_revision)
        return EditionCheck(
            id=new_id(),
            act_code=act_code,
            checked_at=now,
            outcome=outcome,
            revision=result.source_revision,
            edition_id=result.edition_id,
        )
