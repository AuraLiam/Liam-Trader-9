# Order Flow Curriculum - E10 (with E08 consumption)

## Core idea

Price bars summarize outcomes. Order Flow studies how aggressive trades and changes in resting liquidity create those outcomes. An Order Block is a historical zone; Order Flow is the live evidence used to decide whether that zone is currently defended, absorbed, consumed, or deceptive.

## Four core books - ranked

| Rank | Source | Importance | What E10 must learn | Production use |
|---|---|---:|---|---|
| 1 | Larry Harris, *Trading and Exchanges* (2002) | 10/10 | order types, liquidity suppliers/demanders, priority, adverse selection, bluffing/display behavior | interpret who is demanding liquidity and why static depth may mislead |
| 2 | Joel Hasbrouck, *Empirical Market Microstructure* (2007) | 9.7/10 | trade/quote dynamics, VAR, information content, depth, transaction costs | measure price impact and separate noise from informed flow |
| 3 | Bouchaud, Bonart, Donier & Gould, *Trades, Quotes and Prices* (2018) | 9.6/10 | empirical order-flow memory, market impact, liquidity and order-book stylized facts | normalized OFI/MLOFI and impact-aware confirmation |
| 4 | Cartea, Jaimungal & Penalva, *Algorithmic and High-Frequency Trading* (2015) | 9.0/10 | adverse selection, order-book signals, execution and inventory control | convert signals into executable, cost-aware decisions |

## Four core papers - ranked

1. **Hasbrouck (1991), Measuring the Information Content of Stock Trades** - 10/10. Teaches that trade effects can arrive with lag and should be measured as persistent price impact, not merely the next tick.
2. **Cont, Kukanov & Stoikov (2014), The Price Impact of Order Book Events** - 10/10. Establishes Order Flow Imbalance as a stronger short-horizon explanatory variable than raw traded volume and links impact to depth.
3. **Easley, López de Prado & O'Hara (2012), Flow Toxicity and Liquidity in a High-Frequency World** - 8.5/10. Introduces toxicity/VPIN concepts. Use as one feature family only; never as a standalone trigger.
4. **Kolm, Turiel & Westray (2023), Deep Order Flow Imbalance** - 9.0/10. Shows stationary Order Flow-derived inputs can outperform raw book states for short-horizon forecasting. Use only after interpretable baselines and leakage-safe testing.

## Required concepts and formulas

### Aggressive trade imbalance

`TI = (V_buy_aggressive - V_sell_aggressive) / max(V_total_aggressive, epsilon)`

Use rolling event/time/volume windows and record the window type. If the exchange does not supply aggressor side, document and test the classifier.

### Order Flow Imbalance (OFI)

Compute from changes at bid/ask price and size, not from candle volume. Distinguish price-level replacement from size change. Aggregate multiple levels into MLOFI with calibrated weighting.

### Queue imbalance

`QI = (Depth_bid - Depth_ask) / max(Depth_bid + Depth_ask, epsilon)`

QI is conditional evidence, not a direction guarantee. Its usefulness varies with tick size, depth and horizon.

### Microprice

A size-weighted near-touch estimate that shifts toward the thinner side of the book. Store both raw difference and spread/tick-normalized difference from mid.

### Absorption vs exhaustion

- **Absorption**: meaningful aggressive volume executes but price fails to progress because resting liquidity replenishes/holds.
- **Exhaustion**: aggressive flow and execution rate decay after a directional attempt; book pressure normalizes or reverses.

### Sweep and recovery

Measure levels consumed, signed size, spread expansion, continuation, and time/depth recovery. A sweep through an Order Block without rapid recovery is evidence against the block.

## E08 integration

E08 sends zone, direction, structure reason, first-touch/retest status and invalidation. E10 returns ALLOW/WAIT/REJECT with expiry. E08 does not reinterpret a stale packet and E17 does not accept a packet after expiry.

## What must never happen

- infer Order Flow from candle color alone;
- approve an OB because a large wall is visible in one snapshot;
- compare raw depth across symbols without normalization;
- use CVD without explicit reset/window policy;
- train a complex model before a transparent baseline and leakage audit;
- claim causality or guaranteed direction from imbalance.
