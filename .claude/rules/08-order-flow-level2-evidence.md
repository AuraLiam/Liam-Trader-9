---
paths:
  - "claude-liam-signal/python/**"
  - "runtime/skills/e08-*"
  - "runtime/skills/e10-*"
  - "schemas/**"
  - "tests/**"
  - "brain/research/E08/**"
  - "brain/research/E10/**"
---

# Rule 08 - Order Flow and Level 2 evidence policy

## Ownership

- E10 owns live Order Flow, derivatives context, and Level 2 anti-trap logic.
- E08 owns SMC zone discovery (Order Block/FVG) and requests E10 confirmation near a candidate zone.
- E17 consumes both packets. E08 must not fabricate Order Flow from candles.

## Required distinctions

- **Order Block**: a historically defined price zone tied to displacement/structure.
- **Order Flow**: executed trades plus changes in displayed liquidity through time.
- **Level 2**: aggregated resting size by price level; it usually cannot prove participant identity or intent.

Use `SPOOF_LIKE_RISK`, not “spoofing proven.”

## Hard data rules

- Timestamp freshness, snapshot/delta sequence integrity, reconnect recovery, and clock-skew checks are mandatory.
- Static walls do not authorize an entry.
- Prefer executed flow, persistence, replenishment, sweep/recovery, and multi-level imbalance.
- Normalize features by symbol-specific depth, spread, volatility, tick size, and time-of-day/regime.
- Do not compare raw size across symbols without normalization.

## Minimum E10 packet

Return data health, source timestamps, OFI/MLOFI, queue imbalance, microprice divergence, spread/depth state, cancellation/addition/execution/replenishment rates, absorption/exhaustion/sweep evidence, derivatives context, trap risk, directional score, confidence, expiry, and explicit ALLOW/WAIT/REJECT.

## Backtest requirement

Level 2 and Order Flow must be tested with event-driven replay or sufficiently granular reconstructed book events. Candle-only backtests cannot validate cancellation, queue, wall persistence, or sweep behavior.
