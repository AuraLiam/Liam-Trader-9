# Candlestick / Price-Bar Curriculum - E09

## Core idea

Candles are compact descriptions of price geometry. They can help describe rejection, displacement, compression, closing location and failed breaks, but academic evidence does not support treating named candle patterns as universally profitable standalone signals. Their value must be measured conditionally inside Hamid's strategy.

## Four core books - ranked

| Rank | Source | Importance | What E09 must learn | Limitation control |
|---|---|---:|---|---|
| 1 | Steve Nison, *Japanese Candlestick Charting Techniques*, 2nd ed. (2001) | 9.5/10 | canonical vocabulary and multi-bar pattern definitions | translate every visual definition into numerical geometry |
| 2 | Gregory Morris, *Candlestick Charting Explained*, 3rd ed. (2006) | 9.0/10 | systematic definitions and pattern testing mindset | do not inherit equity-gap assumptions blindly into 24/7 crypto |
| 3 | Thomas Bulkowski, *Encyclopedia of Candlestick Charts* (2008) | 8.8/10 | empirical pattern catalog and failure behavior | re-test on Bitunix crypto, current regimes and costs |
| 4 | Adam Grimes, *The Art and Science of Technical Analysis* (2012) | 9.2/10 | context, market structure, expectancy, risk and avoiding pattern mythology | use candles as evidence inside a complete setup |

## Four core papers - balanced evidence

1. **Caginalp & Laurent (1998), The Predictive Power of Price Patterns** - positive evidence under specified definitions; useful for formalization.
2. **Fock, Klein & Zwergel (2005), Performance of Candlestick Analysis on Intraday Futures Data** - found no standalone predictive ability in tested intraday futures; essential negative control.
3. **Marshall, Young & Rose (2006), Candlestick Technical Trading Strategies: Can They Create Value for Investors?** - weak/no economic value in their sample; reinforces cost and benchmark discipline.
4. **Duvinage, Mazza & Petitjean (2013), The Intra-Day Performance of Market Timing Strategies and Trading Systems Based on Japanese Candlesticks** - some raw predictability, but no robust outperformance after costs and data-snooping controls.

Supplementary evidence: Lu and coauthors find profitability can depend on trend definition and holding rules. Treat this as support for context conditioning, not universal pattern validity.

## Quantitative bar model

For each bar:

- `range = H - L`
- `body = abs(C - O)`
- `upper_wick = H - max(O, C)`
- `lower_wick = min(O, C) - L`
- `IBS = (C - L) / (H - L)` with zero-range handling
- body/range, wick/range, close-to-extreme, ATR-normalized range/body
- volume percentile and spread/depth conditions at close

## Context hierarchy

1. 4H macro structure and major S/R.
2. 1H structure, OB/FVG and direction.
3. 15m location, pullback sequence and liquidity context.
4. 5m timing and invalidation.
5. E10 Order Flow/Level 2 confirmation.

## Practical labels

- **Rejection**: excursion into/through a zone followed by close back toward the originating side, with wick and close-location thresholds.
- **Displacement**: ATR-normalized range/body plus close beyond a structure boundary and supporting volume/flow.
- **Compression**: declining range/ATR and directional overlap toward a level.
- **Failed break**: trade beyond boundary followed by return/close inside, ideally with liquidity sweep and flow reversal.
- **Engulfing**: define body/range overlap precisely; do not use name-only matching.

## Crypto-specific rule

Classical gap-based definitions are downweighted because crypto trades continuously. Real discontinuities (venue outage, data gap, listing event) must be distinguished from normal candles.

## Promotion rule

A candle feature survives only when strategy + feature improves out-of-sample net expectancy, drawdown, calibration or entry quality versus the same strategy without that feature, after costs and multiple-testing adjustment.
