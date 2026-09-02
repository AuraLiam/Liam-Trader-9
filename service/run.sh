#!/usr/bin/env bash
# سرویس سایهٔ محلی لیام تریدر ۹ — لینوکس/مک (لپ‌تاپ حمید، استارلینک).
# بدون تلگرام، بدون اجرای زنده؛ خروجی فقط signals/shadow/. قانون ۰۲.
#
# نصب یک‌بار:   python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements-ci.txt
# اجرا:         bash service/run.sh            (Ctrl+C برای توقف)
# آزمایش نصب:   python3 -m hamid.shadow_service --once   (از داخل claude-liam-signal/python)
set -u
cd "$(dirname "$0")/.." || exit 1
[ -f .venv/bin/activate ] && . .venv/bin/activate
export LIAM9_CANDLES="${LIAM9_CANDLES:-perp}"
export LIVE_EXECUTION=false
unset TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID
cd claude-liam-signal/python || exit 1
while true; do
  echo "[$(date -u '+%F %T')] سرویس سایه بالا می‌آید"
  python3 -m hamid.shadow_service --interval "${LIAM9_SHADOW_INTERVAL:-300}" --symbols "${LIAM9_SHADOW_SYMBOLS:-200}"
  echo "[$(date -u '+%F %T')] فرایند مرد (کد $?) — ۱۰ ثانیه بعد دوباره"
  sleep 10
done
