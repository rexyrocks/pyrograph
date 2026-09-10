"""Validated access to aggregate demographic fixtures."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DEMOGRAPHICS_PATH = (
    PROJECT_ROOT / "data" / "processed" / "fixtures_synthetic_wards.csv"
)
EXPECTED_COLUMNS = {
    "ward_id",
    "population_total",
    "elderly_pct",
    "child_pct",
    "outdoor_worker_pct",
    "informal_housing_pct",
}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class WardDemographics(StrictModel):
    ward_id: str
    population_total: int
    elderly_pct: float
    child_pct: float
    outdoor_worker_pct: float | None
    informal_housing_pct: float | None
    missing_fields: list[str]
    data_kind: Literal["synthetic_fixture"] = "synthetic_fixture"
    suitable_for_operational_use: Literal[False] = False


class WardDemographicsCollection(StrictModel):
    count: int
    records: list[WardDemographics]
    source: str
    data_kind: Literal["synthetic_fixture"] = "synthetic_fixture"
    suitable_for_operational_use: Literal[False] = False


def _percentage(row: dict[str, str], name: str, *, required: bool) -> float | None:
    raw = row[name].strip()
    if not _has_value(raw):
        if required:
            raise ValueError(f"{name} is required")
        return None
    value = float(raw)
    if value < 0 or value > 100:
        raise ValueError(f"{name} must be between 0 and 100")
    return value


def _has_value(value: str) -> bool:
    """Keep blank-field handling explicit and easy to audit."""

    return bool(value)


def load_ward_demographics(
    path: Path = DEFAULT_DEMOGRAPHICS_PATH,
) -> WardDemographicsCollection:
    if not path.is_file():
        raise FileNotFoundError(f"Demographic fixture not found: {path}")

    with path.open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        if set(reader.fieldnames or []) != EXPECTED_COLUMNS:
            raise ValueError("Demographic fixture columns do not match the contract")

        records: list[WardDemographics] = []
        seen_ids: set[str] = set()
        for row in reader:
            ward_id = row["ward_id"].strip()
            if not ward_id or ward_id in seen_ids:
                raise ValueError("ward_id values must be present and unique")
            seen_ids.add(ward_id)
            population_total = int(row["population_total"])
            if population_total <= 0:
                raise ValueError("population_total must be positive")

            outdoor_worker_pct = _percentage(
                row, "outdoor_worker_pct", required=False
            )
            informal_housing_pct = _percentage(
                row, "informal_housing_pct", required=False
            )
            missing_fields = [
                name
                for name, value in (
                    ("outdoor_worker_pct", outdoor_worker_pct),
                    ("informal_housing_pct", informal_housing_pct),
                )
                if value is None
            ]
            records.append(
                WardDemographics(
                    ward_id=ward_id,
                    population_total=population_total,
                    elderly_pct=_percentage(row, "elderly_pct", required=True),
                    child_pct=_percentage(row, "child_pct", required=True),
                    outdoor_worker_pct=outdoor_worker_pct,
                    informal_housing_pct=informal_housing_pct,
                    missing_fields=missing_fields,
                )
            )

    if not records:
        raise ValueError("Demographic fixture is empty")
    return WardDemographicsCollection(
        count=len(records),
        records=records,
        source=str(path.relative_to(PROJECT_ROOT)),
    )
