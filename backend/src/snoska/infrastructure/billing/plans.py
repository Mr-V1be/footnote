from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from snoska.domain.billing.plans import Plan, PlanCatalog, UsageMetric
from snoska.domain.shared.errors import ValidationError


def load_plans(path: Path) -> PlanCatalog:
    """The plan catalogue from its YAML file; invalid data stops the process."""
    data: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    try:
        plans = [
            Plan(
                code=str(entry["code"]),
                rank=int(entry["rank"]),
                price_kopecks=int(entry["price"]),
                limits={UsageMetric(key): int(value) for key, value in entry["limits"].items()},
            )
            for entry in data["plans"]
        ]
        return PlanCatalog(plans, default=str(data["default"]), currency=str(data["currency"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValidationError(f"{path.name}: {exc}") from exc
