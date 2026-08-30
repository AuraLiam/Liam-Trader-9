"""پاسبان موتور اجرا — پل تلگرام ↔ داشبورد (دستور حمید، ۳۰ اوت).

«می‌خوام وقتی از تلگرام سیگنال با تأیید دامیننس میاد سریعاً همون توی
ترید پیاده بشه … و این دفعه نمی‌خوام به مشکل بخوره.»

چهار خطری که این آزمون می‌بندد:
۱. قصدِ بی‌مهر (بدون دامیننس/سشن/انقضا) وارد دفتر شود — داشبورد کور
   اجرا می‌کند.
۲. داشبورد قصدِ منقضی یا بی‌استاپ یا کراس را اجرا کند — همان سه عیبی
   که قرارداد اجرای ۲۰ اوت را ساخت.
۳. یک قصد دو بار اجرا شود (کلاس PAXG×۵ این بار در لایهٔ اجرا).
۴. ردِ بی‌صدا — سکوت بدون دلیلِ شمرده (کلاس همان عیب داشبورد ۲۹ اوت).
"""
import json
import sys
import time
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from hamid import execution_gate as EG                        # noqa: E402
import liam9_strategy as S                                    # noqa: E402

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


def intent(now, **kw):
    base = {"id": f"T-{kw.get('sym', 'BTC')}-{len(EG.VALID_MIN)}-{time.time_ns()}",
            "status": "PENDING", "symbol": "BTCUSDT", "direction": "LONG",
            "tf": "15m", "entry": 100.0, "sl": 98.0, "tp1": 104.0,
            "margin_mode": "isolated", "created_at": now,
            "expires_at": now + 90 * 60000,
            "dominance": {"usdt_d": 5.0, "btc_d": 56.0, "age_min": 10.0,
                          "fresh": True}}
    base.update(kw)
    return base


def run():
    now = int(time.time() * 1000)
    tmp = Path(tempfile.mkdtemp())

    # ── ۱) مولد قصد، مهرها را واقعاً می‌گذارد ─────────────────────────────
    EG.DOM = tmp / "dominance.json"
    EG.DOM.write_text(json.dumps({
        "generated": now - 5 * 60000, "usdt_dominance": 4.9,
        "btc_dominance": 56.2, "structure": {"regime": "RANGE"},
        "macro": [{"title": "CPI", "in_hours": 1.5},
                  {"title": "FOMC", "in_hours": 30}]}))
    EG.OUTBOX = tmp / "exec-outbox.json"
    sig = {"sym": "ETHUSDT", "dir": "LONG", "entry": 100.0, "sl": 98.0,
           "tp1": 104.0, "tf": "15m", "trend4": "up", "trend1": "up"}
    r = EG.evaluate(sig)
    check("زنجیرهٔ قصد با سیگنال سالم قبول می‌کند", r["ok"], str(r)[:200])
    it = r["intent"]
    check("مهر دامیننس با سن و تازگی روی قصد است",
          it["dominance"]["fresh"] is True
          and abs(it["dominance"]["age_min"] - 5.0) < 1.0, str(it["dominance"]))
    check("سشن معاملاتی روی قصد است (نام + تعطیلی هفته)",
          it["session"]["name"] in ("asia", "london", "ny", "overlap")
          and "weekend" in it["session"], str(it["session"]))
    check("رویداد ≤۲س پرچم event_window می‌گیرد (CPI در ۱.۵س)",
          it["events"]["event_window"] is True
          and it["events"]["upcoming"][0]["title"] == "CPI", str(it["events"]))
    check("پنجرهٔ اعتبار ۱۵د = ۹۰ دقیقه (قانون ۱۰ بند ۴)",
          abs(it["expires_at"] - it["created_at"] - 90 * 60000) < 2000)
    check("ناحیهٔ ورود = ورود ± ۰.۳۵×ریسک",
          abs(it["entry_zone"]["lo"] - (100 - 0.35 * 2)) < 1e-6
          and abs(it["entry_zone"]["hi"] - (100 + 0.35 * 2)) < 1e-6,
          str(it["entry_zone"]))
    check("قصد فقط ایزوله صادر می‌شود + استاپ/تارگت با نام رایج",
          it["margin_mode"] == "isolated" and it["stop_loss"] == 98.0
          and it["take_profit"] == 104.0)

    # دامیننس کهنه → مهر صادقانه fresh=False (نه پنهان‌کاری)
    EG.DOM.write_text(json.dumps({"generated": now - 300 * 60000,
                                  "usdt_dominance": 4.9,
                                  "btc_dominance": 56.2, "macro": []}))
    it2 = EG.evaluate(sig)["intent"]
    check("دادهٔ دامیننس کهنه = مهر fresh=False (قانون ۱ — پنهان نمی‌شود)",
          it2["dominance"]["fresh"] is False
          and it2["dominance"]["age_min"] > 200, str(it2["dominance"]))

    # ── ۲) مصرف‌کننده: چک‌های قرارداد ────────────────────────────────────
    S.EXEC_SEEN.clear()
    ok_it = intent(now)
    o, why = S._exec_check(ok_it, now)
    check("قصد سالم تحویل می‌شود", o is not None and why is None, str(why))
    check("سفارش تحویلی مهر زمان تحویل دارد", o["delivered_at"] == now)

    for name, bad, frag in (
        ("بی‌استاپ رد می‌شود", intent(now, sl=None), "استاپ"),
        ("بی‌تارگت رد می‌شود", intent(now, tp1=0), "استاپ/تارگت"),
        ("کراس رد می‌شود", intent(now, margin_mode="cross"), "ایزوله"),
        ("منقضی رد می‌شود — تعقیب قیمت ممنوع",
         intent(now, expires_at=now - 1000), "منقضی"),
        ("مهر دامیننس کهنه/غایب = رد",
         intent(now, dominance={"fresh": False, "age_min": 300.0}), "دامیننس"),
        ("وضعیت غیر PENDING اجرا نمی‌شود",
         intent(now, status="FILLED"), "PENDING"),
    ):
        S.EXEC_SEEN.clear()
        o2, w2 = S._exec_check(bad, now)
        check(name, o2 is None and w2 and frag in w2, str(w2))

    # قصد بدون فیلد انقضا (سازگاری با دفتر قدیمی): از created_at حساب می‌شود
    S.EXEC_SEEN.clear()
    legacy = intent(now, created_at=now - 200 * 60000)
    legacy.pop("expires_at")
    o3, w3 = S._exec_check(legacy, now)
    check("قصد قدیمیِ بی‌انقضا هم بعد از ۹۰د منقضی است",
          o3 is None and "منقضی" in (w3 or ""), str(w3))

    # ── ۳) ضدتکرار: هر قصد فقط یک بار (کلاس PAXG×۵ در لایهٔ اجرا) ────────
    S.EXEC_SEEN.clear()
    first, _ = S._exec_check(ok_it, now)
    S.EXEC_SEEN.add(first["id"])
    second, w4 = S._exec_check(ok_it, now)
    check("همان قصد بار دوم تحویل نمی‌شود", second is None
          and "ضدتکرار" in w4, str(w4))

    # ── ۴) رد بی‌صدا ممنوع + شکست شبکه امن ───────────────────────────────
    S.EXEC_SEEN.clear()
    real_get = S._get

    def fake_get(url, timeout=15):
        if S.EXEC_OUTBOX_PATH in url:
            return [ok_it, intent(now, margin_mode="cross"),
                    intent(now, status="FILLED")]
        raise RuntimeError("قطع")

    S._get = fake_get
    try:
        r = S.exec_orders(now_ms=now)
        check("موتور فقط قصد معتبر می‌دهد", len(r["orders"]) == 1
              and r["orders"][0]["id"] == ok_it["id"], str(r)[:300])
        check("هر ردِ PENDING دلیلِ شمرده دارد (سکوت بی‌دلیل ممنوع)",
              len(r["skipped"]) == 1 and "ایزوله" in r["skipped"][0],
              str(r["skipped"]))
        check("منبع خوانده‌شده اعلام می‌شود", bool(r["source"]))

        def dead_get(url, timeout=15):
            raise RuntimeError("قطع کامل")
        S._get = dead_get
        r2 = S.exec_orders(now_ms=now)
        check("شکست شبکه = خالی با دلیل، نه استثنا و نه حدس",
              r2["orders"] == [] and "نیامد" in r2.get("why", ""), str(r2))
    finally:
        S._get = real_get

    # ── ۵) سشن روی خروجی سیگنال و کلاس داشبورد ───────────────────────────
    fin = S._finalize({"action": "LONG", "symbol": "ETHUSDT",
                       "sl": 98.0, "tp1": 104.0})
    check("سشن معاملاتی روی هر سیگنال قابل‌معامله ثبت می‌شود",
          fin.get("session", {}).get("name") in ("asia", "london", "ny",
                                                 "overlap"), str(fin)[:200])
    src = (HERE.parent / "liam9_strategy.py").read_text(encoding="utf-8")
    check("کلاس داشبورد متد موتور را دارد (pending_orders)",
          "def pending_orders(" in src)
    check("نسخهٔ فایل ۳.۱ است — با محتوایش همقد",
          '"liam9-dash-3.1"' in src and "نسخهٔ داشبورد ۳.۱" in src)

    print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(run())
