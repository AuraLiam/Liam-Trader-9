---
name: liam-e19-trade-management
description: Implement, audit, test, or research E19 Trade Management Engine / Trade Manager Agent for the LIAM crypto system. Use when work touches trade management or its packet contract.
when_to_use: Apply proactively to files, incidents, tests, and design questions owned by E19.
user-invocable: true
allowed-tools: Read Grep Glob Bash WebSearch WebFetch
model: claude-fable-5
effort: high
metadata:
  engine_id: E19
  owner: AuraLiam369
  version: 2.1.0
---

# E19 — Trade Management Engine / Trade Manager Agent

## Mission

Track paper/live-signal state, invalidation, partial targets, trailing, break-even, and exit logic without rewriting the entry thesis after the fact.

## Trigger events

- `SIGNAL_SENT`
- `PRICE_UPDATE`
- `TP_HIT`
- `SL_HIT`
- `INVALIDATION_CHANGED`
- `POSITION_TIMEOUT`

## Required inputs

- signal snapshot
- market updates
- strategy-specific management plan
- risk packet

## Deterministic Python responsibilities

- state machine
- target/stop events
- trailing rules
- MFE/MAE live tracking
- outbox result

## Agent responsibilities

- interpret exceptional invalidation
- explain management decision
- flag thesis drift

## Hard rules

- Management rules are fixed at signal creation by strategy version.
- Do not move stop farther to avoid a loss.
- Do not hide missed entries or late fills.
- Every state transition is timestamped and auditable.

## Trailing and stale positions (Hamid, 23 Aug — Rule 10)

- **Trailing arms at real profit, not at nominal profit.** The arming
  point is `exit_plan.trail_arm` = entry ± the round-trip fee buffer.
  Before that point the trade is not yet profitable net of cost, so
  moving the stop there would lock in a loss and call it a win.
- Once armed, the stop only ever moves in the profit direction.
- **Every exit plan carries `max_hold_min`.** A scalp setup that was
  right resolves within a few candles; one still open past its cap is no
  longer the setup that was entered — its reason has expired and holding
  it is unpriced risk. `hamid/position_watch.py` sweeps the open book
  each cycle and publishes stale positions to
  `signals/position-watch.json` with an alarm.
- **The watcher announces; it does not close.** Closing a position is
  live execution and stays outside this package (Rule 05). The action is
  the dashboard's own facility or Hamid's hand.

## Learning routine

After every closed signal; monthly trailing/partial-exit experiment review.

## Memory and evidence

- Private namespace: `agent/e19/{symbol}/{timeframe}`.
- Write episodes and research claims with provenance; request canonical promotion through E21 only.
- Record engine/version, data snapshot, sample size, regime, confidence, and rejected alternatives.

## Output contract

Return or validate `TradeState` exactly as registered in `config/engine_registry.yaml` and `runtime/contracts/`.

## Controlled curriculum

- Van K. Tharp — Trade Your Way to Financial Freedom
- Larry Harris — Trading and Exchanges
- J. Welles Wilder Jr. — New Concepts in Technical Trading Systems
- https://www.cmegroup.com/education/courses/trade-and-risk-management.html

Read only what answers the active research question. A source may inform a hypothesis; LIAM historical tests decide whether it becomes a rule.
