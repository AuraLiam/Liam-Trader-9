"""پاسبانِ پاسبان سیو سود — همراه اجباری trail_alert.py. آفلاین.

عیبی که این ابزار می‌بندد (TRUMP، ۲۴ اوت): پوزیشن واقعی در سود بود و
هیچ‌کس لحظهٔ پله را اعلام نکرد. پس بررسی‌های این‌جا روی سه چیزند:
پله‌ها دقیقاً قانون تریل باشند، هر پله فقط یک بار پیام شود، و فقط
سیگنالِ واقعاً ارسال‌شده پیام بسازد — نه دفترهای داخلی.
"""
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
sys.path.insert(0, str(PY))
from hamid import trail_alert as TA                  # noqa: E402

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


print("— پله‌ها همان قانون تریل‌اند:")
r = TA.rungs(100.0, 106.0, "LONG")                   # TP1 در +۶٪
check("سه پله ساخته می‌شود", len(r) == 3)
check("پلهٔ ۱ = ⅓ مسیر (۱۰۲)", abs(r[0][0] - 102.0) < 1e-9, str(r[0]))
check("و استاپش سودِ کارمزددار است (ورود+۰.۱۵٪)",
      abs(r[0][1] - 100.15) < 1e-9, str(r[0][1]))
check("پلهٔ ۲ = ⅔ مسیر و استاپ به سطحِ ⅓",
      abs(r[1][0] - 104.0) < 1e-9 and abs(r[1][1] - 102.0) < 1e-9)
check("پلهٔ ۳ = خودِ TP1 و دستور ⅓ بستن دارد",
      abs(r[2][0] - 106.0) < 1e-9 and "⅓ حجم" in r[2][2])
s = TA.rungs(100.0, 94.0, "SHORT")
check("شورت قرینهٔ کامل است (پلهٔ ۱ = ۹۸، استاپ ۹۹.۸۵)",
      abs(s[0][0] - 98.0) < 1e-9 and abs(s[0][1] - 99.85) < 1e-9, str(s[0]))
check("هندسهٔ خراب (TP1 سمت اشتباه) پله نمی‌سازد",
      TA.rungs(100.0, 95.0, "LONG") == [])
check("عبور جهت‌دار است: لانگ بالا، شورت پایین",
      TA.crossed(103, 102, "LONG") and not TA.crossed(101, 102, "LONG")
      and TA.crossed(97, 98, "SHORT") and not TA.crossed(99, 98, "SHORT"))

print("\n— فقط سیگنالِ ارسالی، پرشده، یکتا:")


def pos(stage="sig-ibs", filled=1000, sym="TRUMPUSDT", entry=2.0, tp1=2.12,
        d="LONG", opened=500):
    return {"sym": sym, "dir": d, "entry": entry, "sl": entry * 0.97,
            "tp1": tp1, "opened": opened, "filled": filled,
            "why": {"stage": stage}}


def write_open(td, rows):
    p = Path(td) / "open.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n",
                 encoding="utf-8")
    return p


with tempfile.TemporaryDirectory() as td:
    p = write_open(td, [pos(), pos(stage="practice"), pos(stage="scalp"),
                        pos(filled=None), pos()])
    got = TA.open_signal_positions(p)
check("تمرین/اسکلپ/پرنشده/تکراری هیچ‌کدام نمی‌آیند — فقط ۱ سیگنال",
      len(got) == 1 and got[0]["why"]["stage"] == "sig-ibs", str(len(got)))
check("دفتر ناموجود = خالی، نه خطا",
      TA.open_signal_positions("/nonexistent/x.jsonl") == [])

print("\n— هر پله فقط یک بار (قفل state):")
with tempfile.TemporaryDirectory() as td:
    op = write_open(td, [pos()])
    st = Path(td) / "state.json"
    _out = TA.OUT
    TA.OUT = Path(td) / "out.json"
    try:
        r1 = TA.run(quiet=True, open_path=op, state_path=st,
                    price_fn=lambda s: 2.05)         # بالای پلهٔ ۱ (۲.۰۴)
        r2 = TA.run(quiet=True, open_path=op, state_path=st,
                    price_fn=lambda s: 2.05)
        r3 = TA.run(quiet=True, open_path=op, state_path=st,
                    price_fn=lambda s: 2.13)         # بالای TP1 → پلهٔ ۲و۳
        r4 = TA.run(quiet=True, open_path=op, state_path=st,
                    price_fn=lambda s: 1.99)         # برگشت — پلهٔ خورده نمی‌پرد
        rn = TA.run(quiet=True, open_path=op, state_path=st,
                    price_fn=lambda s: None)         # بی‌قیمت
        empty = TA.run(quiet=True, open_path=write_open(td, []),
                       state_path=st, price_fn=lambda s: 9)
        disk = json.loads(TA.OUT.read_text(encoding="utf-8"))
        final_state = json.loads(st.read_text(encoding="utf-8"))
    finally:
        TA.OUT = _out
check("عبور از پلهٔ ۱ → یک اعلام", len(r1["alerts"]) == 1
      and r1["alerts"][0]["rung"] == 1, str(r1["alerts"]))
check("و استاپِ اعلامی همان سودِ کارمزددار است",
      abs(r1["alerts"][0]["new_sl"] - 2.003) < 1e-9, str(r1["alerts"]))
check("نوبت بعد با همان قیمت → هیچ اعلامِ تکراری", r2["alerts"] == [])
check("جهش تا TP1 → پله‌های ۲ و ۳ با هم، هر کدام یک بار",
      [a["rung"] for a in r3["alerts"]] == [2, 3], str(r3["alerts"]))
check("برگشتِ قیمت پله‌های خورده را دوباره نمی‌زند", r4["alerts"] == [])
check("قیمتِ گیرنیامده = رد و شمارش، نه حدس",
      rn["alerts"] == [] and rn["price_unavailable"] == 1)
check("بسته‌شدن پوزیشن، قفلش را از state پاک می‌کند", final_state == {})
check("خروجی روی دیسک با یادداشتِ مرز نوشته می‌شود",
      "قانون ۰۵" in disk["note"] and empty["open_signal_positions"] == 0)

print("\n— مرزها روی کد:")
src = (PY / "hamid" / "trail_alert.py").read_text(encoding="utf-8")
check("اعلام از دروازهٔ آلارم رد می‌شود (قفل دوم)",
      "alert_gate.send" in src)
check("پیام صریح می‌گوید اجرا با داشبورد/حمید است",
      "این فقط " in src and "اعلامِ لحظه" in src)
check("هیچ سفارشی نمی‌فرستد (فقط متن)",
      "urlopen" not in src and "requests" not in src)
check("کندلِ بسته ملاک قیمت است، نه باز", "کندلِ بسته" in src)
check("سقف تعداد پوزیشن دارد (اسکن را کند نکند)",
      "MAX_PRICE_FETCH" in src)
check("بافر کارمزد همان ۰.۱۵٪ قانون تریل است", TA.FEE_BUF_PCT == 0.15)

print()
if FAIL:
    print(f"شکست: {len(FAIL)} از {OK + len(FAIL)}")
    sys.exit(1)
print(f"پاسبان سیو سود: هر {OK} بررسی سبز")
