#!/usr/bin/env bash
# راه‌اندازیِ پوشه/چتِ تازه — کم‌عمق، سریع، بی‌حدس (دستور حمید ۱۴ سپتامبر).
#
# چرا: تاریخچهٔ مخزن ۴.۴ گیگابایت است؛ کلونِ کامل و fetch/push روی آن دقیقه‌ها
# طول می‌کشد (همان علتی که میز اسکلپ را ۱۳ ساعت خواباند). کلونِ کم‌عمق چند
# ثانیه است و ناشر مشترک (scripts/publish.sh) از قبل با نوکِ کم‌عمق کار می‌کند.
#
#   scripts/bootstrap-session.sh [مسیر مقصد]     # پیش‌فرض: ../liam-trader-9-fresh
#
# بعد از اجرا، در چتِ تازه فقط این را بگو:
#   «از claude-liam-signal/HANDOFF.md ادامه بده؛ اول review_queue را بزن و فقط روی needs_reasoning کار کن.»
set -euo pipefail
DEST="${1:-../liam-trader-9-fresh}"
URL="https://github.com/AuraLiam/Liam-Trader-9.git"
if [ -e "$DEST/.git" ]; then
  echo "▸ $DEST از قبل هست — فقط تازه می‌کنم"; git -C "$DEST" fetch -q --depth=50 origin main && git -C "$DEST" reset -q --hard origin/main
else
  echo "▸ کلونِ کم‌عمق (۵۰ کامیت) → $DEST"; git clone -q --depth=50 --single-branch --branch main "$URL" "$DEST"
fi
cd "$DEST"
echo "▸ محیط یگانه (قانون ۱۴)"; pip -q install -r requirements-ci.txt 2>/dev/null || echo "  (pip دردسترس نبود — ماژول‌های استاندارد کافی‌اند)"
cd claude-liam-signal/python
echo; echo "▸ حکم سامانه (قانون ۱۳)"; python3 -m hamid.mcp_server --call state_packet | head -3
echo; echo "▸ صف بازبینی (قانون ۱۷/۱۸)"; python3 -m hamid.mcp_server --call review_queue | head -12
echo; echo "▸ بک‌آپ‌های تأییدشده"; git ls-remote --heads origin 'refs/heads/backup/*' | awk '{print "  "$2}' | tail -3
echo; echo "✓ آماده. پین: claude-liam-signal/HANDOFF.md — پیام اول: «از HANDOFF.md ادامه بده؛ اول review_queue را بزن»"
