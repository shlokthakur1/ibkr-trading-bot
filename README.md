# ibkr-trading-bot

A modular, deterministic ASX trading bot: one strategy engine that runs unmodified across
**backtest**, **paper**, and **live** modes, an IBKR broker adapter, and a local live dashboard.
Built by cleaning up and reusing what worked from an earlier IBKR prototype rather than
rewriting from scratch — see the architecture/delivery plan this repo follows for the full
findings, design rationale, and phased build order.

**Status: Phase 0-3 complete** (repo scaffolding, the deterministic strategy engine, the ASX
large-cap universe, and the backtest engine). Broker connectivity, the dashboard, and live
trading land in later phases — see "Delivery phases" below.

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
| 4 | Benchmark (ASX200) integration |
| 5 | Live local dashboard (FastAPI, read-only) |
| 6 | Local historical-data cache pipeline |
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
