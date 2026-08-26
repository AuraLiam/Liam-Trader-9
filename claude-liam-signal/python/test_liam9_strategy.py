"""آزمون استراتژی داشبورد ۲.۰ — قرارداد بارگذار، تجربه، اسکلپ، ممیزی تداخل.

این فایل نسخه‌ای است که حمید در داشبورد می‌گذارد؛ خرابی‌اش آن‌جا دیده
نمی‌شود مگر با صفر معاملهٔ خاموش. پس هر رفتار قابل‌شکستن این‌جا محافظ
دارد. `--selftest` خودش هستهٔ منطق را می‌سنجد؛ این‌جا قرارداد بیرونی.
"""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import liam9_strategy as st                                   # noqa: E402

OK = 0


def check(name, cond, extra=""):
    global OK
    if not cond:
        print(f"  ✗ {name} {extra}")
        raise SystemExit(1)
    OK += 1
    print(f"  ✓ {name}")


def mk(path, tf_ms=900000, t0=0):
    return [{"t": t0 + i * tf_ms, "o": p, "h": p * 1.004, "l": p * 0.996,
             "c": p} for i, p in enumerate(path)]


def run():
    st._selftest()                       # هستهٔ منطق

    # ۱) قرارداد بارگذار داشبورد: کلاس + meta (خطای ۱۸ اوت: «هیچ کلاس
    #    استراتژی با meta پیدا نشد» — این تست همان را برای همیشه می‌بندد)
    for cls in (st.Liam9Strategy, st.Liam9ScalpStrategy):
        m = getattr(cls, "meta", None)
        check(f"{cls.__name__} کلاس با meta دارد",
              isinstance(m, dict) and m.get("name") and m.get("id")
              and m.get("timeframes"), str(m)[:120])
        for ep in ("generate_signal", "on_bar", "run"):
            check(f"{cls.__name__}.{ep} نقطهٔ ورود دارد",
                  callable(getattr(cls, ep, None)))
    check("meta قرارداد ریسک را اعلام می‌کند",
          st.Liam9Strategy.meta["risk_contract"]["stop_pct"]["scalp_max"] > 0)

    # ۲) کلاس بدون شبکه ساخته می‌شود (داشبورد آفلاین هم بارگذاری کند)
    old_get = st._get
    st._get = lambda *a, **kw: (_ for _ in ()).throw(OSError("بی‌شبکه"))
    try:
        s = st.Liam9Strategy()
        check("ساخت کلاس بدون شبکه خطا نمی‌دهد", s.meta["version"])
        check("sync_all بی‌شبکه امن برمی‌گردد",
              st.sync_all() == {"params": None, "experience_pairs": 0,
                                "top_liquidity": 0, "edge_rules": 0,
                                "room_weights": 0})
        check("وزن اتاق‌ها بی‌شبکه بی‌اثر است (همه ۱.۰، بدون وتو)",
              st.room_weight("candles") == 1.0
              and st.apply_room_weights([("candles", 10)])[0] == 0.0)
        check("و قفسهٔ لبه بی‌شبکه stale می‌ماند (بی‌اثر)",
              st.EDGE.get("stale", True) is True
              or st.edge_boost("ibs", {"dir": "LONG", "btc_up": True})[0] == 0)
    finally:
        st._get = old_get

    # ۳) لایهٔ تجربه: کلید ترکیبی و احترام به thin
    st.EXPERIENCE.clear()
    st.EXPERIENCE["XUSDT|LONG"] = {"n": 20, "win_pct": 90.0, "mean_r": 0.5,
                                   "thin": False}
    check("experience_of کلید (ارز|جهت) را می‌خواند",
          st.experience_of("XUSDT", "LONG")["n"] == 20
          and st.experience_of("XUSDT", "SHORT") is None)

    # ۴) اهرم: محافظ لیکویید هرگز دور زده نمی‌شود
    for stop in (0.4, 0.6, 0.8, 1.0, 1.2):
        lev = st.suggest_leverage(stop, 100, mode="scalp")
        check(f"اهرم اسکلپ با استاپ {stop}٪ داخل محافظ",
              lev is None or lev <= int(50.0 / stop))
    # نسخ ۲۳ اوت: باند سوینگ ۳–۱۰ جای خودش را به نگاشت واحد ۱۵–۳۹ داد
    # («ضرایب بر اساس میزان اطمینان از ۱۵ تا ۳۹»)؛ این بررسی با قانونِ
    # حاکم همتراز شد — محافظ لیکویید همچنان حاکم مطلق است.
    check("اهرم سوینگ = نگاشت واحد ۲۳ اوت (کیفیت ۱۰۰ → ۳۹)",
          st.suggest_leverage(0.5, 100) == 39)
    check("و محافظ لیکویید از نگاشت قوی‌تر است",
          st.suggest_leverage(2.0, 100) == 25)

    # ۵) ممیزی تداخل — سه سناریوی واقعی
    a = st.audit_environment({"max_leverage": 20, "min_stop_pct": 2.5,
                              "timeframes": ["15m", "1h", "4h"]})
    check("کف استاپ ۲.۵٪ = تداخل جدی (وتوی خاموش اسکلپ)",
          a["verdict"] == "تداخل جدی" and a["conflicts"])
    check("نبود تایم ۱د تداخل گزارش می‌شود",
          any("1m" in x for x in a["conflicts"]), str(a["conflicts"]))
    a2 = st.audit_environment({"max_leverage": 20, "min_stop_pct": 0.3,
                               "fee_pct": 0.15,
                               "timeframes": ["1m", "15m", "1h", "4h"]})
    check("سقف اهرم ۲۰ به‌تنهایی تداخل جدی نیست",
          not a2["conflicts"] and any("سایز" in n for n in a2["notes"]),
          str(a2))
    a3 = st.audit_environment({"fee_pct": 0.0})
    check("کارمزد صفر داشبورد = هشدار RR خوش‌بین",
          any("کارمزد" in x for x in a3["conflicts"]), str(a3["conflicts"]))

    class Eng:                                 # آبجکت، نه dict
        leverage_cap = 20
        min_stop_distance_pct = 3.0
    a4 = st.audit_environment(Eng())
    check("ممیزی از آبجکت موتور ریسک هم می‌خواند (نه فقط dict)",
          a4["detected"].get("max_leverage") == 20 and a4["conflicts"])

    # ۶) قانون ۱: دادهٔ ناکافی هرگز سیگنال نمی‌شود
    check("کندل کم = NO_SIGNAL",
          st.analyze("X", None, None, None)["action"] == "NO_SIGNAL"
          and st.scalp_decide([], "X")["action"] == "NO_SIGNAL")

    # ۷) خروجی JSON-سریالایزبل است (داشبورد لاگ/ارسال می‌کند)
    up = [100 + i * 0.4 for i in range(230)]
    c15 = mk(up + [up[-1] - i * 0.5 for i in range(1, 16)])
    c15[-1]["l"], c15[-1]["c"] = c15[-1]["c"] * 0.99, c15[-1]["c"] * 0.9905
    st.EXPERIENCE.clear()
    r = st.analyze("TESTUSDT", mk(up), mk(up), c15)
    check("خروجی سوینگ JSON می‌شود و برند دارد",
          json.loads(json.dumps(r, ensure_ascii=False))["panel"] == "لیام تریدر ۹")

    up1 = [100 + i * 0.05 for i in range(120)]
    c1m = mk(up1 + [up1[-1] - i * 0.03 for i in range(1, 7)], tf_ms=60000,
             t0=int(time.time() * 1000) - 126 * 60000)
    c1m[-1]["l"], c1m[-1]["c"] = c1m[-1]["c"] * 0.998, c1m[-1]["c"] * 0.9982
    c1m[-4]["l"] = c1m[-1]["c"] * 0.993
    sc = st.scalp_decide(c1m, "TESTUSDT")
    check("خروجی اسکلپ سطح تریل ⅓ را چاپ می‌کند (اجرای دستی حمید)",
          sc["trail_at"] > sc["entry"] and "🪜" in " ".join(sc["why"]))
    check("خروجی اسکلپ JSON می‌شود",
          json.loads(json.dumps(sc, ensure_ascii=False))["mode"] == "scalp")

    print(f"\n✓ همهٔ {OK} آزمون استراتژی داشبورد گذشت")


if __name__ == "__main__":
    run()
