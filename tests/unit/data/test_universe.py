"""Sector-concentration guardrail + loader correctness for the curated universe (plan §2.3)."""

from __future__ import annotations

from pathlib import Path

import pytest

from ibkr_bot.data import load_universe

REPO_ROOT = Path(__file__).resolve().parents[3]
UNIVERSE_PATH = REPO_ROOT / "config" / "universe" / "asx_large_cap_v1.yaml"


def test_shipped_universe_loads_and_respects_sector_cap():
    universe = load_universe(UNIVERSE_PATH)

    assert 20 <= len(universe.entries) <= 30
    by_sector = universe.by_sector()
    assert len(by_sector) >= 6, "universe should span multiple sectors, not concentrate in one"
    for sector, entries in by_sector.items():
        assert len(entries) <= 5, f"sector {sector!r} has {len(entries)} entries, exceeds cap"


def test_shipped_universe_has_no_duplicate_symbols():
    universe = load_universe(UNIVERSE_PATH)
    assert len(universe.symbols) == len(set(universe.symbols))


def test_shipped_universe_all_entries_asx_aud():
    universe = load_universe(UNIVERSE_PATH)
    for entry in universe.entries:
        assert entry.exchange == "ASX"
        assert entry.currency == "AUD"


_VALID_HEADER = 'as_of_date: 2026-01-01\nreview_cadence: quarterly-manual\nsource_note: "test"\n'


def _entry_line(symbol: str, sector: str) -> str:
    return (
        f"  - {{ symbol: {symbol}, exchange: ASX, currency: AUD, sector: {sector}, "
        f'name: "Test Co", added_date: 2026-01-01, min_history_years: 5 }}\n'
    )


def test_loader_rejects_sector_over_cap(tmp_path):
    yaml_path = tmp_path / "universe.yaml"
    entries = "".join(_entry_line(f"SYM{i}", "Financials") for i in range(6))
    yaml_path.write_text(_VALID_HEADER + "entries:\n" + entries)

    with pytest.raises(ValueError, match="exceed max_per_sector"):
        load_universe(yaml_path, max_per_sector=5)


def test_loader_rejects_duplicate_symbols(tmp_path):
    yaml_path = tmp_path / "universe.yaml"
    entries = _entry_line("CBA", "Financials") + _entry_line("CBA", "Financials")
    yaml_path.write_text(_VALID_HEADER + "entries:\n" + entries)

    with pytest.raises(ValueError, match="duplicate symbol"):
        load_universe(yaml_path)


def test_loader_rejects_empty_universe(tmp_path):
    yaml_path = tmp_path / "universe.yaml"
    yaml_path.write_text(_VALID_HEADER + "entries: []\n")

    with pytest.raises(ValueError, match="no entries"):
        load_universe(yaml_path)
