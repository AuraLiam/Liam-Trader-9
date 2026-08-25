"""پاسبان ماشین آستانه — همراه اجباری escalation.py. آفلاین.

خطرهایی که می‌بندد: ارجاعِ الکی (حساسیت به نویز)، ارجاع‌ندادن سرِ حدِ
واقعی، و این‌که ماشین از «ارجاع» فراتر برود (تغییر پارامتر/تصمیم).
"""
import json
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from hamid import escalation as ES                   # noqa: E402

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


NOW = 1_787_700_000_000


def row(outcome, sym="AAAUSDT", d="LONG", ago_h=1.0, R=None, stage="sig-ibs"):
    if R is None:
        R = 1.5 if outcome == "target" else (-1.0 if outcome == "stop" else 0.1)
    return {"sym": sym, "dir": d, "outcome": outcome, "R": R,
            "closed": NOW - int(ago_h * 3600_000), "why": {"stage": stage}}


def w(rows):
    td = tempfile.mkdtemp()
    p = Path(td) / "closed.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n",
                 encoding="utf-8")
    return p


print("— E1: استاپ پیاپی —")
rows_ok = [row("target", ago_h=5), row("stop", ago_h=4), row("trail", ago_h=3),
           row("stop", ago_h=2), row("stop", ago_h=1)]
check("۲ استاپ آخر (زیر حد) = سکوت",
      ES.assess(ES._sig_rows(w(rows_ok), NOW)) == [])
rows_e1 = [row("target", ago_h=6), row("stop", sym="BUSDT", ago_h=3),
           row("stop", sym="CUSDT", ago_h=2), row("stop", sym="DUSDT", ago_h=1)]
esc = ES.assess(ES._sig_rows(w(rows_e1), NOW))
e1 = [e for e in esc if e["rule"] == "E1"]
check("۳ استاپ پیاپی = ارجاع E1", len(e1) == 1, str(esc))
check("اتاق‌های مسئول نام برده شده‌اند (علت‌یابی همگانی)",
      set(e1[0]["rooms"]) == {"post-trade-learning", "order-block",
                              "market-structure"})
check("معامله‌های شاهد روی خود ارجاع‌اند", len(e1[0]["evidence"]) == 3)

print("\n— E2: الگوی تکراری بین‌ارزی —")
e2 = [e for e in esc if e["rule"] == "E2" and "LONG" in e["title"]]
check("استاپ LONG در ۳ ارز = ارجاع E2 (مثال خود حمید: OB و ترندلاین)",
      len(e2) == 1 and set(e2[0]["rooms"]) == {"order-block",
                                               "market-structure"}, str(esc))
rows_2sym = [row("stop", sym="AUSDT", ago_h=3), row("stop", sym="AUSDT", ago_h=2),
             row("stop", sym="BUSDT", ago_h=1)]
check("۲ ارز (زیر حد) = بدون E2",
      not [e for e in ES.assess(ES._sig_rows(w(rows_2sym), NOW))
           if e["rule"] == "E2"])

print("\n— E3: کف نرخ برد —")
rows_e3 = ([row("stop", sym=f"S{i}USDT", ago_h=10 - i * 0.5, d="SHORT")
            for i in range(8)]
           + [row("target", sym="WUSDT", ago_h=1.2),
              row("target", sym="W2USDT", ago_h=1.1),
              row("trail", sym="W3USDT", ago_h=1.0, R=0.2)])
e3 = [e for e in ES.assess(ES._sig_rows(w(rows_e3), NOW))
      if e["rule"] == "E3"]
check("برد ۲۷٪ روی n=۱۱ = ارجاع E3", len(e3) == 1, str(e3))
rows_few = [row("stop", ago_h=i + 1) for i in range(2)] + [row("target", ago_h=4)]
check("نمونهٔ کم (n<۱۰) حکم نمی‌گیرد",
      not [e for e in ES.assess(ES._sig_rows(w(rows_few), NOW))
           if e["rule"] == "E3"])

print("\n— مرزها —")
old = [row("stop", ago_h=30), row("stop", ago_h=29), row("stop", ago_h=28)]
check("بیرون پنجرهٔ ۲۴س شمرده نمی‌شود",
      ES.assess(ES._sig_rows(w(old), NOW)) == [])
prac = [row("stop", ago_h=3, stage="practice"),
        row("stop", ago_h=2, stage="scalp"),
        row("stop", ago_h=1, stage="practice")]
check("فقط دفتر سیگنال — تمرین/اسکلپ ارجاع نمی‌سازد",
      ES.assess(ES._sig_rows(w(prac), NOW)) == [])
with tempfile.TemporaryDirectory() as td:
    out = Path(td) / "esc.json"
    rep = ES.run(closed_path=w(rows_e1), out_path=out, now_ms=NOW, quiet=True)
    disk = json.loads(out.read_text(encoding="utf-8"))
check("خروجی همیشه نوشته می‌شود و مرز رویش است",
      disk["escalations"] and "قانون ۰۳" in disk["note"])
check("دفتر ناموجود = گزارش خالی، نه خطا",
      ES.run(closed_path="/nonexistent/x.jsonl",
             out_path=Path(tempfile.mkdtemp()) / "o.json",
             now_ms=NOW, quiet=True)["escalations"] == [])
src = (HERE / "escalation.py").read_text(encoding="utf-8")
check("ماشین فقط ارجاع می‌دهد — هیچ set_param/تغییر پارامتری ندارد",
      "set_param" not in src and "apply" not in src.replace("reapply", ""))
check("پیامش از دروازهٔ آلارم رد می‌شود (ضدتکرار ۶ساعته)",
      "alert_gate.send" in src)

print()
if FAIL:
    print(f"شکست: {len(FAIL)} از {OK + len(FAIL)}")
    sys.exit(1)
print(f"پاسبان ماشین آستانه: هر {OK} بررسی سبز")
