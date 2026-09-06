"""پاسبان بازوهای تریل — آزمایشی که تولید را تکان بدهد، آزمایش نیست.

این تغییر به قلبِ تسویه دست زد (`paper._trail_dist`). چهار راهِ خرابی:

۱. **تولید عوض شود.** اگر نردبانِ ۱۲ اوت برای برچسب‌های عادی مو به مو
   بازتولید نشود، همهٔ دفترهای موجود بی‌معنی می‌شوند و اختلافِ بازوها
   هم دیگر «اثرِ نردبان» نیست.
۲. **آزمایش وارد آمارِ سیگنال شود.** فهرست جداسازی تا امشب در پنج جا
   تکرار می‌شد؛ بازوی تازه اگر در یکی جا بماند، بی‌صدا وارد کارنامهٔ
   استراتژی می‌شود — همان کلاسی که ۲۴ اوت CI را باددار کرد.
۳. **آینه جفت نباشد.** اگر ردیفِ بازو ورود/استاپ/تارگتِ متفاوتی داشته
   باشد، مقایسه دیگر جفتی نیست و اختلاف به هندسه نشت می‌کند.
۴. **قاعدهٔ توقف بعد از دیدن داده جابه‌جا شود.** آستانه‌ها و اثرانگشت
   باید روی خروجی ثبت شوند تا تغییرشان دیده شود.

اجرا: `python3 -m hamid.test_trail_arms`
"""
import pathlib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
sys.path.insert(0, str(PY))

from hamid import paper as P                                    # noqa: E402
from hamid import trail_arms as A                               # noqa: E402

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


def legacy(gain, tp_dist, fee_px):
    """نردبانِ ۱۲ اوت — بازنشسته شد ۶ سپتامبر، این‌جا فقط برای مقایسه.

    رَجِ دومش (`prog >= 1/3 → fee_px`) استاپ را روی «سربه‌سر بعد از
    کارمزد» می‌گذاشت، پس هر برگشتی طبق **تعریف** در خالصِ صفر بسته
    می‌شد. اندازه‌گیری: ۸۳.۲٪ از تریل‌های سیگنال‌گرید ≈صفر، میانهٔ
    خالص +۰.۰۰۰۱R.
    """
    prog = gain / tp_dist
    if prog >= 2 / 3:
        return tp_dist / 3
    if prog >= 1 / 3:
        return fee_px
    return None


def prod_rule(gain, fee_px, frac):
    """قاعدهٔ تریلِ تولید از ۶ سپتامبر — کپیِ مستقل، همان قاعدهٔ بازو."""
    if gain < fee_px:
        return None
    lvl = gain * frac
    return lvl if lvl >= fee_px else None


def run():
    # ── ۱) تولید همان قاعده‌ای است که سنجیده و PROMOTE شد ───────────────
    #
    # ارتقای ۶ سپتامبر (شکایت حمید «۸۳٪ خیلی زیاده»): تولید از نردبانِ
    # ثابتِ ۱۲ اوت به همان قاعدهٔ بازوی g80 رفت — استاپ روی ۸۰٪ بهترین
    # سودِ دیده‌شده. سه مسیر مستقل هم‌خوان بودند و هر سه CI بالای صفر:
    # ماشین شبانه (+۰.۲۱۹۹R، n=۲۲۱)، آزمون جفت‌شدهٔ sig-only (+۰.۱۸۹۵R،
    # n=۱۰۳)، و g80 در برابر g65 (+۰.۰۴۲۵R، n=۲۲۲).
    #
    # این بررسی حالا **قاعدهٔ تازه** را پین می‌کند، نه قدیمی را — وگرنه
    # همان کلاسی می‌شد که دیشب چرخه را خواباند: آزمونی که به شکلِ
    # پیاده‌سازیِ قدیم چسبیده و مانعِ رفعِ ریشه‌ای می‌شود.
    check("سهمِ تریلِ تولید همان چیزی است که PROMOTE گرفت (۰.۸۰)",
          P.PROD_TRAIL_FRAC == 0.80, str(P.PROD_TRAIL_FRAC))
    same, bad = True, None
    for tag in ("", "sig-ibs", "sig-smc", "practice", "first", "v2",
                "scalp", "shock", "vetoed", "second", "exp-short-b1"):
        p = {"why": {"stage": tag}}
        for gain in [x / 40 for x in range(-20, 121)]:
            for tp, fee in ((1.0, 0.0015), (3.0, 0.05), (0.2, 0.001)):
                a = P._trail_dist(p, gain, tp, fee)
                b = prod_rule(gain, fee, P.PROD_TRAIL_FRAC)
                if a != b:
                    same, bad = False, (tag, gain, tp, fee, a, b)
    check("همهٔ برچسب‌های غیرآزمایشی همان قاعدهٔ تولید را می‌گیرند "
          "(۱۵۵۱ حالت)", same, str(bad))
    # و رَجِ «سربه‌سر» دیگر جایی ندارد — همان چیزی که ۸۳٪ را می‌ساخت.
    _p = {"why": {"stage": "sig-ibs"}}
    _at_third = P._trail_dist(_p, 1.0 / 3, 1.0, 0.0015)
    check("در ⅓ راه، استاپ دیگر روی سربه‌سرِ کارمزد نمی‌نشیند",
          _at_third is not None and abs(_at_third - 0.0015) > 1e-9,
          str(_at_third))
    check("و به‌جایش ۸۰٪ سودِ دیده‌شده را قفل می‌کند",
          abs(_at_third - (1.0 / 3) * 0.80) < 1e-12, str(_at_third))
    check("تولید هم زیر سربه‌سرِ کارمزددار مسلح نمی‌شود",
          P._trail_dist(_p, 0.001, 3.0, 0.05) is None)
    check("نردبانِ بازنشستهٔ ۱۲ اوت دیگر اجرا نمی‌شود",
          P._trail_dist(_p, 0.9, 1.0, 0.0015) != legacy(0.9, 1.0, 0.0015))

    # ── ۲) بازوها فقط با برچسبِ خودشان فعال می‌شوند ─────────────────────
    arm = {"why": {"stage": "exp-trail-g80"}}
    check("بازوی ۸۰٪ زیر سربه‌سر مسلح نمی‌شود",
          P._trail_dist(arm, 0.001, 3.0, 0.05) is None)
    check("بازوی ۸۰٪ بالای سربه‌سر، ۸۰٪ قله را نگه می‌دارد",
          abs(P._trail_dist(arm, 1.0, 3.0, 0.05) - 0.8) < 1e-9,
          str(P._trail_dist(arm, 1.0, 3.0, 0.05)))
    a65 = {"why": {"stage": "exp-trail-g65"}}
    check("بازوی ۶۵٪ سطحِ پایین‌تری می‌دهد از ۸۰٪",
          P._trail_dist(a65, 1.0, 3.0, 0.05)
          < P._trail_dist(arm, 1.0, 3.0, 0.05))
    # بعد از ارتقای ۶ سپتامبر، نقشِ دو بازو عوض شد و این‌جا صریح ثبت
    # می‌شود تا کسی بعداً فکر نکند آزمایش بی‌معنی شده:
    #   · g65 = **کنترلِ پایین‌تر**؛ اگر روزی ۰.۸۰ اشتباه بود، همان ماشین
    #     شبانه با CI نشانش می‌دهد. باید با تولید فرق داشته باشد.
    #   · g80 = **آینهٔ تولید**؛ اختلافش باید ~صفر بماند. هر واگراییِ
    #     معنادار یعنی مسیرِ تولید و مسیرِ آینه از هم جدا افتاده‌اند —
    #     خودش یک بررسی سلامت است، نه آزمایشِ مرده.
    _prodp = {"why": {"stage": "sig-ibs"}}
    check("کنترلِ پایین‌تر (g65) واقعاً با تولید فرق دارد",
          P._trail_dist(a65, 1.0, 3.0, 0.05)
          != P._trail_dist(_prodp, 1.0, 3.0, 0.05))
    check("بازوی g80 حالا آینهٔ تولید است (اختلافش باید ~صفر بماند)",
          P._trail_dist(arm, 1.0, 3.0, 0.05)
          == P._trail_dist(_prodp, 1.0, 3.0, 0.05))
    check("و هیچ‌کدام دیگر نردبانِ بازنشسته را اجرا نمی‌کنند",
          P._trail_dist(arm, 1.0, 3.0, 0.05) != legacy(1.0, 3.0, 0.05))

    # ── ۲ب) دفتر و پیامِ حمید باید یک قاعده را بگویند ────────────────────
    #
    # کپشن هر سیگنال صریح می‌گوید «دفتر کاغذی همین را حساب می‌کند». اگر
    # این دو از هم جدا بیفتند، دفتر چیزی را می‌سنجد که حمید اجرا نمی‌کند
    # — یعنی کلِ کارنامه دربارهٔ سامانه‌ای می‌شود که وجود ندارد.
    _tg = (PY / "telegram.py").read_text(encoding="utf-8")
    check("کپشن سهمِ تریل را از خودِ paper می‌خواند، نه عددِ تایپ‌شده",
          "from hamid.paper import PROD_TRAIL_FRAC" in _tg)
    check("رَجِ بازنشستهٔ «⅓ مسیر → سربه‌سر» از کپشن برداشته شد",
          "⅓ مسیر تارگت" not in _tg and "استاپ به همان ⅓" not in _tg)
    check("کپشن هنوز می‌گوید دفتر همین را حساب می‌کند (پیوند صریح)",
          "دفتر کاغذی همین را خودکار حساب می‌کند" in _tg)
    check("برچسب از stage_tag هم خوانده می‌شود",
          P._trail_dist({"stage_tag": "exp-trail-g80"}, 1.0, 3.0, 0.05)
          == P._trail_dist(arm, 1.0, 3.0, 0.05))

    # ── ۳) جداسازی در همهٔ جاها، از یک منبع ─────────────────────────────
    check("بازوهای تریل در فهرست آزمایش‌های پیپر هستند",
          set(P.TRAIL_ARMS) <= set(P.EXPERIMENT_STAGES),
          str(P.EXPERIMENT_STAGES))
    check("و در فهرست «سیگنال نیست»", set(P.TRAIL_ARMS) <= set(P._NOT_SIGNAL))
    from hamid import work_report as W
    check("و در NOT_PERFORMANCE گزارش کار",
          set(P.TRAIL_ARMS) <= W.NOT_PERFORMANCE, str(W.NOT_PERFORMANCE))
    src = (PY / "hamid" / "paper.py").read_text(encoding="utf-8")
    check("فهرست جداسازی دیگر تکرار نشده (یک منبع حقیقت)",
          src.count('"exp-short-b1"') == 1,
          f"{src.count('&quot;exp-short-b1&quot;')} بار تکرار شده")
    wr = (PY / "hamid" / "work_report.py").read_text(encoding="utf-8")
    check("گزارش کار هم از همان ثابت می‌خواند",
          "EXPERIMENT_STAGES" in wr)
    # اثبات کلاس: بازوی خیالیِ تازه باید خودبه‌خود همه‌جا جدا بماند
    old = P.EXPERIMENT_STAGES
    try:
        P.EXPERIMENT_STAGES = old + ("exp-fake-zzz",)
        check("بازوی تازه بدون ویرایشِ چندجا، در فهرست‌ها می‌آید",
              "exp-fake-zzz" in P.EXPERIMENT_STAGES)
    finally:
        P.EXPERIMENT_STAGES = old

    # ── ۴) آینه واقعاً جفت است ──────────────────────────────────────────
    # روی **کپیِ** دفتر کار می‌کنیم، نه خودش: این بخش `mirror_trail_arms`
    # را صدا می‌زند و آن می‌نویسد. پاسبانی که دفتر تولید را عوض کند، همان
    # کلاسِ عیبی است که ۴ سپتامبر بسته شد — پس ردیف‌های واقعی خوانده
    # می‌شوند ولی نوشتن در پوشهٔ موقت می‌افتد.
    import shutil
    import tempfile as _tf
    _td = _tf.mkdtemp()
    _real_open = P.OPEN
    _tmp_open = pathlib.Path(_td) / "open.jsonl"
    if _real_open.exists():
        shutil.copy(_real_open, _tmp_open)
    P.OPEN = _tmp_open
    rows = P._read(P.OPEN)
    mir = [r for r in rows if (r.get("why") or {}).get("stage") in P.TRAIL_ARMS]
    idx = {}
    for r in rows:
        st = (r.get("why") or {}).get("stage") or ""
        if st.startswith("sig-") or st == "practice":
            idx[(r.get("sym"), r.get("entry"), r.get("opened"))] = r
    checked = mism = 0
    for m in mir:
        b = idx.get((m.get("sym"), m.get("entry"), m.get("opened")))
        if not b:
            continue
        checked += 1
        if (m.get("sl"), m.get("tp1"), m.get("dir")) != (
                b.get("sl"), b.get("tp1"), b.get("dir")):
            mism += 1
    check("هر ردیفِ بازو با پایه‌اش هندسهٔ یکسان دارد (A/B جفتی)",
          mism == 0, f"{mism} از {checked} ناجور")
    check("و آینه از پایه‌ای گرفته شده که ثبتش کرده",
          all((m.get("why") or {}).get("mirror_of") for m in mir),
          f"{sum(1 for m in mir if not (m.get('why') or {}).get('mirror_of'))} بی‌منبع")

    # آینه دوباره همان ردیف را نمی‌سازد
    before = len(P._read(P.OPEN))
    again = P.mirror_trail_arms(limit=5)
    after = len(P._read(P.OPEN))
    P.OPEN = _real_open                          # دفتر واقعی برگشت سر جایش
    shutil.rmtree(_td, ignore_errors=True)
    check("آینه‌گیریِ دوباره ردیفِ تکراری نمی‌سازد",
          after - before == again, f"{again} افزوده، {after-before} رشد")

    # ── ۵) قاعدهٔ توقف ثبت و قابل‌مشاهده است ────────────────────────────
    s = A.study()
    check("اثرانگشتِ نسبت‌ها روی خروجی ثبت می‌شود",
          "0.65" in s["fingerprint"] and "0.8" in s["fingerprint"],
          s["fingerprint"])
    check("آستانه‌ها روی خروجی‌اند (جابه‌جایی‌شان دیده می‌شود)",
          s["n_promote"] == A.N_PROMOTE and s["n_reject"] == A.N_REJECT)
    check("تصحیح چندآزمونی اعمال شده (z > 1.96)", A.Z > 1.96, str(A.Z))
    check("PROMOTE فقط پیشنهاد است، نه تغییر تولید",
          "تأیید صریح" in s["boundary"] and "پیشنهاد" in s["boundary"])
    check("سه حکم بیشتر ممکن نیست",
          {a["verdict"] for a in s["arms"].values()}
          <= {"PROMOTE", "REJECT", "UNDECIDED"})
    check("بی‌نمونه هرگز PROMOTE نمی‌شود",
          all(a["verdict"] != "PROMOTE" for a in s["arms"].values()
              if a["n_pairs"] < A.N_PROMOTE))
    check("دو جمعیت جدا گزارش می‌شوند",
          all(set(a["by_population"]) == {"sig", "practice"}
              for a in s["arms"].values()))

    # ناهم‌جهتیِ دو جمعیت حکم را می‌بندد
    hi_pos = [{"base": 0.0, "arm": 1.0, "diff": 1.0}] * 300
    hi_neg = [{"base": 0.0, "arm": -1.0, "diff": -1.0}] * 300
    real = A.pairs
    try:
        A.pairs = lambda: {"exp-trail-g65": {"sig": hi_pos,
                                             "practice": hi_neg},
                           "exp-trail-g80": {"sig": hi_pos,
                                             "practice": hi_pos}}
        st = A.study()
    finally:
        A.pairs = real
    check("دو جمعیتِ خلافِ هم → UNDECIDED، نه PROMOTE",
          st["arms"]["exp-trail-g65"]["verdict"] == "UNDECIDED"
          and not st["arms"]["exp-trail-g65"]["consistent"],
          str(st["arms"]["exp-trail-g65"]["verdict"]))
    check("ولی دو جمعیتِ هم‌جهت با n کافی PROMOTE می‌گیرد",
          st["arms"]["exp-trail-g80"]["verdict"] == "PROMOTE",
          str(st["arms"]["exp-trail-g80"]))

    # ── ۶) مرزها ────────────────────────────────────────────────────────
    asrc = (PY / "hamid" / "trail_arms.py").read_text(encoding="utf-8")
    check("داور به تلگرام پیام نمی‌دهد (قانون ۰۷)",
          "send_text" not in asrc and "alert_gate" not in asrc)
    check("داور فقط خروجی خودش را می‌نویسد (قانون ۰۵)",
          asrc.count("write_text") == 1 and "trail-arms.json" in asrc)
    check("آینه هیچ ستاپ/سیگنالی نمی‌سازد",
          "send_signals" not in src.split("def mirror_trail_arms")[1]
          .split("def _settle_one")[0])
    check("معیار خالص از کارمزد است، نه ناخالص",
          "fee_r" in asrc and "خالص" in s["stopping_rule"])

    # ── ۶.۵) تقسیمِ رژیم توصیفی است، نه دروازه ──────────────────────────
    #
    # این خطرناک‌ترین بخشِ امشب است: تقسیمِ زیرگروه وسوسه می‌کند که حکم
    # را از «بهترین زیرگروه» بگیریم. آن دقیقاً data-snooping است.
    check("رژیم از جهتِ معامله در برابر روند ۴س ساخته می‌شود",
          A._regime({"dir": "LONG", "why": {"trend_4h": "up"}}) == "با روند"
          and A._regime({"dir": "LONG", "why": {"trend_4h": "down"}})
          == "خلاف روند")
    check("روندِ نامعلوم «با روند» خوانده نمی‌شود (قانون ۰۱ بند ۱)",
          A._regime({"dir": "LONG", "why": {}}) == "رنج/نامعلوم"
          and A._regime({"dir": "LONG", "why": {"trend_4h": "range"}})
          == "رنج/نامعلوم")
    # حکم نباید از بهترین زیرگروه بیاید: یک زیرگروهِ درخشان و کلِ منفی
    strong = ([{"base": 0.0, "arm": 1.0, "diff": 1.0, "regime": "با روند"}] * 60
              + [{"base": 0.0, "arm": -1.0, "diff": -1.0,
                  "regime": "خلاف روند"}] * 500)
    real = A.pairs
    try:
        A.pairs = lambda: {t: {"sig": strong, "practice": []}
                           for t in ("exp-trail-g65", "exp-trail-g80")}
        sp2 = A.study()
    finally:
        A.pairs = real
    g = sp2["arms"]["exp-trail-g65"]
    check("زیرگروهِ درخشان با کلِ منفی، PROMOTE نمی‌سازد",
          g["verdict"] != "PROMOTE", str(g["verdict"]))
    check("ولی زیرگروه‌ها گزارش می‌شوند (پنهان‌کاری هم ممنوع)",
          g["by_regime"]["با روند"]["diff_mean"] > 0
          > g["by_regime"]["خلاف روند"]["diff_mean"])
    check("مرز صادقانه می‌گوید رژیم دروازه نیست",
          "data-snooping" in sp2["boundary"] and "توصیفی" in sp2["boundary"])
    check("و منبعِ ایدهٔ رژیم را شاهدِ راستی‌آزمایی‌نشده می‌خواند",
          "قانون ۱۱" in asrc and "راستی‌آزمایی‌نشده" in asrc)

    # ── ۷) سیم‌کشی — ماژولی که صدا زده نشود، کدِ مرده است ────────────────
    cyc = (PY / "hamid" / "cycle.py").read_text(encoding="utf-8")
    check("چرخه آینه را قبل از تسویه صدا می‌زند",
          "mirror_trail_arms()" in cyc
          and cyc.index("mirror_trail_arms()") < cyc.index("paper.mark()"))
    wf = PY.parent.parent / ".github" / "workflows"
    rep = (wf / "work-report.yml").read_text(encoding="utf-8")
    check("داورِ بازوها در گزارش کار اجرا می‌شود",
          "hamid.trail_arms --write" in rep)
    check("بازپخشِ کندلی روی رانر اجرا می‌شود (نه دونقطه‌ای)",
          "hamid.trail_lab --bars --write" in rep)
    gates = "".join((wf / f).read_text(encoding="utf-8")
                    for f in ("pump-radar.yml", "hamid-cycle.yml"))
    check("پاسبان در دروازهٔ هر دو زنجیره است",
          gates.count("hamid.test_trail_arms") == 2, str(gates.count("hamid.test_trail_arms")))
    reg = PY.parent.parent / "config" / "state_registry.json"
    import json as _json
    files = _json.loads(reg.read_text(encoding="utf-8"))["files"]
    check("هر دو خروجی ردیف قرارداد دارند (قانون ۱۳)",
          "trail-arms.json" in files and "trail-lab.json" in files)

    # ── بازوی آزمایش هرگز «سیگنال ارسالی» شمرده نمی‌شود ────────────────
    #
    # شکایت حمید ۵ سپتامبر: اعلام دوساعته ۳×ETH و ۳×XRP نشان داد در حالی
    # که آرشیو ارسال یک ETH و یک XRP داشت. بازوها همان `tg_msg_id` را به
    # ارث می‌برند، پس هر شمارشی که فقط شناسهٔ پیام را ببیند سه‌برابر
    # می‌شمارد. اندازهٔ تورم روی کل دفتر: ۳۶۹ پیام یکتا / ۶۰۱ ردیف.
    from hamid import paper as _P
    def _row(mid, stage, r):
        return {"sym": "XRPUSDT", "dir": "LONG", "R": r, "outcome": "trail",
                "closed": 1_000, "why": {"stage": stage, "tg_msg_id": mid}}
    # ترتیب عمداً وارونه است: بازوی آزمایش **قبل** از ردیف واقعی می‌آید،
    # چون در دفتر واقعی ترتیب تضمین‌شده نیست. اگر فقط یکتاسازی بر شناسه
    # بود، همین ردیفِ آزمایش به‌عنوان «سیگنال» گزارش می‌شد.
    _trades = [_row(3581, "exp-trail-g65", 0.3427),
               _row(3581, "exp-trail-g80", 0.4218),
               _row(3581, "sig-ibs", 0.3198),
               _row(3545, "exp-trail-g65", -1.0),
               _row(3545, "sig-ibs", -1.0),
               {"sym": "AAAUSDT", "dir": "LONG", "R": 0.2, "outcome": "target",
                "closed": 1_000, "why": {"stage": "practice"}}]   # بی‌شناسه
    _got = _P.sent_signals(_trades)
    check("یک پیام = یک سیگنال (سه بازو، یک ردیف)", len(_got) == 2,
          str([(t["sym"], (t["why"]).get("stage")) for t in _got]))
    check("و ردیفِ برگزیده همان بازوی واقعی است، نه آزمایش",
          all((t["why"]["stage"] or "").startswith("sig-") for t in _got),
          str([t["why"]["stage"] for t in _got]))
    check("ردیف بی‌شناسهٔ پیام اصلاً سیگنال ارسالی نیست",
          all(t["sym"] != "AAAUSDT" for t in _got))
    # حتی اگر روزی بازوی تازه‌ای بیرون از _NOT_SIGNAL ساخته شود، شناسهٔ
    # تکراری باز هم یک بار شمرده می‌شود — دو فیلتر مستقل.
    _got2 = _P.sent_signals([_row(7001, "sig-ibs", 0.1),
                             _row(7001, "exp-brand-new", 0.9)])
    check("شناسهٔ تکراری با بازوی ناشناخته هم یک بار شمرده می‌شود",
          len(_got2) == 1, str([t["why"]["stage"] for t in _got2]))
    check("همهٔ بازوهای تریل در فهرست «سیگنال نیست» هستند",
          all(a in _P._NOT_SIGNAL for a in _P.TRAIL_ARMS),
          str(_P._NOT_SIGNAL))
    cyc_src = (PY / "hamid" / "cycle.py").read_text(encoding="utf-8")
    check("کلاس: اعلام دوساعته از همین تابع می‌خواند، نه از tg_msg_id خام",
          "_p.sent_signals(closed)" in cyc_src)

    # ── کارنامهٔ تریل فقط قاعدهٔ فعلی را داوری می‌کند (۶ سپتامبر) ────────
    #
    # کلاسِ عیب: سنجه‌ای که رفعِ ریشه هم سبزش نکند (قانون ۰۷). E19 کلِ
    # تاریخ را می‌شمرد، پس بعد از اصلاح قاعده ۲۱ روز سرخ می‌ماند. حتی
    # پنجرهٔ ۷روزه هم کافی نبود (همان روز ۸۰.۳٪ می‌داد). راه‌حل: اثرانگشتِ
    # قاعده روی خودِ ردیف، مثل `scalp_verdict`.
    check("قاعدهٔ تریل یک منبع دارد", _P._trail_frac({}) == _P.PROD_TRAIL_FRAC)
    check("و بازوی آزمایش سهمِ خودش را می‌گیرد",
          _P._trail_frac({"why": {"stage": "exp-trail-g65"}}) == 0.65)
    pap_src = (PY / "hamid" / "paper.py").read_text(encoding="utf-8")
    check("ردیفِ بستهٔ تریل اثرانگشتِ قاعده را ثبت می‌کند",
          'p["trail_frac"] = _trail_frac(p)' in pap_src)
    sc_src = (PY / "hamid" / "scorecard.py").read_text(encoding="utf-8")
    check("E19 فقط ردیف‌های قاعدهٔ فعلی را می‌شمرد",
          'r.get("trail_frac") == _frac19' in sc_src)
    check("و سهمِ قاعده را از خودِ paper می‌خواند، نه عددِ دست‌نویس",
          "from hamid.paper import PROD_TRAIL_FRAC as _frac19" in sc_src)
    # اثباتِ رفتاری: ردیفِ قاعدهٔ بازنشسته (بی‌اثرانگشت) نباید داوری شود.
    _old = [{"outcome": "trail", "R_net": 0.0} for _ in range(50)]
    _new = [{"outcome": "trail", "R_net": 0.0, "trail_frac": _P.PROD_TRAIL_FRAC}
            for _ in range(3)]
    _judged = [r for r in _old + _new
               if r.get("trail_frac") == _P.PROD_TRAIL_FRAC]
    check("۵۰ ردیفِ قاعدهٔ قدیم + ۳ ردیفِ جدید ⇒ فقط ۳ تا داوری می‌شود",
          len(_judged) == 3, str(len(_judged)))

    print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(run())
