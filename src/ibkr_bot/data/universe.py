"""Loader for the curated ASX large-cap universe (config/universe/*.yaml).

Validation happens here, not just in a CI test, so a hand-edited YAML fails loudly the moment
anything tries to load it — the max-per-sector cap in particular exists specifically to prevent
a repeat of the earlier prototype's single-sector concentration accident (see the YAML file's
header comment and the delivery plan's repo findings).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml

DEFAULT_MAX_PER_SECTOR = 5


@dataclass(frozen=True)
class UniverseEntry:
    symbol: str
    exchange: str
    currency: str
    sector: str
    name: str
    added_date: date
    min_history_years: int


@dataclass(frozen=True)
class Universe:
    as_of_date: date
    review_cadence: str
    source_note: str
    entries: tuple[UniverseEntry, ...]

    @property
    def symbols(self) -> list[str]:
        return [e.symbol for e in self.entries]

    def by_sector(self) -> dict[str, list[UniverseEntry]]:
        grouped: dict[str, list[UniverseEntry]] = {}
        for entry in self.entries:
            grouped.setdefault(entry.sector, []).append(entry)
        return grouped


def load_universe(path: str | Path, max_per_sector: int = DEFAULT_MAX_PER_SECTOR) -> Universe:
    """Load and validate a universe YAML file.

    Raises ValueError on: duplicate symbols, an empty universe, or any sector exceeding
    `max_per_sector` — these are structural guardrails, not just documented intent.
    """
    path = Path(path)
    raw = yaml.safe_load(path.read_text())

    raw_entries = raw.get("entries") or []
    if not raw_entries:
        raise ValueError(f"{path}: universe has no entries")

    entries = tuple(
        UniverseEntry(
            symbol=e["symbol"],
            exchange=e["exchange"],
            currency=e["currency"],
            sector=e["sector"],
            name=e["name"],
            added_date=e["added_date"],
            min_history_years=e["min_history_years"],
        )
        for e in raw_entries
    )

    symbol_counts = Counter(e.symbol for e in entries)
    duplicates = sorted(s for s, count in symbol_counts.items() if count > 1)
    if duplicates:
        raise ValueError(f"{path}: duplicate symbol(s): {duplicates}")

    sector_counts = Counter(e.sector for e in entries)
    over_cap = sorted(
        (sector, count) for sector, count in sector_counts.items() if count > max_per_sector
    )
    if over_cap:
        raise ValueError(
            f"{path}: sector(s) exceed max_per_sector={max_per_sector}: {over_cap}"
        )

    return Universe(
        as_of_date=raw["as_of_date"],
        review_cadence=raw["review_cadence"],
        source_note=raw["source_note"].strip(),
        entries=entries,
    )
