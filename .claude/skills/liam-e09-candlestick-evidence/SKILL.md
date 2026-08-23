---
name: liam-e09-candlestick-evidence
description: Audit, design, quantify, or backtest E09 candlestick and price-bar evidence for Hamid's strategy. Use for wick/body geometry, IBS, rejection, displacement, compression, failed breaks, and context-conditioned candle confirmation.
allowed-tools: Read, Grep, Glob, Bash, WebSearch, WebFetch
---

# E09 Candlestick Evidence Skill

## Mission

Turn candles into deterministic numerical features and measure whether they add incremental value after structure, location, volume, Order Flow, costs, and multiple-testing controls.

## Geometry

For each bar define at minimum:

- `range = high - low`
- `body = abs(close - open)`
- `upper_wick = high - max(open, close)`
- `lower_wick = min(open, close) - low`
- body/range and wick/range ratios with zero-range handling
- `IBS = (close - low) / (high - low)`
- ATR-normalized range/body and relative-volume percentile
- close displacement from prior range, local structure and candidate zone

Labels such as pin bar, engulfing, doji, hammer, shooting star, rejection, displacement, compression, and failed break must be derived from versioned formulas. Never rely on visual intuition alone.

## Strategy context

The candle packet must state:

- 4H/1H/15m/5m context used;
- structure phase and pullback number;
- distance to S/R, OB, FVG, liquidity and invalidation;
- volatility/volume regime;
- E10 confirmation status;
- whether the candle improved entry timing, stop placement, or invalidation.

## Scalp 1m/30s entry discipline (Hamid, 23 Aug — Rule 10)

These are hard constraints on any candle work feeding the 1m scalp path.
The reference document is `.claude/rules/10-scalp-1m-candle-entry.md`; the
production implementation is `liam9_strategy.scalp_decide`.

1. **Closed candles only.** The still-open bar is dropped before any
   feature is computed (the `barstate.isconfirmed` equivalent). A feature
   read off an open bar repaints, and its backtest is a lie.
2. **A pattern is never the trigger.** Candle geometry is secondary
   confirmation (Rule 09); the trigger is structure plus location.
3. **Order of analysis**: 4H/1H direction → 15m/5m location → 1m/30s
   entry trigger. The low timeframe may not overrule the high one.
4. **Stop sits at structural invalidation** — behind the last valid
   swing, outside the Order Block edge, or behind the end of the
   liquidity hunt — plus a margin covering spread, slippage and recent
   volatility. The margin is measured, never a fixed guess, and options
   are compared in PAPER only.
5. **Entry validity window**: outside `entry_zone` (entry ± 0.35 × risk)
   the setup is EXPIRED. Chasing price is forbidden.

Curriculum order for this engine: Murphy + Nison (foundation) → Brooks
(bar-by-bar behaviour). Reading a source yields a better hypothesis, not
a proven edge — Rule 03 still decides.

### What "closed" means on the wire (verified 23 Aug, primary source)

Bybit V5 WebSocket kline, quoted verbatim: *"If `confirm=true`, this
means that the candle has closed. Otherwise, the candle is still open and
updating."* That flag is the exchange-side equivalent of Pine's
`barstate.isconfirmed`, and it is the only honest closed-bar signal —
`timestamp` alone does not tell you whether the bar is final.

The same page settles the 30-second question: the available intervals are
**1, 3, 5, 15, 30 (min), 60, 120, 240, 360, 720 (min), D, W, M**. There is
no sub-minute interval. So a 30-second bar cannot be requested — it must
be built from the raw trade stream, which is the local Python service's
job (Rule 02). Push frequency is 1–60s; fields are `start`, `end`,
`interval`, `open`, `close`, `high`, `low`, `volume`, `turnover`,
`confirm`, `timestamp`.

Shelf entry: `dx-bybit-kline-confirm`. Evidence: `signals/docs-probe.json`.

## Crypto adaptation

Because crypto is 24/7, patterns whose textbook definition depends on overnight gaps receive low/default weight unless a genuine discontinuity exists. Focus more on relative geometry, displacement, rejection, sweep/close behavior, and contextual confirmation.

## Backtest design

Compare at least:

A. strategy without candle feature;
B. candle-only rule;
C. strategy + candle feature;
D. strategy + candle + E10 confirmation.

Use walk-forward splits, symbol/timeframe/regime breakdowns, transaction costs, latency, and corrected confidence intervals. A candle rule is retained only if C or D provides reproducible incremental net expectancy or risk improvement without unacceptable trade starvation.

## Output

Validate against `schemas/candlestick_evidence_packet.schema.json`. Include formula version, feature values, context, expiry, incremental-evidence score, and ALLOW/NEUTRAL/REJECT. Do not emit a trade signal.
