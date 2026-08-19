"""آزمون موتور ۱ ساعته و بک‌تستش — قرارداد داشبورد، ریسک، بدون نگاه به آینده."""
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
    books = BT.replay_symbol("TESTUSDT", c1, c4)
    trs = books["base"]
    check("بک‌تست معاملهٔ واقعی ساخت (نه لیست خالی)", len(trs) >= 1, str(len(trs)))
    check("هر معامله R خالص دارد و از R ناخالص بیشتر نیست",
          all("R_net" in t and t["R_net"] <= t["R"] for t in trs), str(trs[:1]))
    opens = [t["opened"] for t in trs]
    check("معامله‌ها هم‌پوشانی ندارند", len(opens) == len(set(opens)))

    # ۵ب) واریانت‌ها: ورودها باید یکی باشند تا مقایسه منصفانه بماند
    check("همهٔ واریانت‌ها روی همان ورودها سنجیده می‌شوند",
          all(len(v) == len(trs) for v in books.values())
          and all([t["opened"] for t in v] == opens for v in books.values()),
          str({k: len(v) for k, v in books.items()}))
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
        BT.replay_symbol("TESTUSDT", c1, c4)
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

    # ۸) CI: زیر نمونهٔ کافی حکم نمی‌دهد
    check("CI با نمونهٔ کم None است", BT.boot_ci([0.1, 0.2]) == (None, None))
    lo, hi = BT.boot_ci([1.0] * 40)
    check("CI با نمونهٔ کافی بازه می‌دهد", lo is not None and lo <= 1.0 <= hi)

    print(f"\n✓ همهٔ {OK} آزمون موتور ۱ ساعته گذشت")


if __name__ == "__main__":
    run()
