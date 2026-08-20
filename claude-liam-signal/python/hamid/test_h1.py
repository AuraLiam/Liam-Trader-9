"""آزمون موتور ۱ ساعته و بک‌تستش — قرارداد داشبورد، ریسک، بدون نگاه به آینده."""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import liam9_h1_strategy as H1                              # noqa: E402
from hamid import h1_backtest as BT                         # noqa: E402

OK = 0


def check(name, cond, extra=""):
    global OK
    if not cond:
        print(f"  ✗ {name} {extra}")
        raise SystemExit(1)
    OK += 1
    print(f"  ✓ {name}")


def mk(path, tf_ms=3600000, t0=0):
    return [{"t": t0 + i * tf_ms, "o": p, "h": p * 1.004, "l": p * 0.996,
             "c": p} for i, p in enumerate(path)]


def run():
    H1._selftest()

    # ۱) قرارداد بارگذار داشبورد
    m = H1.Liam9H1Strategy.meta
    check("کلاس با meta و پروفایل ریسک", isinstance(m, dict)
          and m["risk_profile"]["max_leverage"] == 20
          and m["timeframes"] == ["4h", "1h"], str(m)[:120])
    for ep in ("generate_signal", "on_bar", "run", "manage_position"):
        check(f"نقطهٔ ورود {ep}", callable(getattr(H1.Liam9H1Strategy, ep, None)))

    # ۲) استاپ همیشه با اهرم ۲۰ سازگار است (< نصف فاصلهٔ لیکویید ۵٪)
    check("سقف استاپ زیر نصف فاصلهٔ لیکویید اهرم ۲۰",
          H1.P["max_stop_pct"] <= 100 * H1.RISK["liq_guard_ratio"]
          / H1.RISK["max_leverage"] * 1.0 + 1e-9,
          f"{H1.P['max_stop_pct']} vs {100*0.5/20}")

    # ۳) ریاضی سقف روزانه: با ۲٪ ریسک، بعد از ۲ باخت کامل هشدار و بعد توقف
    b = H1.RiskBook(1000, {"risk_per_trade_pct": 2.0})
    b.on_open(); b.on_close(-1.0)
    ok, info = b.approve(1.0)
    check("بعد از یک باخت هنوز اجازه هست", ok)
    b.on_open(); b.on_close(-1.0)
    ok2, info2 = b.approve(1.0)
    check("نزدیک سقف روزانه هشدار می‌دهد", ok2 and info2["warn"], str(info2))
    b.on_open(); b.on_close(-1.0)
    check("بعد از سقف ۵٪ توقف خودکار", not b.approve(1.0)[0])
    b1 = H1.RiskBook(1000, {"risk_per_trade_pct": 1.0})
    for _ in range(4):
        b1.on_open(); b1.on_close(-1.0)
    check("با ریسک ۱٪ چهار باخت هنوز اجازه می‌دهد", b1.approve(1.0)[0])

    # ۴) سایز: ریسک ۲٪ روی استاپ ۱٪ = نوشنال ۲ برابر سرمایه
    ok3, i3 = H1.RiskBook(500).approve(1.0)
    check("محاسبهٔ سایز درست است",
          ok3 and abs(i3["notional_usd"] - 1000.0) < 1e-6
          and abs(i3["risk_usd"] - 10.0) < 1e-6, str(i3))

    # ۵) بک‌تست: بدترین‌حالتِ درون‌کندلی و ضدهم‌پوشانی.
    #
    # نکتهٔ داده (اشتباهی که همین‌جا گرفته شد): میدان ۴س باید **قبل از**
    # شروع پنجرهٔ ۱س هم تاریخ داشته باشد، وگرنه replay در هر گام
    # `len(c4) < 220` می‌بیند، هیچ تصمیمی گرفته نمی‌شود و آزمون‌ها روی
    # لیست خالی «الکی سبز» می‌شوند. پس ۴س از خیلی عقب‌تر ساخته می‌شود.
    H4 = 14400000
    c4 = mk([100 + i * 1.4 for i in range(400)], tf_ms=H4)
    t1_start = c4[-100]["t"]                # ۱س فقط روی انتهای بازهٔ ۴س
    up = [c4[-100]["c"] + i * 0.35 for i in range(260)]
    pull = up + [up[-1] - i * 1.2 for i in range(1, 9)]     # پولبک تا اندیس ۲۶۸
    fwd = [pull[-1] * (1 + 0.004 * i) for i in range(1, 80)]  # آیندهٔ نتیجه
    c1 = mk(pull + fwd, t0=t1_start)
    sig_i = len(pull) - 1                   # کندل تأیید: بسته نزدیک کف
    c1[sig_i]["l"] = c1[sig_i]["c"] * 0.988
    c1[sig_i]["c"] = c1[sig_i]["c"] * 0.9895
    books = BT.replay_symbol("TESTUSDT", c1, c4, btc1h=c1, btc4h=c4)
    trs = books["base"]
    check("بک‌تست معاملهٔ واقعی ساخت (نه لیست خالی)", len(trs) >= 1, str(len(trs)))
    check("هر معامله R خالص دارد و از R ناخالص بیشتر نیست",
          all("R_net" in t and t["R_net"] <= t["R"] for t in trs), str(trs[:1]))
    opens = [t["opened"] for t in trs]
    check("معامله‌ها هم‌پوشانی ندارند", len(opens) == len(set(opens)))

    # ۵ب) واریانت‌ها: ورودها باید یکی باشند تا مقایسه منصفانه بماند
    mgmt = {v["key"]: books[v["key"]] for v in BT.VARIANTS}
    check("همهٔ واریانت‌های خروج روی همان ورودها سنجیده می‌شوند",
          all(len(v) == len(trs) for v in mgmt.values())
          and all([t["opened"] for t in v] == opens for v in mgmt.values()),
          str({k: len(v) for k, v in mgmt.items()}))
    # فیلترهای ورود زیرمجموعهٔ پایه‌اند — نه بیشتر، نه معاملهٔ ساختگی
    ent = {f["key"]: books["entry:" + f["key"]] for f in BT.ENTRY_FILTERS}
    check("فیلترهای ورود زیرمجموعهٔ معاملات پایه‌اند",
          len(ent["all"]) == len(trs)
          and all(len(v) <= len(trs) for v in ent.values())
          and all(set(t["opened"] for t in v) <= set(opens)
                  for v in ent.values()),
          str({k: len(v) for k, v in ent.items()}))
    check("فیلتر «فقط شورت» هیچ لانگی ندارد",
          all(t["dir"] == "SHORT" for t in ent["short_only"]))
    check("فیلتر ریکلیم واقعاً کندل تریگر را می‌خواهد",
          BT._has_reclaim("LONG", [{"h": 10, "l": 9, "c": 9.5},
                                   {"h": 11, "l": 10, "c": 10.5}]) is True
          and BT._has_reclaim("LONG", [{"h": 10, "l": 9, "c": 9.5},
                                       {"h": 10, "l": 9, "c": 9.8}]) is False)
    nt = books["no_trail"]
    check("واریانت بدون تریل هیچ خروج trail ندارد",
          all(t["outcome"] != "trail" for t in nt), str(nt[:1]))
    check("واریانت تارگت نزدیک‌تر زودتر یا هم‌زمان بسته می‌شود",
          all(a["bars"] <= b["bars"] for a, b in
              zip(books["tp15_no_trail"], nt)),
          str([(a['bars'], b['bars']) for a, b in
               zip(books['tp15_no_trail'], nt)][:3]))

    # ۶) بدون نگاه به آینده: تصمیم فقط با کندل تا همان لحظه
    seen = {}
    old = H1.analyze

    def spy(sym, c4h, c1h, **kw):
        seen["last_t"] = c1h[-1]["t"]
        seen["max_t"] = max(k["t"] for k in c1h)
        return old(sym, c4h, c1h, **kw)
    H1.analyze = spy
    try:
        BT.replay_symbol("TESTUSDT", c1, c4, btc1h=c1, btc4h=c4)
    finally:
        H1.analyze = old
    check("تصمیم فقط با کندل‌های گذشته گرفته می‌شود",
          seen and seen["last_t"] == seen["max_t"])

    # ۷) منحنی سرمایه سقف روزانه را واقعاً اعمال می‌کند
    day = int(time.time() * 1000)
    losses = [{"opened": day + i * 60000, "R_net": -1.0} for i in range(5)]
    e2 = BT.equity_curve(losses, 2.0)
    e1 = BT.equity_curve(losses, 1.0)
    check("سقف روزانه با ریسک ۲٪ زودتر جلوی معامله را می‌گیرد",
          e2["blocked_by_daily_cap"] > e1["blocked_by_daily_cap"],
          f"{e2} {e1}")

    # ۷ب) خودِ run() هم باید اجرا شود، نه فقط replay_symbol.
    #
    # درس ۱۹ اوت: تست کامل سبز بود ولی run() روی رانر با
    # KeyError: 'entry:all' مرد، چون کلیدهای فیلتر ورود در books ساخته
    # نشده بودند. هیچ تستی run() را صدا نمی‌زد، پس عیب دو بار به تولید رفت.
    import sources
    old_k, old_top = sources.klines, getattr(sources, "top_symbols", None)
    tmp = Path(BT.OUT.parent) / "h1-backtest-test.json"
    old_out = BT.OUT
    c4x = mk([100 + i * 1.4 for i in range(400)], tf_ms=H4)
    # ≥۴۰۰ کندل لازم است: run() سری کوتاه‌تر را (درست) رد می‌کند
    up2 = [c4x[-100]["c"] + i * 0.35 for i in range(320)]
    pull2 = up2 + [up2[-1] - i * 1.2 for i in range(1, 9)]
    c1x = mk(pull2 + [pull2[-1] * (1 + 0.004 * i) for i in range(1, 80)],
             t0=c4x[-100]["t"])
    c1x[len(pull2) - 1]["l"] = c1x[len(pull2) - 1]["c"] * 0.988
    c1x[len(pull2) - 1]["c"] = c1x[len(pull2) - 1]["c"] * 0.9895

    def fake_klines(sym, tf, n, **kw):
        cd = c4x if tf == "4h" else c1x
        return [[k["t"], k["o"], k["h"], k["l"], k["c"], 1.0] for k in cd]
    sources.klines = fake_klines
    sources.top_symbols = lambda n: ["TESTUSDT"]
    BT.OUT = tmp
    try:
        res = BT.run(symbols=1, bars=400, quiet=True)
        check("run() تا آخر می‌رود و گزارش کامل می‌سازد",
              res["overall"]["n"] >= 1 and len(res["variants"]) == len(BT.VARIANTS)
              and len(res["entry_filters"]) == len(BT.ENTRY_FILTERS),
              str(res.get("overall")))
        check("گزارش روی دیسک نوشته و JSON معتبر است",
              json.loads(tmp.read_text())["engine"] == H1.P["version"])
    finally:
        sources.klines = old_k
        if old_top is not None:
            sources.top_symbols = old_top
        BT.OUT = old_out
        tmp.unlink(missing_ok=True)

    # ۸) CI: زیر نمونهٔ کافی حکم نمی‌دهد
    check("CI با نمونهٔ کم None است", BT.boot_ci([0.1, 0.2]) == (None, None))
    lo, hi = BT.boot_ci([1.0] * 40)
    check("CI با نمونهٔ کافی بازه می‌دهد", lo is not None and lo <= 1.0 <= hi)

    print(f"\n✓ همهٔ {OK} آزمون موتور ۱ ساعته گذشت")


if __name__ == "__main__":
    run()
