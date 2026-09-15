#!/usr/bin/env python3
"""تزریق مأموریت وفق‌پذیری + درخواست داده (قانون ۱۹) به همهٔ ایجنت‌ها و متخصصین — idempotent.

الگوی inject_bucket_rule.py: همان چند خط داخل خودِ فایل، با نشانگر.
مقصدها: .claude/agents/*.md (۳۶ ایجنت) و .claude/skills/liam-e*/SKILL.md
(۲۷ متخصص). کلیدِ درخواست داده = Exx برای انجین‌ها، نام فایل برای
ایجنت‌های عملیاتی — همان کلید سطل.

    python3 scripts/inject_adaptive_mandate.py          # اعمال
    python3 scripts/inject_adaptive_mandate.py --check  # فقط بگو کدام‌ها ندارند
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENTS = ROOT / ".claude" / "agents"
SKILLS = ROOT / ".claude" / "skills"
MARK = "<!-- adaptive-mandate -->"

BLOCK = """{mark}
## مأموریت وفق‌پذیری و درخواست داده (قانون ۱۹ — دستور حمید ۱۴ سپتامبر)

ثابت نمان: هر بازبینی با سه جمله شروع می‌شود — رژیم بازار از دور قبل چه
فرقی کرد؟ کدام فرضیه‌ام به‌روز می‌شود؟ کدام داده را کم دارم؟ همراه با پول
و بی‌تعصب: `signals/market-stance.json` و دامیننس‌ها را پیش از حکم بخوان؛
نزولی = شورت‌گرا، صعودی = لانگ‌گرا، باطل‌کننده را همان‌جا بنویس. زنجیرهٔ
استدلال صریح: شواهد → تفسیر → حکم → باطل‌کننده؛ نمی‌دانی، حدس نزن.
آزادی فقط در پیپر (experiments + CI)؛ هیچ دروازه‌ای در تولید بی CI بالای
صفر و تأیید حمید عوض نمی‌شود (قانون ۰۳/۱۲)؛ خبر و رویداد دیدگاه‌اند نه
دروازه (قانون ۱۵). **داده را خودت نرو بیاور — سفارش بده:** نیاز تازه را با
`python3 -m hamid.data_requests --add {key} <kline|feed|state> k=v …` ثبت
کن؛ هر ۵ دقیقه جمع می‌شود و با `python3 -m hamid.data_requests --for {key}`
می‌خوانی. خروجی هر بازبینی = بستهٔ شواهد (قانون ۱۲) + یک خط «چه یاد
گرفتم / چه داده‌ای سفارش دادم». متن کامل: docs/AGENT-ADAPTIVE-MANDATE-FA.md
"""


def key_for(path: Path) -> str:
    m = re.match(r"e(\d\d)-", path.name)
    if m:
        return f"E{m.group(1)}"
    m = re.match(r"liam-e(\d\d)-", path.parent.name)
    if m:
        return f"E{m.group(1)}"
    return path.stem


def targets():
    return sorted(AGENTS.glob("*.md")) + sorted(SKILLS.glob("liam-e*/SKILL.md"))


def apply(check_only=False):
    missing, done = [], []
    for p in targets():
        txt = p.read_text(encoding="utf-8")
        if MARK in txt:
            continue
        missing.append(str(p.relative_to(ROOT)))
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
        print(f"بی‌مأموریت: {len(missing)}" + (" — " + ", ".join(missing) if missing else ""))
        sys.exit(1 if missing else 0)
    print(f"تزریق شد: {len(done)} · از قبل داشتند: {len(targets()) - len(done)}")
