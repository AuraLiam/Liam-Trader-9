#!/usr/bin/env python3
"""پاسبان بودجهٔ پیام و دروازهٔ کادنس (۷ سپتامبر) — آفلاین، بدون شبکه.

قفل می‌کند: حافظهٔ سه‌منبعی (هر منبع به‌تنهایی باید ببندد) · بیشینه
برنده است · سیگنال از دروازهٔ کادنس رد نمی‌شود · شمارش از دفترِ محصول با
یکتاسازی · پنجره و تعداد فایلِ روزانه هم‌قد باشند · EFFECTIVE_FROM ·
و **ratchetِ فرستندهٔ بی‌دفتر**: هیچ ماژول تازه‌ای حق ندارد به تلگرام
بفرستد و ردی روی دفتر نگذارد.
"""
import json
import re
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
sys.path.insert(0, str(PY))

from hamid import cadence_gate as CG                 # noqa: E402
from hamid import msg_budget as MB                   # noqa: E402

OK = 0
FAIL = []


def check(name, cond, extra=""):
    global OK
    if cond:
        OK += 1
        print(f"  ✓ {name}")
    else:
        FAIL.append(name)
        print(f"  ✗ {name}")
        if extra:
            print(f"      ↳ {extra}")


NOW = 1788800000000
HOUR = 3600_000


def _tmp():
    return Path(tempfile.mkdtemp(prefix="liam9-mb-"))


def _feed(d, rows, now=NOW):
    """آرشیوِ روزانه می‌سازد، با همان نام‌گذاری واقعی."""
    d.mkdir(parents=True, exist_ok=True)
    by = {}
    for r in rows:
        day = time.strftime("%Y%m%d", time.gmtime(r["at"] / 1000))
        by.setdefault(day, []).append(r)
    for day, rs in by.items():
        (d / f"telegram-feed-{day}.jsonl").write_text(
            "\n".join(json.dumps({"n": i + 1, **r}, ensure_ascii=False)
                      for i, r in enumerate(rs)) + "\n", encoding="utf-8")
    return d


# ── ۱. دروازهٔ کادنس: هر منبع به‌تنهایی باید ببندد ──────────────────────
#
# این هستهٔ رفع است. عیبِ ۷ سپتامبر این بود که فقط **یک** منبع خوانده
# می‌شد و آن یکی با هر چک‌اوتِ تازه و هر push ناموفق برمی‌گشت عقب.
CG.SIDECAR = _tmp() / "side.json"
CG.ARCHIVE = _tmp()
CG.FEED = CG.ARCHIVE / "nope.json"

mk = _tmp() / "marker.json"
mk.write_text(json.dumps({"last_sent": NOW - 10 * 60000}))
ok, why, age = CG.allow("dom_report", 55, marker_path=mk, now_ms=NOW)
check("منبع ۱ (نشانگر) به‌تنهایی می‌بندد", not ok and why == "too-soon",
      f"{ok}/{why}")

CG.mark("dom_report", now_ms=NOW - 10 * 60000)
ok, why, _ = CG.allow("dom_report", 55, marker_path=None, now_ms=NOW)
check("منبع ۲ (کنارگذاشتهٔ /tmp) به‌تنهایی می‌بندد",
      not ok and why == "too-soon", f"{ok}/{why}")
CG.SIDECAR = _tmp() / "empty.json"

CG.ARCHIVE = _feed(_tmp(), [{"at": NOW - 10 * 60000, "kind": "dom_report",
                             "title": "x"}])
ok, why, _ = CG.allow("dom_report", 55, marker_path=None, now_ms=NOW)
check("منبع ۳ (دفترِ append-only) به‌تنهایی می‌بندد",
      not ok and why == "too-soon", f"{ok}/{why}")

# بیشینه برنده است: نشانگرِ کهنه نباید دفترِ تازه را خنثی کند — همان
# سناریوی واقعی که reset نشانگر را عقب می‌برد.
old = _tmp() / "old.json"
old.write_text(json.dumps({"last_sent": NOW - 5 * HOUR}))
ok, why, _ = CG.allow("dom_report", 55, marker_path=old, now_ms=NOW)
check("نشانگرِ کهنه دفترِ تازه را خنثی نمی‌کند (بیشینه برنده)",
      not ok, f"{ok}/{why}")

CG.ARCHIVE = _feed(_tmp(), [{"at": NOW - 3 * HOUR, "kind": "dom_report",
                             "title": "x"}])
ok, why, age = CG.allow("dom_report", 55, marker_path=None, now_ms=NOW)
check("بعد از گذشتن کادنس، می‌رود", ok and why == "aged", f"{ok}/{why}")

CG.ARCHIVE = _tmp()
ok, why, age = CG.allow("dom_report", 55, marker_path=None, now_ms=NOW)
check("بی‌هیچ ردی، اولین بار می‌رود", ok and why == "never" and age is None)

# منبعِ خراب نباید دروازه را باز کند و نباید بترکاند
bad = _tmp() / "bad.json"
bad.write_text("}{ نه JSON")
ok, _, _ = CG.allow("dom_report", 55, marker_path=bad, now_ms=NOW)
check("نشانگرِ خراب فقط نادیده گرفته می‌شود، نه انفجار", ok is True)

# ── ۲. سیگنال هرگز از دروازهٔ کادنس رد نمی‌شود ─────────────────────────
#
# «هیچ تأخیری در ارسال سیگنال» — اگر کسی روزی `signal` را به جدول اضافه
# کند، محصول را کند کرده و باید همین‌جا بیفتد.
check("کادنسی برای «signal» تعریف نشده", "signal" not in CG.MIN_GAP_MIN)
try:
    CG.allow("signal", None, now_ms=NOW)
    _raised = False
except KeyError:
    _raised = True
check("و اگر کسی صدایش بزند، صریح خطا می‌دهد نه سکوت", _raised)
_tg = (PY / "telegram.py").read_text(encoding="utf-8")
check("مسیر ارسال سیگنال به cadence_gate وصل نیست",
      "cadence_gate" not in _tg)

# ── ۳. شمارش از دفترِ محصول، با یکتاسازی ───────────────────────────────
d = _tmp()
dup = {"at": NOW - HOUR, "kind": "dom_report", "title": "نظریه"}
_feed(d, [dup, dict(dup), {"at": NOW - 2 * HOUR, "kind": "signal",
                           "title": "BTC"}])
v = MB.judge(now_ms=NOW, archive=d, effective_from=0)
check("ردیف تکراری یک بار شمرده می‌شود",
      v["kinds"]["dom_report"]["n"] == 1, str(v["kinds"]["dom_report"]))

d2 = _tmp()
_feed(d2, [{"at": NOW - 30 * HOUR, "kind": "dom_report", "title": "کهنه"}])
v = MB.judge(now_ms=NOW, archive=d2, effective_from=0)
check("خارج از پنجرهٔ ۲۴ساعته شمرده نمی‌شود",
      v["kinds"]["dom_report"]["n"] == 0)

# تعداد فایلِ روزانه از پنجره مشتق شود، نه ثابتِ ۲ — وگرنه پنجرهٔ بلند
# بی‌صدا کم می‌شمارد و «سبزِ دروغ» می‌دهد.
d3 = _tmp()
_feed(d3, [{"at": NOW - i * 20 * HOUR, "kind": "dom_report",
            "title": f"r{i}"} for i in range(6)])
v = MB.judge(now_ms=NOW, window_h=120, archive=d3, effective_from=0)
check("پنجرهٔ ۱۲۰ساعته واقعاً ۱۲۰ ساعت را می‌شمارد",
      v["kinds"]["dom_report"]["n"] == 6, str(v["kinds"]["dom_report"]["n"]))

# ── ۴. حکم و EFFECTIVE_FROM ────────────────────────────────────────────
d4 = _tmp()
_feed(d4, [{"at": NOW - i * 900_000, "kind": "dom_report", "title": f"r{i}"}
           for i in range(40)])
v = MB.judge(now_ms=NOW, archive=d4, effective_from=NOW - 24 * HOUR)
check("بیش از بودجه = OVER", v["verdict"] == "OVER" and
      "dom_report" in v["over"], str(v["kinds"]["dom_report"]))
v = MB.judge(now_ms=NOW, archive=d4, effective_from=NOW - 60_000)
check("ردیف‌های پیش از لحظهٔ رفع شمرده نمی‌شوند",
      v["kinds"]["dom_report"]["n"] <= 1, str(v["kinds"]["dom_report"]["n"]))
check("و سهمِ سنجیده‌شدهٔ پنجره صریح گزارش می‌شود",
      v["covered_h"] < 0.1, str(v["covered_h"]))

# پنجرهٔ ناقص هرگز حکمِ سرخ نمی‌دهد — وگرنه یک لرزشِ زمان‌بند در ساعتِ
# اول، کلِ زنجیره را می‌خواباند (همان آلارمِ کاذبِ ۲۵ اوت، این‌بار از
# دستِ خودِ محافظ).
d5 = _tmp()
# تعداد عمداً از بودجه بیشتر است — وگرنه این بررسی چیزی را قفل نمی‌کند
# و با حذفِ warming هم سبز می‌ماند (اثبات منفی نمی‌دهد).
_feed(d5, [{"at": NOW - i * 30_000, "kind": "dom_report", "title": f"w{i}"}
           for i in range(1, 31)])
v = MB.judge(now_ms=NOW, archive=d5, effective_from=NOW - 30 * 60_000)
check("پنجرهٔ ناقص = WARMING، نه OVER",
      v["verdict"] == "WARMING" and not v["over"],
      f"{v['verdict']}/{v['over']}")
check("ولی نرخِ برآوردی گفته می‌شود، نه پنهان",
      v["kinds"]["dom_report"]["n"] == 30
      and v["kinds"]["dom_report"]["rate_per_day"] is None)
v = MB.judge(now_ms=NOW, archive=d5, effective_from=NOW - 24 * HOUR)
check("و با پنجرهٔ کامل، همان دفتر حکمِ OVER می‌گیرد",
      v["verdict"] == "OVER" and "dom_report" in v["over"], v["verdict"])
check("EFFECTIVE_FROM روی خودِ فایل عدد ثابت است",
      isinstance(MB.EFFECTIVE_FROM, int) and MB.EFFECTIVE_FROM > 1_700_000_000_000)

check("«نتیجه» بودجهٔ ساختگی نمی‌گیرد", "outcome" in MB.NO_BUDGET
      and "outcome" not in MB.BUDGET)
check("هر بودجه دلیلِ نوشته دارد",
      all(len(w) > 10 for _, w in MB.BUDGET.values()))
check("مرز صادقانه روی خروجی هست",
      "record_out" in v["boundary"] and "کفِ واقعیت" in v["boundary"])

# ── ۵. ratchet: فرستندهٔ بی‌دفتر بیشتر نمی‌شود ─────────────────────────
#
# ریشهٔ شکایت حمید این بود که آلارم‌ها **اصلاً** ردی نمی‌گذاشتند، پس
# نه پنل می‌دیدشان نه هیچ سنجه‌ای می‌شمردشان. `send_text` رفع شد؛ این
# ratchet مطمئن می‌شود فهرستِ بی‌دفتر فقط کوچک شود، هرگز بزرگ.
_SEND = re.compile(r'"(sendMessage|sendPhoto)"')
ledgerless = []
for p in sorted(PY.rglob("*.py")):
    if p.name.startswith("test_"):
        continue
    s = p.read_text(encoding="utf-8", errors="ignore")
    if _SEND.search(s) and "record_out" not in s:
        ledgerless.append(p.relative_to(PY).as_posix())
LEDGERLESS_MAX = 11        # اندازه‌گیری ۷ سپتامبر؛ فقط پایین می‌رود
check(f"فرستندهٔ بی‌دفتر ≤ {LEDGERLESS_MAX}",
      len(ledgerless) <= LEDGERLESS_MAX,
      f"{len(ledgerless)}: {ledgerless}")
check("send_text حالا ردِ دفتر می‌گذارد",
      'record_out("alert"' in _tg)
check("و ناکامیِ دفتر بی‌صدا رد نمی‌شود",
      "دفترِ آلارم نوشته نشد" in _tg)

# ── ۶. فقط خروجی خودش را می‌نویسد (قانون ۰۵) ───────────────────────────
_mb = (HERE / "msg_budget.py").read_text(encoding="utf-8")
check("بودجه‌سنج جز خروجی خودش چیزی نمی‌نویسد",
      _mb.count("write_text") == 1 and "OUT.write_text" in _mb)
_cg = (HERE / "cadence_gate.py").read_text(encoding="utf-8")
check("دروازهٔ کادنس فقط کنارگذاشتهٔ /tmp را می‌نویسد",
      _cg.count("write_text") == 1 and "SIDECAR.write_text" in _cg)

print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
sys.exit(1 if FAIL else 0)
