"""پاسبان گشت صرافی‌ها + نقشهٔ پایه — آفلاین، بدون شبکه.

خطرها: عدد تک‌منبعی در واچ‌لیست، میانگین رتبهٔ غلط، سطحِ کم‌برخورد
که «معتبر» جا زده شود، کانالی که قیمت بیرونش بیفتد، و OBای که با
تعریف حمید (بدنه > شدوها، سبز بالای قیمت/قرمز زیر قیمت) نخواند.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from hamid import base_map as BM                      # noqa: E402
from hamid import scout as SC                         # noqa: E402

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


# ── گشت: ادغام چندمنبعی ─────────────────────────────────────────────
def rows(src_spec):
    return [{"sym": s, "chg": c, "vol": v} for s, c, v in src_spec]


per = {
    "ex1": rows([("AAAUSDT", 12.0, 9e6), ("BBBUSDT", -8.0, 5e6),
                 ("CCCUSDT", 1.0, 1e6), ("USDCUSDT", 0.0, 9e9)]),
    "ex2": rows([("AAAUSDT", 10.0, 8e6), ("BBBUSDT", -9.0, 6e6),
                 ("DDDUSDT", 2.0, 2e6)]),
}
# USDCUSDT در _row فیلتر می‌شود نه build — این‌جا دستی حذفش می‌کنیم
check("نرمال‌سازی: استیبل/غیر USDT حذف می‌شود",
      SC._row("USDCUSDT", 0.0, 1e9) is None
      and SC._row("AAABTC", 1.0, 1e9) is None
      and SC._row("aaausdt", 1.0, 1e9)["sym"] == "AAAUSDT")
per["ex1"] = [r for r in per["ex1"] if r["sym"] != "USDCUSDT"]
wl = SC.build(per)
syms = [r["sym"] for r in wl]
check("گشت: فقط ردیف‌های ≥۲ منبع", set(syms) == {"AAAUSDT", "BBBUSDT"},
      str(syms))
aaa = next(r for r in wl if r["sym"] == "AAAUSDT")
check("گشت: میانگین رتبهٔ حجم درست (۱ و ۱ → ۱.۰)",
      aaa["avg_vol_rank"] == 1.0, str(aaa))
check("گشت: میانهٔ تغییر ۲۴س", aaa["chg24_med"] in (10.0, 12.0))
check("گشت: برچسب گینر از هر دو منبع",
      sum(1 for t in aaa["tags"] if t.startswith("گینر")) == 2,
      str(aaa["tags"]))
bbb = next(r for r in wl if r["sym"] == "BBBUSDT")
check("گشت: لوزر هم برچسب دارد ولی امتیازش از گینر کمتر",
      any(t.startswith("لوزر") for t in bbb["tags"])
      and aaa["score"] > bbb["score"])
check("گشت: مرتب‌سازی پایدار بر امتیاز", wl[0]["sym"] == "AAAUSDT")

# ── نقشهٔ پایه: سطح‌ها ──────────────────────────────────────────────
def kc(o, h, l, c):
    return {"o": o, "h": h, "l": l, "c": c}


flat = [kc(100, 100.4, 99.6, 100)] * 80
# سه برخورد واقعی به سقف ۱۰۲ با پیوت اکید
for i in (10, 30, 50):
    flat[i] = kc(100, 102.0, 99.6, 100.5)
lv = BM.sr_levels(flat)
check("سطح: مقاومت ۱۰۲ با ≥۳ برخورد پیدا شد",
      any(abs(x["level"] - 102) < 0.6 and x["touches_wick"] >= 3
          and x["role"] == "resistance" for x in lv),
      str(lv[:2]))
two = [kc(100, 100.4, 99.6, 100)] * 80
for i in (10, 30):
    two[i] = kc(100, 102.0, 99.6, 100.5)
check("سطح: دو برخورد کافی نیست (قانون ≥۳)",
      not any(abs(x["level"] - 102) < 0.6 for x in BM.sr_levels(two)))

# ── کانال ───────────────────────────────────────────────────────────
up = [kc(100 + i * 0.5, 100.9 + i * 0.5, 99.4 + i * 0.5, 100.4 + i * 0.5)
      for i in range(80)]
ch = BM.channel(up)
check("کانال: روند صعودی تشخیص داده شد", ch and ch["dir"] == "up", str(ch))
check("کانال: قیمت داخل کانال است (۰..۱۰۰)",
      ch and 0.0 <= ch["pos_pct"] <= 100.0, str(ch and ch["pos_pct"]))
check("کانال: لبه‌ها بیرون از آخرین قیمت‌اند",
      ch and ch["bottom"] <= up[-1]["c"] <= ch["top"])
check("کانال: سری کوتاه → None (بی‌ادعا)", BM.channel(up[:20]) is None)

# ── اردر بلاک به تعریف حمید ─────────────────────────────────────────
seq = [kc(100, 100.3, 99.7, 100)] * 30
seq[10] = kc(103.0, 103.4, 102.8, 104.6)     # سبز قوی (بدنه ۱.۶ > شدو ۰.۶)
for i in range(11, 30):                      # ریزش بعدش
    seq[i] = kc(102 - (i - 11) * 0.3, 102.2 - (i - 11) * 0.3,
                101.5 - (i - 11) * 0.3, 101.7 - (i - 11) * 0.3)
ob = BM.order_block_hamid(seq, "above")
check("OB بالا: کندل سبزِ قوی بالای قیمت پیدا شد",
      ob and abs(ob["lo"] - 103.0) < 1e-9 and abs(ob["hi"] - 104.6) < 1e-9,
      str(ob))
weak = [dict(k) for k in seq]
weak[10] = kc(103.0, 104.8, 102.0, 103.5)    # بدنه ۰.۵ < شدوها ۲.۳
check("OB: کندل پرشدو (بدنه < شدوها) قبول نمی‌شود — تعریف حمید",
      BM.order_block_hamid(weak, "above") is None)
seq_dn = [kc(100, 100.3, 99.7, 100)] * 30
seq_dn[10] = kc(96.8, 97.0, 96.2, 95.4)      # قرمز قوی زیر قیمت
ob2 = BM.order_block_hamid(seq_dn, "below")
check("OB پایین: کندل قرمزِ قوی زیر قیمت",
      ob2 and abs(ob2["hi"] - 96.8) < 1e-9, str(ob2))

# ── نقشهٔ چندتایمی و هم‌رسی ─────────────────────────────────────────
m = BM.base_map({"4h": up, "1h": up, "15m": up[:20]})
check("نقشه: هر تایم بسته‌اش را دارد",
      "channel" in m["4h"] and m["15m"].get("error") == "سری کوتاه")
check("نقشه: هم‌رسی خطوط دو تایم (سری یکسان → هم‌رسی حتمی)",
      len(m["confluence"]) > 0, str(m["confluence"][:2]))

print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
sys.exit(1 if FAIL else 0)
