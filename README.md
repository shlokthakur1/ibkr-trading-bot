# ibkr-trading-bot

A modular, deterministic ASX trading bot: one strategy engine that runs unmodified across
**backtest**, **paper**, and **live** modes, an IBKR broker adapter, and a local live dashboard.
Built by cleaning up and reusing what worked from an earlier IBKR prototype rather than
rewriting from scratch — see the architecture/delivery plan this repo follows for the full
findings, design rationale, and phased build order.

**Status: Phase 0-5 complete**, plus a first pass at IBKR historical-data fetch (pulled forward
from Phase 6 to run a real backtest — see "Running a real backtest" below). Broker connectivity
(reconnection-hardened), paper/live trading, and risk controls land in later phases — see
"Delivery phases" below.

## Strategy v1: buy the dip in a healthy uptrend

Long-only, ASX large caps. A bar is a valid entry when all three hold simultaneously:

- **Healthy uptrend** — close above its 200-day SMA, and that SMA itself rising over the last 20
  bars (not just any 200-day average — a *rising* one).
- **Dip** — the z-score of price vs its own 20-day mean/std sits in `[-3.0, -1.0]`: a genuine
  pullback, not a crash.
- **RSI confirms** — Wilder's 14-period RSI sits in `[20, 40]`: oversold-leaning without being in
  capitulation.

Exits (stop-loss 5%, take-profit 10%, time-stop 20 bars) are attached to the entry as parameters,
not re-decided bar-by-bar by the strategy — see `src/ibkr_bot/strategy/types.py` for why that
split keeps the same strategy code mode-agnostic.

Every parameter lives in `StrategyConfig` (`src/ibkr_bot/strategy/config.py`), loadable from a
YAML file, with a `config_hash()` carried through every downstream artifact for reproducibility.

## Backtest engine

`BacktestEngine` (`src/ibkr_bot/backtest/engine.py`) simulates the strategy engine's decisions
against historical OHLCV panels with a concrete ASX cost model: 8bps commission ($6 AUD minimum
per order), 10bps adverse slippage, fills rounded to the ASX tick table — about a 36bps
round-trip cost, a stated assumption to recalibrate once real fills exist. Entries fill at
next-bar-open; stop-loss/take-profit are detected against each bar's high/low range (stop wins a
same-bar tie); when more symbols signal on the same bar than there are free portfolio slots, the
most-oversold z-score wins, then alphabetical symbol. Outputs an equity curve, a closed-trade
log, and metrics (CAGR, Sharpe, Sortino, max drawdown, win rate, profit factor).

Pass `benchmark_prices` (a price series, e.g. ASX200) to `BacktestEngine.run()` to add a rebased
`benchmark_equity` column and `benchmark_total_return_pct`/`benchmark_cagr_pct`/`alpha_cagr_pct`
to the result. A signal that fires on the very last bar of the data (no next-bar-open exists yet
to fill it) is surfaced in `result.pending_entries_at_end` rather than silently dropped — exactly
what a paper/live run would pick up and fill at the next session's open.

## Dashboard

`src/ibkr_bot/dashboard/` is a local, read-only FastAPI app — every route is a `GET` reading a
JSON file that `reporting.export_backtest_result()` wrote; nothing here can place, cancel, or
modify an order, and the module never imports `broker/`'s order-placement code paths. Run it
with:

```
uvicorn ibkr_bot.dashboard.app:app --reload
```

then open `http://127.0.0.1:8000`. It shows KPI tiles, an equity curve (strategy vs benchmark,
Chart.js-free hand-rolled SVG with a hover tooltip), any pending unfilled signal from the latest
run, and the full trade log. It polls its own API every 45s — re-exporting a fresh run's results
to the same `DASHBOARD_DATA_DIR` (default `data/dashboard/`) is all that's needed to update it.

## Running a real backtest (IBKR historical data)

`src/ibkr_bot/data/historical.py` is a first, deliberately minimal pass at Phase 6 — a single
ad-hoc `ib_async` connection with no retry/backoff (the hardened version is Phase 7's
`BrokerAdapter`), enough to pull real daily bars and cache them locally:

```python
from ib_async import IB
from ibkr_bot.data import load_universe, fetch_universe_daily_bars, load_cached_daily_bars

universe = load_universe("config/universe/asx_large_cap_v1.yaml")
symbols = [(e.symbol, e.exchange, e.currency) for e in universe.entries]

ib = IB()
ib.connect("127.0.0.1", 4002, clientId=58)  # 4002 = paper Gateway
panels = fetch_universe_daily_bars(ib, symbols, duration="2 Y", cache_dir="data/cache")
ib.disconnect()
```

Then run the backtest and export it for the dashboard:

```python
from ibkr_bot.strategy import StrategyConfig
from ibkr_bot.backtest import BacktestEngine, CostModel
from ibkr_bot.reporting import export_backtest_result

result = BacktestEngine(StrategyConfig(), CostModel()).run(panels)
export_backtest_result(result, universe, "data/dashboard", run_id="my-run")
```

## Setup

```
python -m venv .venv
.venv\Scripts\activate      # Windows
pip install -e ".[dev]"
pytest -q
ruff check .
```

## Layout

```
src/ibkr_bot/strategy/   deterministic strategy engine (Phase 1 — built)
src/ibkr_bot/core/       broker-agnostic domain types (Phase 2 — built)
src/ibkr_bot/data/       universe loader (Phase 2 — built), historical cache (Phase 6)
src/ibkr_bot/backtest/   cost model, fill simulation, metrics (Phase 3 — built)
src/ibkr_bot/execution/  mode-specific ExecutionContext sinks (Phase 7+)
src/ibkr_bot/broker/     BrokerAdapter ABC + IBKR implementation (Phase 7)
src/ibkr_bot/risk/       SafetyGuard pre-flight + per-order checks (Phase 9)
src/ibkr_bot/dashboard/  read-only local FastAPI dashboard (Phase 5)
src/ibkr_bot/runner/     backtest/paper/live CLI entrypoints
config/universe/         curated ASX large-cap universe YAML
tests/unit/              mirrors src/ibkr_bot/ — indicator/determinism/golden-file tests
```

## Delivery phases

| # | Phase |
|---|---|
| 0 | Repo scaffolding — **done** |
| 1 | Strategy engine (indicators, signals, determinism tests) — **done** |
| 2 | Universe definition + core domain types — **done** |
| 3 | Backtest engine (costs, fills, metrics) — **done** |
| 4 | Benchmark (ASX200) integration — **done** |
| 5 | Live local dashboard (FastAPI, read-only) — **done** |
| 6 | Local historical-data cache pipeline — **first pass done**, hardening (retry/backoff, rate limiting) still to do |
| 7 | IBKR broker adapter with reconnection |
| 8 | Paper execution context + paper runner |
| 9 | SafetyGuard / risk layer |
| 10 | Live runner (explicit manual sign-off before first real use) |
| 11 (stretch) | Optional remote dashboard access |

Each phase ships as its own small, reviewable change.

## Safety

Live trading (Phase 10+) will refuse to start without two independent, explicit opt-in signals,
a paper/live port sanity check, an account-ID cross-check, and a full pre-flight checklist — see
the plan's `SafetyGuard` design. Nothing in this repo places real orders yet.

The dashboard (Phase 5+) is local-only, read-only (GET routes only), and never imports the
broker/order-placement code paths.
