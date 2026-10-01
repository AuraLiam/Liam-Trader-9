#!/usr/bin/env bash
# تازه‌سازیِ فایل‌هایی که **این اجرا ننوشته** از نوکِ origin — پیش از داوری.
#
# چرا لازم شد (۱ اکتبر ۱۴:۲۸ UTC): گذرگاه وضعیت (hamid.state_bus) در انتهای
# یک job ~۳۰دقیقه‌ایِ چرخهٔ حمید روی چک‌اوتِ **شروعِ job** داوری کرد و
# SICK داد — ۷ فایل «۴۵ دقیقه کهنه» که روی origin همان لحظه ۲ دقیقه سن
# داشتند (زنجیرهٔ سیگنال در این فاصله تازه‌شان کرده بود). داوری روی عکسِ
# کهنه، آلارمِ کاذب می‌سازد و آلارم کاذب نادیده گرفته می‌شود (قانون ۱۳).
#
# قاعده (همان مرزِ ناشر یگانه، قانون ۱۴): فایلی که ما در درختِ کار دست
# زده‌ایم هرگز تازه نمی‌شود؛ فقط فایلی که بین HEAD و نوکِ origin فرق دارد
# **و** ما ننوشته‌ایم، نسخهٔ origin را می‌گیرد. هیچ merge، هیچ reset، هیچ
# فرمانِ شبکه‌ایِ بی‌سقف. شکستِ fetch = هیچ تغییری (چک‌اوتِ فعلی می‌ماند).
#
# استفاده:  scripts/refresh_unwritten.sh مسیر [مسیر...]
# متغیرها: PUBLISH_REMOTE (origin) · PUBLISH_BRANCH (main) · PUBLISH_NET_TIMEOUT (120)
set -u
REMOTE="${PUBLISH_REMOTE:-origin}"
BRANCH="${PUBLISH_BRANCH:-main}"
NET_TIMEOUT="${PUBLISH_NET_TIMEOUT:-120}"
[ $# -gt 0 ] || { echo "refresh: مسیر داده نشده"; exit 2; }
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
_say() { echo "refresh $(date -u +%H:%M:%S): $*"; }

if ! timeout "$NET_TIMEOUT" git fetch -q --depth=1 "$REMOTE" "$BRANCH" 2>/dev/null; then
  _say "fetch نشد — چک‌اوتِ فعلی می‌ماند"
  exit 0
fi
TIP="$(git rev-parse "$REMOTE/$BRANCH" 2>/dev/null || git rev-parse FETCH_HEAD)"

# فایل‌هایی که همین اجرا نوشته (تغییرِ کامیت‌نشده یا فایلِ تازهٔ ردیابی‌نشده)
MINE="$(git -c core.quotepath=false diff --name-only HEAD -- "$@"
git -c core.quotepath=false ls-files --others --exclude-standard -- "$@")"

n=0; kept=0
while IFS= read -r f; do
  [ -n "$f" ] || continue
  if printf '%s\n' "$MINE" | grep -qxF -- "$f"; then
    kept=$((kept + 1)); continue
  fi
  # فایلی که origin حذف کرده، این‌جا دست نمی‌خورد (حذف کارِ ناشر است)
  git cat-file -e "$TIP:$f" 2>/dev/null || continue
  git checkout -q "$TIP" -- "$f" 2>/dev/null && n=$((n + 1))
done < <(git -c core.quotepath=false diff --name-only HEAD "$TIP" -- "$@" 2>/dev/null)
_say "$n فایل از origin تازه شد · $kept فایلِ نوشته‌شدهٔ همین اجرا دست نخورد"
exit 0
