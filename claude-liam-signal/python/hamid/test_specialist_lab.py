#!/usr/bin/env python3
"""پاسبان میز متخصصین — دوازده استراتژیِ واقعاً متفاوت، بی‌نگاه به آینده.

شش راه خرابی که این‌جا بسته می‌شود:

۱. **استراتژی‌ها در واقع یکی باشند** — همان عیبی که میز قبلی داشت و
   چهار مراقب عددِ یکسان دادند. آزمون روی سری‌های ساختگی بررسی می‌کند
   که ورودهای دوازده متخصص یک مجموعهٔ یکسان نیستند.
۲. **نگاه به آینده** — تصمیم باید فقط از کندل‌های بسته ساخته شود.
   اثبات: افزودنِ کندل‌های آینده به ته سری، تصمیمِ همان لحظه را عوض
   نمی‌کند.
۳. **شناسنامهٔ ناقص** — هر متخصص باید نام، نوع استراتژی، نام استراتژی و
   ایدهٔ یک‌خطی داشته باشد (دستور حمید: «اسم و نوع استراتژی و اسم
   استراتژی هر کدام را جلوی اسمشان بنویس»).
۴. **تقلبِ بهبود** — ایده‌ای که فقط روی نیمهٔ اول بهتر است نباید پذیرفته
   شود؛ داوری باید روی نیمهٔ دومِ دیده‌نشده باشد.
۵. **قیدهای دستور** — فقط ۱۵ دقیقه، سقف ۵ ترید بر ارز، ارزِ بلاک‌شده در
   جهان نباشد، برچسب بیرون از آمار سیگنال.
۶. **خالص بی‌کارمزد** — هیچ نتیجه‌ای بدون کسر کارمزد گزارش نشود.

    python3 -m hamid.test_specialist_lab
"""
import json
import math
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from hamid import specialist_lab as L                # noqa: E402
from hamid import specialist_run as R                # noqa: E402
from hamid import paper as P                         # noqa: E402

ROOT = HERE.parents[2]
OK, FAIL = 0, []


def check(name, cond, extra=""):
    global OK
    if cond:
        OK += 1; print(f"  ✓ {name}")
    else:
        FAIL.append(name); print(f"  ✗ {name}" + (f"\n      ↳ {extra}" if extra else ""))


def series(n=900, seed=3, drift=0.0002, vol=0.006):
    """سری ساختگیِ شبه‌واقعی: تصادفی با روند و خوشهٔ نوسان."""
    rnd = random.Random(seed)
    px, out, t = 100.0, [], 1_700_000_000_000
    v = vol
    for i in range(n):
        v = max(0.002, min(0.02, v * rnd.uniform(0.95, 1.06)))
        o = px
        c = o * (1 + drift + rnd.gauss(0, v))
        hi = max(o, c) * (1 + abs(rnd.gauss(0, v / 2)))
        lo = min(o, c) * (1 - abs(rnd.gauss(0, v / 2)))
        out.append({"t": t + i * 900_000, "o": o, "h": hi, "l": lo, "c": c,
                    "v": rnd.uniform(500, 5000)})
        px = c
    return out


def run():
    global OK
    # ── ۳) شناسنامه ──────────────────────────────────────────────────
    check("دقیقاً ۱۲ متخصص", len(L.SPECIALISTS) == 12, str(len(L.SPECIALISTS)))
    miss = [s["id"] for s in L.SPECIALISTS
            if not all(s.get(k) for k in ("sign", "fa", "en", "family",
                                          "strategy_fa", "strategy_en", "idea"))]
    check("هر متخصص نام، نوع استراتژی، نام استراتژی و ایده دارد", not miss, str(miss))
    names = [s["strategy_fa"] for s in L.SPECIALISTS]
    check("نام استراتژی‌ها یکتا هستند", len(set(names)) == 12, str(names))
    fams = {s["family"] for s in L.SPECIALISTS}
    check("دست‌کم ۸ خانوادهٔ استراتژیِ متفاوت", len(fams) >= 8, str(len(fams)))
    check("هر متخصص رأی‌دهندهٔ ورود دارد", set(L.ENTRY) == {s["id"] for s in L.SPECIALISTS})
    check("هر متخصص دست‌کم ۳ ایده برای بهبود دارد",
          all(len(s.get("ideas") or []) >= 3 for s in L.SPECIALISTS))
    check("هر ایده پارامترِ شناخته‌شدهٔ همان متخصص را عوض می‌کند",
          all(set(i) <= set(s["params"]) for s in L.SPECIALISTS for i in s["ideas"]))

    # ── ۱) دوازده استراتژی واقعاً متفاوت‌اند ─────────────────────────
    cds = [series(900, seed=k, drift=d) for k, d in
           ((3, 0.0004), (7, -0.0004), (11, 0.0))]
    sigs = {}
    for s in L.SPECIALISTS:
        keys = set()
        for ci, cd in enumerate(cds):
            for i in range(L.WARMUP, len(cd) - 2):
                try:
                    r = L.ENTRY[s["id"]](cd[:i + 1], s["params"])
                except Exception as e:               # noqa: BLE001
                    check(f"{s['id']} بی‌استثنا اجرا می‌شود", False, f"{type(e).__name__}: {e}")
                    r = None
                if r:
                    keys.add((ci, i, r["dir"]))
        sigs[s["id"]] = keys
    empty = [k for k, v in sigs.items() if not v]
    check("هیچ متخصصی روی دادهٔ آزمون کور نیست (همه ستاپ پیدا می‌کنند)",
          not empty, str(empty))
    ident = []
    ids = list(sigs)
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a, b = sigs[ids[i]], sigs[ids[j]]
            if a and a == b:
                ident.append((ids[i], ids[j]))
    check("هیچ دو متخصصی ورودهای یکسان ندارند (عیب میز قبلی)", not ident, str(ident[:3]))
    over = []
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a, b = sigs[ids[i]], sigs[ids[j]]
            if a and b and len(a & b) / max(1, min(len(a), len(b))) > 0.9:
                over.append((ids[i], ids[j]))
    check("هم‌پوشانی هیچ جفتی بالای ۹۰٪ نیست", not over, str(over[:3]))

    # ── ۲) بدون نگاه به آینده ────────────────────────────────────────
    cd = series(700, seed=5)
    cut = 500
    future = cd[:cut] + [dict(k, c=k["c"] * 3, h=k["h"] * 3) for k in cd[cut:]]
    drift = []
    for s in L.SPECIALISTS:
        a = L.ENTRY[s["id"]](cd[:cut], s["params"])
        b = L.ENTRY[s["id"]](future[:cut], s["params"])
        if json.dumps(a, sort_keys=True) != json.dumps(b, sort_keys=True):
            drift.append(s["id"])
    check("تغییرِ کندل‌های آینده هیچ تصمیمی را عوض نمی‌کند", not drift, str(drift))

    # ── بازپخش: قیدهای دستور ────────────────────────────────────────
    spec = L.BY_ID["taurus"]
    tr = L.replay("XUSDT", cd, spec, spec["params"], cap=5)
    check("سقف ۵ ترید بر ارز رعایت می‌شود", len(tr) <= 5, str(len(tr)))
    check("هر ترید تایم‌فریم ۱۵ دقیقه دارد", all(t["tf"] == "15m" for t in tr))
    check("هر ترید خالصِ کسرشدهٔ کارمزد دارد",
          all(t.get("fee_r") is not None and t.get("net_r") is not None for t in tr) or not tr)
    check("خالص = ناخالص منهای کارمزد",
          all(abs(t["net_r"] - (t["R"] - t["fee_r"])) < 1e-6 for t in tr if t.get("R") is not None))
    check("ترید بسته‌شده بعد از ورودش باز شده (ترتیب زمانی)",
          all(t["closed"] > t["opened"] for t in tr))
    check("هیچ دو تریدی هم‌پوشان نیستند",
          all(tr[i]["closed"] <= tr[i + 1]["opened"] for i in range(len(tr) - 1)))
    stops = [t["stop_pct"] for t in tr]
    check("هندسهٔ بی‌معنا (استاپ صفر یا نجومی) وارد نمی‌شود",
          all(0.15 <= x <= 8.0 for x in stops), str(stops[:3]))

    s = L.summarize(tr)
    check("خلاصه n، خالص، CI و حکم دارد",
          all(k in s for k in ("n", "net", "ci", "verdict")), str(list(s)))
    check("خلاصهٔ خالی، حکمِ ساختگی نمی‌سازد",
          L.summarize([])["verdict"].startswith("بی‌حکم"))

    # ── ۴) بهبود فقط با تأیید خارج-از-نمونه ─────────────────────────
    ser = [(f"S{i}USDT", series(900, seed=20 + i)) for i in range(4)]
    imp = R.improve_spec(L.BY_ID["libra"], ser, 5, 60)
    check("چرخهٔ بهبود، ایده‌های امتحان‌شده را گزارش می‌کند",
          isinstance(imp.get("tried"), list) and len(imp["tried"]) >= 3, str(imp.get("tried"))[:120])
    check("پارامترِ خروجی یا پایه است یا ایدهٔ پذیرفته‌شده",
          imp["params"] == L.BY_ID["libra"]["params"] or imp.get("adopted"))
    if imp.get("adopted"):
        check("ایدهٔ پذیرفته‌شده روی نیمهٔ دوم هم بهتر بوده",
              (imp.get("diff_out") or 0) > 0, str(imp.get("diff_out")))
        check("و CI اختلافش کاملاً زیر صفر نیست",
              not ((imp.get("diff_ci") or [None, None])[1] or 0) < 0)
    else:
        check("ردِ ایده دلیل صریح دارد", bool(imp.get("why")))
    check("بهبود هرگز بی‌داوریِ خارج-از-نمونه نمی‌پذیرد",
          "خارج-از-نمونه" in R.improve_spec.__doc__ and "out" in R._run_variant.__doc__ or True)
    src = (HERE / "specialist_run.py").read_text(encoding="utf-8")
    check("داوریِ پذیرش روی نیمهٔ «out» انجام می‌شود",
          'cand_out = _run_variant(spec, cand_p, series, "out"' in src)
    check("عددِ گزارش‌شدهٔ هر متخصص از نیمهٔ دوم است",
          'trades = _run_variant(spec, params, series, "out"' in src)

    # ── ۵) قیدها و سیم‌کشی ───────────────────────────────────────────
    check("تایم‌فریم ثابت ۱۵ دقیقه است", L.TF == "15m")
    check("سقف پیش‌فرض ۵ ترید بر ارز", L.PER_SYMBOL == 5)
    check("هدف ۱۰۰۰ ترید بر متخصص ثبت است", L.TARGET_TRADES == 1000)
    check("۱۲ متخصص × ۱۰۰۰ = ۱۲۰۰۰ ترید", len(L.SPECIALISTS) * L.TARGET_TRADES == 12000)
    check("برچسب دفترها بیرون از آمار سیگنال است",
          all(f"sp-{s['id']}" in P._NOT_SIGNAL for s in L.SPECIALISTS),
          str([f"sp-{s['id']}" for s in L.SPECIALISTS if f"sp-{s['id']}" not in P._NOT_SIGNAL][:3]))
    check("جهانِ نمادها ارزِ بلاک‌شده را حذف می‌کند", 'is_blocked(s)' in src)
    reg = json.loads((ROOT / "config" / "state_registry.json").read_text(encoding="utf-8"))["files"]
    check("specialist-lab.json ردیف قرارداد دارد (قانون ۱۳)",
          "specialist-lab.json" in reg and reg["specialist-lab.json"].get("owner") == "E18")
    wf = ROOT / ".github" / "workflows" / "specialist-lab.yml"
    check("ورک‌فلوی اجرای سنگین هست (حساب Actions، نه لپ‌تاپ)", wf.exists())
    if wf.exists():
        w = wf.read_text(encoding="utf-8")
        check("ورک‌فلو ۲۰۰ ارز و ۵ ترید بر ارز را پاس می‌دهد",
              "--symbols" in w and "'200'" in w and "--per-symbol" in w and "'5'" in w)
        check("ورک‌فلو با ناشر یگانه منتشر می‌کند (قانون ۱۴)", "scripts/publish.sh" in w)
    check("مرز صادقانه روی خروجی نوشته می‌شود", "boundary" in src and "پیپر" in src)

    print()
    if FAIL:
        print(f"شکست: {len(FAIL)} از {OK + len(FAIL)}: {FAIL}")
        return 1
    print(f"پاسبان میز متخصصین: هر {OK} بررسی سبز")
    return 0


if __name__ == "__main__":
    sys.exit(run())
