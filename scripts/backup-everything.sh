#!/usr/bin/env bash
# بک‌آپ کاملِ همه‌چیزِ این یوزر — «هم کل اطلاعات Home و هم کل کد» (دستور حمید، ۱۸ سپتامبر).
#
# سه بستهٔ جدا (ضد-merge: هرکدام سرِ جای خودش، با شمارهٔ خودش):
#   A) tree   — کلِ درختِ کاری مخزن: هر ۱۶٬۳۵۱ فایل ردیابی‌شده + هر فایل
#               ردیابی‌نشده. هیچ حذفی جز .git، backups/ و __pycache__.
#   B) home   — دادهٔ خودِ کلود و پیکربندی‌های خانه: ~/.claude (مهارت‌ها،
#               ایجنت‌ها، هوک‌ها، تنظیمات، رونوشت گفتگوها)، ~/.claude.json،
#               ~/.gitconfig، ~/.config، ~/.ccr، ~/.aws، ~/.boto، ~/.profile،
#               ~/.bashrc، ~/.zshrc، و /home/claude/.claude.
#   C) git    — بستهٔ کاملِ تاریخچهٔ در دسترس (کلونِ کم‌عمق = ۵۰ کامیت).
#
# آنچه عمداً بیرون است و **چرا**:
#   · کش‌های زنجیرهٔ ابزار (~/.rustup ۵۹۹M، ~/.cache ۲۲۹M، ~/.npm ۱۲۷M،
#     ~/.bun ۹۵M، ~/.cargo، ~/.local، ~/.gradle) — بازدانلودشدنی، دادهٔ شما
#     نیستند. با `--with-caches` اضافه می‌شوند.
#   · ~/.ssh خالی است و کلیدی وجود ندارد؛ ~/.aws فقط config بدون کلید.
#     اگر روزی کلیدی اضافه شد، همین‌جا بازبینی لازم است (قانون ۰۵).
#
#   scripts/backup-everything.sh [پوشهٔ مقصد] [--with-caches] [--split]
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"; cd "$ROOT"
DEST=""; WITH_CACHES=0; SPLIT=0
for a in "$@"; do case "$a" in --with-caches) WITH_CACHES=1;; --split) SPLIT=1;; *) DEST="$a";; esac; done
DEST="${DEST:-$ROOT/backups}"; mkdir -p "$DEST"
STAMP="$(date -u +%Y%m%d-%H%M)"; SHA="$(git rev-parse --short=12 HEAD)"
BASE="liam9-full-$STAMP-$SHA"
HOME_DIR="${HOME:-/root}"

say() { printf '▸ %s\n' "$*"; }

say "A) درختِ کاری (همهٔ فایل‌ها، بی‌استثنا جز .git و backups)"
tar -czf "$DEST/$BASE.A-tree.tar.gz" \
  --exclude=.git --exclude=backups --exclude=node_modules --exclude=__pycache__ .

say "B) خانه و دادهٔ کلود"
HOME_ITEMS=()
for p in .claude .claude.json .gitconfig .config .ccr .aws .boto .profile .bashrc .zshrc .wget-hsts; do
  [ -e "$HOME_DIR/$p" ] && HOME_ITEMS+=("$p")
done
tar -czf "$DEST/$BASE.B-home.tar.gz" -C "$HOME_DIR" "${HOME_ITEMS[@]}" \
  $( [ -d /home/claude/.claude ] && echo "-C /home /home/claude/.claude" || true ) 2>/dev/null \
  || tar -czf "$DEST/$BASE.B-home.tar.gz" -C "$HOME_DIR" "${HOME_ITEMS[@]}"

say "C) بستهٔ git (تاریخچهٔ در دسترس)"
git bundle create "$DEST/$BASE.C-git.bundle" --all 2>/dev/null || git bundle create "$DEST/$BASE.C-git.bundle" HEAD

if [ "$WITH_CACHES" = 1 ]; then
  say "D) کش‌های زنجیرهٔ ابزار (اختیاری، بازدانلودشدنی)"
  tar -czf "$DEST/$BASE.D-caches.tar.gz" -C "$HOME_DIR" \
    $(for p in .rustup .cargo .npm .bun .local .cache .gradle; do [ -e "$HOME_DIR/$p" ] && echo "$p"; done)
fi

say "مانیفست و امضاها"
{ git ls-files -z | xargs -0 sha256sum; } > "$DEST/$BASE.manifest-repo.sha256" 2>/dev/null || true
find "$HOME_DIR/.claude" -type f -print0 2>/dev/null | xargs -0 sha256sum > "$DEST/$BASE.manifest-home.sha256" 2>/dev/null || true
( cd "$DEST" && sha256sum "$BASE".*.tar.gz "$BASE".*.bundle > "$BASE.sha256" )

{
  echo "liam-trader-9 — بک‌آپ کاملِ یوزر"
  echo "utc: $(date -u '+%Y-%m-%d %H:%M')"
  echo "head: $(git rev-parse HEAD)  ·  کامیت‌های بسته: $(git rev-list --count HEAD)"
  echo "فایل‌های ردیابی‌شدهٔ مخزن: $(git ls-files | wc -l)"
  echo
  echo "بسته‌ها:"
  ( cd "$DEST" && ls -la "$BASE".* | awk '{printf "  %10d  %s\n", $5, $9}' )
  echo
  echo "بازگردانی:"
  echo "  sha256sum -c $BASE.sha256"
  echo "  mkdir liam9 && tar -xzf $BASE.A-tree.tar.gz -C liam9        # درخت کاری"
  echo "  tar -xzf $BASE.B-home.tar.gz -C \$HOME                       # ~/.claude و پیکربندی‌ها"
  echo "  git clone $BASE.C-git.bundle liam9-git                      # تاریخچه"
  echo
  echo "بیرون مانده (عمدی): کش‌های ابزار (~1.1G، بازدانلودشدنی) مگر با --with-caches."
  echo "سکرت: هیچ کلید/توکنی در این بسته‌ها نیست (~/.ssh خالی، ~/.aws بی‌کلید)."
} > "$DEST/$BASE.README.txt"

if [ "$SPLIT" = 1 ]; then
  say "تکه‌کردن به ۲۸ مگابایت برای ارسال"
  ( cd "$DEST" && for f in "$BASE".*.tar.gz "$BASE".*.bundle; do
      [ "$(stat -c%s "$f")" -gt 29360128 ] && split -b 28m -d "$f" "$f.part" && rm -f "$f"
    done; true )
fi

cat "$DEST/$BASE.README.txt"
