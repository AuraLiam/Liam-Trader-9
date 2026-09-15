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


print("— پله‌ها همان قانون تریل نسخهٔ سه‌اند (نه نردبان ⅓/⅔ بازنشسته):")
r = TA.rungs(100.0, 106.0, "LONG")                   # TP1 در +۶٪
check("دو پله ساخته می‌شود", len(r) == 2, str(len(r)))
check("پلهٔ ۱ = گذشتن از کارمزد (۱۰۰.۱۵)", abs(r[0][0] - 100.15) < 1e-9, str(r[0]))
check("و استاپش ۸۰٪ همان سود است (ورود+۰.۱۲)", abs(r[0][1] - 100.12) < 1e-9, str(r[0][1]))
check("پلهٔ ۲ = خودِ TP1 و استاپ روی ۸۰٪ مسیر (۱۰۴.۸)",
      abs(r[1][0] - 106.0) < 1e-9 and abs(r[1][1] - 104.8) < 1e-9, str(r[1]))
check("متن‌ها با دفتر پیپر هم‌قراردادند: «۸۰٪» هست، «⅓ حجم» نیست",
      all("80" in x[2] for x in r) and not any("⅓" in x[2] or "⅔" in x[2] for x in r), str([x[2] for x in r]))
from hamid import paper as _paper
check("درصد قفل از خودِ paper خوانده می‌شود (یک منبع)", abs(r[1][1] - (100 + _paper.PROD_TRAIL_FRAC * 6)) < 1e-9)
s = TA.rungs(100.0, 94.0, "SHORT")
check("شورت قرینهٔ کامل است (پلهٔ ۱ = ۹۹.۸۵، استاپ ۹۹.۸۸)",
      abs(s[0][0] - 99.85) < 1e-9 and abs(s[0][1] - 99.88) < 1e-9, str(s[0]))
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
                    price_fn=lambda s: 2.05)         # بالای پلهٔ ۱ (۲.۰۰۳)
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
check("و استاپِ اعلامی ۸۰٪ سودِ کارمزددار است (۲.۰۰۲۴)",
      abs(r1["alerts"][0]["new_sl"] - 2.0024) < 1e-9, str(r1["alerts"]))
check("نوبت بعد با همان قیمت → هیچ اعلامِ تکراری", r2["alerts"] == [])
check("جهش تا TP1 → پلهٔ ۲، یک بار",
      [a["rung"] for a in r3["alerts"]] == [2], str(r3["alerts"]))
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


# ── ۱۵ سپتامبر: تریل با نوعِ خودش ثبت می‌شود، نه زیر بودجهٔ ۱۲تاییِ پاسبان‌ها
from pathlib import Path as _P2
_src_ta = (_P2(__file__).resolve().parent / "trail_alert.py").read_text(encoding="utf-8")
check("پلهٔ تریل با kind=trade_mgmt فرستاده می‌شود", 'kind="trade_mgmt"' in _src_ta)

print()
if FAIL:
    print(f"شکست: {len(FAIL)} از {OK + len(FAIL)}")
    sys.exit(1)
print(f"پاسبان سیو سود: هر {OK} بررسی سبز")
