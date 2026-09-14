"""محافظ وتوی قانونِ تأییدشدهٔ منفی (ممیزی تلگرام ۱۴ سپتامبر).

خاصیت‌ها: فقط SIGNAL، فقط جمعِ ≤ آستانهٔ ثبت‌شده، تنزل به ARMED با دلیلِ
نام‌بردار، ردیفِ ضدواقع با stage_tag=rule-vetoed، ضدتکرار روی دفتر باز،
سقفِ هر اجرا، قیف رد پا دارد، داور دروازه جمعیت سوم را جدا می‌سنجد.
"""
import os
import sys
from pathlib import Path

os.environ["LIAM9_SANDBOX"] = "1"
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import scan as S                                        # noqa: E402
from hamid import gate_verdict as GV, paper as P       # noqa: E402

OK, FAIL = 0, []


def check(name, cond, extra=""):
    global OK
    if cond:
        OK += 1
        print(f"  ✓ {name}")
    else:
        FAIL.append(name)
        print(f"  ✗ {name}" + (f"\n      ↳ {extra}" if extra else ""))


def setup(sym, stage="SIGNAL", boost=None, rules=None, d="SHORT"):
    s = {"sym": sym, "dir": d, "tf": "5m", "stage": stage, "strategy": "ibs",
         "entry": 1.0, "sl": 1.01, "tp1": 0.98, "quality": 70}
    if boost is not None:
        s["learned"] = {"boost": boost, "rules": rules or [{"rule": "شورت خلاف بیت‌کوین", "delta": boost}]}
    return s


check("آستانه از پیش ثبت‌شده و کوچک‌تر از کوچک‌ترین قانونِ منفیِ تأییدشده (−۰.۱۶۷)", S.RULE_VETO_R == -0.15)
opened = []
_orig = P.open_from
P.open_from = lambda rows, why: (opened.append((rows, why)) or 1)
try:
    ss = [setup("A", boost=-0.584, rules=[{"rule": "شورت خلاف بیت‌کوین", "delta": -0.396}, {"rule": "CHOCH دارد", "delta": -0.188}]),
          setup("B", boost=-0.10),
          setup("C", boost=+0.446, d="LONG"),
          setup("D"),
          setup("E", stage="ARMED", boost=-0.5),
          setup("F", boost=-0.15)]
    n = S.rule_veto(ss, ledger=True, open_keys=set())
    by = {s["sym"]: s for s in ss}
    check("جمعِ −۰.۵۸ → وتو: ARMED با دلیلِ نام‌بردار", n == 2 and by["A"]["stage"] == "ARMED" and "CHOCH" in by["A"]["skip"] and "شورت خلاف" in by["A"]["skip"], str(by["A"].get("skip")))
    check("دقیقاً روی آستانه (−۰.۱۵) هم وتو می‌شود", by["F"]["stage"] == "ARMED")
    check("جمعِ −۰.۱۰ (بالای آستانه) دست‌نخورده", by["B"]["stage"] == "SIGNAL")
    check("قانونِ مثبت و ستاپِ بی‌قانون دست‌نخورده", by["C"]["stage"] == "SIGNAL" and by["D"]["stage"] == "SIGNAL")
    check("فقط SIGNAL؛ ARMEDِ منفی تغییر نمی‌کند و ردیف نمی‌سازد", by["E"]["stage"] == "ARMED" and not any(r[0][0]["symbol"] == "E" for r in opened))
    check("ردیف ضدواقع با stage_tag=rule-vetoed و علتِ قانون", len(opened) == 2 and all(r[0][0]["stage_tag"] == "rule-vetoed" for r in opened)
          and opened[0][1]["veto_why"] == "confirmed_rule" and "شورت خلاف بیت‌کوین" in opened[0][1]["rules"], str(opened[:1]))
    opened.clear()
    ss2 = [setup("A", boost=-0.5)]
    S.rule_veto(ss2, ledger=True, open_keys={("A", "SHORT")})
    check("ضدتکرار: ستاپی که ردیفِ باز دارد دوباره ردیف نمی‌سازد (ولی وتو می‌شود)", not opened and ss2[0]["stage"] == "ARMED")
    opened.clear()
    many = [setup(f"S{i}", boost=-0.5) for i in range(S.RULE_VETO_CAP + 5)]
    S.rule_veto(many, ledger=True, open_keys=set())
    check(f"سقف {S.RULE_VETO_CAP} ردیف در هر اجرا (مهار سیل)", len(opened) == S.RULE_VETO_CAP and all(s["stage"] == "ARMED" for s in many), str(len(opened)))
    ss3 = [setup("Z", boost=-0.5)]
    check("ledger=False هیچ ردیفی نمی‌سازد ولی وتو می‌کند", S.rule_veto(ss3, ledger=False) == 1 and ss3[0]["stage"] == "ARMED")
finally:
    P.open_from = _orig

src = (HERE.parent / "scan.py").read_text(encoding="utf-8")
check("وتو بعد از اتاق یادگیری و پیش از دروازهٔ روند در main صدا زده می‌شود",
      src.index("rule_vetoed = rule_veto(setups)") > src.index("learning room consulted") and
      src.index("rule_vetoed = rule_veto(setups)") < src.index("= gate_stages(setups)"))
check("قیف سلامت ردپای rule_vetoed دارد", '"rule_vetoed": rule_vetoed' in src and "rule_vetoed=rule_vetoed" in src)
check("داور دروازه جمعیت سوم را جدا می‌سنجد (ضد-merge)", GV.STAGES.get("rule") == "rule-vetoed" and "rule" in GV.LABELS)
check("ردیف rule-vetoed هرگز سیگنالِ ارسالی شمرده نمی‌شود", "rule-vetoed" in P._NOT_SIGNAL)
check("کلیدهای باز از دفتر با برچسب خواسته‌شده خوانده می‌شوند", S._stage_veto_open_keys.__defaults__ == ("stage-vetoed",))

print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
sys.exit(1 if FAIL else 0)
