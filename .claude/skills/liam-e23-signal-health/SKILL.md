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

<!-- adaptive-mandate -->
## مأموریت وفق‌پذیری و درخواست داده (قانون ۱۹ — دستور حمید ۱۴ سپتامبر)

ثابت نمان: هر بازبینی با سه جمله شروع می‌شود — رژیم بازار از دور قبل چه
فرقی کرد؟ کدام فرضیه‌ام به‌روز می‌شود؟ کدام داده را کم دارم؟ همراه با پول
و بی‌تعصب: `signals/market-stance.json` و دامیننس‌ها را پیش از حکم بخوان؛
نزولی = شورت‌گرا، صعودی = لانگ‌گرا، باطل‌کننده را همان‌جا بنویس. زنجیرهٔ
استدلال صریح: شواهد → تفسیر → حکم → باطل‌کننده؛ نمی‌دانی، حدس نزن.
آزادی فقط در پیپر (experiments + CI)؛ هیچ دروازه‌ای در تولید بی CI بالای
صفر و تأیید حمید عوض نمی‌شود (قانون ۰۳/۱۲)؛ خبر و رویداد دیدگاه‌اند نه
دروازه (قانون ۱۵). **داده را خودت نرو بیاور — سفارش بده:** نیاز تازه را با
`python3 -m hamid.data_requests --add E23 <kline|feed|state> k=v …` ثبت
کن؛ هر ۵ دقیقه جمع می‌شود و با `python3 -m hamid.data_requests --for E23`
می‌خوانی. خروجی هر بازبینی = بستهٔ شواهد (قانون ۱۲) + یک خط «چه یاد
گرفتم / چه داده‌ای سفارش دادم». متن کامل: docs/AGENT-ADAPTIVE-MANDATE-FA.md
