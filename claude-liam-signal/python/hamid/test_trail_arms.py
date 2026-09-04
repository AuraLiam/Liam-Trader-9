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
    """نردبانِ ۱۲ اوت، دست‌نخورده — کپیِ مستقل برای مقایسه."""
    prog = gain / tp_dist
    if prog >= 2 / 3:
        return tp_dist / 3
    if prog >= 1 / 3:
        return fee_px
    return None


def run():
    # ── ۱) تولید مو به مو همان است ──────────────────────────────────────
    same = True
    bad = None
    for tag in ("", "sig-ibs", "sig-smc", "practice", "first", "v2",
                "scalp", "shock", "vetoed", "second", "exp-short-b1"):
        p = {"why": {"stage": tag}}
        for gain in [x / 40 for x in range(-20, 121)]:
            for tp, fee in ((1.0, 0.0015), (3.0, 0.05), (0.2, 0.001)):
                a = P._trail_dist(p, gain, tp, fee)
                b = legacy(gain, tp, fee)
                if a != b:
                    same, bad = False, (tag, gain, tp, fee, a, b)
    check("نردبانِ تولید برای همهٔ برچسب‌های غیرآزمایشی تغییر نکرده "
          "(۱۵۵۱ حالت)", same, str(bad))

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
    check("بازو با نردبانِ تولید یکی نیست (وگرنه آزمایش بی‌معنی است)",
          P._trail_dist(arm, 1.0, 3.0, 0.05) != legacy(1.0, 3.0, 0.05))
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

    print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(run())
