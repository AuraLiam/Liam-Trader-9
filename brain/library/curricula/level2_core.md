# Level 2 Anti-Liquidity-Trap Curriculum - E10

## Why E10 owns Level 2

Level 2 is a time series of aggregated resting liquidity by price level. It belongs with Order Flow/liquidity, not with candle geometry. E09 may consume a summary, while E08 uses E10 to validate a zone.

## Four core books - ranked

| Rank | Source | Importance | Main lesson for E10 |
|---|---|---:|---|
| 1 | Abergel et al., *Limit Order Books* (2016) | 10/10 | mathematical/statistical LOB models, queue dynamics and empirical features |
| 2 | Lehalle & Laruelle, *Market Microstructure in Practice*, 2nd ed. (2018) | 9.7/10 | practical data handling, execution, toxicity and book interpretation |
| 3 | Olivier Guéant, *The Financial Mathematics of Market Liquidity* (2016) | 9.0/10 | liquidity risk, impact, execution and inventory implications |
| 4 | Irene Aldridge, *High-Frequency Trading*, 2nd ed. (2013) | 8.5/10 | event-driven architecture, data and short-horizon implementation discipline |

## Four core papers - ranked

1. **Gould et al. (2013), Limit Order Books** - 10/10 survey and terminology foundation.
2. **Gould & Bonart (2016), Queue Imbalance as a One-Tick-Ahead Price Predictor in a Limit Order Book** - 9.5/10; shows statistically meaningful conditional next-move information, varying by market structure.
3. **Cartea, Donnelly & Jaimungal (2018), Enhancing Trading Strategies with Order Book Signals** - 9.4/10; connects imbalance to market-order sign and short-term movement in an executable framework.
4. **Lin & Putniņš (2023), Detecting Layering and Spoofing in Markets** - 9.0/10; empirical detection signals include quote imbalance, order activity, abnormal cancellations and cyclical depth/cancellation patterns. Treat as spoof-like risk, not proof of intent.

## Anti-trap features

### Wall persistence

Track displayed size as price approaches. Measure lifetime, fraction retained, and whether the wall moves away. A wall that disappears before touch is weak evidence.

### Execution-to-displayed ratio

Displayed size matters more when actual trades execute against it. High display with near-zero execution and repeated cancellation raises trap risk.

### Replenishment / iceberg-like behavior

Repeated executed volume with stable or recovering displayed size suggests hidden/replenishing interest. Level 2 cannot identify individual hidden orders, so label probabilistically.

### Cancellation-before-touch

Measure cancellation intensity conditioned on decreasing distance to the level. Compare with symbol/regime baseline.

### Cyclical depth behavior

Repeated appearance, cancellation and reappearance at similar distances can be a manipulation-like pattern. Use anomaly scores and do not assert intent.

### Multi-level flow

Top level is important, but deeper levels can improve confirmation. Use MLOFI, book slope/convexity, and distance-weighted depth rather than a single imbalance number.

### Sweep/recovery

A genuine liquidity level may absorb and replenish. A weak level may vanish or be swept with slow recovery. Measure both execution and subsequent state.

## Level 2 limitations

- Aggregated L2 usually lacks individual order IDs and true queue position.
- Crypto liquidity is fragmented; one venue's book is not the whole market.
- Cross-venue data may have different timestamps, symbols and contract specifications.
- Book signals decay rapidly and require expiration.
- A model can detect suspicious behavior, not establish legal intent.

## Data pipeline

Venue WebSocket -> integrity checks -> normalized event store -> feature windows -> E10 packet -> E08/E15/E17 -> outcome capture -> E18 replay -> E21 validated memory.
