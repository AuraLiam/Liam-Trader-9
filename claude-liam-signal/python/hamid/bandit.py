"""چند راهزن مسلح (Multi-Armed Bandit) روی میز آزمایش پیپر — دستور حمید، ۳۱ اوت.

حمید: «کتاب چند راهزن مسلح را بخوان و همان را روی انجین‌های مهم پیاده
کن... مرتب پیپرمود ترید کنند و هر بار که نتیجه را می‌بینی با اطلاعات
جدید تستشون کن.»

## روش — نمونه‌گیری تامسون (Thompson Sampling)

هر «بازو» یک هندسه/فرضیهٔ آزمایشِ پیپر است. برای هر بازو از دفترِ
بسته یک پسینِ گاوسی روی میانگینِ بازدهی می‌سازیم: N(میانگین، واریانس/n).
هر نوبتِ تخصیص، از پسینِ هر بازو یک نمونه کشیده می‌شود و بازویی که
نمونه‌اش بهتر بود، سهم آن نوبت را می‌گیرد. نتیجه: تخصیصِ آزمایش
خودبه‌خود متناسب با «احتمالِ بهتر بودن» می‌شود — بازوی امیدوارکننده
بیشتر تست می‌گیرد، بازوی نامعلوم هم گاهی، و بازوی قطعاً بد کم‌کم هیچ.

منابع (راستی‌آزمایی‌شده ۳۱ اوت، در قفسهٔ کتابخانه):
- Russo et al., *A Tutorial on Thompson Sampling* (arXiv:1707.02038)
- Sutton & Barto, *Reinforcement Learning*, ch.2 — بخش ناایستایی:
  بازدهیِ بازار ثابت نیست، پس پسین روی **پنجرهٔ غلتان** ساخته می‌شود
  (این‌جا: آخرین `WINDOW_N` معاملهٔ هر بازو)، نه کل تاریخ.
- Thompson (1933) — خاستگاه روش.

## سه تصمیم طراحی — و دلیلشان

۱. **بی‌حالت.** پسین هر بار از خودِ دفتر بسته بازسازی می‌شود؛ هیچ فایل
   حالتِ جداگانه‌ای نیست. فایل حالتِ جدا یا یتیمِ قانون ۱۳ می‌شد یا با
   دفتر واگرا؛ دفترِ بسته خودش منبع حقیقت است. «با اطلاعات جدید
   تستشون کن» هم همین‌جا مجانی جواب می‌گیرد: هر ردیفِ تازهٔ بسته،
   خودکار وارد پسینِ نوبت بعد است.
۲. **بذر قطعی.** نمونه‌کشی با بذرِ ساخته‌شده از تاریخِ روز — یعنی
   تخصیصِ هر روز بازتولیدپذیر است (قاعدهٔ «هر عدد قابل اجرای دوباره»).
۳. **معیار = خالص از کارمزد، بازمحاسبه با منبع واحد** — همان قاعدهٔ
   ۳۰ اوت؛ بازویی که فقط ناخالصش خوب است نباید بودجه بخورد.

## مرز — بندیت کجا حق تصمیم دارد

فقط تقسیمِ **بودجهٔ آزمایش پیپر** بین بازوها، و ترتیبِ «تمرکزِ»
پیشنهادی انجین‌ها در گزارش. هیچ سیگنال واقعی، هیچ دروازه و هیچ وزنِ
تولیدی از بندیت اثر نمی‌گیرد — ورود به تولید فقط از مسیر قانون ۰۳
(CI بالای صفر + تأیید صریح حمید). بندیت تعیین می‌کند نمونهٔ بعدی کجا
خرج شود تا ماشینِ CI **زودتر** به حکم برسد؛ جای آن نمی‌نشیند.

اجرا:
  python3 -m hamid.bandit            # وضعیت بازوها + تخصیص امروز
  python3 -m hamid.bandit --focus    # بستهٔ تمرکز انجین‌ها
  python3 -m hamid.bandit --write    # signals/engine-focus.json
"""
import hashlib
import json
import math
import random
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent
OUT = ROOT / "signals" / "engine-focus.json"
LIB = ROOT / "brain" / "library" / "index.jsonl"
QUEUE = ROOT / "brain" / "library" / "queue.jsonl"
REWARDS = ROOT / "brain" / "rewards.json"

WINDOW_N = 400        # پنجرهٔ غلتان بر بازو (ناایستایی — Sutton & Barto ch.2)
DRAWS = 2000          # شمار نمونه‌کشی برای برآورد p(بهترین)
PRIOR_SD = 0.6        # پسینِ بازوی بی‌داده: N(0, PRIOR_SD²) — نه خوش‌بین نه بدبین
MIN_N_VERDICT = 40    # زیر این، فقط کاوش — هیچ برچسب «قوی/ضعیف» نمی‌خورد

# بازوهای فعال آزمایش — هر بازو: (پیشوند دفتر، شرح)
ARMS = {
    "exp-short-b1": "شورت با استاپ ۰.۶۵٪ (باند ۰.۵–۰.۸)",
    "exp-short-b2": "شورت با استاپ ۱.۱۵٪ (باند ۰.۸–۱.۵)",
}

# قاعدهٔ توقفِ از پیش ثبت‌شده (الگوی scalp_verdict — تعریفِ «تمام»)
REJECT_N, PROMOTE_N = 300, 400


def _seed(day=None):
    """بذرِ قطعی از تاریخ روز — تخصیصِ هر روز بازتولیدپذیر است."""
    day = day or time.strftime("%Y-%m-%d", time.gmtime())
    return int(hashlib.sha256(day.encode()).hexdigest()[:12], 16)


def arm_stats(rows=None):
    """پسینِ هر بازو از دفترِ بسته — بی‌حالت، پنجرهٔ غلتان، خالصِ منبع‌واحد."""
    from hamid.direction_autopsy import load
    if rows is None:
        rows = load("exp-short")
    out = {}
    for arm in ARMS:
        xs = sorted((r for r in rows if r["_stage"] == arm),
                    key=lambda r: r.get("closed") or r.get("opened") or 0)
        xs = [r["R_net"] for r in xs][-WINDOW_N:]
        n = len(xs)
        if n >= 2:
            m = statistics.mean(xs)
            sd = statistics.stdev(xs)
            se = sd / math.sqrt(n)
            lo, hi = m - 1.96 * se, m + 1.96 * se
        else:
            m, sd, se, lo, hi = 0.0, PRIOR_SD, PRIOR_SD, None, None
        out[arm] = {"n": n, "mean": round(m, 4), "sd": round(sd, 4),
                    "se": round(se, 4),
                    "ci": [round(lo, 4), round(hi, 4)] if lo is not None else None,
                    "desc": ARMS[arm]}
    return out


def verdict(st):
    """حکمِ بازو با قاعدهٔ از پیش ثبت‌شده — «تمام» تعریف دارد.

    PROMOTE فقط پیشنهاد است؛ ورودش به هر تصمیمی تأیید صریح حمید
    می‌خواهد (قانون ۱۲). REJECT یعنی این بازو دیگر بودجه نمی‌گیرد."""
    ci, n = st.get("ci"), st["n"]
    if ci and ci[1] < 0 and n >= REJECT_N:
        return "REJECT"
    if ci and ci[0] > 0 and n >= PROMOTE_N:
        return "PROMOTE_PROPOSED"
    return "SAMPLING"


def allocate(total, stats=None, day=None):
    """تخصیص تامسون: `total` نمونهٔ این نوبت بین بازوهای فعال.

    بازوی با حکم قطعی (REJECT/PROMOTE_PROPOSED) بازنشسته است و سهم
    نمی‌گیرد — نمونهٔ بیشتر روی سؤالِ جواب‌گرفته، هدر است (تلهٔ آماری
    ثبت‌شدهٔ E18). اگر همه بازنشسته بودند، تخصیص صفر با دلیل."""
    stats = stats or arm_stats()
    live = {a: s for a, s in stats.items() if verdict(s) == "SAMPLING"}
    if not live or total <= 0:
        return {a: 0 for a in stats}, "همهٔ بازوها حکم گرفته‌اند — تخصیص صفر؛ نوبتِ حمید/ماشین CI است"
    rng = random.Random(_seed(day))
    wins = {a: 0 for a in live}
    for _ in range(DRAWS):
        best, best_v = None, -1e18
        for a, s in live.items():
            v = rng.gauss(s["mean"], max(s["se"], 1e-6))
            if v > best_v:
                best, best_v = a, v
        wins[best] += 1
    alloc = {a: 0 for a in stats}
    # سهمِ صحیح با باقی‌مانده به برنده — جمع دقیقاً `total`
    shares = sorted(((wins[a] / DRAWS) * total, a) for a in live)
    used = 0
    for share, a in shares[:-1]:
        alloc[a] = int(share)
        used += int(share)
    alloc[shares[-1][1]] = total - used
    why = " · ".join(f"{a}: p(بهترین)≈{wins[a]/DRAWS:.0%}" for a in live)
    return alloc, why


def _shelf_for(engine):
    """منابع قفسه/صفِ همین انجین — «منابع مهم را در اختیارشان بگذار»."""
    out = []
    for p in (LIB, QUEUE):
        try:
            for line in p.read_text(encoding="utf-8").splitlines():
                if not line.strip().startswith("{"):
                    continue
                r = json.loads(line)
                if r.get("engine") == engine and r.get("status") != "REJECTED":
                    out.append({"id": r.get("id"), "title": r.get("title"),
                                "source": r.get("source")})
        except Exception:                            # noqa: BLE001
            continue
    return out[:6]


def engine_focus():
    """بستهٔ تمرکز انجین‌ها — نقاط قوتِ اندازه‌گیری‌شده + منابع + تمرکز بعدی.

    «نقطهٔ قوت» فقط از شمارش می‌آید (دفتر جایزه: ردپای تأیید روی
    TP/تریل/استاپ). جایزه اثرِ علّی نیست و همین صریح روی خروجی می‌ماند."""
    try:
        eng = (json.loads(REWARDS.read_text(encoding="utf-8"))
               .get("engines") or {})
    except Exception:                                # noqa: BLE001
        eng = {}
    focus = []
    for e, r in eng.items():
        n = (r.get("target", 0) + r.get("trail", 0) + r.get("stop", 0))
        if n < MIN_N_VERDICT:
            focus.append({"engine": e, "n": n,
                          "strength": None,
                          "note": f"نمونه کم ({n} < {MIN_N_VERDICT}) — فقط کاوش، برچسب نمی‌خورد",
                          "sources": _shelf_for(e)})
            continue
        tp_rate = r.get("target", 0) / n
        stop_rate = r.get("stop", 0) / n
        focus.append({
            "engine": e, "n": n,
            "strength": {"tp_rate": round(tp_rate, 3),
                         "stop_rate": round(stop_rate, 3),
                         "points_per_trade": round(r.get("points", 0) / n, 2)},
            "note": ("ردپای تأییدش بیشتر روی معامله‌های تارگت‌خورده است"
                     if tp_rate > stop_rate else
                     "ردپای تأییدش بیشتر روی استاپ‌خورده‌هاست — تمرکز: علت‌یابی همین"),
            "sources": _shelf_for(e),
        })
    focus.sort(key=lambda f: -(f["strength"] or {}).get("points_per_trade", -9))
    return focus


def packet(day=None):
    stats = arm_stats()
    alloc, why = allocate(4, stats, day)
    return {
        "generated": int(time.time() * 1000),
        "method": "Thompson Sampling (Russo et al. arXiv:1707.02038 · "
                  "Sutton&Barto ch.2) — پنجرهٔ غلتان، بذر قطعی روزانه",
        "arms": {a: {**s, "verdict": verdict(s), "alloc_today": alloc[a]}
                 for a, s in stats.items()},
        "alloc_why": why,
        "engine_focus": engine_focus(),
        "boundary": "بندیت فقط بودجهٔ آزمایش پیپر را تقسیم می‌کند؛ سیگنال "
                    "واقعی/دروازه/وزن تولیدی از آن اثر نمی‌گیرد — ورود به "
                    "تولید فقط CI بالای صفر + تأیید صریح حمید (قانون ۰۳/۱۲). "
                    "جایزهٔ انجین ردپای تأیید است نه اثر علّی.",
    }


def main(argv=()):
    p = packet()
    if "--write" in argv:
        OUT.parent.mkdir(exist_ok=True)
        OUT.write_text(json.dumps(p, ensure_ascii=False, indent=1),
                       encoding="utf-8")
        print(f"نوشته شد: {OUT.name}")
    print("### بازوهای آزمایش (تامسون، خالص از کارمزدِ منبع‌واحد)")
    for a, s in p["arms"].items():
        ci = f"CI[{s['ci'][0]:+.3f},{s['ci'][1]:+.3f}]" if s["ci"] else "CI ندارد"
        print(f"  {a}: n={s['n']} میانگین {s['mean']:+.4f} {ci} "
              f"→ {s['verdict']} · سهم امروز {s['alloc_today']}")
    print(f"  {p['alloc_why']}")
    if "--focus" in argv or "--write" in argv:
        print("\n### تمرکز انجین‌ها (جایزه = ردپای تأیید، نه اثر علّی)")
        for f in p["engine_focus"]:
            st = f["strength"]
            line = (f"  {f['engine']}: n={f['n']} · "
                    + (f"tp {st['tp_rate']:.0%} / stop {st['stop_rate']:.0%} · "
                       f"{st['points_per_trade']} امتیاز/معامله · " if st else "")
                    + f["note"])
            print(line)
            for s in f["sources"][:3]:
                print(f"      📚 {s['title']} — {s['source']}")
    print(f"\n{p['boundary']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
