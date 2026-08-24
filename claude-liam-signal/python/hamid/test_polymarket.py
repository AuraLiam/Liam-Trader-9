"""پاسبان پالی‌مارکت — همراه اجباری polymarket.py. آفلاین.

سه خطری که این منبع می‌تواند بیاورد و این‌جا بسته می‌شوند:
۱. **دروازه‌شدن**: خروجی‌اش نباید بتواند امتیازی را بالا ببرد — شاهد است.
۲. **عدد ساختگی**: کجِ نهنگی با نمونهٔ کم، یا احتمالِ بازارِ نامفهوم.
۳. **ادعای بی‌اثبات**: هر اجرا باید ردِ بازدید با retrieved_at بگذارد.
"""
import json
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
sys.path.insert(0, str(PY))
from hamid import polymarket as PM                   # noqa: E402

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


print("— شناخت بازار کریپتو و جهتش:")
a, d = PM.crypto_direction("Will Bitcoin reach $150,000 by December 31?")
check("بازار BTC صعودی شناخته می‌شود", (a, d) == ("BTC", "up"), f"{a},{d}")
a, d = PM.crypto_direction("Will Ethereum dip below $3,000 in September?")
check("بازار ETH نزولی شناخته می‌شود", (a, d) == ("ETH", "down"), f"{a},{d}")
a, d = PM.crypto_direction("Will the Fed cut rates in September?")
check("بازار غیرکریپتو رد می‌شود", a is None)
a, d = PM.crypto_direction("Bitcoin above $100k or below $90k first?")
check("سؤالِ دوجهته جهت نمی‌گیرد — حدس ممنوع", a == "BTC" and d is None)

print("\n— پارس بازار Gamma:")
m = PM.parse_market({"question": "Will Bitcoin reach $150,000?",
                     "outcomePrices": '["0.65", "0.35"]',
                     "volume24hr": "125000.7", "liquidity": 40000,
                     "conditionId": "0xabc", "endDate": "2026-12-31"})
check("outcomePrices رشته‌ای پارس می‌شود و YES=۰.۶۵", m["implied_yes"] == 0.65)
check("حجم و نقدینگی عددی می‌شوند", m["volume24h"] == 125001.0)
check("قیمتِ بیرون از [۰,۱] رد می‌شود",
      PM.parse_market({"question": "Bitcoin above $1?",
                       "outcomePrices": '["1.65"]'}) is None)
check("بازار غیرکریپتو در پارس هم رد می‌شود",
      PM.parse_market({"question": "Election winner?",
                       "outcomePrices": '["0.5"]'}) is None)

print("\n— ردِ پول بزرگ (هستهٔ دستور حمید):")


def tr(usd, p_yes, side="BUY", outcome="yes"):
    return {"size": usd / p_yes if p_yes else 0, "price": p_yes,
            "side": side, "outcome": outcome}


# جمعیتِ خرد نصف روی وقوع، نصف علیه → سهم YES خرد = ۰.۵
small_mix = ([tr(50, 0.50) for _ in range(20)]
             + [tr(50, 0.50, outcome="no") for _ in range(20)])
big_opt = [tr(8000, 0.70) for _ in range(6)]         # ۶ نهنگ، همه روی وقوع
w = PM.whale_split(big_opt + small_mix)
check("تفکیک بزرگ/خرد با آستانهٔ دلاری", (w["n_big"], w["n_small"]) == (6, 40))
check("کجِ نهنگی = سهم YESِ بزرگ‌ها منهای خردها (+۰.۵)",
      abs(w["skew"] - 0.50) < 1e-6, str(w["skew"]))
check("و به فارسی تفسیر می‌شود", "خوش‌بین‌تر" in w["note"])
w2 = PM.whale_split([tr(9000, 0.30, outcome="no")] * 6 + small_mix)
check("نهنگِ بدبین هم دیده می‌شود (کج منفی)", w2["skew"] < -0.1
      and "بدبین‌تر" in w2["note"])
few = PM.whale_split([tr(9000, 0.9)] * 3 + small_mix)
check("زیر ۵ معاملهٔ بزرگ → کج اعلام نمی‌شود، با دلیل",
      few["skew"] is None and "اعلام نمی‌شود" in few["note"])
check("فروشِ YES = علیه وقوع",
      PM.whale_split([tr(8000, 0.70, side="SELL")] * 6 + small_mix)["p_big"] == 0.0)
check("خریدِ NO = علیه وقوع",
      PM.whale_split([tr(8000, 0.30, outcome="no")] * 6 + small_mix)["p_big"] == 0.0)
check("فروشِ NO = روی وقوع (دو منفی، مثبت)",
      PM.whale_split([tr(8000, 0.3, side="SELL", outcome="no")] * 6
                     + small_mix)["p_big"] == 1.0)
check("معاملهٔ خراب (قیمت صفر/منفی) بی‌صدا رد می‌شود، نه crash",
      PM.whale_split([{"size": "x", "price": 0}, tr(60, 0.5)])["n_small"] == 1)
check("مجموع دلاری هر دو گروه گزارش می‌شود (شفافیت پول)",
      w["big_usd_total"] > 0 and w["small_usd_total"] > 0)

print("\n— مقایسه با تحلیل خودمان:")
mk = [{"asset": "BTC", "direction": "up", "implied_yes": 0.65,
       "question": "BTC to 150k?"},
      {"asset": "BTC", "direction": "down", "implied_yes": 0.70,
       "question": "BTC below 90k?"},
      {"asset": "ETH", "direction": "up", "implied_yes": 0.9, "question": "e"}]
c = PM.compare(mk, "BULLISH")
check("بازار up با YES=۰.۶۵ → دید BULLISH و توافق با رژیم ما",
      c[0]["polymarket_view"] == "BULLISH" and c[0]["verdict"] == "توافق")
check("بازار down با YES=۰.۷۰ → p_up=۰.۳ → BEARISH → تعارض",
      c[1]["polymarket_view"] == "BEARISH" and c[1]["verdict"] == "تعارض")
check("فعلاً فقط BTC مقایسه می‌شود (رژیم ما رژیم BTC/دامیننس است)",
      len(c) == 2)
check("رژیمِ نامعلومِ ما → «قابل‌مقایسه نیست»، نه توافقِ الکی",
      PM.compare(mk[:1], "UNKNOWN")[0]["verdict"] == "قابل‌مقایسه نیست")

print("\n— اثباتِ بازدید (قانون ۰۳):")
with tempfile.TemporaryDirectory() as td:
    _v = PM.VISITS
    PM.VISITS = Path(td) / "visits.jsonl"
    try:
        row = PM.prove_visit(["u1", "u2", "u3", "u4"], 5, 200, "خلاصه", [])
        PM.prove_visit(["u1"], 1, 10, "دومی", ["gamma: X"])
        lines = PM.VISITS.read_text(encoding="utf-8").strip().splitlines()
    finally:
        PM.VISITS = _v
check("هر اجرا یک ردیف اثبات می‌نویسد (append-only)", len(lines) == 2)
check("ردیف retrieved_at و منبع و شمارش دارد",
      row["retrieved_at"].endswith("UTC") and row["markets_read"] == 5
      and "polymarket.com" in row["source"])
check("وضعیت claim صریح UNVERIFIED است — نه دانشِ اثبات‌شده",
      row["validation_status"] == "UNVERIFIED")
check("خطاها هم در اثبات ثبت می‌شوند (بازدیدِ ناموفق پنهان نمی‌شود)",
      json.loads(lines[1])["errors"] == ["gamma: X"])

print("\n— شاهد است، نه دروازه:")
src = (PY / "hamid" / "polymarket.py").read_text(encoding="utf-8")
check("ماژول به هیچ موتور تصمیمی وصل نیست",
      "edge_boost" not in src and "scalp_decide" not in src
      and "confidence" not in src.lower())
check("مرز روی خروجی نوشته می‌شود", "شاهد " in src and "نه دروازه" in src)
check("ارتقا فقط از مسیر قانون ۰۳ اعلام شده", "قانون ۰۳" in src)
strat = (PY / "liam9_strategy.py").read_text(encoding="utf-8")
check("فایل داشبورد هیچ اتکایی به پالی‌مارکت ندارد (تا CI چیزی را تأیید نکرده)",
      "polymarket" not in strat.lower())
check("آستانهٔ پول بزرگ صریح و یک‌جا تعریف شده", PM.BIG_USD == 5000.0)

print()
if FAIL:
    print(f"شکست: {len(FAIL)} از {OK + len(FAIL)}")
    sys.exit(1)
print(f"پاسبان پالی‌مارکت: هر {OK} بررسی سبز")
