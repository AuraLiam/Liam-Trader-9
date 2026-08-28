#!/bin/bash
# استارتاپ مک — فقط پنج چیز (دستور حمید، ۲۸ اوت)
#
# اجرا:
#   bash startup-macos.sh          # فقط گزارش، چیزی عوض نمی‌شود
#   bash startup-macos.sh --apply  # اعمال
#   bash startup-macos.sh --restore
#
# مک دو جای استارتاپ دارد و این اسکریپت هر دو را می‌بیند:
#   ۱) Login Items (تنظیمات سیستم)
#   ۲) LaunchAgents کاربر (~/Library/LaunchAgents)

set -euo pipefail
PANEL_URL="https://auraliam.github.io/Liam-Trader-9/aura/"
LA="$HOME/Library/LaunchAgents"
BAK="$HOME/Library/LaunchAgents-disabled-liam9"
MODE="${1:-report}"

apps=("AuraLiam Max" "Claude" "ChatGPT" "Visual Studio Code")

echo "=== وضعیت فعلی استارتاپ ==="
echo "--- Login Items ---"
osascript -e 'tell application "System Events" to get the name of every login item' 2>/dev/null \
  | tr ',' '\n' | sed 's/^ */   • /' || echo "   (خواندن ممکن نشد — به Terminal اجازهٔ Automation بده)"
echo "--- LaunchAgents ---"
ls -1 "$LA" 2>/dev/null | sed 's/^/   • /' || echo "   (خالی)"

if [ "$MODE" = "--restore" ]; then
  [ -d "$BAK" ] && mv "$BAK"/* "$LA"/ 2>/dev/null || true
  echo "LaunchAgents برگشت. Login Itemها را از تنظیمات سیستم دستی برگردان."
  exit 0
fi

if [ "$MODE" != "--apply" ]; then
  echo
  echo "(حالت گزارش — چیزی عوض نشد. برای اعمال: bash startup-macos.sh --apply)"
  exit 0
fi

# ۱) همهٔ Login Itemهای فعلی حذف شوند
osascript -e 'tell application "System Events" to delete every login item' 2>/dev/null \
  || echo "هشدار: حذف Login Items نشد — دستی از System Settings → General → Login Items"

# ۲) LaunchAgentهای کاربر غیرفعال (منتقل، نه حذف)
if [ -d "$LA" ] && [ -n "$(ls -A "$LA" 2>/dev/null)" ]; then
  mkdir -p "$BAK"
  for f in "$LA"/*; do
    launchctl unload "$f" 2>/dev/null || true
    mv "$f" "$BAK"/
    echo "غیرفعال شد: $(basename "$f")"
  done
fi

# ۳) پنج موردِ مجاز
for a in "${apps[@]}"; do
  if [ -d "/Applications/$a.app" ]; then
    osascript -e "tell application \"System Events\" to make login item at end \
      with properties {path:\"/Applications/$a.app\", hidden:false}" >/dev/null
    echo "استارتاپ: $a"
  else
    echo "✗ $a پیدا نشد در /Applications — نامش را داخل اسکریپت اصلاح کن"
  fi
done

# پنل به‌صورت اپ در مرورگر
cat > "$HOME/Library/LaunchAgents/com.liam9.panel.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.liam9.panel</string>
  <key>ProgramArguments</key>
  <array><string>/usr/bin/open</string><string>$PANEL_URL</string></array>
  <key>RunAtLoad</key><true/>
</dict></plist>
PLIST
launchctl load "$HOME/Library/LaunchAgents/com.liam9.panel.plist" 2>/dev/null || true
echo "استارتاپ: پنل لیام تریدر ۹ → $PANEL_URL"
echo
echo "تمام. بعد از ری‌استارت فقط همین موارد بالا می‌آیند."
