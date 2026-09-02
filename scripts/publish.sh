#!/usr/bin/env bash
# ناشر مشترک همهٔ ورک‌فلوها — «یک ناشر، یک آزمون» (دستور حمید، ۲ سپتامبر:
# «قرار نیست این مشکل برای همیشه برطرف بشه؟»)
#
# چرا لازم شد: ۴۶ ورک‌فلو داشتیم، ۴۱تا push می‌کردند، ۳۶تا حلقهٔ انتشارِ
# دست‌نویسِ خودشان را داشتند، ۹تا با reset سخت، و فقط ۱۸تا از حل‌کنندهٔ
# معنادار استفاده می‌کردند. سه قطعیِ یک روز (۲ سپتامبر) هر سه از همین
# تکثیر آمدند: فایلِ بی‌handler که حلقه را کشت، ناشری که فقط دو فایل را
# از reset نجات می‌داد، و محیطی که یک وابستگی کم داشت. هر ناشرِ تازه = یک
# راهِ تازه برای خرابی. پس یکی، با آزمونِ رفتاری (hamid/test_publish.py).
#
# استفاده:
#   scripts/publish.sh -m "پیام کامیت" مسیر [مسیر...]
#   متغیرها: PUBLISH_BRANCH (main) · PUBLISH_REMOTE (origin) ·
#            PUBLISH_ATTEMPTS (8) · PUBLISH_RESOLVER (scripts/resolve_brain_conflicts.py)
#
# قرارداد:
#   ۱. فقط مسیرهای داده‌شده add می‌شوند؛ چیزی برای انتشار نبود → خروج ۰.
#   ۲. اول کامیت، بعد حلقهٔ push/fetch/merge — هرگز reset --hard، چون
#      reset خروجیِ همین اجرا را دور می‌ریزد (عیب work-report، ۱ سپتامبر).
#   ۳. تعارض با «معنا» حل می‌شود (resolve_brain_conflicts: دفتر → اجتماع،
#      عکس‌فوری → تازه‌تر، نشانگر → تاریخ جلوتر). هر چه حل‌کننده جا گذاشت:
#      فایلی که همین اجرا نوشته → نسخهٔ ما؛ غیر آن → نسخهٔ origin. هیچ
#      تعارضی job بی‌ناظر را نمی‌کشد.
#   ۴. هیچ فایلی با مارکر تعارض هرگز push نمی‌شود.
#   ۵. ۸ تلاش با jitter؛ بعد از آن خروج ۱ (خرابیِ واقعیِ شبکه/ریموت).
set -u

REMOTE="${PUBLISH_REMOTE:-origin}"
BRANCH="${PUBLISH_BRANCH:-main}"
ATTEMPTS="${PUBLISH_ATTEMPTS:-8}"
ROOT="$(git rev-parse --show-toplevel)"
RESOLVER="${PUBLISH_RESOLVER:-$ROOT/scripts/resolve_brain_conflicts.py}"
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

# ── ۱) فقط خروجیِ همین اجرا ─────────────────────────────────────────────
git add -A -- "${PATHS[@]}" 2>/dev/null || true
if git diff --cached --quiet; then
  echo "publish: بدون تغییر"
  exit 0
fi
CHANGED="$(git diff --cached --name-only)"
git commit -q -m "$MSG" || { echo "publish: کامیت نشد"; exit 1; }
echo "publish: $(printf '%s\n' "$CHANGED" | wc -l | tr -d ' ') فایل کامیت شد"

# چک‌اوتِ کم‌عمق (fetch-depth: 1) مبنای مشترک ندارد و هر merge را add/add
# می‌کند. عمیق‌کردنِ **محدود** کافی است: origin معمولاً چند کامیت جلوتر
# است، پس ۵۰ کامیت مبنای مشترک را برمی‌گرداند. `--unshallow` روی این
# مخزن (۳۰۰۰+ کامیت، هزاران فایل JSON در تاریخچه) دقیقه‌ها طول می‌کشد و
# یک بار گام انتشار را تا سقف ۱۵ دقیقهٔ job خواباند (۲ سپتامبر ۰۹:۳۹).
# اگر بعد از سه پله هم مبنا پیدا نشد، merge بی‌ربط می‌شود و همان مسیرِ
# آزموده (نانوشته → origin، نوشته → ما) جواب می‌دهد.
_deepen_until_related() {
  git fetch -q "$REMOTE" "$BRANCH" 2>/dev/null || return 0
  local d
  for d in 50 200 800; do
    git merge-base HEAD "$REMOTE/$BRANCH" >/dev/null 2>&1 && return 0
    [ "$(git rev-parse --is-shallow-repository 2>/dev/null)" = "true" ] || return 0
    git fetch -q --deepen="$d" "$REMOTE" "$BRANCH" 2>/dev/null || return 0
  done
}
_deepen_until_related

_in_changed() { printf '%s\n' "$CHANGED" | grep -qxF -- "$1"; }

_settle_untouched() {
  # فایلی که همین اجرا ننوشته ولی در تعارض است (فقط وقتی پیش می‌آید که
  # تاریخچه‌ها بی‌ربط دیده شوند و هر فایلِ متفاوت add/add شود): نسخهٔ
  # origin بی‌چون‌وچرا. وگرنه حل‌کننده «عکس‌فوری → مال ما» را روی
  # چک‌اوتِ کهنهٔ رانر اعمال می‌کند و خروجیِ تازهٔ اجرای دیگر را می‌کوبد
  # (همان عیب ۲۵ اوت: pump-radar.json تازه با نسخهٔ صبح بازنویسی شد).
  local f
  git -c core.quotepath=false diff --name-only --diff-filter=U | while IFS= read -r f; do
    [ -n "$f" ] || continue
    _in_changed "$f" && continue
    git checkout -q --theirs -- "$f" 2>/dev/null || git rm -q --cached -- "$f" 2>/dev/null || true
    git add -- "$f" 2>/dev/null || true
  done
}

_settle_leftovers() {
  # هر چه حل‌کننده جا گذاشت، بر اساس «کی این فایل را نوشته» حل می‌شود.
  local f side
  git -c core.quotepath=false diff --name-only --diff-filter=U | while IFS= read -r f; do
    [ -n "$f" ] || continue
    if _in_changed "$f"; then side=--ours; else side=--theirs; fi
    if ! git checkout -q "$side" -- "$f" 2>/dev/null; then
      # طرفِ خواسته‌شده نسخه‌ای ندارد (حذف/تغییر) → طرف دیگر، وگرنه حذف
      if [ "$side" = --ours ]; then side=--theirs; else side=--ours; fi
      git checkout -q "$side" -- "$f" 2>/dev/null || git rm -q --cached -- "$f" 2>/dev/null || true
    fi
    git add -- "$f" 2>/dev/null || true
    echo "publish: جامانده حل شد ($side): $f"
  done
}

_strip_markers() {
  # مارکر تعارض هرگز منتشر نمی‌شود (یک بار index.json با مارکر رفت و
  # یادگیری ساعت‌ها خاموش ماند). فایلِ مارکردار: مالِ ما اگر ما نوشتیم.
  local f
  git grep -lE "^(<<<<<<< |=======$|>>>>>>> )" -- "${PATHS[@]}" 2>/dev/null | while IFS= read -r f; do
    if _in_changed "$f"; then git checkout -q --ours -- "$f" 2>/dev/null || true
    else git checkout -q --theirs -- "$f" 2>/dev/null || true; fi
    git add -- "$f" 2>/dev/null || true
    echo "publish: مارکر تعارض پاک شد: $f"
  done
}

for attempt in $(seq 1 "$ATTEMPTS"); do
  if git push -q "$REMOTE" "HEAD:$BRANCH" 2>/dev/null; then
    echo "publish: منتشر شد (تلاش $attempt)"
    exit 0
  fi
  git fetch -q "$REMOTE" "$BRANCH" || { sleep $((attempt * 4 + RANDOM % 7)); continue; }
  if ! git merge -q --no-edit --allow-unrelated-histories "$REMOTE/$BRANCH" 2>/dev/null; then
    _settle_untouched
    if [ -f "$RESOLVER" ]; then
      python3 "$RESOLVER" || true
    fi
    _settle_leftovers
    _strip_markers
    if git -c core.quotepath=false diff --name-only --diff-filter=U | grep -q .; then
      echo "publish: تعارضِ حل‌نشده ماند — merge لغو شد"; git merge --abort 2>/dev/null || true
      sleep $((attempt * 4 + RANDOM % 7)); continue
    fi
    git commit -q --no-edit 2>/dev/null || git commit -q -m "ادغام $REMOTE/$BRANCH" 2>/dev/null || true
  fi
  if git grep -qE "^(<<<<<<< |>>>>>>> )" -- "${PATHS[@]}" 2>/dev/null; then
    _strip_markers
    git commit -q -m "پاک‌سازی مارکر تعارض" 2>/dev/null || true
  fi
  sleep $((attempt * 4 + RANDOM % 7))
done
echo "publish: بعد از $ATTEMPTS تلاش منتشر نشد"
exit 1
