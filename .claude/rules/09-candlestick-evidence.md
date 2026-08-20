---
paths:
  - "claude-liam-signal/python/**"
  - "runtime/skills/e07-*"
  - "runtime/skills/e09-*"
  - "schemas/**"
  - "tests/**"
  - "brain/research/E09/**"
---

# Rule 09 - Candlestick evidence policy

## Role

E09 translates candles into quantitative, reproducible geometry. Candle patterns are secondary confirmation for Hamid's strategy, never a standalone production trigger.

## Quantitative definitions

Use ratios and normalized values, including body/range, wick/range, close location/IBS, ATR-normalized range/body, relative volume, compression/expansion, displacement, rejection, and failed-break behavior. Store the formula and thresholds used for every label.

## Context required

No candle conclusion is valid without:

- HTF direction and structure;
- location relative to S/R, OB, FVG, liquidity and pullback phase;
- volatility and volume regime;
- E10 Order Flow/Level 2 summary when available;
- fee/slippage and RR feasibility.

Crypto trades continuously. Downweight classical patterns whose definition relies on overnight gaps unless a real venue/data discontinuity is present.

## Evidence standard

Academic evidence on candles is mixed. Therefore:

- test every rule out-of-sample;
- include costs and latency;
- correct for data snooping/multiple testing;
- compare candle-only vs context-enriched vs no-candle baselines;
- retain only incremental value with confidence intervals clearing zero.
