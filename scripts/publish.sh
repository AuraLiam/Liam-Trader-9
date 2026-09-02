#!/usr/bin/env bash
# ناشر مشترک همهٔ ورک‌فلوها — «یک ناشر، یک آزمون» (دستور حمید، ۲ سپتامبر:
# «قرار نیست این مشکل برای همیشه برطرف بشه؟»)
#
# چرا لازم شد: ۴۶ ورک‌فلو داشتیم، ۴۱تا push می‌کردند، ۳۶تا حلقهٔ انتشارِ
# دست‌نویسِ خودشان را داشتند، ۹تا با reset سخت، و فقط ۱۸تا از حل‌کنندهٔ
# معنادار استفاده می‌کردند. سه قطعیِ یک روز (۲ سپتامبر) هر سه از همین
# تکثیر آمدند. هر ناشرِ تازه = یک راهِ تازه برای خرابی. پس یکی، با آزمونِ
# رفتاری (hamid/test_publish.py).
#
# چرا merge نمی‌کند: تاریخچهٔ مخزن ۴.۴ گیگابایت است. merge روی چک‌اوتِ
# کم‌عمق یا باید تاریخچه بکشد (دو بار job را تا سقف ۱۵ دقیقه خواباند) یا
# تاریخچه را بی‌ربط می‌بیند و هزاران تعارضِ ساختگی می‌سازد (اجرای ۳۶۱).
# پس ناشر **بر پایهٔ محتوا** کار می‌کند: نوکِ تازهٔ origin را (کم‌عمق،
# ارزان) می‌گیرد و فقط فایل‌هایی را که همین اجرا نوشته، هر کدام با معنای
# خودش (scripts/publish_merge.py → resolve_brain_conflicts)، روی همان
# نوک می‌نشاند و یک کامیتِ تازه می‌سازد — بدون merge، بدون چک‌اوت، بدون
# دست‌زدن به فایلی که ما ننوشته‌ایم.
#
# استفاده:
#   scripts/publish.sh -m "پیام کامیت" مسیر [مسیر...]
#   متغیرها: PUBLISH_BRANCH (main) · PUBLISH_REMOTE (origin) ·
#            PUBLISH_ATTEMPTS (8) · PUBLISH_NET_TIMEOUT (120 ثانیه)
#
# قرارداد:
#   ۱. فقط مسیرهای داده‌شده add می‌شوند؛ چیزی برای انتشار نبود → خروج ۰.
#   ۲. خروجیِ همین اجرا هرگز دور ریخته نمی‌شود (نه reset، نه فهرست سفت).
#   ۳. دفتر append-only → اجتماع؛ عکس‌فوری/نشانگر → قاعدهٔ خودش؛ فایلی که
#      ما ننوشته‌ایم → دقیقاً نسخهٔ origin. هیچ تعارضی job را نمی‌کشد.
#   ۴. هیچ فرمانِ شبکه‌ای بی‌سقف نیست و هر مرحله با ساعت روی لاگ می‌آید.
#   ۵. ۸ تلاش با jitter؛ بعد از آن خروج ۱ (خرابیِ واقعیِ شبکه/ریموت).
set -u

REMOTE="${PUBLISH_REMOTE:-origin}"
BRANCH="${PUBLISH_BRANCH:-main}"
ATTEMPTS="${PUBLISH_ATTEMPTS:-8}"
NET_TIMEOUT="${PUBLISH_NET_TIMEOUT:-120}"
ROOT="$(git rev-parse --show-toplevel)"
MERGER="$ROOT/scripts/publish_merge.py"
MSG=""
PATHS=()
while [ $# -gt 0 ]; do
  case "$1" in
    -m) MSG="$2"; shift 2 ;;
    *)  PATHS+=("$1"); shift ;;
  esac
done
[ ${#PATHS[@]} -gt 0 ] || { echo "publish: مسیر داده نشده"; exit 2; }
[ -n "$MSG" ] || MSG="انتشار $(date -u '+%Y-%m-%d %H:%M') UTC"

cd "$ROOT"
git config user.name  >/dev/null 2>&1 || git config user.name  "Claude"
git config user.email >/dev/null 2>&1 || git config user.email "noreply@anthropic.com"
_say() { echo "publish $(date -u +%H:%M:%S): $*"; }
_net() { timeout "$NET_TIMEOUT" "$@"; }

# ── ۱) فقط خروجیِ همین اجرا، در یک کامیت محلی ────────────────────────────
git add -A -- "${PATHS[@]}" 2>/dev/null || true
if git diff --cached --quiet; then
  _say "بدون تغییر"
  exit 0
fi
CHANGED="$(git -c core.quotepath=false diff --cached --name-only)"
git commit -q -m "$MSG" || { _say "کامیت نشد"; exit 1; }
OURS="$(git rev-parse HEAD)"
_say "$(printf '%s\n' "$CHANGED" | wc -l | tr -d ' ') فایل کامیت شد"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# ── ۲) کامیتِ ما را روی نوکِ تازهٔ origin بازمی‌سازیم (بدون merge) ───────
_build_on() {
  # $1 = نوکِ origin. خروجی: sha کامیت تازه روی stdout.
  local base="$1" idx="$TMP/index" f blob mode ours_f theirs_f out_f
  rm -f "$idx"
  GIT_INDEX_FILE="$idx" git read-tree "$base" || return 1
  while IFS= read -r f; do
    [ -n "$f" ] || continue
    ours_f="$TMP/ours"; theirs_f="$TMP/theirs"; out_f="$TMP/out"
    rm -f "$ours_f" "$theirs_f" "$out_f"
    if git cat-file -e "$OURS:$f" 2>/dev/null; then
      git cat-file -p "$OURS:$f" > "$ours_f"
    else
      ours_f="-"
    fi
    if git cat-file -e "$base:$f" 2>/dev/null; then
      git cat-file -p "$base:$f" > "$theirs_f"
    else
      theirs_f="-"
    fi
    if [ "$ours_f" = "-" ]; then
      GIT_INDEX_FILE="$idx" git update-index --force-remove -- "$f" 2>/dev/null || true
      continue
    fi
    if [ "$theirs_f" = "-" ] || cmp -s "$ours_f" "$theirs_f"; then
      cp "$ours_f" "$out_f"
    else
      python3 "$MERGER" "$f" "$ours_f" "$theirs_f" "$out_f" || cp "$ours_f" "$out_f"
    fi
    [ -f "$out_f" ] || cp "$ours_f" "$out_f"
    if grep -qE "^(<<<<<<< |>>>>>>> )" "$out_f" 2>/dev/null; then
      _say "مارکر تعارض در $f — نسخهٔ ما"; cp "$ours_f" "$out_f"
    fi
    blob="$(git hash-object -w "$out_f")"
    mode="$(git ls-tree "$OURS" -- "$f" | awk '{print $1}')"
    [ -n "$mode" ] || mode=100644
    GIT_INDEX_FILE="$idx" git update-index --add --cacheinfo "$mode,$blob,$f"
    # کارِ ما هم همان چیزی می‌شود که منتشر شد (مثلاً اجتماعِ دفتر)
    mkdir -p "$(dirname "$f")"; cp "$out_f" "$f"
  done <<< "$CHANGED"
  local tree
  tree="$(GIT_INDEX_FILE="$idx" git write-tree)" || return 1
  git commit-tree "$tree" -p "$base" -m "$MSG"
}

for attempt in $(seq 1 "$ATTEMPTS"); do
  _say "fetch $REMOTE/$BRANCH (تلاش $attempt)"
  if ! _net git fetch -q --depth=1 "$REMOTE" "$BRANCH" 2>/dev/null; then
    _say "fetch ناموفق/دیر"; sleep $((attempt * 4 + RANDOM % 7)); continue
  fi
  TIP="$(git rev-parse "$REMOTE/$BRANCH" 2>/dev/null || git rev-parse FETCH_HEAD)"
  if git merge-base --is-ancestor "$TIP" "$OURS" 2>/dev/null; then
    NEW="$OURS"                                   # origin تکان نخورده
  else
    NEW="$(_build_on "$TIP")" || { _say "ساختِ کامیت روی نوک شکست"; sleep $((attempt * 4 + RANDOM % 7)); continue; }
  fi
  _say "push $(git rev-parse --short "$NEW") روی $(git rev-parse --short "$TIP")"
  if _net git push -q "$REMOTE" "$NEW:refs/heads/$BRANCH" 2>/dev/null; then
    # HEAD و فایل‌های مسیرهای منتشرشده به همان چیزی می‌رسند که منتشر شد —
    # گام‌های بعدی (مثلاً انتشار روی پنل) نسخهٔ تازهٔ origin را می‌بینند،
    # نه چک‌اوتِ کهنهٔ رانر را (درس ۲۵ اوت: pump-radar.json کهنه روی تازه).
    git reset -q "$NEW" 2>/dev/null || true
    git checkout -q -- "${PATHS[@]}" 2>/dev/null || true
    _say "منتشر شد (تلاش $attempt)"
    exit 0
  fi
  _say "push رد شد"
  sleep $((attempt * 4 + RANDOM % 7))
done
_say "بعد از $ATTEMPTS تلاش منتشر نشد"
exit 1
