"""پاسبان بررسی‌کنندهٔ سازمان — آفلاین، روی مخزن‌های موقت + مخزن واقعی.

قفل می‌کند: DONEِ بی‌ماژول/بی‌محافظ/بی‌دروازه رد شود؛ PARTIAL و PLANNED
بدون note رد شوند؛ شناسهٔ تکراری گرفته شود؛ و خودِ سند واقعیِ مخزن سبز باشد.
"""
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from hamid import spec_check as SC                    # noqa: E402

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


TMP = Path(tempfile.mkdtemp(prefix="liam9-spec-"))
(TMP / "mod").mkdir()
(TMP / "g").mkdir()
(TMP / "wf").mkdir()
(TMP / "mod" / "a.py").write_text("x = 1\n")
(TMP / "g" / "test_a.py").write_text("x = 1\n")
(TMP / "wf" / "cycle.yml").write_text("      - run: python3 -m hamid.test_a\n")


def spec(*clauses):
    return {"clauses": list(clauses)}


def one(**kw):
    base = {"id": "X1", "room": "اتاق", "text": "متن", "status": "DONE",
            "module": "mod/a.py", "guard": "g/test_a.py"}
    base.update(kw)
    return base


def run(*clauses):
    return SC.check(spec(*clauses), root=TMP, wf_dir=TMP / "wf")

# ── ۱. DONEِ سالم ─────────────────────────────────────────────────────────
r = run(one())
check("بند کامل (ماژول + محافظ + دروازه) سبز است", r["verdict"] == "GREEN" and not r["faults"], str(r["faults"]))
check("شمارش وضعیت‌ها درست است", r["by_status"]["DONE"] == 1)

# ── ۲. سه راهِ دروغ‌گفتن، هر سه بسته ────────────────────────────────────
r = run(one(module="mod/ghost.py"))
check("DONE بدون ماژول = تخلف", r["verdict"] == "RED" and "ماژول نیست" in r["faults"][0])
r = run(one(guard="g/test_ghost.py"))
check("DONE بدون محافظ = تخلف", r["verdict"] == "RED" and "محافظ نیست" in r["faults"][0])
(TMP / "g" / "test_lonely.py").write_text("x = 1\n")
r = run(one(guard="g/test_lonely.py"))
check("محافظِ بیرون از دروازه = تخلف (نوشتنش کافی نیست، باید بدود)",
      r["verdict"] == "RED" and "دروازهٔ هیچ ورک‌فلویی" in r["faults"][0], str(r["faults"]))

# ── ۳. ناقص و در-برنامه باید دلیل بنویسند ──────────────────────────────
r = run(one(status="PARTIAL"))
check("PARTIAL بدون note = تخلف", r["verdict"] == "RED" and "بدون note" in r["faults"][0])
r = run(one(status="PARTIAL", note="فلان تکه هنوز اجرا نشده"))
check("PARTIAL با note و ماژول = سبز", r["verdict"] == "GREEN", str(r["faults"]))
r = run(one(status="PLANNED", module="mod/ghost.py", guard="g/test_ghost.py"))
check("PLANNED بدون note = تخلف", r["verdict"] == "RED")
r = run(one(status="PLANNED", module="mod/ghost.py", guard="g/test_ghost.py", note="منبع کلیددار ندارد"))
check("PLANNED با دلیل سبز است و ماژول نمی‌خواهد", r["verdict"] == "GREEN", str(r["faults"]))

# ── ۴. عیب‌های سند ────────────────────────────────────────────────────────
r = run(one(), one())
check("شناسهٔ تکراری گرفته می‌شود", any("تکراری" in f for f in r["faults"]))
r = run(one(status="MAYBE"))
check("وضعیت ناشناخته گرفته می‌شود", any("وضعیت ناشناخته" in f for f in r["faults"]))
r = run(one(text="   "))
check("بند بی‌متن گرفته می‌شود", any("متن بند خالی" in f for f in r["faults"]))

# ── ۵. سند واقعی مخزن ─────────────────────────────────────────────────────
real = SC.check()
check("سند واقعی سازمان سبز است", real["verdict"] == "GREEN",
      "\n".join(real["faults"][:12]))
check("سند دستور ۳ سپتامبر را کامل پوشش می‌دهد (≥ ۴۰ بند)", real["clauses"] >= 40, str(real["clauses"]))
rooms = {r["room"] for r in real["rows"]}
for must in ("اتاق توزیع اطلاعات (E27)", "اتاق ساختار", "بورد خبر", "دامیننس",
             "شورای ققنوس", "ریسک و ورود", "پیپر و حافظه", "حافظهٔ سازمانی",
             "انجین پامپ", "تحویل"):
    check(f"اتاق «{must}» در سند هست", any(must in r for r in rooms), str(sorted(rooms))[:200])
check("هیچ بندی بی‌محافظ ادعای DONE ندارد",
      all(r["guard_ok"] and r["gated"] for r in real["rows"] if r["status"] == "DONE"))

import shutil                                         # noqa: E402
shutil.rmtree(TMP, ignore_errors=True)
print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
sys.exit(1 if FAIL else 0)
