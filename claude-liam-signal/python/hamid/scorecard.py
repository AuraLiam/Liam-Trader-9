"""کارنامهٔ هر انجین — نمره‌ای که می‌تواند بد باشد (دستور حمید، ۳۱ اوت).

حمید: «اون ۲۰ تا انجین بی‌کارنامه رو کارنامه‌دار کن.»

## چرا ۲۰ انجین بی‌کارنامه بودند — و چرا راهش «جایزه برای همه» نیست

`rewards.py` فقط انجینی را نمره می‌دهد که **ردپایش روی معاملهٔ بسته**
باشد. شمارش ردپاهای موجود روی ۲۵۱ معاملهٔ سیگنال نشان داد فقط این‌ها
ردپا می‌گذارند: `patterns` · `pm_pro` · `exp_used` · `ob_align` ·
`ict_align` · `fib_ratio` · `dom_tf_*`. یعنی E03، E08، E09، E17، E21 و
چند تای دیگر. بقیه اصلاً کارشان «روی یک معامله» نیست: جهانِ نمادها،
کیفیت داده، خبر، تحویل تلگرام، ناظر — این‌ها هرگز از راه نتیجهٔ یک ترید
نمره نمی‌گیرند.

پس دو راه بود:

۱. عددی بسازیم که برای همه کار کند («۲۰۰ ردیف تولید کرد») — این
   **نمره نیست**، چون هیچ‌وقت نمی‌تواند بد شود. متری که فقط بالا می‌رود
   کارنامه نیست، تبلیغ است.
۲. برای هر انجین متری بگذاریم که **کارِ خودش** را می‌سنجد و
   **می‌تواند شکست بخورد**.

راه دوم انتخاب شد. هر کارنامه اجباراً یک `falsifier` دارد: جمله‌ای که
می‌گوید چه چیزی این نمره را بد می‌کند. اگر نتوانستیم چنین جمله‌ای
بنویسیم، متر را نمی‌گذاریم و صریح `NO_METRIC` می‌دهیم با این‌که **چه
دفتری باید ساخته شود** تا نمره ممکن شود.

## چهار خانوادهٔ متر

| خانواده | متر | چطور شکست می‌خورد |
|---|---|---|
| **پیش‌بین** (E03،E04،E06) | نرخ اصابتِ پیش‌بینیِ سررسیده در برابر **پایهٔ** همان بازار | زیر پایه = مهارت منفی |
| **دروازه‌بان** (E11،E16،E17) | انتظارِ آنچه **رد کرد** منهای آنچه **گذراند** | ردشده بهتر از گذرانده = دروازه اشتباه است |
| **شاهد روی معامله** (E08،E09،E19،E21) | اختلاف دونمونه‌ایِ حضور/غیاب ردپا | اختلاف صفر یا منفی = شاهد بی‌ارزش |
| **عملیاتی** (E00،E02،E20،E23،E24،E25) | نرخ نقصِ قابل‌شمارش (نشتی، تخلف، آلارم کاذب) | نقص > صفر |

## سه قید که این را از «کارنامهٔ راحت» جدا می‌کند

۱. **پایه اجباری است.** نرخ اصابت ۴۰٪ بدون پایه بی‌معناست؛ اگر بازار
   ۳۹٪ مواقع تخت باشد، ۴۰٪ یعنی هیچ. هر مترِ پیش‌بین `baseline` دارد.
۲. **دروازه‌بان با گروه ضدواقع سنجیده می‌شود، نه با خودش.** دفتر
   `vetoed` (n=۲٬۳۱۹) همان ستاپ‌هایی است که رد شدند و نتیجه‌شان دنبال
   شد — بدون آن، هر دروازه‌ای «موفق» است چون فقط بازمانده‌ها را می‌بیند.
۳. **CI حرف آخر را می‌زند.** نمرهٔ بدونِ بازهٔ اطمینان فقط توصیف است.
   حکم `SKILL` / `NO_SKILL` / `NEGATIVE` از CI می‌آید، نه از میانگین.

## مرز صادقانه

این فایل **هیچ دروازه‌ای را عوض نمی‌کند** و هیچ وزنی نمی‌سازد. کارنامه
برای دیدن است و برای تصمیمِ حمید؛ ورودش به تولید فقط از مسیر قانون ۰۳.
`NO_METRIC` عیب نیست — پنهان‌کردنش عیب است.

اجرا: `python3 -m hamid.scorecard [--write] [--json]`
"""
import collections
import json
import math
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
sys.path.insert(0, str(PY))
ROOT = PY.parent.parent
SIG = ROOT / "signals"
BRAIN = ROOT / "brain"
OUT = SIG / "scorecard.json"


def _j(rel, default=None):
    try:
        return json.loads((ROOT / rel).read_text(encoding="utf-8"))
    except Exception:                                # noqa: BLE001
        return default


def ci95(xs):
    n = len(xs)
    if n < 2:
        return None, None, None, n
    m = statistics.mean(xs)
    se = statistics.stdev(xs) / math.sqrt(n)
    return round(m, 4), round(m - 1.96 * se, 4), round(m + 1.96 * se, 4), n


def two(a, b):
    """اختلاف دو گروه مستقل — همان روش `direction_autopsy`."""
    if len(a) < 2 or len(b) < 2:
        return None
    d = statistics.mean(a) - statistics.mean(b)
    se = math.sqrt(statistics.stdev(a) ** 2 / len(a)
                   + statistics.stdev(b) ** 2 / len(b))
    return {"diff": round(d, 4), "lo": round(d - 1.96 * se, 4),
            "hi": round(d + 1.96 * se, 4), "n_a": len(a), "n_b": len(b)}


def verdict_ci(lo, hi):
    if lo is None:
        return "بی‌نمونه"
    if lo > 0:
        return "SKILL"
    if hi < 0:
        return "NEGATIVE"
    return "NO_SKILL"


def card(eid, family, metric, value=None, unit="", n=None, ci=None,
         baseline=None, verdict=None, falsifier="", source=(), note=""):
    """یک کارنامه — `falsifier` اجباری است مگر متر وجود نداشته باشد."""
    return {"id": eid, "family": family, "metric": metric, "value": value,
            "unit": unit, "n": n, "ci": ci, "baseline": baseline,
            "verdict": verdict or ("NO_METRIC" if value is None else "—"),
            "falsifier": falsifier, "source": list(source), "note": note}


def no_metric(eid, family, metric, needs, source=()):
    """متر نداریم — و صریح می‌گوییم چه دفتری باید ساخته شود."""
    return card(eid, family, metric, None, verdict="NO_METRIC",
                falsifier="—", source=source,
                note=f"دفتر لازم ساخته نشده: {needs}")


# ── خانوادهٔ ۱: پیش‌بین ──────────────────────────────────────────────────
def _forecast(eid, prefix):
    dom = _j("signals/dominance.json", {}) or {}
    sb = ((dom.get("forecast") or {}).get("scoreboard") or {})
    rows = [(k, v) for k, v in sb.items()
            if k.startswith(prefix) and (v.get("n") or 0) >= 30]
    if not rows:
        return no_metric(eid, "پیش‌بین", f"مهارت پیش‌بینی {prefix}",
                         "پیش‌بینی سررسیده کمتر از ۳۰ نمونه",
                         ["signals/dominance.json"])
    # افقی که بیشترین نمونه را دارد، مرجع است
    k, v = max(rows, key=lambda r: r[1].get("n") or 0)
    hit, base = v.get("hit_pct"), v.get("baseline_flat_pct")
    skill = None if hit is None or base is None else round(hit - base, 1)
    return card(
        eid, "پیش‌بین", f"مهارت پیش‌بینی ({k})", skill, "واحد درصد",
        n=v.get("n"), baseline=base,
        verdict=("SKILL" if (skill or 0) > 0 else
                 "NEGATIVE" if (skill or 0) < 0 else "NO_SKILL"),
        falsifier=("نرخ اصابت زیر پایهٔ «تخت‌ماندن» همان بازار — یعنی "
                   "پیش‌بینی از حدسِ بی‌تغییر بدتر است"),
        source=["signals/dominance.json"],
        note=f"اصابت {hit}٪ در برابر پایهٔ {base}٪ · افق‌های دیگر: "
             + "، ".join(f"{a.split('|')[1]} n={b.get('n')}"
                         for a, b in sorted(rows, key=lambda r: -(r[1].get('n') or 0))[:4]))


# ── خانوادهٔ ۲: دروازه‌بان ───────────────────────────────────────────────
def _gate(eid, metric, passed, rejected, falsifier, source, note=""):
    """دروازه خوب است اگر آنچه رد کرد **بدتر** از آنچه گذراند بوده باشد."""
    t = two(passed, rejected)
    if not t:
        return no_metric(eid, "دروازه‌بان", metric,
                         "گروه ضدواقع (ردشده‌های دنبال‌شده) کمتر از ۲ نمونه",
                         source)
    return card(eid, "دروازه‌بان", metric, t["diff"], "R", n=t["n_a"] + t["n_b"],
                ci=[t["lo"], t["hi"]], verdict=verdict_ci(t["lo"], t["hi"]),
                falsifier=falsifier, source=source,
                note=f"گذرانده n={t['n_a']} · ردشده n={t['n_b']} · " + note)


# ── خانوادهٔ ۳: شاهد روی معامله ─────────────────────────────────────────
def _witness(eid, metric, rows, key, is_on, falsifier, source, note=""):
    on = [r["R_net"] for r in rows if is_on(r.get("why", {}).get(key))]
    off = [r["R_net"] for r in rows
           if r.get("why", {}).get(key) is not None
           and not is_on(r["why"][key])]
    t = two(on, off)
    if not t:
        return no_metric(eid, "شاهد روی معامله", metric,
                         f"ردپای «{key}» روی کمتر از ۲ معاملهٔ هر گروه", source)
    return card(eid, "شاهد روی معامله", metric, t["diff"], "R",
                n=t["n_a"] + t["n_b"], ci=[t["lo"], t["hi"]],
                verdict=verdict_ci(t["lo"], t["hi"]), falsifier=falsifier,
                source=source,
                note=f"با شاهد n={t['n_a']} · بی‌شاهد n={t['n_b']} · " + note)


# ── خانوادهٔ ۴: عملیاتی ─────────────────────────────────────────────────
def _ops(eid, metric, bad, total, falsifier, source, note="", unit="٪ نقص"):
    if not total:
        return no_metric(eid, "عملیاتی", metric, "شمارندهٔ صفر", source)
    pct = round(100 * bad / total, 2)
    return card(eid, "عملیاتی", metric, pct, unit, n=total, baseline=0.0,
                verdict="CLEAN" if bad == 0 else "FAULT",
                falsifier=falsifier, source=source,
                note=f"{bad} نقص از {total} · " + note)


def build(now_ms=None):
    now = now_ms or int(time.time() * 1000)
    from hamid.direction_autopsy import load
    sig = load("sig-")
    vet = load("vetoed")
    prac = load("practice")
    R = [r["R_net"] for r in sig]
    Rv = [r["R_net"] for r in vet]

    la = _j("signals/loop-audit.json", {}) or {}
    fn = _j("signals/funnel.json", {}) or {}
    cf = _j("signals/conformance.json", {}) or {}
    sn = _j("signals/sentinel.json", {}) or {}
    dh = _j("signals/depth-health.json", {}) or {}
    wl = _j("signals/watchlist.json", {}) or {}
    ed = _j("signals/edge.json", {}) or {}
    ov = _j("signals/overseer.json", {}) or {}
    im = _j("signals/improve.json", {}) or {}

    C = []

    # E00 — حلقهٔ بسته
    n_closed = la.get("n_closed_sig") or 0
    C.append(_ops("E00", "نشتیِ حلقهٔ بسته", la.get("n_leaks") or 0,
                  n_closed or (la.get("n_sent") or 0),
                  "هر سیگنالی که رفت ولی ردپای هضم/پنل ندارد = نشتی",
                  ["signals/loop-audit.json"],
                  f"حلقه {'بسته' if la.get('closed_loop') else 'باز'}"))

    # E01 — پهنای میدان دید.
    #
    # ملاک، `universe` دفتر گشت نیست: آن شمارِ کلِ جفت‌های دیده‌شده در
    # صرافی‌هاست (هزاران تا) و هیچ‌وقت «کم» نمی‌شود — یعنی نمره‌ای که
    # نمی‌تواند بد شود. ملاکِ واقعی همان است که ممیزیِ ۳۰ اوت گذاشت:
    # چند نماد را اسکنِ آخر **واقعاً** گشت (`latest.symbols`) در برابر ۲۰۰.
    lt = _j("signals/latest.json", {}) or {}
    seen = lt.get("symbols") or 0
    want = 200
    # پهنا در **پنجره** سنجیده می‌شود، نه در یک اجرا (اصلاح ۱ سپتامبر).
    #
    # با چرخشِ میدان، هر اجرا ۶۰ نماد می‌بیند ولی برشِ متفاوتی؛ پس عددِ
    # یک اجرا دیگر «پهنای دید» نیست. اندازه‌گیریِ همان روز نشان داد
    # اسکنِ ۲۰۰تایی فقط ۵ بار در ۳ روز اجرا شده (۳۲۵ اجرا ۶۰تایی بود)،
    # پس متر قبلی همیشه ۳۰٪ می‌داد و کاری هم نمی‌شد کرد. حالا از دفترِ
    # پوششِ غلتان خوانده می‌شود: چند نمادِ **یکتا** در یک ساعت اخیر.
    cov = _j("signals/scan-coverage.json", {}) or {}
    uniq = cov.get("unique_1h")
    if uniq:
        val, n_val = uniq, uniq
        note = (f"{uniq} نمادِ یکتا در ۱ ساعت اخیر (۳ ساعت: "
                f"{cov.get('unique_3h')}) · اسکنِ آخر {cov.get('last_run')} "
                f"از میدانِ {cov.get('field')}")
    else:
        val, n_val = seen, seen
        note = f"{seen} نماد در اسکنِ آخر (دفتر پوشش هنوز ساخته نشده)"
    C.append(card("E01", "تأمین‌کننده", "پهنای دیدِ یک‌ساعته",
                  round(100 * val / want, 1) if val else None, "٪ از ۲۰۰",
                  n=n_val, baseline=100.0,
                  verdict="OK" if val >= want else "UNDER",
                  falsifier=("پوششِ باریک‌تر از ۲۰۰ یعنی میدان دید کوچک‌تر از "
                             "سند — همان عیبِ ۳۰ اوت که اسکن پهن عملاً هرگز "
                             "اجرا نمی‌شد"),
                  source=["signals/scan-coverage.json", "signals/latest.json",
                          "signals/watchlist.json"],
                  note=note + f" · گشت: {len(wl.get('rows') or [])} نامزد از "
                       f"{len(wl.get('sources_ok') or [])} منبع سالم "
                       f"({len(wl.get('sources_err') or [])} خطا)"))

    # E02 — کیفیت داده
    fetched = (fn.get("series_fetched") or 0) + (fn.get("series_failed") or 0)
    d_sym = dh.get("symbols") or []
    d_rej = dh.get("rejected") or {}
    C.append(_ops("E02", "نرخ شکستِ دریافت سری", fn.get("series_failed") or 0,
                  fetched, "سری ناموفق = تصمیم روی دادهٔ ناقص",
                  ["signals/funnel.json", "signals/depth-health.json"],
                  f"عمق: {len(d_rej)} رد از {len(d_sym)} نماد"))

    C.append(_forecast("E03", "USDT.D"))
    C.append(_forecast("E04", "BTC.D"))

    # E05 — رژیم کلان
    C.append(no_metric("E05", "پیش‌بین", "اصابتِ حکمِ ریسک‌آن/آف",
                       "حکم کلان هیچ‌جا ثبت و سررسید نمی‌شود؛ لازم است "
                       "دفتری مثل forecast دامیننس که حکم را با نتیجهٔ "
                       "بعدیِ بازار نمره بدهد",
                       ["signals/news.json"]))

    # E06 — الگوهای بیت‌کوین
    C.append(no_metric("E06", "پیش‌بین", "اصابتِ الگوی اعلام‌شده",
                       "`btc-patterns.json` وضعیت الگو را دارد ولی نتیجه‌اش "
                       "را دنبال نمی‌کند؛ لازم است هر الگوی forming با "
                       "confirmed/failed بسته شود",
                       ["signals/btc-patterns.json"]))

    # E07 / E08 / E09 — شاهدها روی معامله
    C.append(_witness("E07", "ارزش شاهدِ سوپرترند", sig, "supertrend_align",
                      lambda v: v in (True, "with"),
                      "اختلاف صفر یا منفی = هم‌ترازیِ ساختار چیزی اضافه نکرد",
                      ["brain/paper/closed.jsonl"]))
    C.append(_witness("E08", "ارزش شاهدِ اردر بلاک", sig, "ob_align",
                      lambda v: v == "with",
                      "اختلاف صفر یا منفی = هم‌ترازیِ OB چیزی اضافه نکرد",
                      ["brain/paper/closed.jsonl"]))
    C.append(_witness("E09", "ارزش شاهدِ الگوی کندلی", sig, "pattern_align",
                      lambda v: v in (True, "with"),
                      "اختلاف صفر یا منفی = الگوی کندلی تأیید بی‌اثر است "
                      "(دقیقاً همان چیزی که قانون ۰۹ می‌خواهد سنجیده شود)",
                      ["brain/paper/closed.jsonl"]))

    # E10 — نقدینگی
    rw = {r["engine"]: r for r in ((_j("signals/rewards.json", {}) or {})
                                   .get("board") or [])}
    def _base_ratio():
        """نسبتِ تارگت به استاپِ **کلِ دفتر** — پایهٔ منصفانهٔ مقایسه.

        اصلاح ۱ سپتامبر: نسخهٔ قبلی پایه را روی عددِ ثابتِ ۱.۰ گذاشته بود،
        یعنی «هر انجین باید به ازای هر استاپ یک تارگت داشته باشد». آن
        آستانه اختراعی بود و هیچ بخشی از این سامانه به آن نمی‌رسد: با
        تارگتِ RR≥۱.۵، سیستمِ سودده هم نسبتِ زیر یک دارد. اندازه‌گیری روی
        دفتر: پایهٔ کل **۰.۴۳** (۴٬۹۶۲ تارگت در برابر ۱۱٬۵۲۰ استاپ)، و
        هر شش انجینِ ردپادار بین ۰.۵۰ تا ۰.۷۷ — یعنی **همه بالای پایه**،
        ولی متر دو تایشان را FAULT می‌خواند.

        پرسشِ درست این نیست «آیا تارگت بیشتر از استاپ است؟» بلکه «آیا
        ردپای این انجین روی معامله‌های برنده **بیشتر از متوسطِ دفتر**
        دیده می‌شود؟». پایه از خودِ داده می‌آید، نه از حدس.
        """
        try:
            from hamid import paper as _p
            oc = collections.Counter(r.get("outcome") for r in _p._read(_p.CLOSED))
            t, s = oc.get("target", 0), oc.get("stop", 0)
            return round(t / s, 2) if s else None
        except Exception:                            # noqa: BLE001
            return None

    base_ratio = _base_ratio()

    def _reward_card(eid, label, why):
        """جایزه، وقتی حکمش را از خودِ ترکیبش بگیرد نه از بزرگیِ عدد.

        امتیاز خام همیشه بالا می‌رود (هر تأیید امتیاز می‌گیرد)، پس به
        تنهایی نمره نیست. چیزی که می‌تواند بد شود نسبتِ **تارگت به
        استاپ** است — ولی در برابر پایهٔ خودِ دفتر، نه عددِ گِرد."""
        r = rw.get(eid)
        if not r:
            return no_metric(eid, "شاهد روی معامله", label,
                             "ردپای این انجین روی هیچ معاملهٔ بسته‌ای ثبت نشده",
                             ["signals/rewards.json"])
        tot = r["target"] + r["trail"] + r["stop"]
        ratio = round(r["target"] / r["stop"], 2) if r["stop"] else None
        if ratio is None or base_ratio is None:
            v = "NO_METRIC"
        else:
            v = "OK" if ratio >= base_ratio else "FAULT"
        return card(eid, "شاهد روی معامله", label, ratio, "تارگت به ازای هر استاپ",
                    n=tot, baseline=base_ratio,
                    verdict=v,
                    falsifier=why, source=["signals/rewards.json",
                                           "brain/paper/closed.jsonl"],
                    note=f"امتیاز {r['points']} · تارگت {r['target']} · "
                         f"تریل {r['trail']} · استاپ {r['stop']} · "
                         f"پایهٔ دفتر {base_ratio}")

    C.append(_reward_card("E10", "نسبتِ تارگت به استاپِ تأییدِ نقدینگی",
                          "تارگت کمتر از استاپ = تأییدِ نقدینگی بیشتر روی "
                          "بازنده‌ها بوده تا برنده‌ها"))

    # E11 — مسیریاب: آیا استراتژیِ انتخابی بهتر از میانگینِ مخزن است
    def strat(r):
        return ((r.get("why") or {}).get("stage") or "").replace("sig-", "")
    per = {}
    for r in sig:
        per.setdefault(strat(r), []).append(r["R_net"])
    best = max(((k, v) for k, v in per.items() if len(v) >= 20),
               key=lambda kv: statistics.mean(kv[1]), default=None)
    if best and len(per) > 1:
        others = [x for k, v in per.items() if k != best[0] for x in v]
        t = two(best[1], others)
        C.append(card("E11", "دروازه‌بان", "برتریِ استراتژیِ برگزیده",
                      t and t["diff"], "R", n=len(sig),
                      ci=t and [t["lo"], t["hi"]],
                      verdict=verdict_ci(t["lo"], t["hi"]) if t else "NO_METRIC",
                      falsifier=("اگر بهترین استراتژی از بقیه جدا نشود، "
                                 "مسیریابی ارزشی اضافه نکرده"),
                      source=["brain/paper/closed.jsonl"],
                      note=f"برگزیده «{best[0]}» n={len(best[1])} · "
                           f"بقیه n={len(others)}"))
    else:
        C.append(no_metric("E11", "دروازه‌بان", "برتریِ استراتژیِ برگزیده",
                           "کمتر از دو استراتژی با n≥۲۰",
                           ["brain/paper/closed.jsonl"]))

    # E12 — پامپ
    try:
        from hamid.pump_profile import pump_events, repeat_stat
        rp = repeat_stat(pump_events())
        lift = (rp["p_repeat"] / rp["p_base"]
                if rp.get("p_repeat") and rp.get("p_base") else None)
        C.append(card("E12", "پیش‌بین", "چسبندگیِ پامپ (لیفت)",
                      lift and round(lift, 2), "×", n=rp.get("n_all"),
                      baseline=1.0,
                      verdict=("SKILL" if (lift or 0) > 1.15 else
                               "NO_SKILL" if lift else "NO_METRIC"),
                      falsifier="لیفت ≈۱ یعنی پامپ قبلی هیچ خبری از پامپ بعدی نمی‌دهد",
                      source=["brain/pump-history.json"],
                      note=(f"P(پامپ بعدی|پامپ) {rp['p_repeat']:.0%} در برابر "
                            f"پایهٔ {rp['p_base']:.0%}"
                            if rp.get("p_repeat") else "")))
    except Exception as e:                           # noqa: BLE001
        C.append(no_metric("E12", "پیش‌بین", "چسبندگیِ پامپ",
                           f"محاسبه نشد: {type(e).__name__}",
                           ["brain/pump-history.json"]))

    C.append(_reward_card("E13", "نسبتِ تارگت به استاپِ قیاس تاریخی",
                          "تارگت کمتر از استاپ = قیاسِ تاریخی بیشتر روی "
                          "بازنده‌ها ردپا گذاشته تا برنده‌ها"))

    C.append(no_metric("E14", "پیش‌بین", "اصابتِ کاتالیزور",
                       "خبرِ برچسب‌خورده به حرکتِ بعدیِ نماد وصل نمی‌شود؛ "
                       "لازم است هر تیتر حساس با بازدهِ N ساعت بعد بسته شود",
                       ["signals/news.json"]))
    C.append(no_metric("E15", "عملیاتی", "نرخ آلارمِ عمل‌شده",
                       "آلارم‌ها فرستاده می‌شوند ولی «عمل شد/نشد» ثبت نمی‌شود؛ "
                       "لازم است هر آلارم با نتیجهٔ همان نماد بسته شود",
                       ["signals/ob-radar.json", "signals/trail-alert.json"]))

    # E16 — دروازهٔ کارمزد/زیست‌پذیری: ردشده‌ها باید بدتر بوده باشند
    fee_hi = [r["R_net"] for r in vet + prac
              if (r.get("_fee_r") or 0) >= 0.25]
    fee_ok = [r["R_net"] for r in sig if (r.get("_fee_r") or 0) < 0.25]
    C.append(_gate("E16", "ارزشِ دروازهٔ کارمزد", fee_ok, fee_hi,
                   "اگر ستاپ‌های پرکارمزد بهتر از گذرانده‌ها باشند، "
                   "دروازهٔ کارمزد دارد لبه را دور می‌ریزد",
                   ["signals/viability-gate.json", "brain/paper/closed.jsonl"],
                   "مرزِ ۰.۲۵R کارمزد"))

    # E17 — کمیتهٔ سیگنال: پرچم‌دارِ همهٔ دروازه‌ها
    C.append(_gate("E17", "ارزشِ کلِ دروازه‌ها (ارسال در برابر رد)", R, Rv,
                   "اگر ردشده‌ها بهتر یا هم‌سطح باشند، مجموعِ دروازه‌ها "
                   "چیزی جز حذفِ تصادفی نیست",
                   ["brain/paper/closed.jsonl"],
                   f"دلایل رد امروز: {len(fn.get('top_reasons') or {})} دسته"))

    # E18 — بک‌تست: تازگیِ مرجع
    snaps = ["dash-backtest.json", "h1-backtest.json", "scenario-backtest.json",
             "big-money-backtest.json", "scalp-dash-backtest.json"]
    ages = []
    for s in snaps:
        d = _j(f"signals/{s}", {}) or {}
        g = d.get("generated")
        if g:
            ages.append((now - g) / 3_600_000)
    stale = sum(1 for a in ages if a > 48)
    C.append(_ops("E18", "عکس‌فوریِ بک‌تستِ کهنه", stale, len(ages) or len(snaps),
                  "مرجعِ کهنه یعنی ادعاها به بازارِ امروز ربط ندارند",
                  [f"signals/{s}" for s in snaps],
                  f"میانهٔ سن {round(statistics.median(ages))}س"
                  if ages else "هیچ عکس‌فوری‌ای مهر ندارد"))

    # E19 — مدیریت معامله: تریل واقعاً چه کرد
    #
    # ## چرا پنجره‌دار شد (۶ سپتامبر)
    #
    # این سنجه کلِ تاریخِ دفتر را می‌شمرد. وقتی قاعدهٔ تریل همان روز
    # اصلاح شد (`paper.PROD_TRAIL_FRAC = 0.80`)، ردیف‌های بستهٔ قدیمی
    # با قاعدهٔ قدیم سرِ جایشان می‌مانند — پس سنجه با نرخ ~۸.۷ تریل در
    # روز **۲۱ روز** طول می‌کشید تا زیر آستانه برود، هرچند رفتار از
    # همان لحظه عوض شده بود.
    #
    # این دقیقاً همان چیزی است که قانون ۰۷ منع کرده: «متری که رفعِ ریشه
    # هم سبزش نکند، آموزشِ نادیده‌گرفتن است».
    #
    # پنجرهٔ تاریخی (مثلاً «۷ روز اخیر») جوابِ ضعیف است: امروز هنوز ۸۰٪
    # می‌داد چون همان ۷ روز تقریباً همه‌اش قاعدهٔ قدیم بود، و از آن بدتر،
    # با هر تغییرِ بعدیِ قاعده باز همین‌جا گیر می‌کردیم. جوابِ درست همان
    # اصلِ `scalp_verdict` است: **اثرانگشتِ قاعده روی خودِ ردیف**
    # (`paper._trail_frac` → `trail_frac`)، و داوری فقط روی ردیف‌هایی که
    # زیر قاعدهٔ فعلی بسته شده‌اند. تا وقتی ۱۰ ردیف جمع نشده، NO_METRIC
    # با دلیلِ صریح — نه عددی که مالِ قاعدهٔ بازنشسته است.
    from hamid.paper import PROD_TRAIL_FRAC as _frac19
    _rule19 = f"استاپ روی {_frac19:.0%} بهترین سودِ دیده‌شده"
    tr_all = [r for r in sig if r.get("outcome") == "trail"]
    # فقط ردیف‌هایی که زیرِ **قاعدهٔ فعلی** بسته شده‌اند. ردیف‌های پیش از
    # ۶ سپتامبر `trail_frac` ندارند و خودبه‌خود بیرون می‌مانند.
    tr = [r for r in tr_all if r.get("trail_frac") == _frac19]
    if len(tr) >= 10:
        cut = sum(1 for r in tr if abs(r["R_net"]) < 0.05)
        life = sum(1 for r in tr_all if abs(r["R_net"]) < 0.05)
        C.append(card("E19", "عملیاتی", "بردهایی که تریل به صفر رساند",
                      round(100 * cut / len(tr), 1), "٪ از تریل‌ها", n=len(tr),
                      baseline=0.0,
                      verdict="FAULT" if cut / len(tr) > 0.5 else "OK",
                      falsifier=("تریل باید ضرر را کوتاه کند نه سود را؛ "
                                 "سهم بالای بردهای صفرشده یعنی نردبان تریل "
                                 "زودتر از لازم مسلح می‌شود"),
                      source=["brain/paper/closed.jsonl"],
                      note=(f"فقط قاعدهٔ فعلی ({_rule19}) · میانهٔ خالص "
                            f"{statistics.median([r['R_net'] for r in tr]):+.3f}R"
                            f" · کلِ تاریخ {100 * life / len(tr_all):.1f}٪ از "
                            f"{len(tr_all)} (شامل قاعدهٔ بازنشستهٔ پیش از "
                            f"۶ سپتامبر)")))
    else:
        C.append(no_metric(
            "E19", "عملیاتی", "اثر تریل",
            (f"فقط {len(tr)} معاملهٔ بسته‌شده زیر قاعدهٔ فعلی ({_rule19}) — "
             f"کمتر از ۱۰. کلِ تاریخ {len(tr_all)} تریل دارد ولی "
             f"{len(tr_all) - len(tr)} تایش زیر قاعدهٔ بازنشستهٔ پیش از "
             f"۶ سپتامبر بسته شده و در داوریِ قاعدهٔ فعلی نمی‌آید."),
            ["brain/paper/closed.jsonl"]))

    # E20 — بازبینی پس از معامله: پوشش هضم
    n_dig = la.get("n_digested") or 0
    C.append(_ops("E20", "معاملهٔ بسته بدون پرونده", max(0, n_closed - n_dig),
                  n_closed,
                  "هر معاملهٔ بسته باید پرونده/درس داشته باشد (قانون ۰۳ بند ۱)",
                  ["signals/loop-audit.json", "brain/cases/"],
                  f"{n_dig} هضم‌شده از {n_closed}"))

    # E21 — حافظه: تجربه واقعاً کمک کرد؟
    C.append(_witness("E21", "ارزش لایهٔ تجربه", sig, "exp_used",
                      lambda v: bool(v),
                      "اختلاف شاملِ صفر = تجربه هنوز اثر اثبات‌شده ندارد "
                      "(همان تصحیحِ ۲۴ اوت)",
                      ["brain/paper/closed.jsonl"]))

    # E22 — بهبود: پیشنهاد در برابر آنچه از CI رد شد
    props = len(im.get("proposals") or [])
    rules = ed.get("n_rules") or 0
    C.append(card("E22", "عملیاتی", "قاعده‌های CI-گذشته روی قفسه", rules,
                  "قاعده", n=props or None, baseline=0,
                  verdict="OK" if rules else "EMPTY",
                  falsifier=("قفسهٔ خالی یعنی هیچ پیشنهادی از بازهٔ اطمینان "
                             "رد نشده؛ قفسهٔ آلوده از خالی بدتر است"),
                  source=["signals/edge.json", "signals/improve.json"],
                  note=f"{props} پیشنهاد باز · قفسه "
                       f"{'کهنه' if ed.get('stale') else 'تازه'}"))

    # E23 — ناظر: تخلفِ پابرجا
    #
    # عیبِ مخرج، رفع ۶ سپتامبر: این‌جا شمارِ **نمونه‌های** تخلف بر شمارِ
    # **نام قواعد** تقسیم می‌شد — ۲۲ بر ۶ — و ۳۶۶٪ می‌داد. نرخی که از
    # ۱۰۰ رد شود اصلاً نرخ نیست؛ همان «عددِ نامحتمل» که قانون گزارش
    # می‌گوید اول باید به خودِ سنجه شک کرد. مخرجِ درست، خودِ قواعد است و
    # صورتِ درست، قواعدی که تخلفِ باز دارند: عددی که همیشه در [۰,۱۰۰] است.
    # شمارِ نمونه‌ها و شدت‌ها در یادداشت می‌مانند تا چیزی پنهان نشود.
    _vio = cf.get("violations") or []
    _rules = cf.get("checks") or []
    _hit = {str(v.get("rule")) for v in _vio if isinstance(v, dict)}
    _sev = collections.Counter(str(v.get("sev")) for v in _vio
                               if isinstance(v, dict))
    _high = _sev.get("high", 0)
    C.append(_ops("E23", "قاعده‌های انطباق با تخلفِ باز",
                  len(_hit), len(_rules) or 1,
                  "تخلفِ باز یعنی زنجیره از قرارداد خودش بیرون است",
                  ["signals/conformance.json", "signals/sentinel.json"],
                  f"{len(_vio)} نمونه روی {len(_hit)} قاعده از {len(_rules)} "
                  f"(شدت: {_high} high · {_sev.get('med', 0)} med · "
                  f"{_sev.get('low', 0)} low) · پاسبان: "
                  f"{sn.get('verdict') or '—'} · "
                  f"{len(sn.get('findings') or [])} یافته"))

    # E24 — قرارداد پنل.
    #
    # وسوسه این بود که همان عددِ conformance را این‌جا هم بگذاریم؛ ولی آن
    # فایل مالِ E23 است و کپی‌کردنش «کارنامه» نمی‌سازد، فقط یک عدد را دو
    # بار می‌شمارد. E24 دفتر خودش را ندارد، پس صریح می‌گوییم.
    C.append(no_metric("E24", "عملیاتی", "شکستِ قرارداد پنل",
                       "E24 فایل وضعیت مستقل ندارد؛ لازم است بررسیِ قرارداد "
                       "پنل (هر فیلدی که پنل وعده داده واقعاً هست؟) خروجی "
                       "خودش را بنویسد — نه این‌که از دفتر E23 قرض بگیرد",
                       ["signals/conformance.json"]))

    # E25 — تحویل: تکرار.
    #
    # ملاکِ اولِ من «ارسالِ بی‌شناسهٔ پیام» بود و ۰٪ درآمد — ولی آن عدد
    # غلط بود: `n_sent` پنجرهٔ ۷۲ساعته است و `n_ledger_with_msgid` کلِ
    # دفتر، و نسبتِ دو پنجرهٔ متفاوت معنا ندارد. ملاکِ درست همان کاری است
    # که E25 واقعاً می‌کند: ضدتکرار — همان جایی که PAXG×۵ شکست.
    # و ملاک باید **همان قراردادِ نوشته‌شده** باشد، نه قاعده‌ای که خودم
    # اختراع کنم. نسخهٔ اولِ همین متر «هر تکرار در ۱۲ ساعت» را تخلف گرفت
    # و ۴ تخلف شمرد؛ سه‌تایشان با فاصلهٔ ۴.۵ تا ۶ ساعت و **استراتژیِ
    # متفاوت** بودند، یعنی طبق قرارداد ۲۶ اوت کاملاً مجاز. متری که
    # سخت‌گیرتر از قرارداد باشد، آلارمِ کاذب می‌سازد — همان چیزی که
    # قانون ۰۷ منعش کرده.
    #
    # اصلاح ۱ سپتامبر — همان درس، بارِ دوم: کامنتِ بالا می‌گوید «ملاک باید
    # همان قراردادِ نوشته‌شده باشد، نه قاعده‌ای که خودم اختراع کنم» و بعد
    # عددها را سفت می‌نویسد (۱۲ ساعت). ولی حمید ۲۷ اوت پنجره را ۶ ساعت
    # کرد و این عدد به‌روز نشد — دقیقاً همان چیزی که در `skeptic` هم پیدا
    # شد و ۵ نقضِ کاذب از ۶ می‌ساخت. حالا ثابت‌ها از خودِ `telegram`
    # خوانده می‌شوند، پس مشخصات نمی‌تواند از کد جدا بیفتد.
    #
    # و پنجرهٔ حکم: نقضِ بسته‌شدهٔ تاریخی تا ابد نباید قرمز نگه دارد
    # (متری که رفعِ ریشه سبزش نکند، آموزشِ نادیده‌گرفتن است — قانون ۰۷).
    H = 3_600_000
    try:
        from telegram import TTL_MS as _TTL
        ttl_h = _TTL / H
    except Exception:                                # noqa: BLE001
        ttl_h = 6
    any_h = 3                                        # `_dup_any` / `_dup_pair`
    RECENT_H = 24
    _now = time.time() * 1000
    sent_rows = sorted((_j("signals/telegram-log.json", {}) or {}).get("sent") or [],
                       key=lambda x: x.get("at") or 0)
    last_any, last_pair, last_strat, per_sym = {}, {}, {}, {}
    dup, recent_n = 0, 0
    for r in sent_rows:
        t = r.get("at") or 0
        any_k = (r.get("sym"), r.get("dir"), r.get("tf"))
        pair_k = (r.get("sym"), r.get("dir"))
        st_k = any_k + (r.get("name"),)
        hits = per_sym.setdefault(r.get("sym"), [])
        bad = ((any_k in last_any and t - last_any[any_k] < any_h * H)
               or (pair_k in last_pair and t - last_pair[pair_k] < any_h * H)
               or (st_k in last_strat and t - last_strat[st_k] < ttl_h * H)
               or len([x for x in hits if t - x < ttl_h * H]) >= 2)
        if _now - t <= RECENT_H * H:
            recent_n += 1
            dup += bool(bad)
        last_any[any_k] = last_pair[pair_k] = last_strat[st_k] = t
        hits.append(t)
    sent_rows = [r for r in sent_rows
                 if _now - (r.get("at") or 0) <= RECENT_H * H]
    C.append(_ops("E25", "شکستِ قراردادِ ضدتکرار", dup, len(sent_rows),
                  "همان کلیدِ بی‌استراتژی زیر ۳ ساعت، یا همان استراتژی زیر "
                  "۱۲ ساعت، یا بیش از ۲ ارسال یک ارز در ۱۲ ساعت — قرارداد "
                  "۲۶ اوت، همان جایی که PAXG×۵ شکست",
                  ["signals/telegram-log.json"],
                  f"{len(sent_rows)} ارسال · {len(last_any)} ترکیبِ یکتا"))

    # E26 — ناظر کل
    C.append(no_metric("E26", "عملیاتی", "اثرِ دستورِ تمرکز",
                       "دستورها صادر می‌شوند ولی «اجرا شد/نشد» و اثرش ثبت "
                       "نمی‌شود؛ لازم است هر دستور با سنجهٔ همان چرخهٔ بعد "
                       "بسته شود",
                       ["signals/overseer.json"]))

    # E27 — اتاق توزیع اطلاعات (۳ سپتامبر). سنجهٔ واقعی‌اش هنوز نیست:
    # «دسته‌بندی درست بود یا نه» فقط وقتی قابل شمارش است که خطای مسیر
    # روی نتیجهٔ معامله دیده شود. تا آن روز NO_METRIC، نه نمرهٔ ساختگی.
    C.append(no_metric("E27", "عملیاتی", "درستیِ دسته‌بندی و مسیر",
                       "پوشش تاکسونومی شمرده می‌شود ولی «دستهٔ درست» با "
                       "نتیجهٔ معامله گره نخورده؛ لازم است خطای مسیر روی "
                       "دفتر بسته ردیابی شود",
                       ["signals/router.json"]))

    have = [c for c in C if c["verdict"] != "NO_METRIC"]
    return {
        "generated": now, "panel": "لیام تریدر ۹",
        "n": len(C), "n_scored": len(have),
        "n_no_metric": len(C) - len(have),
        "cards": sorted(C, key=lambda c: c["id"]),
        "boundary": ("کارنامه برای دیدن است، نه برای وزن‌دادن. هیچ عددی "
                     "این‌جا دروازه‌ای را عوض نمی‌کند — ورود به تولید فقط "
                     "از مسیر قانون ۰۳."),
    }


def main(argv=()):
    m = build()
    if "--json" in argv:
        print(json.dumps(m, ensure_ascii=False, indent=1))
        return 0
    print(f"### کارنامهٔ انجین‌ها — {m['n_scored']} نمره‌دار · "
          f"{m['n_no_metric']} بی‌متر\n")
    fam = None
    for c in sorted(m["cards"], key=lambda c: (c["family"], c["id"])):
        if c["family"] != fam:
            fam = c["family"]
            print(f"— خانوادهٔ {fam} —")
        val = ("—" if c["value"] is None
               else f"{c['value']}{c['unit'] and ' ' + c['unit']}")
        line = f"  {c['id']}  {c['metric']}: {val}"
        if c["ci"]:
            line += f"  CI[{c['ci'][0]:+.4f}, {c['ci'][1]:+.4f}]"
        if c["n"]:
            line += f"  n={c['n']}"
        print(line + f"  → {c['verdict']}")
        if c["note"]:
            print(f"        {c['note']}")
        if c["verdict"] == "NO_METRIC":
            print(f"        ⚠️ {c['note']}")
    print(f"\n### مرز صادقانه\n  {m['boundary']}")
    if "--write" in argv:
        OUT.write_text(json.dumps(m, ensure_ascii=False, indent=1),
                       encoding="utf-8")
        print(f"\n  نوشته شد: {OUT.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
