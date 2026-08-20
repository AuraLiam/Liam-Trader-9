---
name: liam-e23-signal-health
description: Diagnose why the Liam Trader 9 panel has not sent validated signals, distinguish healthy no-setup periods from pipeline failures, and verify scheduler, data, engine, committee, risk, and Telegram delivery health.
allowed-tools: Read, Grep, Glob, Bash
---

# E23 Signal Funnel Health Skill

## Required funnel

Track per scan/window:

1. universe eligible;
2. data fresh/valid;
3. macro/dominance gate;
4. HTF structure;
5. strategy sequence/pullback;
6. OB/FVG/location;
7. IBS/candle evidence;
8. E10 Order Flow/Level 2;
9. fee/slippage/net RR;
10. risk/cooldown;
11. E17 decision;
12. E25 delivery receipt.

## Classifications

- `NO_VALID_SETUP_HEALTHY`
- `PIPELINE_DEGRADED`
- `SIGNAL_SUPPRESSED_BY_RISK`
- `SIGNAL_READY`
- `DELIVERY_FAILED`

For each classification, include evidence, last-success timestamps, stale components, rejection counts, queue latency, and remediation. A long quiet period is not itself a defect.

## Alerting

Do not send routine “still alive” Telegram spam. Alert only when a health SLO is breached, recovery occurs, or a validated signal/delivery event requires notification.
