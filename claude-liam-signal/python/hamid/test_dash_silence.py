"""پاسبان سکوت داشبورد — سؤال حمید ۲۹ اوت: «چرا هیچ پوزیشنی باز نمی‌شود؟»

عیبِ کلاس که این آزمون می‌بندد: **همگام‌سازیِ یک‌بارهٔ شکست‌خورده**.
کلاس استراتژی فقط در `__init__` همگام می‌شد؛ اگر همان یک بار شکست
می‌خورد، `_TOP_LIQ_OK` تا پایان عمر پروسه False می‌ماند و analyze()
برای هر آلتی NO_SIGNAL می‌داد — درست طبق قانون ۱، ولی **ابدی و بی‌صدا**.
از بیرون فرقی با «ستاپ نیست» نداشت.

سه چیزی که این‌جا قفل می‌شود:
۱. دروازهٔ نقدشوندگی شل نشده (سکوت با لایهٔ ناهمگام هنوز درست است).
۲. ولی ابدی نیست: تلاش دوباره با فاصله انجام می‌شود.
۳. و بی‌صدا نیست: دلیلِ رد شمرده می‌شود و diagnose() علتِ غالب را
   می‌گوید — «موتور کور است» در برابر «ستاپ نیست».
"""
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

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


def candles(n, up=True, base=100.0):
    out, px = [], base
    for i in range(n):
        px = px * (1.004 if up else 0.996)
        o = px * 0.999
        h, l = max(o, px) * 1.001, min(o, px) * 0.997
        out.append({"t": (i + 1) * 900000, "o": o, "h": h, "l": l,
                    "c": px, "v": 1000.0})
    return out


def run():
    c4h, c1h, c15 = candles(260), candles(260), candles(300)

    # ── ۱) دروازه شل نشده: لایهٔ ناهمگام = NO_SIGNAL برای آلت ──────────────
    S.TOP_LIQUIDITY.clear()
    S._TOP_LIQ_OK = False
    S.FUNNEL.clear()
    r = S.analyze("ARBUSDT", c4h, c1h, c15, btc4h=c4h, btc1h=c1h)
    check("لایهٔ نقدشوندگی ناهمگام = NO_SIGNAL (دروازه سرِ جایش)",
          r["action"] == "NO_SIGNAL" and "نقدشوندگی" in r["why"], str(r)[:200])
    check("خودِ خروجی راهِ تشخیص را نشان می‌دهد",
          "diagnose" in r, str(r)[:200])

    # ── ۲) و بی‌صدا نیست: شمارش دلیل + حکمِ خوانا ─────────────────────────
    for _ in range(4):
        S.analyze("OPUSDT", c4h, c1h, c15, btc4h=c4h, btc1h=c1h)
    d = S.diagnose()
    check("دلیلِ ردها شمرده می‌شود (سکوتِ بی‌عدد ممنوع)",
          d["decisions_seen"] == 5, str(d["decisions_seen"]))
    check("علتِ غالب همان دروازهٔ نقدشوندگی است و ۱۰۰٪ می‌خورد",
          d["top_reasons"] and d["top_reasons"][0]["pct"] == 100.0
          and "نقدشوندگی" in d["top_reasons"][0]["reason"],
          str(d["top_reasons"])[:200])
    check("حکم صریح می‌گوید موتور کور است، نه «ستاپ نیست»",
          "کور" in d["verdict"], d["verdict"])
    check("وضعیت لایه روی تشخیص است", d["liquidity_layer_ok"] is False)

    # ── ۳) ابدی نیست: تلاش دوبارهٔ همگام‌سازی ─────────────────────────────
    calls = {"n": 0}
    real_sync = S.sync_all

    def fake_fail():
        calls["n"] += 1
        S._TOP_LIQ_OK = False
        return {"top_liquidity": 0}

    S.sync_all = fake_fail
    S._LAST_SYNC = 0.0
    try:
        S.ensure_sync()
        check("اولین بار همگام می‌شود", calls["n"] == 1)
        S.ensure_sync()
        check("بلافاصله دوباره شبکه نمی‌زند (ضدِ هدررفت)", calls["n"] == 1)
        S._LAST_SYNC = time.time() - S._SYNC_RETRY_S - 1
        S.ensure_sync()
        check(f"بعد از {S._SYNC_RETRY_S}s دوباره تلاش می‌کند "
              "(شکستِ یک‌بار، ابدی نمی‌ماند)", calls["n"] == 2)

        # همگامِ موفق دیگر تکرار نمی‌شود
        def fake_ok():
            calls["n"] += 1
            S._TOP_LIQ_OK = True
            S.TOP_LIQUIDITY.update({"ARBUSDT"})
            return {"top_liquidity": 1}

        S.sync_all = fake_ok
        S._LAST_SYNC = time.time() - S._SYNC_RETRY_S - 1
        S.ensure_sync()
        n_after_ok = calls["n"]
        S._LAST_SYNC = time.time() - S._SYNC_RETRY_S - 1
        S.ensure_sync()
        check("همگامِ موفق بی‌دلیل تکرار نمی‌شود", calls["n"] == n_after_ok)
    finally:
        S.sync_all = real_sync

    # ── ۴) با لایهٔ همگام، موتور دوباره تصمیم می‌گیرد (کور نمی‌ماند) ───────
    S.FUNNEL.clear()
    r2 = S.analyze("ARBUSDT", c4h, c1h, c15, btc4h=c4h, btc1h=c1h)
    check("با لایهٔ همگام، رد دیگر به‌خاطر نقدشوندگی نیست",
          r2["action"] != "NO_SIGNAL" or "نقدشوندگی" not in r2["why"],
          str(r2)[:200])
    d2 = S.diagnose()
    check("حکم به «موتور بینا» برمی‌گردد",
          "کور" not in d2["verdict"], d2["verdict"])

    # ── ۵) مسیرهای ورودیِ داشبورد همگام‌سازی را صدا می‌زنند ────────────────
    src = (HERE.parent / "liam9_strategy.py").read_text(encoding="utf-8")
    for fn in ("def signal(", "def scalp_signal("):
        body = src.split(fn, 1)[1][:400]
        check(f"«{fn.strip('def (')}» قبل از کندل، ensure_sync دارد",
              "ensure_sync()" in body, body[:120])
    check("کلاس‌های داشبورد به‌جای همگامِ یک‌باره، ensure_sync دارند",
          src.count("ensure_sync()") >= 6 and "        sync_all()" not in src)
    check("راه تشخیص از خط فرمان هست (--diagnose)", "--diagnose" in src)

    # ── ۶) راهِ دستیِ لایه، برای داشبوردِ بی‌اینترنت — بدون شل‌کردن دروازه ──
    S.TOP_LIQUIDITY.clear()
    S._TOP_LIQ_OK = False
    check("فهرست خالی، دروازه را باز نمی‌کند",
          S.set_top_liquidity([]) == 0 and S._TOP_LIQ_OK is False)
    n = S.set_top_liquidity(["arbusdt", "ETHUSDT"])
    check("فهرست دستی پذیرفته می‌شود و بزرگ‌حرف می‌شود",
          n == 2 and "ARBUSDT" in S.TOP_LIQUIDITY and S._TOP_LIQ_OK is True)
    check("منبعِ دستی روی تشخیص ثبت می‌شود (ردپا می‌ماند)",
          "دستی" in str(S.diagnose()["last_sync"]), str(S.diagnose()["last_sync"]))

    print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(run())
