"""آزمون میز اسکلپ — دفتر جدا، اهرم محافظ‌دار، تریل، بدون دستکاری تولید."""
import json
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from hamid import scalp                                        # noqa: E402

OK = 0


def check(name, cond, extra=""):
    global OK
    if not cond:
        print(f"  ✗ {name} {extra}")
        raise SystemExit(1)
    OK += 1
    print(f"  ✓ {name}")


def mk(path, t0=0):
    return [{"t": t0 + i * 60000, "o": p, "h": p * 1.0015, "l": p * 0.9985,
             "c": p} for i, p in enumerate(path)]


def run():
    # ۱) سشن‌ها
    def at(h):
        return int(time.mktime((2026, 8, 18, h, 30, 0, 0, 0, 0))
                   - time.timezone) * 1000
    check("سشن‌ها درست برچسب می‌خورند",
          scalp.session_of(at(3)) == "asia"
          and scalp.session_of(at(9)) == "london"
          and scalp.session_of(at(13)) == "overlap"
          and scalp.session_of(at(18)) == "ny")

    # ۲) تصمیم لانگ در روند صعودی با پولبک + IBS پایین، در سشن overlap
    up = [100 + i * 0.05 for i in range(90)]
    pull = up + [up[-1] - i * 0.03 for i in range(1, 7)]
    cd = mk(pull, t0=at(13))
    cd[-1]["l"], cd[-1]["c"] = cd[-1]["c"] * 0.998, cd[-1]["c"] * 0.9982
    # کندل قبلی: بدنهٔ قاطع صعودی + سوییپ شدو زیر کف‌ها
    cd[-2]["o"], cd[-2]["c"] = cd[-2]["c"] * 0.997, cd[-2]["c"]
    cd[-2]["l"] = min(k["l"] for k in cd[-12:-2]) * 0.999
    # کف پولبک ~۰.۷٪ زیر قیمت: استاپی که هم از دام کارمزد رد شود
    # (fee_r<0.30 یعنی استاپ>0.5٪) و هم داخل بند لیکویید اهرم بماند
    cd[-4]["l"] = cd[-1]["c"] * 0.993
    s = scalp.decide(cd)
    check("ستاپ لانگ ساخته شد", s is not None and s["dir"] == "LONG", str(s))
    # قانون واحد ۲۳ اوت: بازه از liam9_strategy می‌آید (۱۵–۳۹)، نه عدد
    # جدا برای این میز — باند ۴۵–۹۰ نسخ شد.
    import liam9_strategy as _ST
    check("اهرم در بازهٔ قانون واحد و سقفش با فاصلهٔ لیکویید محدود شد",
          _ST.LEV_MIN <= s["lev"] <= _ST.LEV_MAX_CONF
          and s["lev"] <= int(50.0 / s["stop_pct"]), str(s["lev"]))
    check("سشن و ویژگی کندل قبلی ثبت شد",
          s["session"] == "overlap" and (s["decisive_prev"] or s["shadow_sweep"]))

    # ۳) محافظ لیکویید: استاپ گشاد در اهرم بالا رد می‌شود
    wide = mk([100] * 70 + [100 + i * 0.5 for i in range(20)]
              + [110 - i * 0.9 for i in range(1, 6)], t0=at(13))
    wide[-1]["l"] = wide[-1]["c"] * 0.97      # استاپ خیلی دور
    check("استاپ بزرگ‌تر از نصف فاصلهٔ لیکویید = رد",
          scalp.decide(wide) is None)

    # ۴) شبیه‌سازی تریل: بعد از ⅓ مسیر، برگشت کامل دیگر ضرر کامل نیست
    s2 = {"dir": "LONG", "entry": 100.0, "sl": 99.5, "tp1": 100.75}
    cd2 = mk([100.0] * 5)
    cd2 += [{"t": 5 * 60000, "o": 100, "h": 100.3, "l": 100, "c": 100.28}]
    cd2 += [{"t": 6 * 60000, "o": 100.28, "h": 100.28, "l": 99.0, "c": 99.1}]
    out, r = scalp.simulate(cd2, 4, s2)
    check("تریل: برگشت بعد از ⅓ = trail با زیان تقریباً صفر",
          out == "trail" and r > -0.35, f"{out} {r}")

    # ۴ب) محافظ مرز: کندل‌های نارس (بدون آیندهٔ کافی) نسوزند.
    # کلاس خطای ۱۸ اوت: frontier تا cd[-1] جلو می‌رفت و دفتر یخ می‌زد.
    cd_f = mk([100.0] * 200)
    _, fr = scalp.replay_symbol("X", cd_f, 0)
    limit_t = cd_f[len(cd_f) - scalp.HOLD_BARS - 3]["t"]
    check("مرز از آخرین کندل ارزیابی‌شدنی جلوتر نمی‌رود",
          fr <= limit_t < cd_f[-1]["t"], f"fr={fr} limit={limit_t}")
    # کندلی که امروز نارس بود، بعد از رسیدن آیندهٔ کافی باید ارزیابی شود
    fire2 = cd_f[190]["t"]                       # دیروز نارس (> limit)
    old_d2 = scalp.decide
    scalp.decide = lambda win, now_ms=None: (
        {"dir": "LONG", "entry": win[-1]["c"], "sl": win[-1]["c"] * 0.993,
         "tp1": win[-1]["c"] * 1.0105, "stop_pct": 0.7, "fee_r": 0.214,
         "ibs": 0.1, "session": "overlap", "lev": 45,
         "decisive_prev": True, "shadow_sweep": False}
        if win[-1]["t"] == fire2 else None)
    try:
        rows0, fr0 = scalp.replay_symbol("X", cd_f, 0)
        cd_g = cd_f + mk([100.0] * 100, t0=cd_f[-1]["t"] + 60000)
        rows1, _ = scalp.replay_symbol("X", cd_g, fr0)
        check("کندل نارسِ دیروز، امروز ارزیابی شد",
              len(rows0) == 0 and len(rows1) == 1,
              f"{len(rows0)} {len(rows1)}")
    finally:
        scalp.decide = old_d2

    # ۵) run() فقط در sandbox: دفتر و state منحرف؛ لوله‌کشی با انجین تزریقی
    # (الگوی test_fill_books — منطق decide بالا جدا سنجیده شد)
    tmp = Path(tempfile.mkdtemp())
    from hamid import paper
    old = (paper.CLOSED, scalp.STATE, scalp.OUT)
    paper.CLOSED = tmp / "closed.jsonl"
    scalp.STATE, scalp.OUT = tmp / "state.json", tmp / "scalp.json"
    long_cd = mk([100.0] * 300, t0=at(13))
    fire_t = long_cd[120]["t"]
    old_decide = scalp.decide
    scalp.decide = lambda win, now_ms=None: (
        {"dir": "LONG", "entry": win[-1]["c"], "sl": win[-1]["c"] * 0.993,
         "tp1": win[-1]["c"] * 1.0105, "stop_pct": 0.7, "fee_r": 0.214,
         "ibs": 0.1, "session": "overlap", "lev": 71,
         "decisive_prev": True, "shadow_sweep": False}
        if win[-1]["t"] == fire_t else None)
    try:
        import sources
        old_k = sources.klines
        sources.klines = lambda sym, tf, n, **kw: [
            [k["t"], k["o"], k["h"], k["l"], k["c"], 1.0] for k in long_cd]
        n = scalp.run(symbols=["XUSDT"], quiet=True)
        check("ریپلی معامله ساخت و در دفتر جدا نشست", n >= 1
              and all((json.loads(l).get("why") or {}).get("stage") == "scalp"
                      for l in paper.CLOSED.read_text().splitlines() if l))
        j = json.loads(scalp.OUT.read_text())
        check("عکس‌فوری پنل با کارنامهٔ سشن نوشته شد",
              j["book"]["n"] >= 1 and j["book"]["by_session"], str(j["book"]))
        check("ضدتکرار: اجرای دوم صفر معاملهٔ تازه",
              scalp.run(symbols=["XUSDT"], quiet=True) == 0)
    finally:
        paper.CLOSED, scalp.STATE, scalp.OUT = old
        sources.klines = old_k
        scalp.decide = old_decide

    print(f"\n✓ همهٔ {OK} آزمون میز اسکلپ گذشت")


if __name__ == "__main__":
    run()
