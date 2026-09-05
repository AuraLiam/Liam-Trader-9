"""پاسبان شکاک — بازرسِ بی‌شاهد، خودش بدترین نوع ادعاست.

شکاک برای این ساخته شد که به نتیجه‌گیری‌ها شک کند. پس اگر خودش شل باشد،
یک لایهٔ اطمینانِ کاذب اضافه کرده‌ایم — بدتر از نداشتنش. سه راه خرابی:

۱. **سؤالی که همیشه سبز است.** متری که نتواند رد شود، بازجویی نیست.
۲. **نبودِ داده = قبول.** اگر فایلی نباشد و شکاک «ثابت شد» بدهد، دقیقاً
   همان کاری را کرده که قانون ۰۱ بند ۱ منع کرده.
۳. **آلارمِ زودرس.** یک شکستِ لحظه‌ای پیام نمی‌خواهد؛ سه نوبتِ پیاپی
   می‌خواهد. وگرنه همان اسپمی می‌شود که قانون ۰۷ بسته.

اجرا: `python3 -m hamid.test_skeptic`
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
sys.path.insert(0, str(PY))

from hamid import skeptic as S                                  # noqa: E402

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


def run():
    res = S.interrogate()

    # ── ۱) ترتیب و پوشش: از جهانِ نمادها تا فرستنده ────────────────────
    ids = [e for e, _, _ in S.BANK]
    check("بازجویی از E01 شروع می‌شود", ids[0] == "E01", str(ids[:3]))
    check("و به E25 (فرستنده) می‌رسد", "E25" in ids, str(ids))
    check("بازرسیِ نتیجه‌گیری هم در بانک هست", "**" in ids)

    # ── محتوای سیگنالِ رفته، نه فقط رفتنش (دستور حمید ۵ سپتامبر) ───────
    _e25 = [pool for e, _, pool in S.BANK if e == "E25"][0]
    check("E25 محتوای سیگنال‌های رفته را هم می‌سنجد",
          S.q_signal_sanity in _e25, str([f.__name__ for f in _e25]))
    _now = 1_700_000_000_000
    _good = {"at": _now - 1000, "sym": "AAAUSDT", "dir": "LONG", "tf": "5m",
             "entry": 100.0, "sl": 95.0, "tp1": 110.0,
             "trend4": "up", "trend1": "up"}
    _cases = [
        ("سالم", _good, "PROVED"),
        ("تایم‌فریم غیرمجاز", dict(_good, tf="1m"), "UNPROVED"),
        ("بی‌استاپ", dict(_good, sl=None), "UNPROVED"),
        ("بی‌تارگت", dict(_good, tp1=0), "UNPROVED"),
        ("ترتیب قیمت لانگ غلط", dict(_good, sl=105.0), "UNPROVED"),
        ("RR زیر ۰.۸", dict(_good, tp1=102.0), "UNPROVED"),
        ("وتوی روند نقض‌شده", dict(_good, trend4="down", trend1="down"), "UNPROVED"),
        ("شورتِ سالم", dict(_good, dir="SHORT", sl=105.0, tp1=90.0,
                            trend4="down", trend1="down"), "PROVED"),
    ]
    _saved = S._j
    try:
        for _name, _row, _want in _cases:
            S._j = lambda rel, default=None, _r=_row: (
                {"sent": [_r]} if rel.endswith("telegram-log.json") else default)
            _got = S.q_signal_sanity(_now)["verdict"]
            check(f"سیگنال «{_name}» → {_want}", _got == _want, _got)
        S._j = lambda rel, default=None: ({"sent": []} if rel.endswith(
            "telegram-log.json") else default)
        check("بدون ارسال در پنجره: NO_DATA (نه سبزِ دروغین)",
              S.q_signal_sanity(_now)["verdict"] == "NO_DATA")
    finally:
        S._j = _saved
    check("هر انجینِ بانک دست‌کم یک سؤال دارد",
          all(pool for _, _, pool in S.BANK))

    # ── ۲) سه حکم، و هیچ‌کدام حدس نیست ─────────────────────────────────
    vs = {a["verdict"] for a in res["answers"]}
    check("فقط سه حکم ممکن است", vs <= {"PROVED", "UNPROVED", "NO_DATA"}, str(vs))
    check("هر جواب شواهدِ نوشته‌شده دارد",
          all(a["evidence"] for a in res["answers"]),
          str([a["q"] for a in res["answers"] if not a["evidence"]]))
    check("هر جواب به انجینش نسبت داده می‌شود",
          all(a.get("engine") for a in res["answers"]))

    # ── ۳) نبودِ داده هرگز «ثابت شد» نمی‌شود ───────────────────────────
    f = S.q_fresh("signals/__nope__.json", 10, "چیزِ نبوده")
    a = f(0)
    check("فایلِ ناموجود → NO_DATA، نه PROVED و نه UNPROVED",
          a["verdict"] == "NO_DATA", str(a))
    check("و دلیلِ بی‌داده‌بودن نوشته می‌شود", bool(a["evidence"]))

    # ── ۴) سؤالِ تازگی واقعاً می‌تواند رد شود ───────────────────────────
    import json
    import tempfile
    d = Path(tempfile.mkdtemp())
    old_root = S.ROOT
    try:
        S.ROOT = d
        (d / "signals").mkdir()
        now = 10_000_000
        (d / "signals" / "x.json").write_text(
            json.dumps({"generated": now - 60 * 60000}), encoding="utf-8")
        fresh = S.q_fresh("signals/x.json", 120, "تست")(now)
        stale = S.q_fresh("signals/x.json", 30, "تست")(now)
        check("۶۰ دقیقه زیر سقف ۱۲۰ → ثابت", fresh["verdict"] == "PROVED")
        check("همان ۶۰ دقیقه بالای سقف ۳۰ → رد", stale["verdict"] == "UNPROVED")
    finally:
        S.ROOT = old_root

    # ── ۵) قیفِ تک‌دلیل رد می‌شود (دروازهٔ کور) ─────────────────────────
    old = S._j
    try:
        S._j = lambda rel, default=None: (
            {"top_reasons": {"یک دلیل": 100}} if "funnel" in rel else default)
        deg = S.q_funnel_degenerate(0)
        S._j = lambda rel, default=None: (
            {"top_reasons": {"الف": 30, "ب": 25, "ج": 25, "د": 20}}
            if "funnel" in rel else default)
        div = S.q_funnel_degenerate(0)
    finally:
        S._j = old
    check("قیفی که یک دلیل ۱۰۰٪ آن است، رد می‌شود",
          deg["verdict"] == "UNPROVED", str(deg))
    check("و قیفِ متنوع قبول می‌شود", div["verdict"] == "PROVED", str(div))

    # ── ۵.۵) قرارداد ضدتکرار از کد خوانده می‌شود، نه از سند ────────────
    #
    # عیب ۱ سپتامبر: این بررسی عددها را سفت نوشته بود (۱۲ ساعت، از روی
    # `trading-core.md`) در حالی که حمید ۲۷ اوت پنجره را ۶ ساعت کرده بود.
    # نتیجه: ۶ «نقض» که ۵تایش نقض نبود — بازرس علیه مشخصاتی می‌سنجید که
    # کد هرگز اجرا نمی‌کرد. اگر عددها دوباره سفت شوند، همین می‌افتد.
    import telegram as _TG
    a = S.q_dedupe_contract(10_000_000_000_000)
    ttl_h = _TG.TTL_MS / 3_600_000
    check("قرارداد گزارش‌شده همان پنجرهٔ واقعیِ telegram.py است",
          f"{ttl_h:g}س" in a["detail"], f"TTL={ttl_h:g}س · {a['detail']}")
    old_ttl = _TG.TTL_MS
    try:
        _TG.TTL_MS = 9 * 3_600_000
        b = S.q_dedupe_contract(10_000_000_000_000)
    finally:
        _TG.TTL_MS = old_ttl
    check("عوض‌شدن پنجرهٔ کد، گزارشِ بازرس را هم عوض می‌کند "
          "(عدد سفت‌نوشته باقی نمانده)",
          "9س" in b["detail"] and a["detail"] != b["detail"], b["detail"])
    check("حکم روی پنجرهٔ تازه است، نه کلِ تاریخ",
          "اخیر" in a["evidence"] and "کل تاریخ" in a["evidence"],
          a["evidence"])

    # ── ۵.۷) نوبتِ محلی نباید آلارمِ تولید بسازد ────────────────────────
    #
    # عیب ۱ سپتامبر: سؤال‌های «تازگی» سنِ فایل‌های همین درخت را
    # می‌سنجند. روی رانر یعنی سنِ تولید؛ در نشستِ محلی یعنی «آخرین بار
    # کِی fetch کردم». همان لحظه شکاکِ محلی گفت دامیننس ۴۱۹ دقیقه کهنه
    # است و گذرگاه وضعیت ۳ دقیقه می‌دید — هیچ‌کدام دروغ نگفتند، دو چیزِ
    # متفاوت را می‌سنجیدند. ولی چون دفترِ شکست مشترک بود، همان نوبتِ
    # محلی می‌توانست شمارنده را باد کند و آلارمِ تلگرام شلیک شود.
    import os as _os
    old_env = _os.environ.get("GITHUB_ACTIONS")
    try:
        _os.environ["GITHUB_ACTIONS"] = "true"
        check("روی رانر، محیط ci علامت می‌خورد", S.where() == "ci")
        _os.environ.pop("GITHUB_ACTIONS", None)
        check("در نشست محلی، محیط local علامت می‌خورد", S.where() == "local")
    finally:
        if old_env is None:
            _os.environ.pop("GITHUB_ACTIONS", None)
        else:
            _os.environ["GITHUB_ACTIONS"] = old_env

    d2 = Path(tempfile.mkdtemp())
    old_log = S.LOG
    try:
        S.LOG = d2 / "log.jsonl"
        rowl = {"env": "local", "answers": [{"engine": "E01", "q": "س",
                                             "verdict": "UNPROVED"}]}
        rowc = {"env": "ci", "answers": [{"engine": "E01", "q": "س",
                                          "verdict": "UNPROVED"}]}
        S.LOG.write_text("\n".join(json.dumps(r, ensure_ascii=False)
                                   for r in [rowl] * 5) + "\n", encoding="utf-8")
        check("پنج نوبتِ محلیِ ناموفق، شمارندهٔ شکست را تکان نمی‌دهد",
              S._history().get(("E01", "س"), 0) == 0, str(S._history()))
        S.LOG.write_text("\n".join(json.dumps(r, ensure_ascii=False)
                                   for r in [rowc] * 3) + "\n", encoding="utf-8")
        check("ولی سه نوبتِ رانرِ ناموفق شمرده می‌شود",
              S._history().get(("E01", "س"), 0) == 3, str(S._history()))
        S.LOG.write_text(json.dumps(
            {"answers": [{"engine": "E01", "q": "س", "verdict": "UNPROVED"}]},
            ensure_ascii=False) + "\n", encoding="utf-8")
        check("ردیفِ بی‌برچسب (پیش از ۱ سپتامبر) رانر فرض می‌شود",
              S._history().get(("E01", "س"), 0) == 1)
    finally:
        S.LOG = old_log

    ssrc = (PY / "hamid" / "skeptic.py").read_text(encoding="utf-8")
    check("محیط روی هر ردیفِ دفتر نوشته می‌شود",
          '"env": where()' in ssrc)
    check("اجرای محلی حق ارسال تلگرام ندارد (قانون ۰۷)",
          'where() != "ci"' in ssrc
          and ssrc.index('where() != "ci"') < ssrc.index("alert_gate.send"))

    # ── ۶) آلارم فقط با شکستِ پابرجا ───────────────────────────────────
    check("آستانهٔ آلارم سه نوبتِ پیاپی است", S.FAIL_STREAK_ALARM == 3)
    check("پیام فقط از موارد پابرجا ساخته می‌شود",
          S.caption({"persistent": [], "n": 1, "proved": 1,
                     "unproved": 0, "no_data": 0}) is None)
    cap = S.caption({"persistent": [{"engine": "E01", "label": "ل", "q": "س",
                                     "evidence": "ش", "detail": "", "streak": 3}],
                     "n": 5, "proved": 4, "unproved": 1, "no_data": 0})
    check("پیامِ پابرجا شواهد و سؤال را می‌برد", "س" in cap and "ش" in cap)
    check("و امضای پنل دارد (دستور ۱۶ اوت)", "لیام" in cap)

    # ── ۷) چرخش: سؤال ثابت پرسیده نمی‌شود ──────────────────────────────
    a1 = {(x["engine"], x["q"]) for x in S.interrogate(rnd=0)["answers"]}
    a2 = {(x["engine"], x["q"]) for x in S.interrogate(rnd=1)["answers"]}
    check("دو نوبتِ پیاپی مجموعهٔ سؤال یکسان ندارند", a1 != a2,
          "چرخش کار نمی‌کند — سؤال ثابت شده")
    check("و چرخش قطعی است (همان نوبت، همان سؤال‌ها)",
          {(x["engine"], x["q"]) for x in S.interrogate(rnd=0)["answers"]} == a1)

    # ── ۸) مرزها ───────────────────────────────────────────────────────
    src = (PY / "hamid" / "skeptic.py").read_text(encoding="utf-8")
    check("شکاک از دروازهٔ آلارم رد می‌شود (قانون ۰۷)",
          "alert_gate.send" in src and "tg.send_text" not in src)
    check("شکاک سیگنال صادر یا وتو نمی‌کند",
          "send_signals" not in src and "veto" not in src)
    check("فقط خروجی و دفتر خودش را می‌نویسد (قانون ۰۵)",
          src.count("write_text") == 1 and 'LOG.open("a"' in src)
    check("دفترش append-only است", '"a"' in src and '"w"' not in src)
    check("خروجی مرز صادقانه دارد", "دروازه" in res["boundary"])
    check("شمارش‌ها با فهرست می‌خوانند",
          res["n"] == len(res["answers"])
          and res["proved"] + res["unproved"] + res["no_data"] == res["n"])

    print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(run())
