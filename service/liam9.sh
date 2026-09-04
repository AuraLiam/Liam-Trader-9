#!/usr/bin/env bash
# لیام تریدر ۹ — یک فرمان، برای همیشه.  (مک و لینوکس)
#
# حمید (۴ سپتامبر): «به ساده‌ترین شکل ممکن اجرا شود و بی‌وقفه پشتیبان من باشی.»
#
#   bash service/liam9.sh            روشن کن و روشن نگه دار
#   bash service/liam9.sh doctor     فقط بگو این ماشین آماده است یا نه
#   bash service/liam9.sh boot       با روشن‌شدن لپ‌تاپ خودش بالا بیاید
#   bash service/liam9.sh stop       خاموش کن
#
# «بی‌وقفه» یعنی: اگر فرایند بمیرد، همین اسکریپت دوباره بالایش می‌آورد؛
# اگر لپ‌تاپ ریست شود، `boot` کاری می‌کند که خودش برگردد. هیچ‌کدام به
# گیت‌هاب کاری ندارند.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
ROOT="$PWD"
PYDIR="$ROOT/claude-liam-signal/python"
PIDF="$ROOT/signals/liam9d.pid"
OUT="$ROOT/signals/liam9d.out"

pick_python() {
  for p in python3.12 python3.11 python3 python; do
    command -v "$p" >/dev/null 2>&1 && { echo "$p"; return; }
  done
  echo ""
}

# فقط **مسیر پایتون** روی stdout؛ هر پیامی روی stderr.
# (اولین نسخه هر دو را روی stdout می‌داد و `VP=$(setup)` متنِ فارسیِ
#  «→ ساخت محیط…» را به‌عنوان مسیرِ مفسر می‌گرفت. اجرا شد، افتاد، رفع شد.)
setup() {
  PY=$(pick_python)
  if [ -z "$PY" ]; then
    echo "پایتون پیدا نشد. از python.org نصب کن و دوباره بزن." >&2
    exit 1
  fi
  VP="$ROOT/.venv/bin/python"
  if [ ! -x "$VP" ]; then
    echo "→ ساخت محیط پایتون (یک بار، ~۱ دقیقه)" >&2
    if ! "$PY" -m venv "$ROOT/.venv" >&2 2>&1; then
      # روی بعضی نصب‌ها venv نیست؛ نبودنش دلیل نمی‌شود سرویس بالا نیاید.
      echo "  محیط جدا ساخته نشد — با پایتون خودِ سامانه ادامه می‌دهم" >&2
      VP="$PY"
    fi
  fi
  if ! "$VP" -c "import requests, matplotlib, arabic_reshaper, bidi, yaml" 2>/dev/null; then
    echo "→ نصب کتابخانه‌ها (یک بار)" >&2
    "$VP" -m pip -q install --upgrade pip >&2 2>&1
    if ! "$VP" -m pip -q install -r "$ROOT/requirements-ci.txt" >&2 2>&1; then
      echo "  نصب کامل نشد — دکتر پایین می‌گوید دقیقاً چه چیزی کم است" >&2
    fi
  fi
  echo "$VP"
}

case "${1:-run}" in
  doctor)
    VP=$(setup) || exit 1
    cd "$PYDIR" && exec "$VP" -m hamid.liam9d --doctor
    ;;

  stop)
    if [ -f "$PIDF" ] && kill -0 "$(cat "$PIDF")" 2>/dev/null; then
      kill "$(cat "$PIDF")" && echo "خاموش شد."
    else
      echo "چیزی روشن نبود."
    fi
    pkill -f "hamid.liam9d" 2>/dev/null
    rm -f "$PIDF"
    ;;

  boot)
    # با روشن‌شدن لپ‌تاپ، خودش بالا بیاید.
    if [ "$(uname)" = "Darwin" ]; then
      PL="$HOME/Library/LaunchAgents/com.liam9.trader.plist"
      mkdir -p "$HOME/Library/LaunchAgents"
      cat > "$PL" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.liam9.trader</string>
  <key>ProgramArguments</key>
  <array><string>/bin/bash</string><string>$ROOT/service/liam9.sh</string></array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$OUT</string>
  <key>StandardErrorPath</key><string>$OUT</string>
</dict></plist>
PLIST
      launchctl unload "$PL" 2>/dev/null
      launchctl load -w "$PL" && echo "✓ با هر بار روشن‌شدن مک، خودش بالا می‌آید."
    else
      U="$HOME/.config/systemd/user"; mkdir -p "$U"
      cat > "$U/liam9.service" <<UNIT
[Unit]
Description=Liam Trader 9 — local service
[Service]
ExecStart=/bin/bash $ROOT/service/liam9.sh
Restart=always
RestartSec=10
[Install]
WantedBy=default.target
UNIT
      systemctl --user daemon-reload
      systemctl --user enable --now liam9.service \
        && loginctl enable-linger "$USER" 2>/dev/null
      echo "✓ با هر بار روشن‌شدن، خودش بالا می‌آید."
    fi
    ;;

  *)
    VP=$(setup) || exit 1
    echo "$$" > "$PIDF"
    echo "لیام تریدر ۹ — سرویس محلی"
    echo "پنل: http://127.0.0.1:${LIAM9D_PORT:-9009}"
    echo "توقف: Ctrl+C  ·  لاگ: $OUT"
    echo
    # حلقهٔ بی‌وقفه: هر مرگی، ۱۰ ثانیه بعد دوباره بالا. عمداً ساده —
    # چیزی که خودش می‌تواند خراب شود، نباید نگهبانِ بقیه باشد.
    trap 'rm -f "$PIDF"; exit 0' INT TERM
    n=0
    while true; do
      n=$((n + 1))
      ( cd "$PYDIR" && "$VP" -m hamid.liam9d ) 2>&1 | tee -a "$OUT"
      echo "[$(date '+%F %T')] سرویس ایستاد (بار $n) — ۱۰ ثانیه دیگر دوباره" \
        | tee -a "$OUT"
      sleep 10
    done
    ;;
esac
