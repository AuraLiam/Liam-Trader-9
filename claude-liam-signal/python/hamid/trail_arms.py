"""داوریِ بازوهای تریل — قاعدهٔ توقف، ثبت‌شده پیش از دیدن داده.

## چرا این آزمایش هست

اندازه‌گیریِ ۱ سپتامبر روی ۲۵۶ معاملهٔ بستهٔ سیگنال:

| نتیجه | n | خالص |
|---|---|---|
| تارگت | ۳۰ | +۱.۳۵۵R |
| **تریل** | **۱۳۴** | **+۰.۰۶۶R — و ۸۴٪ دقیقاً صفر** |
| استاپ | ۸۱ | −۱.۲۶۵R |

معامله‌های تریل‌شده به‌طور میانه **MFE ‎+۰.۸۵۰R دیدند و ‎+۰.۰۰۰R
برداشتند**. نردبانِ ۱۲ اوت در ⅓ مسیر روی سربه‌سرِ کارمزددار مسلح
می‌شود، پس هر برگشتی به‌ساخت صفر می‌بندد.

## چرا با بازپخش تمامش نکردیم

وسوسه این بود که با `mfe/mae` بازپخش کنیم و همان‌جا حکم بدهیم. اولین
اجرا همین را کرد و گفت «نگه‌داشت ۸۰٪ قله، ‎+۰.۴۷R بهتر از فعلی، CI
بالای صفر». **آن عدد قابل استناد نیست**: بازپخشِ دونقطه‌ای پولبکِ
میانی را نمی‌بیند، و تریلِ تنگ‌تر دقیقاً از همین نابینایی سود می‌برد.
اندازهٔ خطا در `trail_lab.bias_demo()` عددی است: ‎+۰.۴R روی **یک**
پولبک. ترتیبِ ۸۰٪>۶۵٪>۵۰٪ همان چیزی است که این خطا پیش‌بینی می‌کند،
پس شاهدِ قاعده نیست.

## طرح — A/B جفتی روی همان ستاپ

`paper.mirror_trail_arms` هر ستاپِ سیگنال‌شدهٔ باز را با دو نردبانِ
دیگر هم باز می‌کند. همان نماد، ورود، استاپ، تارگت و لحظه؛ تنها متغیر
نردبان. پس اختلاف مستقیماً به نردبان نسبت داده می‌شود.

- `exp-trail-g65` — نگه‌داشت ۶۵٪ قله
- `exp-trail-g80` — نگه‌داشت ۸۰٪ قله

## قاعدهٔ توقف — همین حالا ثبت می‌شود، نه بعد از دیدن اعداد

| حکم | شرط |
|---|---|
| **PROMOTE** | CI اختلافِ جفتیِ **خالص از کارمزد** کاملاً بالای صفر، روی n ≥ ۲۰۰ جفت → فقط *پیشنهاد*؛ ورود به تولید تأیید صریح حمید می‌خواهد (قانون ۰۳/۱۲) |
| **REJECT** | CI کاملاً زیر صفر روی n ≥ ۴۰۰ جفت |
| **UNDECIDED** | بقیه — با برآوردِ «چند جفت دیگر تا تصمیم‌پذیری» |

سه قید که این را از «حکمِ راحت» جدا می‌کند:

۱. **دو بازو یعنی دو آزمون.** آستانه با Šidák تصحیح می‌شود (z=۲.۲۴ به‌جای
   ۱.۹۶)، وگرنه با دو قرعه‌کشی شانسِ «برندهٔ تصادفی» دو برابر است.
۲. **معیار خالص است.** ناخالصِ بهتر بی‌معنی است اگر کارمزد بخوردش —
   همان جایی که میز ۱ دقیقه باخت.
۳. **حکم به هندسه گره خورده.** اثرانگشتِ نسبت‌ها روی حکم ثبت می‌شود؛
   عوض‌کردنِ هر نسبت یعنی دفترِ حکم از صفر.

اجرا: `python3 -m hamid.trail_arms [--json] [--write]`
"""
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
OUT = ROOT / "signals" / "trail-arms.json"

Z = 2.2414              # Šidák برای ۲ آزمون، دوطرفه، آلفا ۰.۰۵
N_PROMOTE = 200
N_REJECT = 400
HALF_WIDTH_TARGET = 0.05   # نیم‌پهنای هدف برای برآوردِ نمونهٔ لازم


def fingerprint():
    from hamid import paper
    return "·".join(f"{k}={v}" for k, v in sorted(paper.TRAIL_ARMS.items()))


# ── رژیم — تقسیمِ توصیفی، نه دروازه ──────────────────────────────────────
#
# شاهدِ بیرونی (جست‌وجوی ۱ سپتامبر، منابع در `brain/library/queue.jsonl`):
# ادعا می‌شود تریل فقط در بازارِ رونددار مثبت است و در بازارِ برگشتی
# ارزشِ منفی دارد. آن ادعا **راستی‌آزمایی نشده** و طبق قانون ۱۱ شاهدی با
# ~۳۰٪ خطاست، نه دروازه. ولی یک شکافِ واقعی در طراحی را نشان داد:
# بازوهای من رژیم‌کور بودند، و میانگین‌گیری روی دو رژیمِ متضاد می‌تواند
# اثرِ قوی را به «بی‌اثر» تبدیل کند. قانون ۰۳ هم از قبل regime split
# می‌خواست. پس رژیم فقط **ثبت و گزارش** می‌شود؛ حکم همچنان از نمونهٔ
# کل می‌آید و هیچ آستانه‌ای بر پایهٔ رژیم عوض نمی‌شود.
def _regime(r):
    w = r.get("why") or {}
    t = w.get("trend_4h")
    d = r.get("dir")
    if t in ("up", "down") and d in ("LONG", "SHORT"):
        return "با روند" if (t == "up") == (d == "LONG") else "خلاف روند"
    return "رنج/نامعلوم"


def _net(r):
    if r.get("R") is None:
        return None
    fee = r.get("fee_r")
    return r["R"] - (fee if fee is not None else 0.0)


def pairs():
    """جفت‌های (پایه، بازو) روی همان ستاپ — کلید: نماد+ورود+لحظهٔ باز شدن.

    خروجی: {tag: {"sig": [...], "practice": [...]}} — دو جمعیت جدا
    می‌مانند؛ قاطی‌کردنشان همان کاری است که قانون ۰۹ منع کرده.
    """
    from hamid import paper
    rows = paper._read(paper.CLOSED)
    base, arms = {}, {t: {} for t in paper.TRAIL_ARMS}
    for r in rows:
        st = (r.get("why") or {}).get("stage") or ""
        k = (r.get("sym"), r.get("entry"), r.get("opened"))
        if st.startswith("sig-") or st == "practice":
            base[k] = r
        elif st in arms:
            arms[st][k] = r
    out = {}
    for tag, d in arms.items():
        got = {"sig": [], "practice": []}
        for k, arm in d.items():
            b = base.get(k)
            if not b:
                continue
            nb, na = _net(b), _net(arm)
            if nb is None or na is None:
                continue
            bw = b.get("why") or {}
            bst = bw.get("stage") or ""
            got["practice" if bst == "practice" else "sig"].append(
                {"key": k, "base": round(nb, 4), "arm": round(na, 4),
                 "diff": round(na - nb, 4), "regime": _regime(b),
                 "base_out": b.get("outcome"), "arm_out": arm.get("outcome")})
        out[tag] = got
    return out


def _ci(xs):
    n = len(xs)
    if n < 2:
        return None, None, None, n
    m = statistics.mean(xs)
    sd = statistics.stdev(xs)
    if sd == 0:
        return round(m, 4), round(m, 4), round(m, 4), n
    se = sd / math.sqrt(n)
    return round(m, 4), round(m - Z * se, 4), round(m + Z * se, 4), n


def _need(xs):
    """چند جفت دیگر تا نیم‌پهنای هدف — برآورد، نه وعده."""
    if len(xs) < 5:
        return None
    sd = statistics.stdev(xs)
    if sd == 0:
        return 0
    return max(0, int((Z * sd / HALF_WIDTH_TARGET) ** 2) - len(xs))


def _group(rows):
    d = [r["diff"] for r in rows]
    m, lo, hi, n = _ci(d)
    return {"n_pairs": n, "diff_mean": m, "ci": [lo, hi],
            "base_mean_net": _ci([r["base"] for r in rows])[0],
            "arm_mean_net": _ci([r["arm"] for r in rows])[0],
            "zero_pct_base": _zero(rows, "base"),
            "zero_pct_arm": _zero(rows, "arm"),
            "need_more": _need(d)}


def _sign(g):
    lo, hi = g["ci"]
    if lo is None:
        return 0
    return 1 if lo > 0 else -1 if hi < 0 else 0


def study():
    ps = pairs()
    arms = {}
    for tag, pops in ps.items():
        groups = {k: _group(v) for k, v in pops.items()}
        pooled = _group(pops["sig"] + pops["practice"])
        n = pooled["n_pairs"]
        lo, hi = pooled["ci"]
        # هم‌جهتی دو جمعیت شرطِ حکم است. اگر یکی بالای صفر و دیگری زیرِ
        # صفر باشد، اثر به جمعیت وابسته است نه به نردبان — و ادعای
        # عمومی کردنش همان تعمیمِ بی‌سند است.
        ss, sp = _sign(groups["sig"]), _sign(groups["practice"])
        clash = ss * sp < 0
        if clash:
            v = "UNDECIDED"
            why = ("دو جمعیت خلافِ هم‌اند (سیگنال و تمرین) — اثر به "
                   "جمعیت وابسته است، نه به نردبان")
        elif lo is not None and lo > 0 and n >= N_PROMOTE:
            v, why = "PROMOTE", f"CI بالای صفر روی n={n} ≥ {N_PROMOTE}"
        elif hi is not None and hi < 0 and n >= N_REJECT:
            v, why = "REJECT", f"CI زیر صفر روی n={n} ≥ {N_REJECT}"
        else:
            need = pooled["need_more"]
            v = "UNDECIDED"
            why = (f"n={n}؛ برآورد ~{need} جفت دیگر تا نیم‌پهنای "
                   f"{HALF_WIDTH_TARGET}R" if need is not None
                   else f"n={n} — هنوز برای برآورد هم کم است")
        allrows = pops["sig"] + pops["practice"]
        by_reg = {}
        for reg in ("با روند", "خلاف روند", "رنج/نامعلوم"):
            sub = [r for r in allrows if r.get("regime") == reg]
            if sub:
                by_reg[reg] = _group(sub)
        arms[tag] = {**pooled, "verdict": v, "why": why,
                     "consistent": not clash, "by_population": groups,
                     "by_regime": by_reg}
    return {
        "generated": int(time.time() * 1000),
        "fingerprint": fingerprint(),
        "z": Z, "n_promote": N_PROMOTE, "n_reject": N_REJECT,
        "arms": arms,
        "stopping_rule": (
            f"PROMOTE = CI خالصِ جفتی کاملاً بالای صفر روی n≥{N_PROMOTE} "
            f"(فقط پیشنهاد، تأیید حمید لازم است) · "
            f"REJECT = CI کاملاً زیر صفر روی n≥{N_REJECT} · "
            f"بقیه UNDECIDED. تصحیح Šidák برای ۲ بازو (z={Z})."),
        "boundary": (
            "این دفتر فقط پیپر است و هیچ دروازهٔ تولیدی را عوض نمی‌کند. "
            "PROMOTE هم فقط پیشنهاد است — تغییر نردبانِ تولید تأیید صریح "
            "حمید می‌خواهد (قانون ۰۳/۱۲). حکم به اثرانگشتِ نسبت‌ها گره "
            "خورده؛ عوض‌شدنِ هر نسبت یعنی دفترِ حکم از صفر. "
            "پیپر سقفِ خوش‌بینانه است: فیل کامل و بدون لغزش فرض می‌شود. "
            "تقسیمِ رژیم **توصیفی** است: از شاهدِ بیرونیِ راستی‌آزمایی‌نشده "
            "آمده (قانون ۱۱، ~۳۰٪ خطا) و هیچ آستانه‌ای را عوض نمی‌کند؛ "
            "حکم از نمونهٔ کل می‌آید نه از بهترین زیرگروه — وگرنه همان "
            "data-snooping است که قانون ۰۳ منعش کرده.")}


def _zero(rows, side):
    if not rows:
        return None
    return round(100 * sum(1 for r in rows if abs(r[side]) < 0.05)
                 / len(rows), 1)


def render(s):
    L = [f"### بازوهای تریل — اثرانگشت: {s['fingerprint']}\n"]
    if not any(a["n_pairs"] for a in s["arms"].values()):
        L.append("  هنوز هیچ جفتی بسته نشده — دفتر تازه باز شده.")
    for tag, a in s["arms"].items():
        ci = (f"[{a['ci'][0]:+.3f}, {a['ci'][1]:+.3f}]"
              if a["ci"][0] is not None else "—")
        dm = f"{a['diff_mean']:+.4f}R" if a["diff_mean"] is not None else "—"
        L.append(f"  {tag}: n={a['n_pairs']}  اختلاف {dm}  CI {ci}")
        L.append(f"      پایه {a['base_mean_net']}  بازو {a['arm_mean_net']}  "
                 f"صفرشده: پایه {a['zero_pct_base']}٪ / بازو "
                 f"{a['zero_pct_arm']}٪")
        for pop, g in a["by_population"].items():
            L.append(f"      • {pop}: n={g['n_pairs']}  "
                     f"اختلاف {g['diff_mean']}  CI {g['ci']}")
        for reg, g in a.get("by_regime", {}).items():
            L.append(f"      ▸ {reg}: n={g['n_pairs']}  "
                     f"اختلاف {g['diff_mean']}  CI {g['ci']}")
        L.append(f"      → {a['verdict']} — {a['why']}")
    L.append(f"\n### قاعدهٔ توقف (ثبت‌شده پیش از داده)\n  {s['stopping_rule']}")
    L.append(f"\n### مرز صادقانه\n  {s['boundary']}")
    return "\n".join(L)


def main(argv=()):
    s = study()
    print(json.dumps(s, ensure_ascii=False, indent=1) if "--json" in argv
          else render(s))
    if "--write" in argv:
        OUT.write_text(json.dumps(s, ensure_ascii=False, indent=1),
                       encoding="utf-8")
        print(f"\n  نوشته شد: {OUT.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
