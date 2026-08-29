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
    # بازنگری ۲۹ اوت (بند ۱): تنزل به FLAT، تلهٔ خودتقویت‌شونده بود —
    # ادعا می‌ماند، وزنش کم می‌شود. اگر کسی تنزل را برگرداند، این می‌افتد.
    check("با کارنامهٔ بد، ادعا **نمی‌میرد** بلکه کم‌اعتماد می‌شود",
          d120["path"] == "UP" and d120.get("low_confidence") is True,
          str(d120))
    check("وزن اعتماد عددی و صریح است", d120.get("confidence") == 0.25,
          str(d120))
    check("هیچ ادعایی بی‌صدا به FLAT تبدیل نمی‌شود (تلهٔ مارپیچ بسته است)",
          "demoted_from" not in d120, str(d120))
    check("و دلیلِ کم‌اعتمادی، خودِ عدد کارنامه است",
          any("16.7" in r for r in d120["reasons"]), str(d120["reasons"]))
    check("کارنامهٔ سطل روی خود پیش‌بینی ثبت می‌شود", d120.get("hist") == hs)

    # بازآزمایی: کم‌اعتمادی ابدی نیست — پنجمین بار ادعا با اعتماد کامل می‌رود
    bad_st["probe"] = {}                  # شمارنده از صفر برای همین سنجش
    rows = []
    for _ in range(df.REPROBE_EVERY):
        f = [x for x in df.make_forecast(up_pts, {}, now, st=bad_st)
             if x["metric"] == "BTC.D" and x["horizon_min"] == 120][0]
        rows.append(f)
    check("همهٔ نوبت‌ها ادعای جهت‌دار می‌مانند (نمونه‌گیری زنده است)",
          all(r["path"] == "UP" for r in rows), str([r["path"] for r in rows]))
    check(f"هر {df.REPROBE_EVERY} نوبت یک بازآزمایی با اعتماد کامل دارد",
          sum(1 for r in rows if r.get("reprobe")) == 1
          and rows[-1].get("reprobe") is True
          and "low_confidence" not in rows[-1],
          str([bool(r.get("reprobe")) for r in rows]))

    # نمونهٔ کم حکم نمی‌گیرد — ۱۰ ردیف زیر BAD_N است
    small_st = {"open": [], "graded": _graded("UP", "MISS", 10),
                "score": {}, "probe": {}}
    f_small = [x for x in df.make_forecast(up_pts, {}, now, st=small_st)
               if x["metric"] == "BTC.D" and x["horizon_min"] == 120][0]
    check("زیر حداقل نمونه، اعتماد کم نمی‌شود (نمونهٔ کم دروغ می‌گوید)",
          f_small["path"] == "UP" and "low_confidence" not in f_small)

    # سطل خوب دست نمی‌خورد
    good_st = {"open": [], "graded": _graded("UP", "HIT", 20)
               + _graded("UP", "MISS", 5), "score": {}, "probe": {}}
    f_good = [x for x in df.make_forecast(up_pts, {}, now, st=good_st)
              if x["metric"] == "BTC.D" and x["horizon_min"] == 120][0]
    check("کارنامهٔ خوب = ادعا سر جایش (کم‌اعتمادی فقط برای خطای سیستماتیک)",
          f_good["path"] == "UP" and f_good.get("hist", {}).get("n") == 25
          and "low_confidence" not in f_good)

    # ── بند ۴ (۲۹ اوت): افق و آستانه ────────────────────────────────────────
    check("افق‌های بلند (۴س و ۲۴س) اضافه شده‌اند",
          240 in df.HORIZONS_MIN and 1440 in df.HORIZONS_MIN,
          str(df.HORIZONS_MIN))
    check("افق‌های کوتاه حذف نشدند (بنچمارک لازم است)",
          30 in df.HORIZONS_MIN and 120 in df.HORIZONS_MIN)
    fs_all = df.make_forecast(pts, struct, now)
    check("هر متریک برای همهٔ افق‌ها پیش‌بینی می‌گیرد",
          len(fs_all) == 2 * len(df.HORIZONS_MIN), str(len(fs_all)))

    # سری با نوسانِ شناخته‌شده: هر گام ۵ دقیقه‌ای دقیقاً ۰.۰۱ بالا می‌رود،
    # پس حرکتِ ۳۰دقیقه‌ای = ۰.۰۶ و ۱۲۰دقیقه‌ای = ۰.۲۴ — عددِ دستی، نه حدس.
    ramp = [{"t": now - (600 - i) * 5 * 60000, "u": round(8.0 + i * 0.01, 3),
             "b": 56.0} for i in range(600)]
    thr30, n30, med30 = df.horizon_noise(ramp, "u", 30)
    thr120, _, med120 = df.horizon_noise(ramp, "u", 120)
    check("نوسانِ افق از خودِ سری شمرده می‌شود، نه فرض",
          abs(med30 - 0.06) < 0.011 and abs(med120 - 0.24) < 0.011,
          f"med30={med30} med120={med120}")
    check("آستانه با افق بزرگ می‌شود (۰.۰۲ ثابت، دو معنی داشت)",
          thr120 > thr30 * 3, f"{thr30} vs {thr120}")
    check("کفِ مطلق حفظ می‌شود — لرزشِ ذره‌ای «حرکت» نمی‌شود",
          df.horizon_noise([{"t": now - i * 60000, "u": 8.0, "b": 56.0}
                            for i in range(400, 0, -1)], "u", 30)[0] == df.NOISE)
    check("نمونهٔ کم = کفِ مطلق، نه عددِ ساختگی (قانون ۱)",
          df.horizon_noise(ramp[:5], "u", 30) == (df.NOISE, 0, None))

    # اثرِ عملیاتی: حرکتی که با آستانهٔ ثابت «UP» بود، در افقِ بلند FLAT است
    st_thr = {"open": [
        {"made": now - 130 * 60000, "due": now - 60000, "metric": "USDT.D",
         "key": "u", "horizon_min": 120, "path": "UP",
         "base": round(ramp[-1]["u"] - 0.05, 3), "reasons": ["تست"]}],
        "graded": [], "score": {}}
    df.grade_due(st_thr, ramp, now)
    row = st_thr["graded"][0]
    check("حرکت ۰.۰۵ در افق ۱۲۰د با آستانهٔ نوسانی FLAT است (با ۰.۰۲ نبود)",
          row["real_path"] == "FLAT" and abs(row["actual_delta"]) > df.NOISE,
          str(row))
    check("آستانهٔ به‌کاررفته روی ردیف ثبت می‌شود (نمره قابل بازتولید است)",
          row.get("noise_used") == thr120 and row.get("noise_windows"),
          str(row))

    # ── بند ۵ (۲۹ اوت): احتمال کالیبره به‌جای برچسب + نمرهٔ برایر ──────────
    def _g(path, real, n, ev_n=3, metric="USDT.D", h=120):
        return [{"metric": metric, "horizon_min": h, "path": path,
                 "real_path": real, "ev_n": ev_n,
                 "result": "HIT" if real == path else "MISS"}
                for _ in range(n)]

    # سطلی با نتیجهٔ شمرده‌شده: از ۴۰ نوبتِ ادعای UP، ۱۰ تا واقعاً UP شد
    pst = {"open": [], "graded": _g("UP", "UP", 10) + _g("UP", "FLAT", 24)
           + _g("UP", "DOWN", 6), "score": {}, "probe": {}}
    pr = df.probabilities(pst, "USDT.D", 120, "UP", 3)
    check("احتمال از شمارشِ دفتر می‌آید، نه فرمول",
          pr["p"]["UP"] == 0.25 and pr["p"]["FLAT"] == 0.6
          and pr["p"]["DOWN"] == 0.15, str(pr))
    check("تعداد نمونه کنار احتمال گزارش می‌شود", pr["n"] == 40, str(pr))
    thin = {"open": [], "graded": _g("UP", "UP", 5), "score": {}, "probe": {}}
    tp = df.probabilities(thin, "USDT.D", 120, "UP", 3)
    check("نمونهٔ کم = احتمال چاپ نمی‌شود (قانون ۱)",
          tp["p"] is None and "نمونه" in tp["why"], str(tp))

    # برایر: کمتر بهتر؛ حدسِ بی‌اطلاع ⅓ = ۰.۶۶۷
    check("برایرِ پیش‌بینی کامل صفر است",
          df.brier({"UP": 1.0, "DOWN": 0.0, "FLAT": 0.0}, "UP") == 0.0)
    check("برایرِ حدسِ بی‌اطلاع ~۰.۶۶۷ است",
          abs(df.brier({"UP": 1 / 3, "DOWN": 1 / 3, "FLAT": 1 / 3}, "UP")
              - 0.6667) < 0.001)
    check("برایرِ پیش‌بینیِ کاملاً غلط ۲.۰ است",
          df.brier({"UP": 0.0, "DOWN": 1.0, "FLAT": 0.0}, "UP") == 2.0)
    check("بدون احتمال، برایر ساخته نمی‌شود", df.brier(None, "UP") is None)

    # احتمال روی خودِ پیش‌بینی می‌نشیند و بعد از سررسید نمره می‌خورد
    up_pts2 = [{"t": now - m * 60000, "u": 5.0 + 0.001 * (300 - m), "b": 60.0}
               for m in range(300, -1, -3)]
    f_p = [x for x in df.make_forecast(up_pts2, {}, now, st=pst)
           if x["metric"] == "USDT.D" and x["horizon_min"] == 120][0]
    check("شمار شواهد روی پیش‌بینی ثبت می‌شود (سطلِ احتمال)",
          isinstance(f_p.get("ev_n"), int), str(f_p)[:200])
    check("پیش‌بینی احتمالِ شمرده‌شده را حمل می‌کند",
          f_p.get("p") is not None and f_p.get("p_n") == 40, str(f_p)[:260])

    st_b = {"open": [dict(f_p, due=now - 60000,
                          base=up_pts2[-1]["u"] - 0.5)],
            "graded": [], "score": {}}
    df.grade_due(st_b, up_pts2, now)
    row = st_b["graded"][0]
    check("بعد از سررسید، برایر روی همان احتمالِ قبلی حساب می‌شود",
          isinstance(row.get("brier"), float), str(row)[:260])
    sb2 = df.scoreboard(st_b)
    key = "USDT.D|120m"
    check("برایر در کارنامه تجمیع می‌شود", sb2[key].get("brier") is not None,
          str(sb2))
    check("و بدون مرجعِ اقلیم چاپ نمی‌شود (درسِ درصدِ بی‌بنچمارک)",
          sb2[key].get("brier_climate") is not None
          and sb2[key].get("brier_skill") is not None, str(sb2[key]))

    print(f"\n✓ همهٔ {OK} آزمون ناظر پیش‌بینی دامیننس گذشت")


if __name__ == "__main__":
    run()
