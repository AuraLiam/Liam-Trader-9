"""آزمون ناظر پیش‌بینی دامیننس — پیش‌بینی مستدل، نمره‌دهی صادقانه."""
import json
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from hamid import dom_forecast as df                          # noqa: E402

OK = 0


def check(name, cond, extra=""):
    global OK
    if not cond:
        print(f"  ✗ {name} {extra}")
        raise SystemExit(1)
    OK += 1
    print(f"  ✓ {name}")


def series(n, step_u=0.01, step_b=0.0, gap_min=5, end=None):
    end = end or int(time.time() * 1000)
    return [{"t": end - (n - 1 - i) * gap_min * 60000,
             "u": round(8.0 + i * step_u, 3),
             "b": round(56.0 + i * step_b, 3)} for i in range(n)]


def run():
    df.LEDGER = Path(tempfile.mkdtemp()) / "ledger.json"
    now = int(time.time() * 1000)

    # ۱) سری صعودی قوی → پیش‌بینی UP با دلایل نوشته‌شده
    pts = series(80, step_u=0.02)
    struct = {"usdt": {"trend_1h": "up", "trend_4h": "up"},
              "btc_d": {"trend_1h": "range"}}
    fs = df.make_forecast(pts, struct, now)
    u30 = [f for f in fs if f["metric"] == "USDT.D" and f["horizon_min"] == 30]
    check("پیش‌بینی USDT.D صادر شد و UP است", u30 and u30[0]["path"] == "UP")
    check("دلایل اجباری نوشته شده‌اند (≥۲ شاهد)", len(u30[0]["reasons"]) >= 2,
          str(u30))
    b30 = [f for f in fs if f["metric"] == "BTC.D" and f["horizon_min"] == 30]
    check("BTC.D بدون شواهد هم‌جهت → FLAT (نه حدس جهت‌دار)",
          b30 and b30[0]["path"] == "FLAT")

    # ۲) دادهٔ کهنه → هیچ پیش‌بینی (قانون ۱)
    old = series(80, step_u=0.02, end=now - 30 * 60000)
    check("دادهٔ کهنه = NO_FORECAST", df.make_forecast(old, struct, now) == [])

    # ۳) نمره‌دهی: پیش‌بینی UP که واقعاً بالا رفت = HIT؛ خلافش = MISS
    st = {"open": [
        {"made": now - 40 * 60000, "due": now - 10 * 60000, "metric": "USDT.D",
         "key": "u", "horizon_min": 30, "path": "UP",
         "base": pts[-8]["u"], "reasons": ["تست"]},
        {"made": now - 40 * 60000, "due": now - 10 * 60000, "metric": "BTC.D",
         "key": "b", "horizon_min": 30, "path": "UP",
         "base": 56.0, "reasons": ["تست"]}], "graded": [], "score": {}}
    g = df.grade_due(st, pts, now)
    check("دو پیش‌بینی سررسید نمره گرفتند", g == 2)
    res = {f["metric"]: f["result"] for f in st["graded"]}
    check("USDT.D صعودی = HIT", res["USDT.D"] == "HIT", str(res))
    check("BTC.D ثابت ولی پیش‌بینی UP = MISS", res["BTC.D"] == "MISS", str(res))
    sb = df.scoreboard(st)
    check("کارنامه درصد درست می‌دهد", sb["USDT.D|30m"]["hit_pct"] == 100.0
          and sb["BTC.D|30m"]["hit_pct"] == 0.0, str(sb))

    # ۴) چرخهٔ کامل update: ضدتکرار (یک پیش‌بینی باز به ازای متریک/افق) و ذخیره
    out1 = df.update(pts, struct, now)
    out2 = df.update(pts, struct, now + 60000)
    check("ضدتکرار: تعداد بازها ثابت می‌ماند", out1["open"] == out2["open"],
          f"{out1['open']} vs {out2['open']}")
    check("دفتر روی دیسک نوشته شد", df.LEDGER.exists()
          and json.loads(df.LEDGER.read_text())["open"])

    # ۵) مولتی‌تایم دامیننس واقعاً اجرا می‌شود (۱۷ اوت: AttributeError روی
    # Trendline در تولید — تست باید کل مسیر ۴س/۱س را طی کند، نه فقط پیش‌بینی)
    from hamid import dominance as dm
    long_pts = [{"t": now - (3000 - i) * 5 * 60000,
                 "u": round(8.0 + (i % 60) * 0.003, 3),
                 "b": round(56.0 - (i % 40) * 0.004, 3)} for i in range(3000)]
    m = dm.multi_tf(long_pts)
    check("مولتی‌تایم بدون خطا و با ساختار ۴س/۱س",
          "note" not in m and "4h" in m["usdt"] and "1h" in m["btc_d"], str(m)[:120])
    u1 = m["usdt"]["1h"]
    check("۱س USDT: روند و سطح دارد (یا INSUFFICIENT صادق)",
          ("trend" in u1 and "px" in u1) or "note" in u1, str(u1)[:120])

    print(f"\n✓ همهٔ {OK} آزمون ناظر پیش‌بینی دامیننس گذشت")


if __name__ == "__main__":
    run()
