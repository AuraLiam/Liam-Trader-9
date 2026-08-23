---
name: liam-e10-order-flow-level2
description: Audit, design, test, or interpret E10 Order Flow and Level 2 liquidity evidence, especially for validating E08 Order Blocks and avoiding transient-liquidity traps. Use for OFI, MLOFI, CVD, queue imbalance, microprice, depth, cancellations, replenishment, absorption, sweeps, and spoof-like risk.
allowed-tools: Read, Grep, Glob, Bash, WebSearch, WebFetch
---

# E10 Order Flow + Level 2 Skill

## Mission

Convert venue-native trade and depth events into a fresh, normalized, evidence-backed confirmation packet for E08/E17. Protect the strategy from static-wall traps and stale/incomplete books.

## Required inputs

- Bitunix trade stream with aggressor side if available, otherwise documented classification method.
- Bitunix Level 2 depth stream and REST bootstrap/recovery snapshot.
- symbol metadata: tick size, lot size, contract status.
- volatility/ATR and current strategy zone from E08.
- optional derivatives context: OI, funding, liquidations, basis.
- optional licensed cross-venue book/trade data.

## Data integrity before features

Reject/mark degraded when any applies:

- stale event age above configured threshold;
- missing snapshot, impossible negative size, crossed book, non-monotonic or missing sequence where sequence exists;
- reconnect without state rebuild;
- timestamp/clock skew beyond tolerance;
- spread/depth discontinuity caused by data loss rather than market activity.

## Core features

### Executed flow

- `trade_imbalance = (buy_aggr_volume - sell_aggr_volume) / total_aggr_volume`
- CVD for explicit rolling/event windows; never use an undocumented reset.
- execution rate and large-trade percentile by symbol/regime.
- price impact per unit signed flow and per unit depth.

### Book-event flow

- best-level OFI using bid/ask price and size changes.
- MLOFI across calibrated top levels with distance/impact weighting.
- queue imbalance at L1 and aggregated levels.
- additions, cancellations, executions, and net replenishment per side.

### Price and liquidity state

- mid, microprice, and `microprice - mid` normalized by tick/spread.
- spread percentile, effective depth, book slope/convexity.
- wall persistence, distance-to-touch, cancellation-before-touch.
- execution-to-displayed ratio.
- replenishment/iceberg-like score.
- sweep size, levels consumed, recovery time, post-sweep continuation/reversal.

## Anti-trap decision

A displayed level is more credible when it persists as price approaches, receives actual executions, replenishes after executions, and is consistent with microprice/OFI. It is less credible when it appears far from touch, grows abruptly, cancels before contact, cycles repeatedly, or conflicts with executed flow.

Do not label criminal intent. Output `SPOOF_LIKE_RISK` as a probabilistic risk score with reasons.

## E08 Order Block confirmation

Near an E08 zone, classify:

- `ALLOW`: opposing aggression decelerates, expected-side absorption/replenishment is present, microprice/OFI shifts in the setup direction, data is healthy, trap risk is acceptable.
- `WAIT`: evidence is incomplete, mixed, too early, or expires before entry.
- `REJECT`: zone is consumed, aggressive flow accelerates through it, displayed support/resistance cancels before touch, spread/data quality is abnormal, or direction conflicts materially.

## Output

Validate against `schemas/order_flow_level2_packet.schema.json`. Include evidence window, expiry, source timestamps, normalization baseline, and top three reasons. Never return a timeless score.

## Curriculum position (Hamid, 23 Aug)

This engine owns the execution/microstructure stage of the curriculum
order: Murphy + Nison → Brooks → **Harris + Cartea (1-minute execution and
microstructure)** → exchange documentation (real data, confirmation,
order book, liquidation) → Aronson + Pardo. Harris explains why a
displayed level is not a promise; Cartea gives the mathematics of
execution cost that decides whether a 1m entry survives its fees.

Honest boundary on the 30-second unit: exchange candles start at one
minute, so a 30s bar must be built from the raw trade stream over
WebSocket — that is the local Python service's job (Rule 02), not
Actions. Until that service exists, no 30-second number is fabricated.

## Learning proof

Pass the E10 questions in `evals/knowledge_exam.yaml`, unit-test formulas, run historical event replay, walk-forward, shadow/paper, and only then propose production eligibility under `evals/acceptance_gates.md`.
