#!/usr/bin/env python3
"""تزریق قانون ۱۷ (سطلِ من) به همهٔ ایجنت‌های `.claude/agents/` — idempotent.

قاعده‌ای که فقط در سند باشد، ایجنت هنگام استدلال نمی‌بیندش (درس ۲۳
اوت: «منابع اعلامی به ایجنت‌ها تزریق نشده بود»). پس همان چند خط داخل
خودِ فایلِ هر ایجنت می‌نشیند، با یک نشانگر تا دوباره‌کاری نشود.

    python3 scripts/inject_bucket_rule.py          # اعمال
    python3 scripts/inject_bucket_rule.py --check  # فقط بگو کدام‌ها ندارند
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENTS = ROOT / ".claude" / "agents"
MARK = "<!-- bucket-rule -->"

BLOCK = """{mark}
## سطلِ من (قانون ۱۷ — اول بخوان، بعد فکر کن)

قبل از هر تحلیل: `python3 -m hamid.dispatch --bucket {key}` (یا
`signals/buckets.json`). فایلِ خام را **فقط** از `read_next` باز کن؛ اگر
خالی بود یعنی از دورِ قبل چیزی عوض نشده — هیچ فایلی باز نکن و چیزی را
دوباره نفهم. آیتم‌های `viewpoint` (خبر/تقویم/جمعیت/ترند/آنلاک) دیدگاه‌اند
نه دروازه (قانون ۱۵). ریزنینگ فقط روی `changed`.
"""


def key_for(path: Path) -> str:
    m = re.match(r"e(\d\d)-", path.name)
    return f"E{m.group(1)}" if m else path.stem


def apply(check_only=False):
    missing, done = [], []
    for p in sorted(AGENTS.glob("*.md")):
        txt = p.read_text(encoding="utf-8")
        if MARK in txt:
            continue
        missing.append(p.name)
        if check_only:
            continue
        block = BLOCK.format(mark=MARK, key=key_for(p))
        p.write_text(txt.rstrip("\n") + "\n\n" + block, encoding="utf-8")
        done.append(p.name)
    return missing, done


if __name__ == "__main__":
    chk = "--check" in sys.argv
    missing, done = apply(check_only=chk)
    if chk:
        print(f"بی‌سطل: {len(missing)}" + (" — " + ", ".join(missing) if missing else ""))
        sys.exit(1 if missing else 0)
    print(f"تزریق شد: {len(done)} · از قبل داشتند: {len(list(AGENTS.glob('*.md'))) - len(done)}")
