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
# مسیرِ ناموجود کلِ `git add` را می‌کشد و هیچ‌چیز stage نمی‌شود — اجرای ۱
# اتاق فومو (۲ سپتامبر ۱۵:۲۵): «brain/fomo» هنوز ساخته نشده بود، پس
# تغییرِ واقعیِ signals/fomo.json هم بی‌صدا «بدون تغییر» شد. فقط مسیرهایی
# add می‌شوند که روی دیسک یا در ایندکس هستند؛ غایب‌ها با اعلام رد می‌شوند.
#
# ⚠️ **حذف هم یک تغییر است** (کشف ۱۱ سپتامبر). دو شرطِ بالا فایلی را که
# عمداً حذف شده «ناموجود» می‌گرفتند: بعد از `git mv` نه روی دیسک است و
# نه در ایندکس، پس مسیر کنار گذاشته می‌شد و **حذف هرگز منتشر نمی‌شد** —
# بی‌صدا. نمونهٔ اندازه‌گیری‌شده: تغییرِ نام موتور داشبورد به «ققنوس»
# منتشر شد ولی فایلِ قدیمی سرِ جایش ماند، یعنی دو نسخه از یک موتور در
# ریپو. همان کلاسِ تکثیری که ناشرِ یگانه قرار بود جلویش را بگیرد.
#
# شرطِ سوم همین را می‌گیرد: مسیری که در HEAD ردیابی شده، حتی اگر الان
# نه روی دیسک باشد نه در ایندکس، هنوز یک تغییرِ واقعی (حذف) دارد.
LIVE=()
for p in "${PATHS[@]}"; do
  if [ -e "$p" ] || git ls-files --error-unmatch -- "$p" >/dev/null 2>&1; then
    LIVE+=("$p")
  else
    _say "مسیر ناموجود نادیده گرفته شد: $p"
  fi
done
[ ${#LIVE[@]} -gt 0 ] && git add -A -- "${LIVE[@]}"
if git diff --cached --quiet; then
  _say "بدون تغییر"
  exit 0
fi
# `--no-renames` عمدی است (کشف ۱۱ سپتامبر): گیت تغییرِ نام را یک ردیفِ
# R100 می‌بیند و `--name-only` فقط **مقصد** را چاپ می‌کند. آن‌وقت مسیرِ
# مبدأ از `CHANGED` می‌افتد، و چون بازسازیِ کامیت روی نوکِ origin فقط
# همین فهرست را می‌پیماید، **حذف هرگز منتشر نمی‌شود** — بی‌صدا.
#
# اندازه‌گیری: تغییرِ نامِ موتور داشبورد به «ققنوس» منتشر شد ولی فایلِ
# قدیمی سرِ جایش ماند؛ یعنی دو نسخه از یک موتور در ریپو — همان کلاسِ
# تکثیری که ناشرِ یگانه قرار بود جلویش را بگیرد. با این پرچم، تغییرِ نام
# دوباره به «حذف + افزودن» باز می‌شود و هر دو سرِ جایشان اعمال می‌شوند.
CHANGED="$(git -c core.quotepath=false diff --cached --no-renames --name-only)"
git commit -q -m "$MSG" || { _say "کامیت نشد"; exit 1; }
OURS="$(git rev-parse HEAD)"
_say "$(printf '%s\n' "$CHANGED" | wc -l | tr -d ' ') فایل کامیت شد"

# فایل‌هایی که در درختِ کار دست‌خورده‌اند ولی جزوِ همین انتشار نبودند —
# یعنی ویرایشِ نیمه‌کارهٔ ایجنت. `_sync_moved` پایین از همگام‌سازی
# مستثنایشان می‌کند تا هرگز دور ریخته نشوند.
#
# **فایلِ ردیابی‌نشده هم باید این‌جا باشد** — و نسخهٔ اولِ همین وصله
# نداشتش. آزمونِ اثباتِ منفی گرفتش: فایلی که محلی ساخته شده ولی هنوز
# tracked نیست، در `git diff` دیده نمی‌شود؛ اگر origin بعداً همان مسیر را
# اضافه کند، همگام‌سازی رویش می‌نوشت و کارِ نیمه‌تمام گم می‌شد.
MINE="$(git -c core.quotepath=false diff --name-only
git -c core.quotepath=false ls-files --others --exclude-standard)"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# ── ۲) کامیتِ ما را روی نوکِ تازهٔ origin بازمی‌سازیم (بدون merge) ───────
_build_on() {
  # $1 = نوکِ origin. خروجی: sha کامیت تازه در "$TMP/new".
  #
  # stdout این تابع عمداً به stderr می‌رود: حل‌کننده برای فایل‌های ناشناختهٔ
  # brain/*.json هشدار روی stdout چاپ می‌کند و اجرای ۳۶۳ چرخه (۱۰:۳۷) همان
  # هشدارها را به‌جای sha گرفت («Needed a single revision»، ۸ تلاش، هیچ
  # انتشاری). sha فقط از فایل خوانده می‌شود، نه از خروجی متنی.
  local base="$1" idx="$TMP/index" f blob mode ours_f theirs_f out_f
  rm -f "$idx" "$TMP/new"
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
  git commit-tree "$tree" -p "$base" -m "$MSG" > "$TMP/new" || return 1
  [ -s "$TMP/new" ] || return 1
} 1>&2

# ── ۳) همگام‌سازیِ آنچه origin جلو برده و ما ننوشته‌ایم ───────────────────
#
# خطِ `git checkout -- "${PATHS[@]}"` فقط مسیرهای **همین انتشار** را تازه
# می‌کند. هر مسیرِ دیگری که CI در فاصلهٔ اجرای ما جلو برده، در درختِ محلی
# کهنه می‌ماند و از آن پس همیشه «تغییریافته» دیده می‌شود.
#
# اندازه‌گیری ۹ سپتامبر: ۶۱ فایل «تغییریافته» که **همه‌شان سمتِ کهنه
# بودند** (نمونه: signals/latest.json محلی ۵۰ دقیقه عقب‌تر از کامیت‌شده،
# brain/events/*.jsonl محلی ۲۲۶ خط در برابر ۲۳۶). هیچ‌کدام دادهٔ
# منتشرنشده نداشتند. خطرش نظری نیست: همین انبوهِ کاذب یک بار نزدیک بود
# ۲۲۳ فایل را «حذف‌شده» کامیت کند — یعنی پاک‌کردنِ پرونده‌هایی که ایجنت
# اصلاً نساخته بود.
#
# دو مرزِ ایمنی، هر دو لازم:
#   الف) فقط فایلی که بین کامیتِ ما و کامیتِ منتشرشده فرق دارد — یعنی
#        origin جلویش برده، نه ما.
#   ب)  فایلی که خودمان در درختِ کار دست زده‌ایم (`MINE`) هرگز همگام
#        نمی‌شود. ویرایشِ کامیت‌نشدهٔ ایجنت دور ریختنی نیست.
_sync_moved() {
  local ours="$1" new="$2" f n=0
  [ "$ours" = "$new" ] && return 0
  while IFS= read -r f; do
    [ -n "$f" ] || continue
    printf '%s\n' "$MINE" | grep -qxF -- "$f" && continue
    git checkout -q "$new" -- "$f" 2>/dev/null && n=$((n + 1))
  done < <(git -c core.quotepath=false diff --name-only "$ours" "$new" 2>/dev/null)
  [ "$n" -gt 0 ] && _say "$n فایل از origin همگام شد"
  return 0
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
    _build_on "$TIP" || { _say "ساختِ کامیت روی نوک شکست"; sleep $((attempt * 4 + RANDOM % 7)); continue; }
    NEW="$(tr -d '[:space:]' < "$TMP/new")"
    git rev-parse -q --verify "$NEW^{commit}" >/dev/null 2>&1 || { _say "sha نامعتبر: '$NEW'"; sleep $((attempt * 4 + RANDOM % 7)); continue; }
  fi
  _say "push $(git rev-parse --short "$NEW") روی $(git rev-parse --short "$TIP")"
  if _net git push -q "$REMOTE" "$NEW:refs/heads/$BRANCH" 2>/dev/null; then
    # HEAD و فایل‌های مسیرهای منتشرشده به همان چیزی می‌رسند که منتشر شد —
    # گام‌های بعدی (مثلاً انتشار روی پنل) نسخهٔ تازهٔ origin را می‌بینند،
    # نه چک‌اوتِ کهنهٔ رانر را (درس ۲۵ اوت: pump-radar.json کهنه روی تازه).
    git reset -q "$NEW" 2>/dev/null || true
    git checkout -q -- "${PATHS[@]}" 2>/dev/null || true
    # مسیری که در کامیتِ منتشرشده دیگر نیست، از درختِ کار هم برداشته
    # می‌شود — وگرنه فایلِ حذف‌شده به شکلِ «ردیابی‌نشده» روی دیسک می‌ماند
    # و نشستِ بعد فکر می‌کند حذف نشده.
    for _p in "${PATHS[@]}"; do
      if [ -f "$_p" ] && ! git cat-file -e "$NEW:$_p" 2>/dev/null; then
        rm -f -- "$_p"
      fi
    done
    _sync_moved "$OURS" "$NEW"
    _say "منتشر شد (تلاش $attempt)"
    exit 0
  fi
  _say "push رد شد"
  sleep $((attempt * 4 + RANDOM % 7))
done
_say "بعد از $ATTEMPTS تلاش منتشر نشد"
exit 1
