"""آزمون موتور شوک، خط زندهٔ امن، و میز شوک — قانون تازهٔ حمید (۱۹ اوت).

قانون تازه بدون محافظ تحویل نمی‌شود. مهم‌ترین چیزهایی که این‌جا قفل
می‌شوند: «۱۰۰ درصد یعنی صد درصد»، اهرم هرگز از محافظ لیکویید رد نشود،
و خط زنده هیچ فرمانی را بدون امضا/تازگی/مجوز اجرا نکند.
"""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import liam9_shock as SH                                     # noqa: E402
import liam9_link as LINK                                    # noqa: E402
from hamid import shock_desk as DESK                         # noqa: E402

OK = 0


def check(name, cond, extra=""):
    global OK
    if not cond:
        print(f"  ✗ {name} {extra}")
        raise SystemExit(1)
    OK += 1
    print(f"  ✓ {name}")


def calm(n=80, px=100.0, vol=100.0, tf_ms=300_000, t0=0, rng_pct=0.2):
    """بستر آرام. rng_pct دامنهٔ کندل‌های عادی است — نسبت ایمپالس به همین
    ATR سنجیده می‌شود، پس برای تایم پایین باید کوچک‌تر باشد."""
    out = []
    for i in range(n):
        p0 = px + (i % 3) * px * rng_pct / 100 / 10
        out.append({"t": t0 + i * tf_ms, "o": p0,
                    "h": p0 * (1 + rng_pct / 100),
                    "l": p0 * (1 - rng_pct / 100), "c": p0, "v": vol})
    return out


def with_impulse(up=True, vol=700.0, pct=1.58, rng_pct=0.2):
    """ایمپالس با بزرگی دلخواه — هر تایم کف مطلق خودش را دارد (shock_min_pct)،
    پس اندازهٔ ایمپالس آزمون باید با تایم بزرگ شود، وگرنه موتور درست ردش
    می‌کند و آزمون به‌غلط قرمز می‌شود."""
    cd = calm(rng_pct=rng_pct)
    t = len(cd) * 300_000
    if up:
        close = 99.92 * (1 + pct / 100)
        cd.append({"t": t, "o": 100.05, "h": 100.08, "l": 99.90,
                   "c": 99.92, "v": 90})                     # OB مخالف
        cd.append({"t": t + 300_000, "o": 99.92, "h": close * 1.001,
                   "l": 99.90, "c": close, "v": vol})        # ایمپالس
    else:
        cd.append({"t": t, "o": 99.95, "h": 100.10, "l": 99.92,
                   "c": 100.08, "v": 90})
        cd.append({"t": t + 300_000, "o": 100.08, "h": 100.10, "l": 98.40,
                   "c": 98.50, "v": vol})
    return cd


def run():
    SH._selftest()
    LINK._selftest()

    # ── قانون ۱: شوک روی هر تایم‌فریم شناسایی شود ─────────────────────
    for tf in SH.TFS:
        pct = SH.P["shock_min_pct"][tf] * 1.6
        cd = with_impulse(pct=pct, rng_pct=pct / 8)
        for k in cd:
            k["t"] = k["t"] // 300_000 * SH.TF_MS[tf]
        s = SH.detect_shock(cd, tf)
        check(f"شوک روی تایم {tf} دیده می‌شود", s is not None and s["dir"] == "PUMP")
    check("بازار آرام شوک ندارد", SH.detect_shock(calm(120), "5m") is None)
    d = SH.detect_shock(with_impulse(up=False), "5m")
    check("دامپ هم شناسایی می‌شود", d is not None and d["dir"] == "DUMP", str(d))

    # ── قانون ۲: «۱۰۰ درصد» یعنی هر شش تأیید ──────────────────────────
    cd = with_impulse()
    s = SH.detect_shock(cd, "5m")
    vc = SH.volume_confirmation(cd, s)
    check("تأیید حجمی کامل = هر شش شرط", vc["full"] and vc["score"] == 6, str(vc))
    for spoil, label in (
            (lambda c: c[-1].update({"v": 150}), "حجم کم"),
            (lambda c: c[-1].update({"h": 103.0}), "ویک مخالف بزرگ"),
            (lambda c: c[-1].update({"c": 100.2}), "کلوز وسط دامنه")):
        c2 = [dict(k) for k in cd]
        spoil(c2)
        s2 = SH.detect_shock(c2, "5m")
        vc2 = SH.volume_confirmation(c2, s2) if s2 else {"full": False,
                                                         "score": 0}
        check(f"با «{label}» تأیید ۱۰۰٪ باطل می‌شود", not vc2["full"], str(vc2))
        r2 = SH.decide("BTCUSDT", c2, "5m")
        check(f"با «{label}» اهرم ۱۵ صادر نمی‌شود",
              r2.get("mode") != "PUMP_CHASE"
              and r2.get("leverage") != SH.P["lev_pump_chase"], str(r2)[:150])

    # ── قانون ۳: اهرم‌ها دقیقاً همان چیزی که حمید گفت ──────────────────
    r = SH.decide("BTCUSDT", cd, "5m", equity=1000)
    check("شکار پامپ = اهرم ۱۵", r["mode"] == "PUMP_CHASE"
          and r["leverage"] == 15, str(r)[:160])
    check("شکار پامپ: قرارداد اجرا کامل (ایزوله + SL/TP اجباری) — "
          "همان محافظی که سوینگ/۱ساعته دارند، این‌جا هم قفل می‌شود",
          r.get("margin_mode") == "isolated" and r.get("sl_tp_mandatory") is True
          and r.get("stop_loss") and r.get("take_profit")
          and r["stop_loss"] == r["sl"] and r["take_profit"] == r["tp1"],
          str(r)[:200])
    cd3 = [dict(k) for k in cd]
    for i in range(1, 6):
        cd3.append({"t": cd[-1]["t"] + i * 300_000, "o": 101.5 - i * 0.22,
                    "h": 101.6 - i * 0.22, "l": 101.3 - i * 0.22,
                    "c": 101.4 - i * 0.22, "v": 120})
    r3 = SH.decide("BTCUSDT", cd3, "5m", equity=1000)
    check("دنبال‌کردن شوک = اهرم ۵ یا ۶",
          r3["mode"] == "SHOCK_FOLLOW" and r3["leverage"] in (5, 6), str(r3)[:160])
    check("ورود روی اردر بلاک است، نه وسط ایمپالس",
          r3["ob"] is not None and r3["entry"] <= cd[-1]["h"], str(r3["ob"]))
    check("دنبال‌کردن شوک: قرارداد اجرا کامل (ایزوله + SL/TP اجباری)",
          r3.get("margin_mode") == "isolated" and r3.get("sl_tp_mandatory") is True
          and r3.get("stop_loss") and r3.get("take_profit")
          and r3["stop_loss"] == r3["sl"] and r3["take_profit"] == r3["tp1"],
          str(r3)[:200])

    # محافظ لیکویید و سقف داشبورد، در همهٔ حالت‌ها
    for st in (0.4, 0.8, 1.5, 2.5, 3.0, 4.0):
        for mode in ("SHOCK_FOLLOW", "PUMP_CHASE"):
            lv = SH.leverage_for(mode, st)
            check(f"اهرم {mode} با استاپ {st}٪ داخل محافظ",
                  lv is None or (lv <= int(50.0 / st)
                                 and lv <= SH.P["max_leverage_cap"]),
                  f"{lv}")

    # سایز از ریسک ۲٪ می‌آید نه از اهرم
    s5 = SH.size_for(1000, 1.0, 5)
    s15 = SH.size_for(1000, 1.0, 15)
    check("ضرر استاپ مستقل از اهرم همان ۲٪ می‌ماند",
          s5["risk_usd"] == s15["risk_usd"] == 20.0
          and s5["notional_usd"] == s15["notional_usd"], f"{s5} {s15}")
    check("اهرم بالاتر فقط مارجین را کم می‌کند",
          s15["margin_usd"] < s5["margin_usd"])

    # ── قانون ۴: نماد بدون همراهی، فقط چون بیت‌کوین شوک دارد وارد نشود ──
    quiet_alt = calm(120)
    r4 = SH.decide("ALTUSDT", quiet_alt, "5m", btc_shock=s)
    check("شوک بیت‌کوین به‌تنهایی مجوز ورود آلت نیست",
          r4["action"] == "NO_SIGNAL" and "همراهی" in r4["why"], str(r4)[:140])

    # ── خط زنده: امنیت ─────────────────────────────────────────────────
    tmp = Path(tempfile.mkdtemp())
    up, down = tmp / "up.json", tmp / "down.json"
    os.environ["LIAM9_LINK_SECRET"] = "unit-test-key"
    lk = LINK.Link(role="test", up=up, down=down, remote=False)
    lk.event("SIGNAL", {"symbol": "BTCUSDT", "mode": "PUMP_CHASE"})
    check("رویداد روی خط زنده ثبت شد",
          json.loads(up.read_text())["events"][-1]["kind"] == "SIGNAL")
    check("سکرت هرگز در فایل خط زنده نوشته نمی‌شود",
          "unit-test-key" not in up.read_text())

    params = dict(SH.P)
    LINK.push_command(LINK.make_command("set_param", 1, key="shock_vol_mult",
                                        value=3.0), down)
    lk.apply(lk.pull(), params=params)
    check("فرمان امضاشده پارامتر را عوض می‌کند", params["shock_vol_mult"] == 3.0)
    check("پارامترهای تولید دست‌نخورده ماندند", SH.P["shock_vol_mult"] == 2.0)

    for bad_key in ("lev_pump_chase", "max_leverage_cap", "liq_guard_ratio"):
        LINK.push_command(LINK.make_command("set_param", LINK.next_seq(down),
                                            key=bad_key, value=99), down)
        res = lk.apply(lk.pull(), params=params)
        check(f"اهرم/محافظ «{bad_key}» از راه دور قابل تغییر نیست",
              res and not res[0]["ok"], str(res))

    # ── میز شوک: لوله‌کشی کامل در sandbox ─────────────────────────────
    from hamid import paper
    old = (paper.CLOSED, DESK.STATE, DESK.OUT)
    paper.CLOSED = tmp / "closed.jsonl"
    DESK.STATE, DESK.OUT = tmp / "state.json", tmp / "shock.json"
    long_cd = with_impulse() + [
        {"t": (82 + i) * 300_000, "o": 101.5 + i * 0.05,
         "h": 101.6 + i * 0.05, "l": 101.4 + i * 0.05,
         "c": 101.55 + i * 0.05, "v": 120} for i in range(1, 60)]
    import sources
    old_k = sources.klines
    sources.klines = lambda sym, tf, n, **kw: [
        [k["t"], k["o"], k["h"], k["l"], k["c"], k["v"]] for k in long_cd]
    lk2 = LINK.Link(role="desk-test", up=up, down=down, remote=False)
    try:
        n = DESK.run(symbols=["XUSDT"], quiet=True, link=lk2)
        rows = [json.loads(x) for x in paper.CLOSED.read_text().splitlines()
                if x.strip()]
        check("میز شوک معامله ساخت و در دفتر جدا نشست",
              n >= 1 and all((r.get("why") or {}).get("stage") == "shock"
                             for r in rows), f"n={n}")
        check("هر ردیف ردپای قابل‌سنجش دارد (حالت، اهرم، امتیاز حجم)",
              all((r["why"].get("mode") and r["why"].get("lev")
                   and r["why"].get("vol_score")) for r in rows),
              str(rows[:1])[:200])
        j = json.loads(DESK.OUT.read_text())
        check("عکس‌فوری پنل با تفکیک حالت نوشته شد",
              j["book"]["n"] >= 1 and j["book"]["by_mode"], str(j["book"]))
        check("ضدتکرار: اجرای دوم معاملهٔ تازه نمی‌سازد",
              DESK.run(symbols=["XUSDT"], quiet=True, link=lk2) == 0)
        # فرمان توقف باید واقعاً متوقف کند
        LINK.push_command(LINK.make_command("pause", LINK.next_seq(down)), down)
        lk3 = LINK.Link(role="desk-test2", up=up, down=down, remote=False)
        check("فرمان امضاشدهٔ توقف میز را می‌خواباند",
              DESK.run(symbols=["XUSDT"], quiet=True, link=lk3) == 0
              and lk3.paused)
    finally:
        paper.CLOSED, DESK.STATE, DESK.OUT = old
        sources.klines = old_k
        os.environ.pop("LIAM9_LINK_SECRET", None)

    print(f"\n✓ همهٔ {OK} آزمون قانون شوک و خط زنده گذشت")


if __name__ == "__main__":
    run()
