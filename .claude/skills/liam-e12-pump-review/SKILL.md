---
name: liam-e12-pump-review
description: Run or audit the bounded five-times-per-day E12 pump review, historical analog tracking, lead-lag outcome measurement, and pre-move anomaly handoff to E15 without starving validated-signal monitoring.
allowed-tools: Read, Grep, Glob, Bash, WebSearch, WebFetch
---

# E12 Pump Review Skill

## Schedule

- Exactly five completed report windows per local day.
- DST-aware timezone, idempotent window IDs, one backfill maximum.
- LOW-priority queue and rolling resource/API cap.
- Reuse shared ingestion; do not launch duplicate full-universe collectors.

## Report content

Separate:

1. already-moved assets and causal/context notes;
2. historically related/lagged assets;
3. pre-move candidates that have not yet met the real-time anomaly gate;
4. outcome statistics of previous reports.

For every item, show detection vs movement timing, MFE/MAE, +3R/+5R/+7R-before--1R, net costs, lead time, and whether Hamid's actual strategy offered an entry.

## Real-time exception

E12 does not directly send a real-time pump call. It hands a candidate packet to E15. E15 applies data quality, persistence, multi-source, pre-move, duplicate and cooldown gates before any alert.

## Memory

Raw repeated scan logs do not go into startup memory. E20/E21 store only aggregated, reusable findings and exceptional case files with evidence.

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
`python3 -m hamid.data_requests --add E12 <kline|feed|state> k=v …` ثبت
کن؛ هر ۵ دقیقه جمع می‌شود و با `python3 -m hamid.data_requests --for E12`
می‌خوانی. خروجی هر بازبینی = بستهٔ شواهد (قانون ۱۲) + یک خط «چه یاد
گرفتم / چه داده‌ای سفارش دادم». متن کامل: docs/AGENT-ADAPTIVE-MANDATE-FA.md
