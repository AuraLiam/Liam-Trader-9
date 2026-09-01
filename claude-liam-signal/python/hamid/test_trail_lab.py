"""پاسبان آزمایشگاه تریل — یک بازپخشِ دروغ‌گو، بدتر از بازپخش‌نداشتن است.

این ماژول قرار است بگوید «کدام نردبان تریل بهتر بود». اگر خودش سوگیری
داشته باشد، ما را با اطمینان به قاعدهٔ اشتباه می‌برد. پنج راهِ خرابی:

۱. **بازپخش با تولید فرق کند.** اگر `replay_bars` همان نردبانِ
   `paper._settle_one` را بازتولید نکند، «قاعدهٔ فعلی» که با آن مقایسه
   می‌کنیم اصلاً قاعدهٔ فعلی نیست و کلِ اختلاف‌ها بی‌معنی است.
۲. **خوش‌بینیِ درون-کندلی.** اگر استاپ و تارگت در یک کندل بخورند و ما
   تارگت را برداریم، هر قاعده‌ای بهتر از واقعیت به نظر می‌رسد.
۳. **سوگیریِ دونقطه‌ای اعلام نشود.** اندازه‌گیریِ ۱ سپتامبر نشان داد
   بازپخشِ دونقطه‌ای تریلِ تنگ را سیستماتیک بالا می‌برد. اگر ماژول این
   را پنهان کند، رتبه‌بندی‌اش تبلیغ است نه سنجش.
۴. **نامسلح = ضرر فرض شود.** نسخهٔ اول همین را داشت: قاعده‌ای که تریل
   نگذاشته بود، ‎−۱R می‌گرفت حتی اگر معامله در سود بسته بود — پایهٔ
   «بی‌تریل» مصنوعی خراب می‌شد و هر تریلی برنده به نظر می‌رسید.
۵. **تریل به عقب برگردد.** استاپِ تریل فقط در جهت سود می‌رود (قانون
   تریل). اگر برگردد، ضررِ ناممکن می‌سازیم.

اجرا: `python3 -m hamid.test_trail_lab`
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
sys.path.insert(0, str(PY))

from hamid import trail_lab as T                                # noqa: E402

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


def trade(direction="LONG", entry=100.0, risk=1.0, rr=3.0, fee=0.05):
    sgn = 1 if direction == "LONG" else -1
    return {"sym": "TEST", "dir": direction, "entry": entry,
            "sl": entry - sgn * risk, "tp1": entry + sgn * rr * risk,
            "_fee_r": fee, "R": 0.0,
            "why": {"mfe": 0.0, "mae": 0.0, "mfe_bar": 1, "mae_bar": 1}}


def bars(r, path):
    """path = فهرست (high_R, low_R) نسبت به ورود، بر حسب R."""
    sgn = 1 if r["dir"] == "LONG" else -1
    risk = abs(r["entry"] - r["sl"])
    out = []
    for i, (hi, lo) in enumerate(path):
        a, b = r["entry"] + sgn * hi * risk, r["entry"] + sgn * lo * risk
        out.append({"t": i, "o": r["entry"], "c": b,
                    "h": max(a, b), "l": min(a, b)})
    return out


def run():
    # ── ۱) بازپخش باید نردبانِ تولید را مو به مو بسازد ──────────────────
    # ⅓ مسیر تارگت ۳R یعنی ‎+۱R → استاپ می‌رود روی کارمزد (۰.۰۵R).
    r = trade()
    got = T.replay_bars(r, T.RULES[T.BASE], bars(r, [(1.0, 0.0), (0.2, -0.9)]))
    check("⅓ مسیر → استاپ روی سربه‌سرِ کارمزددار (نه ورود، نه استاپِ اول)",
          got == (0.05, "تریل"), str(got))
    # ⅔ یعنی ‎+۲R → استاپ می‌رود روی ⅓ مسیر = ‎+۱R
    got = T.replay_bars(r, T.RULES[T.BASE], bars(r, [(2.0, 0.0), (1.5, 0.5)]))
    check("⅔ مسیر → استاپ روی ⅓ مسیر", got == (1.0, "تریل"), str(got))
    # زیر ⅓ اصلاً مسلح نمی‌شود
    got = T.replay_bars(r, T.RULES[T.BASE], bars(r, [(0.5, 0.0), (0.4, -1.2)]))
    check("زیر ⅓ مسلح نمی‌شود → استاپِ کاملِ ‎−۱R",
          got == (-1.0, "استاپ"), str(got))
    got = T.replay_bars(r, T.RULES[T.BASE], bars(r, [(3.0, 0.0)]))
    check("رسیدن به تارگت، تارگت ثبت می‌شود", got == (3.0, "تارگت"), str(got))

    # ── ۲) محافظه‌کاری: تریل از کندلِ قبلی، و استاپ بر تارگت مقدم ────────
    got = T.replay_bars(r, T.RULES[T.BASE], bars(r, [(1.0, -1.2)]))
    check("در همان کندلی که قله ساخت، تریل هنوز مسلح نیست (بدون "
          "خوش‌بینی درون-کندلی)", got == (-1.0, "استاپ"), str(got))
    got = T.replay_bars(r, T.RULES[T.BASE], bars(r, [(3.0, -1.5)]))
    check("برخورد هم‌زمان استاپ و تارگت → استاپ برنده",
          got == (-1.0, "استاپ"), str(got))

    # ── ۳) شورت قرینه است ───────────────────────────────────────────────
    s = trade("SHORT")
    got = T.replay_bars(s, T.RULES[T.BASE], bars(s, [(2.0, 0.0), (1.5, 0.5)]))
    check("شورت دقیقاً قرینهٔ لانگ است", got == (1.0, "تریل"), str(got))

    # ── ۴) تریل هرگز به عقب برنمی‌گردد ──────────────────────────────────
    got = T.replay_bars(r, T.RULES["نگه‌داشت ۸۰٪ قله"],
                        bars(r, [(2.0, 0.0), (0.1, 0.05), (0.1, -1.5)]))
    check("بعد از قله، استاپِ تریل پایین‌تر نمی‌آید (سود قفل می‌ماند)",
          got is not None and got[0] > 0, str(got))

    # ── ۵) نامسلح ≠ ضرر (عیبِ نسخهٔ اول) ────────────────────────────────
    p = trade()
    p["why"] = {"mfe": 0.4, "mae": -0.3, "mfe_bar": 2, "mae_bar": 3}
    p["R"] = 0.4
    got = T.replay_points(p, T.RULES["بی‌تریل"])
    check("قاعدهٔ بی‌تریل روی معاملهٔ سودده ‎−۱R نمی‌دهد",
          got is not None and got[0] > 0, str(got))
    n = trade()
    n["why"] = {"mfe": 0.2, "mae": -1.0, "mfe_bar": 1, "mae_bar": 2}
    got = T.replay_points(n, T.RULES["بی‌تریل"])
    check("ولی افتِ ‎−۱R همچنان استاپ است", got == (-1.0, "استاپ"), str(got))

    # ── ۶) سوگیریِ دونقطه‌ای: اعلام‌شده و اندازه‌گرفته ───────────────────
    b = T.bias_demo()
    check("ماژول سوگیریِ خودش را عددی اثبات می‌کند (نه ادعا)",
          b["gap"] is not None and b["gap"] > 0.1,
          f"gap={b['gap']} — اگر صفر شد یعنی نمونهٔ اثبات دیگر کار نمی‌کند")
    check("و جهتش همان است: دونقطه‌ای تریلِ تنگ را بالاتر می‌زند",
          b["points"][0] > b["bars"][0], str(b))

    sp = T.study("points", rows=[])
    check("خروجیِ دونقطه‌ای صریحاً «برای رتبه‌بندی معتبر نیست» می‌گوید",
          "معتبر نیست" in sp["boundary"], sp["boundary"][:80])
    check("و حالتش روی خروجی نوشته می‌شود", sp["mode"] == "points")

    # ── ۷) قاعده‌ها واقعاً از هم فرق دارند ──────────────────────────────
    path = bars(r, [(1.2, 0.0), (1.9, 1.0), (1.2, 0.9), (1.0, -1.2)])
    outs = {k: T.replay_bars(r, f, path) for k, f in T.RULES.items()}
    check("قاعده‌های مختلف روی یک معامله نتیجهٔ یکسان نمی‌دهند",
          len({v[0] for v in outs.values() if v}) > 2, str(outs))
    check("بی‌تریل در این مسیر به استاپِ کامل می‌خورد",
          outs["بی‌تریل"] == (-1.0, "استاپ"), str(outs["بی‌تریل"]))
    check("نگه‌داشت ۸۰٪ همان‌جا سود قفل کرده",
          outs["نگه‌داشت ۸۰٪ قله"][0] > 0.5, str(outs["نگه‌داشت ۸۰٪ قله"]))

    # ── ۸) هندسه از خودِ معامله می‌آید، نه فرضِ ثابت ─────────────────────
    w = trade(rr=1.5)
    got = T.replay_bars(w, T.RULES[T.BASE], bars(w, [(0.6, 0.0), (0.2, -0.9)]))
    check("تارگت ۱.۵R: ⅓ آن ‎+۰.۵R است، پس در ‎+۰.۶R مسلح می‌شود",
          got == (0.05, "تریل"), str(got))
    check("و rr از tp1/sl خوانده می‌شود نه عددِ ثابت",
          T.geometry(w)[1] == 1.5 and T.geometry(trade(rr=3.0))[1] == 3.0)
    check("ریسکِ صفر معامله را کنار می‌گذارد، نه این‌که تقسیم بر صفر کند",
          T.geometry({"entry": 1.0, "sl": 1.0, "tp1": 2.0}) is None)

    # ── ۹) مرزهای قانون ۰۵ و ۰۷ ────────────────────────────────────────
    src = (PY / "hamid" / "trail_lab.py").read_text(encoding="utf-8")
    check("آزمایشگاه به تلگرام پیام نمی‌دهد (قانون ۰۷)",
          "send_text" not in src and "alert_gate" not in src)
    check("سیگنال صادر یا وتو نمی‌کند",
          "send_signals" not in src and "veto" not in src)
    check("فقط خروجی خودش را می‌نویسد (قانون ۰۵)",
          src.count("write_text") == 1 and "trail-lab.json" in src)
    check("دفترِ پیپر را دست نمی‌زند (فقط می‌خواند)",
          "paper.mark" not in src and "closed.jsonl" not in src)
    check("مرز صادقانه به قانون ۰۳ ارجاع می‌دهد",
          "قانون ۰۳" in T.study("points", rows=[])["boundary"])
    check("سوگیریِ انتخاب هم صریح گفته شده",
          "سوگیریِ انتخاب" in T.study("points", rows=[])["boundary"])

    # ── ۱۰) شمارش‌ها با فهرست می‌خوانند ─────────────────────────────────
    st = T.study("points", rows=[trade(), trade("SHORT")])
    check("n هر قاعده از تعداد معامله‌های واقعی می‌آید",
          all(v["n"] <= 2 for v in st["rules"].values()), str(st["rules"]))
    check("قاعدهٔ پایه در جدول اختلاف با خودش نیست",
          T.BASE not in st["vs_current"])
    check("همهٔ قاعده‌ها ردیف اختلاف دارند",
          set(st["vs_current"]) == set(T.RULES) - {T.BASE})

    print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(run())
