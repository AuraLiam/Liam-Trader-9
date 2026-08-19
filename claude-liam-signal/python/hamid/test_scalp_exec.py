"""آزمون پل اسکلپ→داشبورد و گزارش روزانه.

این‌جا مرز پول واقعی است، پس محافظ‌ها سخت‌اند: فقط فیوچرز، اهرم داخل
محافظ، سقف نوشنال، ضدتکرار، و «live» بدون تأیید صریح حمید روی ماشین
داشبورد به demo تنزل می‌کند.
"""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import liam9_link as LINK                                    # noqa: E402
from hamid import scalp_exec as EX                           # noqa: E402
from hamid import daily_report as DR                         # noqa: E402

OK = 0


def check(name, cond, extra=""):
    global OK
    if not cond:
        print(f"  ✗ {name} {extra}")
        raise SystemExit(1)
    OK += 1
    print(f"  ✓ {name}")


def good_setup(now, **kw):
    s = {"symbol": "SOLUSDT", "action": "LONG", "entry": 100.0, "sl": 99.3,
         "tp1": 101.5, "stop_pct": 0.7, "leverage": 45, "quality": 75,
         "session": "overlap", "fee_r": 0.21, "tf": "1m", "t": now}
    s.update(kw)
    return s


def run():
    now = int(time.time() * 1000)

    # ── دروازهٔ «مناسب اسکلپ» ─────────────────────────────────────────
    ok, why = EX.scalp_ready(good_setup(now, leverage=15), now)
    check("ستاپ سالم عبور می‌کند", ok, why)
    for kw, label in (
            ({"t": now - 600_000}, "کهنه"),
            ({"fee_r": 0.45}, "دام کارمزد"),
            ({"quality": 50}, "کیفیت پایین"),
            ({"session": "asia"}, "سشن آسیا"),
            ({"leverage": 90, "stop_pct": 0.7}, "اهرم بیرون محافظ")):
        ok2, why2 = EX.scalp_ready(good_setup(now, **kw), now)
        check(f"«{label}» رد می‌شود", not ok2, why2)

    # ── سفارش: فقط فیوچرز و داخل مرزها ───────────────────────────────
    cmd = LINK.make_exec_command(1, "SOLUSDT", "LONG", 100.0, 99.3, 101.5,
                                 0.7, 15, 150.0)
    check("سفارش فیوچرز ساخته شد", cmd["order"]["product"] == "futures"
          and cmd["order"]["mode"] == "demo" and cmd["order"]["margin_mode"]
          == "isolated", str(cmd["order"])[:150])
    for bad, label in (
            (dict(symbol="SOLUSD"), "نماد غیر USDT"),
            (dict(leverage=60), "اهرم بالای سقف"),
            (dict(leverage=15, stop_pct=5.0), "اهرم بیرون محافظ لیکویید"),
            (dict(notional_usd=5000), "نوشنال بالای سقف"),
            (dict(sl=101.0), "استاپ سمت اشتباه")):
        args = dict(symbol="SOLUSDT", side="LONG", entry=100.0, sl=99.3,
                    tp1=101.5, stop_pct=0.7, leverage=15, notional_usd=150.0)
        args.update(bad)
        try:
            LINK.make_exec_command(2, **args)
            raise AssertionError(f"سفارش نامعتبر ساخته شد: {label}")
        except ValueError:
            OK_ = True
        check(f"«{label}» در ساخت سفارش رد می‌شود", OK_)

    # محصول اسپات هرگز از اعتبارسنجی رد نمی‌شود
    spot = {"product": "spot", "symbol": "SOLUSDT", "side": "LONG",
            "entry": 100.0, "sl": 99.3, "stop_pct": 0.7, "leverage": 5,
            "notional_usd": 100.0, "mode": "demo"}
    check("اسپات رد می‌شود (داشبورد فقط فیوچرز)",
          any("فیوچرز" in e for e in LINK.validate_exec(spot)))

    # ── مرز پول واقعی ────────────────────────────────────────────────
    tmp = Path(tempfile.mkdtemp())
    up, down = tmp / "up.json", tmp / "down.json"
    os.environ["LIAM9_LINK_SECRET"] = "exec-test-key"
    os.environ.pop("LIAM9_ALLOW_LIVE", None)
    lk = LINK.Link(role="test", up=up, down=down, remote=False)
    LINK.push_command(LINK.make_exec_command(1, "SOLUSDT", "LONG", 100.0, 99.3,
                                             101.5, 0.7, 15, 150.0,
                                             mode="live"), down)
    res = lk.apply(lk.pull())
    check("سفارش live بدون تأیید حمید به demo تنزل می‌کند",
          res and res[0]["ok"] and res[0]["order"]["mode"] == "demo"
          and res[0]["order"].get("downgraded"), str(res))
    os.environ["LIAM9_ALLOW_LIVE"] = "1"
    LINK.push_command(LINK.make_exec_command(2, "SOLUSDT", "LONG", 100.0, 99.3,
                                             101.5, 0.7, 15, 150.0,
                                             mode="live"), down)
    res2 = lk.apply(lk.pull())
    check("با تأیید صریح، live عبور می‌کند",
          res2 and res2[0]["order"]["mode"] == "live", str(res2))
    os.environ.pop("LIAM9_ALLOW_LIVE", None)

    # سفارش دستکاری‌شده در فایل (امضای درست، محتوای بد) رد می‌شود
    forged = {"type": "open_position", "seq": 50,
              "expires": time.time() + 60,
              "order": {"product": "futures", "symbol": "SOLUSDT",
                        "side": "LONG", "entry": 100.0, "sl": 99.3,
                        "stop_pct": 0.7, "leverage": 50,
                        "notional_usd": 150.0, "mode": "demo"}}
    forged["sig"] = LINK.sign(forged)
    LINK.push_command(forged, down)
    res3 = lk.apply(lk.pull())
    check("سفارش با اهرم غیرمجاز حتی با امضای درست رد می‌شود",
          res3 and not res3[0]["ok"], str(res3))

    # ── لوله‌کشی کامل: ستاپ زنده → سفارش ─────────────────────────────
    old = (EX.ROOT, EX.STATE, EX.OUT, LINK.DOWN)
    EX.ROOT = tmp
    EX.STATE, EX.OUT = tmp / "state.json", tmp / "out.json"
    LINK.DOWN = tmp / "cmds.json"
    (tmp / "signals").mkdir(parents=True, exist_ok=True)
    (tmp / "signals" / "scalp.json").write_text(json.dumps(
        {"generated": now, "live_setups": [good_setup(now, leverage=15)]},
        ensure_ascii=False))
    (tmp / "signals" / "shock.json").write_text(json.dumps(
        {"generated": now, "live_setups": []}, ensure_ascii=False))
    lk2 = LINK.Link(role="t2", up=up, down=LINK.DOWN, remote=False)
    try:
        n = EX.run(equity=1000, quiet=True, link=lk2, now_ms=now)
        check("ستاپ زنده به سفارش فیوچرز تبدیل شد", n == 1, str(n))
        sent = json.loads(EX.OUT.read_text())["sent"]
        check("سایز از ریسک ۲٪ آمد و زیر سقف کانال ماند",
              sent[0]["notional_usd"] <= LINK.EXEC_MAX_NOTIONAL_USD,
              str(sent[0]))
        check("ضدتکرار: اجرای دوم سفارش تازه نمی‌سازد",
              EX.run(equity=1000, quiet=True, link=lk2, now_ms=now + 1000) == 0)
        # بعد از کول‌داون: ستاپ هم باید تازه باشد، وگرنه دروازهٔ تازگی
        # (به‌درستی) ردش می‌کند — پس ستاپ را با زمان جدید بازنویسی می‌کنیم.
        later = now + 950_000
        (tmp / "signals" / "scalp.json").write_text(json.dumps(
            {"generated": later,
             "live_setups": [good_setup(later, leverage=15)]},
            ensure_ascii=False))
        check("بعد از کول‌داون با ستاپ تازه دوباره مجاز است",
              EX.run(equity=1000, quiet=True, link=lk2, now_ms=later) == 1)
    finally:
        EX.ROOT, EX.STATE, EX.OUT, LINK.DOWN = old
        os.environ.pop("LIAM9_LINK_SECRET", None)

    # بدون کلید امضا، هیچ سفارشی فرستاده نمی‌شود
    EX.ROOT, EX.STATE, EX.OUT = tmp, tmp / "s2.json", tmp / "o2.json"
    LINK.DOWN = tmp / "c2.json"
    try:
        n0 = EX.run(equity=1000, quiet=True,
                    link=LINK.Link(role="t3", up=up, down=LINK.DOWN,
                                   remote=False), now_ms=now)
        check("بدون کلید امضا سفارش فرستاده نمی‌شود", n0 == 0)
    finally:
        EX.ROOT, EX.STATE, EX.OUT, LINK.DOWN = old

    # ── گزارش روزانه ─────────────────────────────────────────────────
    d = DR.build(days=1)
    check("گزارش روزانه ساخته می‌شود و بخش‌های لازم را دارد",
          all(k in d for k in ("signal_grade", "desks", "experience",
                               "live_link", "exec_bridge")), str(list(d)))
    txt = DR.render(d)
    check("متن گزارش فارسی و شامل تجربه است",
          "لیام تریدر ۹" in txt and ("تجربه" in txt or d["experience"]["used"]["n"] == 0))

    print(f"\n✓ همهٔ {OK} آزمون پل اجرا و گزارش روزانه گذشت")


if __name__ == "__main__":
    run()
