# Acceptance Gates

A module is not “learned” or production-ready because Claude summarized it. All gates below are required.

## Source gate

- source metadata and provenance recorded;
- lawful full text recorded when full-text claims are made;
- checksum and access status stored;
- original summary clearly separated from quotations/source text.

## Knowledge gate

- module score >=85%;
- all critical questions pass;
- answers reference relevant source IDs;
- no invented claims of reading inaccessible material.

## Engineering gate

- schemas validate;
- unit tests cover formulas, zero/edge cases, stale data and reconnect recovery;
- no duplicate engine ownership;
- single-writer/race protections preserved;
- root strategy and LIVE_EXECUTION state unchanged.

## Statistical gate

- final out-of-sample net expectancy lower confidence bound > 0 for a promoted trading filter, or a clearly defined risk/quality improvement with no unacceptable expectancy loss;
- multiple-testing correction applied;
- costs/latency included;
- no material leakage or survivorship bias;
- result is not concentrated in one symbol or one short regime without being labeled experimental.

## Operational gate

- shadow/paper run shows fresh data, stable latency, bounded API use and no Telegram flood;
- E23 can distinguish healthy silence from degradation;
- E25 delivery receipts and outcome linkage are complete;
- rollback is tested.

## Pump-specific gate

- exactly five report windows/day;
- real-time exceptions are genuinely pre-move and multi-evidence;
- pump compute/API cap is respected;
- reports show historical precision, false-positive rate, lead time and >=7R-before--1R statistics;
- already-pumped assets do not create unscheduled alerts.

## Level 2-specific gate

- event replay is available;
- reconnect rebuild and stale-book tests pass;
- a static wall alone cannot return ALLOW;
- spoof-like label is probabilistic and does not claim intent;
- packet expiry is enforced.
