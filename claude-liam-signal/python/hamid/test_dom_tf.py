"""پاسبان دامیننسِ هم‌ترازِ تایم‌فریم (۳۰ اوت).

سه چیزی که قفل می‌شود:

۱. **آستانه از توزیع می‌آید، نه از عدد ثابت.** اگر کسی دوباره عددِ
   دست‌ساز بگذارد، آستانه با تغییرِ نوسانِ سری تکان نمی‌خورد و همان
   سکوتِ ۹۷.۵٪ برمی‌گردد.
۲. **کندلِ بی‌رزولوشن جعل نمی‌شود.** سری با گام ۳.۲ دقیقه کندل ۵دقیقه‌ای
   واقعی نمی‌دهد (میانه ۱ نقطه در هر کندل)؛ باید صریح LOW_RESOLUTION
   بگوید، نه o=h=l=c تحویل بدهد.
۳. **این ماژول دروازه نیست.** خروجی‌اش نباید در pro/con بنشیند — وگرنه
   بی‌CI وارد تصمیم شده و قانون ۰۳ نقض شده است.

به‌علاوه کلاسِ عیبی که امشب پیدا شد: **تایم‌فریم باید به دفتر برسد.**
هر ۲۳۵ ردیف بستهٔ سیگنال `tf: null` داشتند، چون `telegram.py` آن را به
`paper.open_from` نمی‌داد. نتیجه: اعتبار لیمیت ۷۲۰ دقیقه به‌جای ۲۴۰،
و هیچ سنجشی نمی‌توانست تایم‌فریم را تفکیک کند.
"""
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
sys.path.insert(0, str(PY))

from hamid import dom_tf as D                                # noqa: E402

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


def series(n=4000, base=6.0, amp=0.05):
    """سری مصنوعی با همان **گامِ نامنظمِ** سری واقعی.

    گام یکنواخت، آزمون را گول می‌زند: با فاصلهٔ دقیقاً ۳.۲۵ دقیقه هر
    سطلِ ۵دقیقه‌ای دقیقاً ۲ نقطه می‌گیرد و «رزولوشن دارد» به نظر
    می‌رسد. سری واقعی میانهٔ ۳.۲۴ ولی صدک ۹۰ برابر ۷.۸ دقیقه دارد، و
    میانهٔ نقاطش در سطل ۵دقیقه‌ای **۱** است. پس گام این‌جا هم پراکنده
    ساخته می‌شود (قطعی و بی‌تصادف، تا آزمون تکرارپذیر بماند)."""
    import math
    t0 = 1_700_000_000_000
    out, t = [], t0
    for i in range(n):
        out.append({"t": t,
                    "u": round(base + amp * math.sin(i / 40.0), 4),
                    "b": round(55 + amp * math.cos(i / 40.0), 4)})
        # گام ۱۹۵ ثانیه با پراکندگیِ قطعی — میانه ~۳.۳ دقیقه، دنبالهٔ بلند
        t += 195_000 + (i * 7919 % 11) * 21_000
    return out


def run():
    pts = series()

    # ── ۱) کندل در هر تایم‌فریم + رزولوشنِ صادقانه ──────────────────────
    b15, r15 = D.bars(pts, "u", "15m")
    b5, r5 = D.bars(pts, "u", "5m")
    b1h, r1h = D.bars(pts, "u", "1h")
    check("کندل ۱۵ دقیقه ساخته می‌شود", len(b15) > 100, str(len(b15)))
    check("رزولوشن ۱۵د کافی است", r15 >= D.MIN_PTS_PER_BAR, str(r15))
    check("رزولوشن ۵د کافی نیست (صادقانه)", r5 < D.MIN_PTS_PER_BAR, str(r5))
    check("کندل ۱ ساعته هم ساخته می‌شود", len(b1h) > 10 and r1h > r15,
          f"{len(b1h)} / {r1h}")
    check("سطل باز کندل نیست (آخری حذف شده)",
          b15[-1]["t"] + D.TF_MS["15m"] <= pts[-1]["t"] + D.TF_MS["15m"])
    check("o/h/l/c واقعی است نه تکرارِ یک عدد",
          any(k["h"] > k["l"] for k in b15))

    r5_read = D.read(pts, "5m", "u")
    check("۵ دقیقه صریح LOW_RESOLUTION می‌دهد",
          r5_read["regime"] == "LOW_RESOLUTION", str(r5_read.get("regime")))
    check("و دلیلش نوشته می‌شود، نه سکوت", "رزولوشن" in r5_read.get("note", ""))
    check("در LOW_RESOLUTION هیچ عددی جعل نمی‌شود",
          "delta" not in r5_read and "threshold" not in r5_read, str(r5_read))

    # ── ۲) آستانه از توزیع می‌آید ──────────────────────────────────────
    thr_q, st_q = D.delta_threshold(b15)
    check("آستانه از توزیع ساخته شد", thr_q is not None, str(st_q))
    check("آستانه با آستانهٔ ثابتِ قدیمی (۰.۱۵) یکی نیست",
          thr_q is not None and thr_q < 0.15, str(thr_q))
    check("شناسنامهٔ آستانه (n/صدک/میانه) همراهش است",
          {"n", "pctl", "median"} <= set(st_q), str(st_q))

    loud = series(n=4000, amp=0.5)                # سری ده برابر پرنوسان‌تر
    b_loud, _ = D.bars(loud, "u", "15m")
    thr_loud, _ = D.delta_threshold(b_loud)
    check("آستانه با نوسانِ سری بالا می‌رود (توزیعی است، نه ثابت)",
          thr_loud > thr_q * 3, f"{thr_q} → {thr_loud}")

    calm = series(n=4000, amp=0.005)
    b_calm, _ = D.bars(calm, "u", "15m")
    thr_calm, _ = D.delta_threshold(b_calm)
    check("و در سری آرام پایین می‌آید", thr_calm < thr_q, f"{thr_q} → {thr_calm}")
    check("ولی هرگز زیر کف مطلق نمی‌رود", thr_calm >= D.FLOOR, str(thr_calm))

    short = b15[:10]
    t2, s2 = D.delta_threshold(short)
    check("نمونهٔ کم، آستانه نمی‌سازد و دلیل می‌دهد",
          t2 is None and "why" in s2, str(s2))

    # ── ۳) رژیم و هم‌ترازی ─────────────────────────────────────────────
    m = D.map_all(pts)
    check("نقشه هر چهار تایم‌فریم را دارد", set(m) == set(D.TF_MS), str(set(m)))
    check("هر تایم‌فریم هم USDT.D دارد هم BTC.D",
          all({"usdt", "btc_d"} <= set(v) for v in m.values()))

    dom = {"tf_map": m}
    ev15 = D.for_signal(dom, "15m", "LONG")
    check("ستاپ ۱۵د با خوانشِ ۱۵د سنجیده می‌شود",
          ev15["tf_used"] == "15m" and ev15["same_tf"] is True, str(ev15)[:160])
    ev5 = D.for_signal(dom, "5m", "LONG")
    check("ستاپ ۵د به بالاترین تایمِ معتبر می‌افتد و برچسب می‌خورد",
          ev5["tf_used"] == "15m" and ev5["same_tf"] is False, str(ev5)[:160])

    # هم‌ترازی باید با جهت برگردد — نه یک عددِ ثابت برای هر دو جهت
    for tf in ("15m", "1h"):
        a = D.for_signal(dom, tf, "LONG").get("aligned")
        b = D.for_signal(dom, tf, "SHORT").get("aligned")
        if a is None:
            check(f"{tf}: نمی‌دانم برای هر دو جهت یکسان است", b is None)
        else:
            check(f"{tf}: هم‌ترازی لانگ و شورت قرینه‌اند", a != b, f"{a}/{b}")

    fake = {"tf_map": {"15m": {"usdt": {"regime": "BULLISH", "delta": -0.03,
                                        "threshold": 0.01, "meaningful": True,
                                        "note": "x"}}}}
    check("رژیم BULLISH با LONG هم‌جهت است",
          D.for_signal(fake, "15m", "LONG")["aligned"] is True)
    check("و با SHORT خلاف جهت", D.for_signal(fake, "15m", "SHORT")["aligned"] is False)
    check("پایهٔ حکم ثبت می‌شود", D.for_signal(fake, "15m", "LONG")["basis"] == "regime")

    rng = {"tf_map": {"15m": {"usdt": {"regime": "RANGE", "delta": 0.05,
                                       "threshold": 0.01, "meaningful": True,
                                       "note": "x"}}}}
    check("در رنج، حرکتِ معنادار حرف می‌زند (سؤال حمید)",
          D.for_signal(rng, "15m", "SHORT")["aligned"] is True
          and D.for_signal(rng, "15m", "LONG")["aligned"] is False)
    quiet = {"tf_map": {"15m": {"usdt": {"regime": "RANGE", "delta": 0.001,
                                         "threshold": 0.01, "meaningful": False,
                                         "note": "x"}}}}
    check("رنجِ بی‌حرکت «نمی‌دانم» است، نه حکمِ ساختگی",
          D.for_signal(quiet, "15m", "LONG")["aligned"] is None)
    check("نبودِ خوانشِ معتبر هم «نمی‌دانم» است",
          D.for_signal({"tf_map": {}}, "15m", "LONG")["aligned"] is None)

    # ── ۴) شاهد است، نه دروازه ─────────────────────────────────────────
    pm = (PY / "hamid" / "premortem.py").read_text(encoding="utf-8")
    i_dom = pm.find("dom_tf")
    check("premortem شاهد دامیننسِ هم‌تراز را ثبت می‌کند", i_dom > 0)
    tail = pm[i_dom:]
    check("و آن را در pro/con نمی‌ریزد (دروازه نمی‌شود)",
          "_add(" not in tail and "pro.append" not in tail
          and "con.append" not in tail, tail[:200])
    check("روی خروجی review برمی‌گردد تا روی پرونده ثبت شود",
          '"dom_tf": dom_tf_ev' in pm)

    # ── ۵) کلاسِ عیب: تایم‌فریم باید به دفتر برسد ──────────────────────
    tg = (PY / "telegram.py").read_text(encoding="utf-8")
    calls, i = [], tg.find("_paper.open_from")
    while i >= 0:
        calls.append(tg[i:tg.find("}]", i) + 2])
        i = tg.find("_paper.open_from", i + 1)
    check("گلوگاه ارسال دست‌کم دو دفتر می‌نویسد (سیگنال + کنترل)",
          len(calls) >= 2, str(len(calls)))
    missing = [c[:60] for c in calls if '"tf": s.get("tf")' not in c]
    check("هر جای گلوگاه که ردیف دفتر می‌سازد، تایم‌فریم را هم می‌دهد",
          not missing, str(missing))
    i_sig = tg.find('"stage_tag": f"sig-')
    check("ردیفِ سیگنالِ ارسالی پیدا می‌شود", i_sig > 0)
    # ── مرزِ ساختاری، نه فاصلهٔ بایتی (رفع ۶ سپتامبر) ────────────────────
    #
    # این‌جا قبلاً پنجرهٔ ثابتِ `tg[i_sig-400 : i_sig+2400]` بود. یعنی آزمون
    # به **فاصلهٔ بایتیِ** کد چسبیده بود، نه به خاصیتش. نتیجه: افزودنِ چند
    # خط کامنتِ کاملاً بی‌ضرر، `dom_tf_aligned` را از پنجره بیرون انداخت،
    # آزمون افتاد، و چون در دروازهٔ **سختِ** زنجیرهٔ سیگنال است، ۷۸ دقیقه
    # کلِ تولید سیگنال خوابید (اجرای ۱۸۷۲، ۱۸:۵۲ UTC).
    #
    # همان کلاسی که ۶ سپتامبر ثبت شد: «آزمونی که به شکلِ پیاده‌سازی بچسبد،
    # مانعِ رفعِ ریشه‌ای می‌شود» — و این بار خودش خرابی ساخت. حالا مرز
    # ساختاری است: از خودِ فراخوانیِ `open_from` تا `except` که آن را
    # می‌پوشاند. کامنت هرچقدر هم اضافه شود، مرز جابه‌جا نمی‌شود.
    _i_of = tg.rfind("_paper.open_from(", 0, i_sig)
    _i_end = tg.find("except Exception", i_sig)
    check("بلوکِ دفترِ سیگنال با مرزِ ساختاری پیدا شد",
          0 < _i_of < i_sig < _i_end, f"{_i_of}/{i_sig}/{_i_end}")
    blk = tg[_i_of:_i_end]
    check("تایم‌فریم سیگنال به دفتر پیپر منتقل می‌شود",
          '"tf": s.get("tf")' in blk, blk[:200])
    check("شاهد دامیننسِ هم‌تراز روی ردیف دفتر ثبت می‌شود",
          "dom_tf_aligned" in blk and "dom_tf_regime" in blk)

    dm = (PY / "hamid" / "dominance.py").read_text(encoding="utf-8")
    check("نقشهٔ تایم‌فریم روی خروجی دامیننس می‌نشیند", '"tf_map": tfm' in dm)

    # ── ۶) دفترِ زندهٔ سری، اگر بود: ۱۵ دقیقه واقعاً شدنی است ───────────
    live = PY.parents[1] / "brain" / "dominance-series.json"
    if live.exists():
        lp = json.loads(live.read_text(encoding="utf-8")).get("points") or []
        if len(lp) > 1000:
            _, res_live = D.bars(lp, "u", "15m")
            check("روی سریِ واقعی هم کندل ۱۵د رزولوشن دارد",
                  res_live >= D.MIN_PTS_PER_BAR, f"{res_live} نقطه در هر کندل")

    print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(run())
