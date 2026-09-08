"""محافظِ نردبانِ ریزش — سیم‌کشی، ضدآینده، و مرزِ «برچسب است نه دروازه».

خودآزماییِ خودِ `hamid/stairs.py` هندسه را می‌سنجد. این فایل چیزِ دیگری
را می‌سنجد که آن‌جا **قابل سنجش نبود**: قراردادِ فراخوان.

چرا این تفکیک مهم است — درسِ ۸ سپتامبر: `stables._at` «نزدیک‌ترین» نقطه
را برمی‌داشت و می‌توانست تا ۸ دقیقه جلوتر باشد. تابع به‌تنهایی سالم به
نظر می‌رسید؛ عیب در این بود که چه چیزی به آن داده می‌شد. پس آزمونِ
ضدآیندهٔ واقعی باید **مسیرِ کامل** را برود: بازپخش → برچسب → دفتر.

اجرا: python3 -m hamid.test_stairs
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from hamid import stairs                                        # noqa: E402

OK = [0]
BAD = [0]


def chk(cond, msg):
    if cond:
        OK[0] += 1
    else:
        BAD[0] += 1
        print(f"  ✗ {msg}")


def _series(steps=18):
    """نردبانِ ریزشیِ بلند — به اندازه‌ای که بازپخش چند ورود بسازد.

    `trainer.replay_symbol` از کندلِ ۱۶۰ (warmup) شروع می‌کند، پس سریِ
    کوتاه هیچ معامله‌ای نمی‌سازد و آزمون بی‌اثر می‌شود — همان چیزی که
    بارِ اول اتفاق افتاد و `chk` گرفتش."""
    return stairs._ladder(steps=steps, start=200.0, leg=6.0, back=2.2, bars=7)


def test_module_selftest():
    """خودآزمایی ماژول باید سبز باشد — وگرنه بقیه بی‌معناست."""
    chk(stairs._selftest() == 0, "خودآزمایی hamid/stairs قرمز است")


def test_label_is_causal_through_trainer():
    """**ضدآینده، مسیر کامل**: برچسبِ روی هر معامله باید دقیقاً از
    `c15[:i+1]` بازتولید شود.

    این آزمونِ توخالی نیست: نردبان بعد از لحظهٔ ورود ادامه دارد، پس اگر
    trainer کلِ سری را به برچسب‌زن می‌داد، `stair_steps` عددِ بزرگ‌تری
    می‌شد و بازتولید نمی‌خواند. اثبات منفی‌اش پایین‌تر (`test_spy_bites`).
    """
    from hamid import trainer
    cd = _series()
    trades, _ = trainer.replay_symbol("TESTUSDT", cd, tf="15m")
    chk(len(trades) > 0, "بازپخش هیچ معامله‌ای نساخت — آزمون بی‌اثر می‌شود")
    tagged = 0
    for t in trades:
        w = t["why"]
        if "stair_dir" not in w:
            continue
        tagged += 1
        i = next(k for k, c in enumerate(cd) if c["t"] == t["opened"])
        want = stairs.label(cd[:i + 1], tf="15m", direction=t["dir"])
        got = {k: v for k, v in w.items() if k.startswith("stair_")}
        chk(got == want,
            f"برچسبِ معاملهٔ {t['opened']} از پنجرهٔ علّی بازتولید نشد:\n"
            f"      دفتر={got}\n      بازتولید={want}")
    chk(tagged > 0, "هیچ معامله‌ای برچسبِ نردبان نگرفت — سیم‌کشی قطع است")


def test_spy_bites():
    """اثبات منفی: اگر پنجرهٔ **کاملِ** آینده‌دار داده شود، برچسب فرق کند.

    بدون این، آزمون بالا می‌توانست همیشه سبز باشد و چیزی ثابت نکند.
    """
    cd = _series()
    i = len(cd) // 2
    causal = stairs.label(cd[:i + 1], tf="15m", direction="SHORT")
    future = stairs.label(cd, tf="15m", direction="SHORT")
    chk(causal != future,
        "پنجرهٔ علّی و پنجرهٔ آینده‌دار یکی درآمدند — آزمونِ ضدآینده بی‌اثر است")


def test_events_are_append_only_over_time():
    """**علّیت، به شکلِ قابل‌سنجش**: تاریخ بازنویسی نمی‌شود.

    اگر شمارشِ پله علّی باشد، رویدادهایی که تا کندلِ `cut1` ثبت شده‌اند
    باید **پیشوندِ** رویدادهای `cut2 > cut1` باشند — کندلِ تازه فقط
    می‌تواند رویدادِ تازه اضافه کند، نه رویدادِ دیروز را عوض کند.

    این جای آن آزمونِ قبلی نشست که `lag >= 2` می‌خواست. آن ادعا **غلط
    بود**: `lag` فاصله تا آخرین *رویدادِ ساختاری* است، و رویداد دقیقاً
    روی همان کندلی می‌افتد که سطح را می‌بندد — پس صفر بودنش درست است.
    چیزی که باید دو کندل عقب باشد **پیوت** است، نه رویداد؛ و آن در
    خودآزمایی ماژول (بررسی ۶) سنجیده می‌شود.
    """
    from hamid.microstructure import structure
    cd = _series()
    # برش‌ها زیر `BARS` نگه داشته می‌شوند تا پنجره کوتاه نشود و اندیس‌ها
    # جابه‌جا نشوند — وگرنه آزمون چیزِ دیگری را می‌سنجد.
    cuts = [c for c in range(80, min(len(cd), stairs.BARS) + 1, 10)]
    prev = None
    checked = 0
    for cut in cuts:
        st = structure(cd[:cut])
        evs = [(e["i"], e["kind"], e["dir"], round(e["level"], 8))
               for e in (st or {}).get("events", [])]
        if prev is not None and evs:
            chk(evs[:len(prev)] == prev,
                f"در برشِ {cut} تاریخِ رویدادها بازنویسی شد")
            checked += 1
        prev = evs or prev
    chk(checked >= 3, f"برش‌های کافی سنجیده نشد ({checked})")


def test_no_gate_behaviour_changed():
    """**مرز**: برچسب هیچ تصمیمی را عوض نکرده باشد.

    همان بازپخش، یک‌بار با برچسب‌زنِ سالم و یک‌بار با برچسب‌زنی که
    می‌ترکد. تعداد، جهت، ورود، استاپ و تارگتِ معامله‌ها باید **مو به مو**
    یکی باشند — یعنی `stairs` واقعاً فقط ناظر است، نه دروازه.
    """
    from hamid import trainer
    cd = _series()
    a, _ = trainer.replay_symbol("TESTUSDT", cd, tf="15m")

    def boom(*_a, **_k):
        raise RuntimeError("برچسب‌زن عمداً خراب")

    orig = stairs.label
    stairs.label = boom
    try:
        b, _ = trainer.replay_symbol("TESTUSDT", cd, tf="15m")
    finally:
        stairs.label = orig
    key = lambda t: (t["dir"], t["entry"], t["sl"], t["tp1"],   # noqa: E731
                     t["opened"], t["outcome"], t["R"])
    chk([key(t) for t in a] == [key(t) for t in b],
        "خرابیِ برچسب‌زن تصمیمِ معامله را عوض کرد — یعنی برچسب دروازه شده")
    chk(all("stair_dir" not in t["why"] for t in b),
        "با برچسب‌زنِ خراب هم کلیدِ نردبان نوشته شد")


def test_conditions_registered():
    """شرط‌های شبانه ثبت شده‌اند و روی ردیفِ بی‌برچسب نمی‌ترکند."""
    from hamid import paper
    names = [n for n, _ in paper.CONDITIONS]
    for want in ("نردبان ریزشی، پلهٔ ۲+", "نردبان ریزشی، پلهٔ ۱",
                 "چسبیده به زیرِ OB بالاسری", "داخلِ OB بالاسری",
                 "نردبان شکسته (برگشت محتمل)", "نردبان هم‌جهت با معامله"):
        chk(want in names, f"شرطِ «{want}» در ماشین شبانه ثبت نشده")
    for _n, fn in paper.CONDITIONS:
        try:
            fn({})                       # ردیفِ قدیمی، بی‌هیچ کلیدِ نردبان
            fn({"stair_dir": None, "stair_steps": None,
                "stair_broken": None, "stair_ob": None})
        except Exception as e:           # noqa: BLE001
            chk(False, f"شرطِ «{_n}» روی ردیفِ بی‌برچسب ترکید: {e}")
            break
    else:
        chk(True, "")


def test_verdict_rule_is_preregistered():
    """قاعدهٔ توقف نباید بعد از دیدنِ عدد شل شود."""
    chk(stairs.PROMOTE_MIN_N >= 150, "کفِ PROMOTE پایین آمده")
    chk(stairs.REJECT_MIN_N >= 300, "کفِ REJECT پایین آمده")
    chk(stairs.HYPOTHESES == len(stairs.TESTS),
        "تعداد فرضیه‌ها با فهرستِ آزمون نمی‌خواند — تصحیح چندآزمونی غلط می‌شود")
    chk(abs(stairs.ALPHA_SIDAK - (1 - 0.95 ** (1 / stairs.HYPOTHESES))) < 1e-12,
        "آستانهٔ Šidák با تعداد فرضیه هم‌گام نیست")
    # حکمِ زودرس ممنوع: بازوی کوچک زیر کف، حتی با اختلافِ آشکار
    rows = ([{"R_net": 1.0, "why": {"stair_dir": "down", "stair_steps": 3}}] * 40
            + [{"R_net": -1.0, "why": {"stair_dir": "down", "stair_steps": 1}}] * 40)
    j = stairs.judge(rows, verbose=False)
    h1 = next(t for t in j["tests"] if t["test"].startswith("H1"))
    chk(h1["verdict"] == "UNDECIDED", f"حکمِ زودرس: {h1['verdict']}")


def test_module_writes_nothing():
    """قانون ۰۵: یک نویسنده برای هر دامنه — این ماژول نویسنده نیست."""
    src = (HERE / "stairs.py").read_text(encoding="utf-8")
    for bad in ("write_text(", "open(", "_append(", "mkdir("):
        chk(bad not in src, f"ماژولِ ناظر می‌نویسد: {bad}")


def main():
    for fn in (test_module_selftest, test_label_is_causal_through_trainer,
               test_spy_bites, test_events_are_append_only_over_time,
               test_no_gate_behaviour_changed, test_conditions_registered,
               test_verdict_rule_is_preregistered, test_module_writes_nothing):
        fn()
    print(f"test_stairs: {OK[0]} بررسی سبز"
          + (f" · {BAD[0]} قرمز" if BAD[0] else ""))
    return 1 if BAD[0] else 0


if __name__ == "__main__":
    sys.exit(main())
