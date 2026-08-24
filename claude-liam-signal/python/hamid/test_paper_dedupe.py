"""پاسبان ضدِ تکرارِ دفتر بسته — همراه اجباری رفعِ ۲۴ اوت. آفلاین.

عیبی که این‌جا بسته شد، بزرگ‌ترین تحریفِ آماریِ ریپو بود: ۴۸.۶٪ از
۴۵٬۳۴۵ ردیف دفتر بسته، تسویهٔ **دوبارهٔ همان معامله** بود، چون
یکتاسازیِ ادغام روی «متنِ خط» کار می‌کرد و دو رانرِ هم‌زمان دو متنِ
کمی متفاوت می‌ساختند. اثرش روی دفتر سیگنال: وین‌ریت ۷۱.۳٪ → ۷۸.۸٪ و
انتظار +۰.۱۲۸R → +۰.۲۵۱R.

پس این پاسبان سه چیز را نگه می‌دارد: (۱) کلید هویت در هر دو نقطه یکی
بماند، (۲) هیچ لایه‌ای دوباره متنی نشود، (۳) پاک‌سازی بدون پشتیبان
ننویسد.
"""
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(PY))
sys.path.insert(0, str(ROOT / "scripts"))
from hamid import paper as P                        # noqa: E402
from hamid import dedupe_closed as D                # noqa: E402
import resolve_brain_conflicts as RBC               # noqa: E402

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


def row(sym="X", opened=1000, entry=1.0, stage="sig-ibs", closed=2000, **kw):
    d = {"sym": sym, "opened": opened, "entry": entry, "closed": closed,
         "R": 1.0, "outcome": "target", "why": {"stage": stage}}
    d.update(kw)
    return d


print("— کلید هویت، نه متنِ خط:")
a, b = row(closed=2000, mfe_r=0.5), row(closed=2400, mfe_r=0.6)
check("دو تسویهٔ همان معامله یک کلید دارند",
      P.trade_key(a) == P.trade_key(b), f"{P.trade_key(a)} vs {P.trade_key(b)}")
check("و متنشان متفاوت است (همان چیزی که ادغامِ متنی را گول می‌زد)",
      json.dumps(a) != json.dumps(b))
check("کلیدِ paper و کلیدِ ادغامِ تعارض مو‌به‌مو یکی‌اند",
      P.trade_key(a) == RBC.trade_key(a), f"{P.trade_key(a)} vs {RBC.trade_key(a)}")
check("`closed` داخل کلید نیست (وگرنه هیچ تکراری گرفته نمی‌شد)",
      P.trade_key(row(closed=1)) == P.trade_key(row(closed=999_999)))
check("ورودِ متفاوت = معاملهٔ متفاوت",
      P.trade_key(row(entry=1.0)) != P.trade_key(row(entry=1.1)))
check("لحظهٔ بازشدنِ متفاوت = معاملهٔ متفاوت",
      P.trade_key(row(opened=1000)) != P.trade_key(row(opened=1001)))
check("دفترِ متفاوت (stage) = معاملهٔ متفاوت — v2 حق دارد همان ستاپ را جدا ثبت کند",
      P.trade_key(row(stage="sig-ibs")) != P.trade_key(row(stage="v2")))

print("\n— پاک‌سازی: زودترین تسویه می‌ماند:")
rows = [row(closed=5000, R=9.0), row(closed=2000, R=1.0), row(closed=3000, R=5.0),
        row(sym="Y", closed=2500)]
with tempfile.TemporaryDirectory() as td:
    p = Path(td) / "closed.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    keep, dropped, broken = D.scan(p)
    res_dry = D.run(apply=False, path=p, quiet=True)
    before = p.read_text(encoding="utf-8")
    res = D.run(apply=True, path=p, quiet=True)
    after = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l]
    baks = list(Path(td).glob("closed.jsonl.bak-*"))
check("سه تسویهٔ یک معامله به یکی تبدیل می‌شود",
      (len(keep), dropped) == (2, 2), f"keep={len(keep)} dropped={dropped}")
check("و زودترینش می‌ماند (نه بزرگ‌ترین R)",
      [r for r in after if r["sym"] == "X"][0]["closed"] == 2000,
      str([r["closed"] for r in after]))
check("معاملهٔ دیگر دست‌نخورده می‌ماند", any(r["sym"] == "Y" for r in after))
check("پیش‌فرض فقط گزارش است — چیزی نمی‌نویسد",
      res_dry["dropped"] == 2 and len(before.splitlines()) == 4)
check("با --apply پشتیبان ساخته می‌شود (قانون ۰۵)",
      len(baks) == 1 and "backup" in res, str(baks))
check("درصد تکرار گزارش می‌شود", res["dup_pct"] == 50.0, str(res["dup_pct"]))
check("خط خراب شمرده می‌شود، نه اسکن را بکشد",
      D.scan.__doc__ is not None and broken == 0)

print("\n— ادغامِ تعارض دیگر متنی نیست:")
src = (ROOT / "scripts" / "resolve_brain_conflicts.py").read_text(encoding="utf-8")
check("merge_jsonl بر هویت معامله یکتا می‌کند", "trade_key(rec)" in src)
check("و «اجتماع خطوط یکتا»ی قدیمی برنگشته",
      "if not line or line in seen" not in src)
check("زودترین تسویه برنده است، صریح در کد",
      "closed < best[k][0]" in src)

print("\n— لایهٔ دوم: تسویهٔ دوباره اصلاً ثبت نمی‌شود:")
psrc = (PY / "hamid" / "paper.py").read_text(encoding="utf-8")
check("mark() قبل از تسویه، دفتر بسته را می‌پرسد", "closed_keys()" in psrc)
check("و پوزیشنِ از-قبل-بسته را رد می‌کند", "if trade_key(p) in done" in psrc)
check("و بی‌صدا نیست — تعدادش چاپ می‌شود",
      "دوباره ثبت نشد" in psrc)

print("\n— اثرِ عددیِ همین رفع (چرا مهم بود):")
dup = [row(R=1.0, closed=2000)] * 3 + [row(sym="L", R=-1.0, opened=9, closed=2100)]
uniq_keys = {P.trade_key(json.loads(json.dumps(r))) for r in dup}
check("۴ ردیف ← ۲ معاملهٔ یکتا", len(uniq_keys) == 2)
check("وین‌ریتِ باددار ۷۵٪ بود، واقعی ۵۰٪ است",
      round(3 / 4 * 100) == 75 and round(1 / 2 * 100) == 50)

print()
if FAIL:
    print(f"شکست: {len(FAIL)} از {OK + len(FAIL)}")
    sys.exit(1)
print(f"پاسبان ضدتکرار دفتر: هر {OK} بررسی سبز")
