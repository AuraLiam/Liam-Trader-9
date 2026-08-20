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
