"""آزمون ناظر کل (E26) — دستور مستدل، بدون وتو، بدون دستکاری تولید."""
import json
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from hamid import overseer as ov                              # noqa: E402

OK = 0


def check(name, cond, extra=""):
    global OK
    if not cond:
        print(f"  ✗ {name} {extra}")
        raise SystemExit(1)
    OK += 1
    print(f"  ✓ {name}")


def run():
    tmp = Path(tempfile.mkdtemp())
    ov.SIG, ov.OUT = tmp, tmp / "overseer.json"
    now = int(time.time() * 1000)

    # ۱) کارنامهٔ ضعیف دفتر → دستور دقت به E17/E11 با دلیل عددی
    rep = {"paper": {"sent_scan_signals": {"trades": 30, "win_pct": 40,
                                          "mean_r": -0.1}}}
    ds = ov.directives(rep, now)
    d = [x for x in ds if x["engine"] == "E17,E11"]
    check("برد ۴۰٪ در دفترِ صادرشده → دستور دقت به کمیته/روتر",
          d and d[0]["sev"] == "high")
    check("دلیل عددی نوشته شده", "40" in d[0]["reason"], d[0]["reason"])
    # عیب ممیزی ۲۳ اوت: lifetime دفترهای تمرین/اسکلپ/شوک را قاطی می‌کند و
    # مبنای دستور نیست — دفترِ آلودهٔ منفی با دفترِ صادرشدهٔ سالم = بی‌دستور.
    ds2 = ov.directives({"paper": {
        "lifetime": {"trades": 31000, "win_pct": 40, "mean_r": -0.1},
        "sent_scan_signals": {"trades": 300, "win_pct": 80, "mean_r": 0.1}}}, now)
    check("دفتر آلودهٔ lifetime دیگر دستور نمی‌سازد (قلاب به دفتر صادرشده)",
          not [x for x in ds2 if x["engine"] == "E17,E11"], str(ds2))

    # ۲) کارنامهٔ پیش‌بینی دامیننس زیر ۵۰٪ → دستور به E03/E04
    (tmp / "dominance.json").write_text(json.dumps({
        "generated": now,
        "forecast": {"scoreboard": {"USDT.D|30m": {"n": 30, "hit": 10}}}}))
    ds = ov.directives({}, now)
    check("پیش‌بینی ضعیف دامیننس → دستور به E03,E04",
          any(x["engine"] == "E03,E04" for x in ds), str(ds))

    # ۳) رژیم UNSAFE → دستور سایز/اجرا
    (tmp / "dominance.json").write_text(json.dumps({
        "generated": now,
        "structure": {"regime": "UNSAFE", "unsafe_reason": "CPI تا ۱ ساعت"}}))
    ds = ov.directives({}, now)
    check("UNSAFE → دستور E16,E19", any(x["engine"] == "E16,E19" for x in ds))

    # ۴) امتیاز منفی دفتر جایزه → بازبینی همان انجین
    (tmp / "rewards.json").write_text(json.dumps(
        {"board": [{"engine": "E10", "points": -4, "stop": 4}]}))
    ds = ov.directives({}, now)
    check("امتیاز −۴ → دستور بازبینی به E10",
          any(x["engine"] == "E10" for x in ds), str(ds))

    # ۵) دادهٔ کهنه → دستور احیا به E02/E23
    (tmp / "dominance.json").write_text(json.dumps(
        {"generated": now - 90 * 60000}))
    ds = ov.directives({}, now)
    check("دامیننس ۹۰ دقیقه کهنه → دستور به E02,E23",
          any(x["engine"] == "E02,E23" for x in ds))

    # ۶) وضعیت سالم → فقط پیام info، نه دستور الکی؛ و run() فایل می‌نویسد
    (tmp / "dominance.json").write_text(json.dumps({"generated": now}))
    (tmp / "rewards.json").write_text(json.dumps({"board": []}))
    ds = ov.run({"paper": {"sent_scan_signals": {"trades": 30, "win_pct": 60,
                                                 "mean_r": 0.2}}})
    check("وضعیت سالم = فقط info", len(ds) == 1 and ds[0]["sev"] == "info")
    j = json.loads(ov.OUT.read_text())
    check("خروجی پنل نوشته شد و بدون وتو است", j["engine"] == "E26"
          and "وتو" in j["note"])

    print(f"\n✓ همهٔ {OK} آزمون ناظر کل گذشت")


if __name__ == "__main__":
    run()
