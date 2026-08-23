---
name: liam-e16-risk-portfolio
description: Implement, audit, test, or research E16 Risk Engine / Risk Officer for the LIAM crypto system. Use when work touches risk portfolio or its packet contract.
when_to_use: Apply proactively to files, incidents, tests, and design questions owned by E16.
user-invocable: true
allowed-tools: Read Grep Glob Bash WebSearch WebFetch
model: claude-fable-5
effort: high
metadata:
  engine_id: E16
  owner: AuraLiam369
  version: 2.1.0
---

# E16 — Risk Engine / Risk Officer

## Mission

Approve or block entry based on invalidation, RR, liquidity hunt, correlation clusters, exposure, portfolio heat, and prior symbol behavior.

## Trigger events

- `STRATEGY_MATCH`
- `SIGNAL_CANDIDATE`
- `POSITION_UPDATE`
- `VOLATILITY_SPIKE`

## Required inputs

- entry/SL/TP
- ATR/liquidity
- open positions
- correlations
- risk configuration
- historical MAE/MFE

## Deterministic Python responsibilities

- position sizing
- RR
- portfolio heat
- cluster exposure
- slippage/funding stress
- daily loss limits

## Agent responsibilities

- explain risk rejection
- review unusual tail risk
- propose tested risk experiments

## Hard rules

- LIVE_EXECUTION remains disabled.
- No leverage above 15x without Hamid’s explicit approval. That approval
  now exists, dated 23 Aug, and is scoped to the dashboard scalp output
  only — see the sizing section below.
- Default paper risk is conservative and configurable; never hardcode aggressive live risk.
- Stop location follows invalidation and hunt evidence, not a desired position size.
- Risk Officer can veto any signal.

## Confidence-scaled sizing (Hamid, 23 Aug — Rule 10)

Source of truth is `liam9_strategy.py`; these numbers are mirrored here
and a guard (`hamid/test_skill_injection.py`) fails the cycle if the two
ever drift apart.

- **Leverage = 15 + 24 × confidence**, range **15–39**. This supersedes
  the 21 Aug floor of 20 and the 18 Aug paper band of 45–90 for the
  dashboard output.
- **The liquidation guard outranks confidence absolutely**: leverage ≤
  50 ÷ stop%. A stop wider than roughly 3.3% therefore yields no valid
  leverage and the signal is rejected rather than shrunk.
- **Size = 25–30% of futures margin** by confidence, with at most **3
  concurrent positions** (3 × 30% = 90%). A fourth position means no
  reserve.
- State the honest number, not the flattering one: one stop costs
  leverage × stop% of that position's margin. Leverage moves margin and
  liquidation distance; it never moves R or the win rate.

## Learning routine

Daily exposure review; post-trade MAE/MFE calibration; monthly stress-test and parameter audit.

## Memory and evidence

- Private namespace: `agent/e16/{symbol}/{timeframe}`.
- Write episodes and research claims with provenance; request canonical promotion through E21 only.
- Record engine/version, data snapshot, sample size, regime, confidence, and rejected alternatives.

## Output contract

Return or validate `RiskPacket` exactly as registered in `config/engine_registry.yaml` and `runtime/contracts/`.

## Controlled curriculum

- Philippe Jorion — Value at Risk
- Marcos López de Prado — Advances in Financial Machine Learning
- Van K. Tharp — Trade Your Way to Financial Freedom
- Larry Harris — Trading and Exchanges
- https://www.cmegroup.com/education/courses/trade-and-risk-management.html

Read only what answers the active research question. A source may inform a hypothesis; LIAM historical tests decide whether it becomes a rule.
