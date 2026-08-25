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
    # درس ۱۸ اوت: پیش‌بینی باز نباید با هر نوبت تازه شود وگرنه هرگز به
    # سررسید نمی‌رسد و کارنامه ابدی خالی می‌ماند — due باید ثابت بماند
    dues1 = sorted(f["due"] for f in json.loads(df.LEDGER.read_text())["open"])
    df.update(pts, struct, now + 120000)
    dues2 = sorted(f["due"] for f in json.loads(df.LEDGER.read_text())["open"])
    check("سررسید پیش‌بینی باز با نوبت‌های بعدی عوض نمی‌شود", dues1 == dues2,
          f"{dues1[:2]} vs {dues2[:2]}")
    # و بعد از عبور از سررسید، واقعاً نمره می‌خورد و جای خالی دوباره پر می‌شود
    later = now + 35 * 60000
    pts2 = pts + [{"t": later, "u": pts[-1]["u"], "b": pts[-1]["b"]}]
    out3 = df.update(pts2, struct, later)
    check("سررسیدها در چرخهٔ واقعی نمره خوردند", out3["graded_now"] >= 2,
          str(out3))
    check("کارنامه دیگر خالی نیست", out3["scoreboard"], str(out3["scoreboard"]))

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

    # ── حلقهٔ تجربه (سؤال حمید ۲۵ اوت: «مگر حافظه ندارد؟») ────────────────
    # سناریوی واقعی: BTC.D|120m با ~۱۸٪ اصابت. دفتر جعلی با همان کارنامه
    # می‌سازیم و می‌بینیم ادعای UP دیگر کورکورانه تکرار نمی‌شود.
    def _graded(path, result, n):
        return [{"metric": "BTC.D", "horizon_min": 120, "path": path,
                 "result": result} for _ in range(n)]

    bad_st = {"open": [], "graded": _graded("UP", "MISS", 25)
              + _graded("UP", "HIT", 5), "score": {}, "probe": {}}
    hs = df.bucket_stats(bad_st, "BTC.D", 120, "UP")
    check("کارنامهٔ سطل شمرده می‌شود، نه حدس", hs["n"] == 30
          and abs(hs["hit_pct"] - 16.7) < 0.1, str(hs))

    # شواهدی که UP قوی می‌سازند (دلتای مثبت ۱س و ۴س برای BTC.D)
    up_pts = [{"t": now - m * 60000, "u": 5.0, "b": 60.0 - 0.002 * m}
              for m in range(300, -1, -3)]
    fs_nofb = df.make_forecast(up_pts, {}, now)
    b120 = [f for f in fs_nofb if f["metric"] == "BTC.D"
            and f["horizon_min"] == 120]
    check("بدون دفتر، ادعای UP صادر می‌شود (رفتار قدیم)",
          b120 and b120[0]["path"] == "UP", str(b120))
    fs_fb = df.make_forecast(up_pts, {}, now, st=bad_st)
    d120 = [f for f in fs_fb if f["metric"] == "BTC.D"
            and f["horizon_min"] == 120][0]
    check("با کارنامهٔ بدِ نمونه‌دار، همان ادعا پس گرفته می‌شود (FLAT)",
          d120["path"] == "FLAT" and d120.get("demoted_from") == "UP",
          str(d120))
    check("و دلیلِ پس‌گرفتن، خودِ عدد کارنامه است",
          any("16.7" in r for r in d120["reasons"]), str(d120["reasons"]))
    check("کارنامهٔ سطل روی خود پیش‌بینی ثبت می‌شود", d120.get("hist") == hs)

    # بازآزمایی: سرکوب ابدی نیست — پنجمین بار ادعا عمداً صادر می‌شود
    bad_st["probe"] = {}                  # شمارنده از صفر برای همین سنجش
    paths = []
    for _ in range(df.REPROBE_EVERY):
        f = [x for x in df.make_forecast(up_pts, {}, now, st=bad_st)
             if x["metric"] == "BTC.D" and x["horizon_min"] == 120][0]
        paths.append(f["path"])
    check(f"هر {df.REPROBE_EVERY} سرکوب یک بازآزمایی دارد (نمونه‌گیری نمی‌میرد)",
          paths.count("UP") == 1 and paths[-1] == "UP", str(paths))

    # نمونهٔ کم حکم نمی‌گیرد — ۱۰ ردیف زیر BAD_N است
    small_st = {"open": [], "graded": _graded("UP", "MISS", 10),
                "score": {}, "probe": {}}
    f_small = [x for x in df.make_forecast(up_pts, {}, now, st=small_st)
               if x["metric"] == "BTC.D" and x["horizon_min"] == 120][0]
    check("زیر حداقل نمونه، ادعا سرکوب نمی‌شود (نمونهٔ کم دروغ می‌گوید)",
          f_small["path"] == "UP" and "demoted_from" not in f_small)

    # سطل خوب دست نمی‌خورد
    good_st = {"open": [], "graded": _graded("UP", "HIT", 20)
               + _graded("UP", "MISS", 5), "score": {}, "probe": {}}
    f_good = [x for x in df.make_forecast(up_pts, {}, now, st=good_st)
              if x["metric"] == "BTC.D" and x["horizon_min"] == 120][0]
    check("کارنامهٔ خوب = ادعا سر جایش (سرکوب فقط برای خطای سیستماتیک)",
          f_good["path"] == "UP" and f_good.get("hist", {}).get("n") == 25)

    print(f"\n✓ همهٔ {OK} آزمون ناظر پیش‌بینی دامیننس گذشت")


if __name__ == "__main__":
    run()
