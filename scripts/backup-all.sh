#!/usr/bin/env bash
# بک‌آپ کلی — «یک بک‌آپ کلی از کلود می‌خوام که داشته باشمش» (دستور حمید، ۱۸ سپتامبر).
#
# چه چیزی داخلش است: کل درختِ کاری (کد، قوانین، ایجنت‌ها، مهارت‌ها، پیکربندی،
# حافظه و دفترهای brain/، signals/، اسناد و نسخهٔ انتقال) + مانیفستِ sha256 +
# بستهٔ git از کامیت‌های در دسترس. بیرون می‌ماند: .git، کش کندل، و گزارش‌های
# بک‌تستِ قدیمی (فقط ۳ تای آخر می‌ماند؛ بقیه در تاریخچهٔ گیت‌هاب هستند).
#
#   scripts/backup-all.sh [پوشهٔ مقصد]     # پیش‌فرض: backups/ (gitignore)
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"; cd "$ROOT"
DEST="${1:-$ROOT/backups}"; mkdir -p "$DEST"
STAMP="$(date -u +%Y%m%d-%H%M)"; SHA="$(git rev-parse --short=12 HEAD)"
NAME="liam9-backup-$STAMP-$SHA"
# فقط سه گزارش بک‌تست آخر
KEEP="$(ls -1 claude-liam-signal/backtests/ | grep -E '^backtest-.*\.json(\.gz)?$' | sort | tail -3 | sed 's#^#claude-liam-signal/backtests/#')"
EXCL="$(ls -1 claude-liam-signal/backtests/ | grep -E '^backtest-.*\.json(\.gz)?$' | sort | head -n -3 | sed 's#^#--exclude=claude-liam-signal/backtests/#' | tr '\n' ' ')"
# مانیفست پیش از فشرده‌سازی: هر فایل با sha256، تا صحتِ بازگردانی قابل‌بررسی باشد
git ls-files -z | xargs -0 sha256sum > "$DEST/$NAME.manifest.sha256" 2>/dev/null || true
{
  echo "liam-trader-9 full backup"; echo "utc: $(date -u '+%Y-%m-%d %H:%M')"; echo "head: $(git rev-parse HEAD)"
  echo "branch: $(git rev-parse --abbrev-ref HEAD)"; echo "commits_in_bundle: $(git rev-list --count HEAD)"
  echo "kept_backtests:"; echo "$KEEP" | sed 's/^/  /'
  echo "restore: tar -xzf $NAME.tar.gz && git clone $NAME.git.bundle  (تاریخچهٔ کامل: GitHub tag backup/full-$STAMP)"
} > "$DEST/$NAME.README.txt"
# shellcheck disable=SC2086
tar -czf "$DEST/$NAME.tar.gz" --exclude=.git --exclude='claude-liam-signal/python/.klines-cache' --exclude='backups' --exclude='node_modules' $EXCL .
git bundle create "$DEST/$NAME.git.bundle" --all 2>/dev/null || git bundle create "$DEST/$NAME.git.bundle" HEAD
( cd "$DEST" && sha256sum "$NAME.tar.gz" "$NAME.git.bundle" > "$NAME.sha256" )
ls -la "$DEST" | grep "$NAME" | awk '{print $5, $9}'
echo "✓ $DEST/$NAME.tar.gz"
