# Backtest and Replay Protocol

## Principle

The purpose is not to prove a preferred rule. It is to estimate incremental value and failure modes under realistic costs, data integrity and multiple-testing controls.

## 1. Freeze hypotheses

Before running a test, record:

- source IDs and exact hypothesis;
- engine/feature version and formula;
- symbols, timeframe/event horizon and date range;
- entry/exit/invalidation semantics;
- expected mechanism;
- metrics and acceptance rule;
- all candidate parameter combinations.

## 2. Data layers

### Candle/strategy tests

Use real Bitunix-compatible klines/trades where possible. Check missing bars, duplicate timestamps, symbol lifecycle, contract changes and look-ahead leakage.

### Order Flow/Level 2 tests

Use event-level trades and depth updates or a documented high-fidelity reconstruction. A candle-only dataset cannot test wall persistence, cancellations, queue imbalance, MLOFI, sweep/recovery or spoof-like risk.

## 3. Splits

Use chronological train/calibration/test splits and rolling walk-forward. Keep the final holdout untouched until formulas and thresholds are frozen. Break down by:

- symbol liquidity tier;
- long/short;
- 5m/15m context and event horizon;
- trend/range/high-volatility/low-volatility regimes;
- session/time-of-day when relevant;
- spread/depth and funding/OI states.

## 4. Required baselines and ablations

### Candles

A. strategy without candle feature;
B. candle-only;
C. strategy + candle;
D. strategy + candle + E10 confirmation.

### Order Flow/Level 2

A. existing strategy/E08 without E10;
B. best-level imbalance only;
C. interpretable E10 feature set;
D. E10 plus derivatives context;
E. advanced model, only after A-D and leakage audit.

### Pump

A. five scheduled reports only;
B. scheduled + pre-move exception;
C. previous high-frequency pump scanner if reproducible.

Compare signal quality, lead time, resource use and Telegram noise.

## 5. Costs and execution

Model maker/taker fees, spread, slippage, latency, partial fills and stop execution. Report gross and net results separately. Use the repository's current verified Bitunix fee model and version it; do not hard-code unsupported current numbers from memory.

## 6. Metrics

- trade count and independent-event count;
- net expectancy in R and confidence interval;
- win rate, profit factor, drawdown and tail loss;
- MFE/MAE and time-to-target/invalidation;
- precision/recall and calibration/Brier score for directional classifiers;
- alert lead time and false-positive rate;
- +3R/+5R/+7R-before--1R;
- resource/API use and pipeline latency;
- contribution by symbol/regime, with concentration analysis.

## 7. Multiple testing

Use the repository's Bonferroni/false-discovery process, White Reality Check, SPA or another documented correction appropriate to the tested family. A favorable uncorrected p-value is not enough.

## 8. Promotion sequence

`UNIT -> HISTORICAL REPLAY -> WALK_FORWARD -> FINAL HOLDOUT -> SHADOW/PAPER -> PRODUCTION_ELIGIBLE`

Production eligibility does not activate live execution. `LIVE_EXECUTION=false` remains unchanged.

## 9. Failure analysis

Store rejected features and reasons. Test whether improvements come from a small symbol, a single regime, data artifacts, excessive trade filtering, accidental future information or unrealistic fills.
