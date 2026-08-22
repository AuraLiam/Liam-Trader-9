"""آیا عمق دفتر، شکستِ واقعی BOS/CHoCH را از کاذب جدا می‌کند؟

## چرا این فایل وجود دارد

سه بک‌تست ۲۲ اوت روی ۱-۳ دقیقه با کندلِ تنها به این رسیدند که BOS/CHoCH
لبه ندارد — و تأیید خارج از نمونه روی نمونهٔ مستقل (رتبه‌های ۳۱–۵۶) هر
۱۲ خانه را با CI کاملاً زیر صفر رد کرد. تشخیصی که آن‌جا نوشتم این بود:
مسئله انتخاب پارامتر نیست؛ **کندل اطلاعات لازم برای جدا کردن شکست واقعی
از کاذب را ندارد**. قانون ۰۸ هم از قبل همین را گفته بود.

این فایل همان تشخیص را **می‌سنجد**، نه اینکه فرضش کند. اگر عمق واقعاً
این دو را جدا می‌کند، باید در تفاوت معنادارِ ویژگی‌ها بین دو گروه دیده
شود. اگر نه، همین‌جا رد می‌شود و E10 خاموش می‌ماند.

## برچسب‌گذاری — و چرا این نگاه به آینده نیست

این اسکریپت **قاعدهٔ معامله نمی‌سازد**؛ می‌پرسد «آیا اطلاعاتی هست؟».
برچسب واقعی/کاذب طبیعتاً از آینده می‌آید (شکست وقتی «واقعی» است که ادامه
داده باشد) — این تعریفِ متغیر وابسته است، نه تقلب. تقلبی که باید نباشد
این است که **ویژگی** از آینده بیاید: ویژگی‌ها فقط از سطر دقیقه‌ایِ خودِ
کندلِ شکست خوانده می‌شوند، نه از دقیقه‌های بعد. اگر تفاوتی پیدا شد،
قدم بعدی ساختن قاعده و بک‌تست بی‌آینده است — نه ادعای عملکرد.

## مرزهای صادقانه

۱. نمونه‌برداری REST است نه استریم رویداد؛ `up_/dn_` تقریب درشتِ جریان
   است و لغو از اجرا تفکیک نمی‌شود (قانون ۰۸).
۲. هر ویژگی یک آزمون است. با m ویژگی، آستانهٔ t باید sqrt(2·ln m) باشد
   وگرنه یکی از آن‌ها شانسی معنادار می‌شود.
۳. زیر ۳۰ رویداد در هر گروه، هیچ CI گزارش نمی‌شود.
۴. رویدادِ بی‌سطرِ عمق **حذف** می‌شود و تعدادش چاپ — حذف بی‌صدا همان
   جایی است که نمونه بی‌سروصدا سوگیری می‌گیرد.

خروجی: signals/depth-bos.json
اجرا:  python3 -m hamid.depth_bos --horizon 20
"""
import argparse
import json
import math
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
ROOT = PY.parents[1]
sys.path.insert(0, str(PY))

from hamid import depth_collector as DC               # noqa: E402
from hamid import microstructure as MS                # noqa: E402

OUT = ROOT / "signals" / "depth-bos.json"
MIN_GROUP = 30                 # کف نمونه در هر گروه — قانون CI
HORIZON = 20                   # کندل برای حل شدن برچسب
GO_ATR = 1.0                   # ادامهٔ لازم برای «واقعی»
BACK_ATR = 0.5                 # برگشت پشت سطح برای «کاذب»


def label_break(cd, i, direction, horizon=HORIZON, go_atr=GO_ATR,
                back_atr=BACK_ATR):
    """شکست بعد از کندل i واقعی بود یا کاذب؟ → 1 / 0 / None (حل‌نشده).

    واقعی: قبل از برگشتِ back_atr پشت کلوزِ شکست، به اندازهٔ go_atr در
    جهت شکست پیش رفت. کاذب: عکسش. هیچ‌کدام تا افق → None (کنار گذاشته
    می‌شود و شمرده می‌شود، نه اینکه به یکی از دو گروه چسبانده شود).

    اگر یک کندل هر دو آستانه را لمس کرد، **کاذب** حساب می‌شود — ترتیب
    درون کندل معلوم نیست و فرض خوش‌بینانه یعنی دروغ به خودمان."""
    atr = MS._atr_at(cd, i)
    if not atr:
        return None
    base = cd[i]["c"]
    up = direction == "up"
    goal = base + go_atr * atr if up else base - go_atr * atr
    stop = base - back_atr * atr if up else base + back_atr * atr
    for j in range(i + 1, min(i + 1 + horizon, len(cd))):
        k = cd[j]
        hit_back = k["l"] <= stop if up else k["h"] >= stop
        hit_go = k["h"] >= goal if up else k["l"] <= goal
        if hit_back:
            return 0
        if hit_go:
            return 1
    return None


def event_features(row, direction):
    """ویژگی‌های عمقِ کندلِ شکست، علامت‌خورده در جهت شکست.

    علامت‌گذاری لازم است وگرنه شکست بالا و پایین اثر هم را خنثی می‌کنند
    و همه‌چیز صفر به نظر می‌رسد."""
    d = 1.0 if direction == "up" else -1.0
    f = {
        "spread_bps": row["spread_bps_mean"],
        "micro_dev": row["micro_dev_mean"] * d,
        "imb_mean_1": row["imb_mean_1"] * d,
        "imb_mean_5": row["imb_mean_5"] * d,
        "imb_mean_15": row["imb_mean_15"] * d,
        "imb_last_15": row["imb_last_15"] * d,
    }
    # کشش عدم‌تعادل داخل دقیقه: بیشترین لحظهٔ هم‌جهت
    f["imb_extreme_15"] = (row["imb_max_15"] if d > 0 else -row["imb_min_15"])
    for n in (5, 15):
        # سمتی که شکست باید بخوردش: در شکست رو به بالا، اسک.
        eaten = -row[f"dn_ask_{n}"] if d > 0 else -row[f"dn_bid_{n}"]
        refill = row[f"up_ask_{n}"] if d > 0 else row[f"up_bid_{n}"]
        base = max(1e-9, row[f"depth_ask_mean_{n}"] if d > 0
                   else row[f"depth_bid_mean_{n}"])
        # نرمال‌سازی با عمق خودِ نماد — قانون ۰۸: اندازهٔ خام بین نمادها
        # قابل مقایسه نیست.
        f[f"eaten_{n}"] = eaten / base
        f[f"refill_{n}"] = refill / base
        f[f"net_taken_{n}"] = (eaten - refill) / base
    return f


def boot_ci(xs, n_boot=3000, seed=7, alpha=0.05):
    """CI بوت‌استرپ درصدی روی میانگین."""
    if len(xs) < 2:
        return None, None
    import random as _r
    rnd = _r.Random(seed)
    n = len(xs)
    means = []
    for _ in range(n_boot):
        means.append(sum(xs[rnd.randrange(n)] for _ in range(n)) / n)
    means.sort()
    lo = means[int(alpha / 2 * n_boot)]
    hi = means[min(n_boot - 1, int((1 - alpha / 2) * n_boot))]
    return lo, hi


def diff_ci(a, b, n_boot=3000, seed=7, alpha=0.05):
    """CI بوت‌استرپ روی «میانگین گروه واقعی − میانگین گروه کاذب».

    هر دو گروه در هر تکرار جدا نمونه‌گیری می‌شوند (بوت‌استرپ دو نمونه‌ای)."""
    if len(a) < 2 or len(b) < 2:
        return None, None
    import random as _r
    rnd = _r.Random(seed)
    na, nb = len(a), len(b)
    ds = []
    for _ in range(n_boot):
        ma = sum(a[rnd.randrange(na)] for _ in range(na)) / na
        mb = sum(b[rnd.randrange(nb)] for _ in range(nb)) / nb
        ds.append(ma - mb)
    ds.sort()
    lo = ds[int(alpha / 2 * n_boot)]
    hi = ds[min(n_boot - 1, int((1 - alpha / 2) * n_boot))]
    return lo, hi


def welch_t(a, b):
    """t ولچ — واریانس نابرابر، که این‌جا حالت عادی است."""
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return None
    ma, mb = sum(a) / na, sum(b) / nb
    va = sum((x - ma) ** 2 for x in a) / (na - 1)
    vb = sum((x - mb) ** 2 for x in b) / (nb - 1)
    se = math.sqrt(va / na + vb / nb)
    return (ma - mb) / se if se > 0 else None


# ── پیش‌ثبت فرضیه‌ها (قبل از دیدن داده) ─────────────────────────────────
# چرا: شکستِ ۲۲ اوت این بود که یک جستجوی پارامتری عدد مثبت داد و تأیید
# خارج از نمونه کاملاً ردش کرد — یعنی «کشف»، نویزِ جستجو بود. علاجش در
# ادبیات همین است (Bailey و López de Prado، هر دو در قفسه): فرضیه و
# **جهتش** قبل از دیدن داده نوشته شود. آن‌وقت آزمون تأییدی است نه اکتشافی،
# خانوادهٔ آزمون کوچک‌تر است، و جهت‌دار بودن اجازهٔ آزمون یک‌طرفه می‌دهد.
#
# این جدول قبل از رسیدن هیچ نمونه‌ای از عمق نوشته شد (۲۲ اوت، شب).
# هر سطر: ویژگی → (جهت پیش‌بینی‌شده، منبعِ قفسه، استدلال).
# جهت +۱ یعنی «در شکست واقعی بزرگ‌تر از شکست کاذب».
PREREGISTERED = {
    "imb_mean_15": (
        +1, "Gould & Bonart; Cont, Kukanov, Stoikov",
        "اگر عدم‌تعادل صف قدم بعدی قیمت را بگوید، شکستی که دفترش هم‌جهت "
        "خمیده واقعی‌تر از شکستی است که دفترش خنثی یا مخالف است."),
    "net_taken_15": (
        +1, "Harris; Bouchaud و همکاران",
        "شکست واقعی نقدینگیِ مستقر را **خالص** مصرف می‌کند؛ شکست کاذب "
        "فقط لمس می‌کند و مصرفش با بازپرشدن جبران می‌شود."),
    "refill_15": (
        -1, "قانون ۰۸ (بازپرشدن) — Harris",
        "بازپرشدنِ سمتِ شکسته یعنی کسی دارد سطح را دفاع می‌کند؛ پس "
        "بازپرشدنِ بیشتر باید با شکستِ **کاذب** همراه باشد، نه واقعی."),
    "micro_dev_mean": (
        +1, "Harris; Bouchaud و همکاران (microprice)",
        "میکروپرایسِ خم‌شده در جهت شکست، برآورد بهترِ قیمت منصفانه است و "
        "باید حرکت بعدی را زودتر از mid نشان بدهد."),
}
# عمداً بیرون از پیش‌ثبت: `spread_bps` و `imb_extreme_15`. برای اسپرد
# استدلال هر دو طرف قابل‌دفاع است (اسپرد باز = شرایط نازک و شکست شکننده،
# یا = حرکت واقعی در جریان)، و وقتی جهت را نمی‌دانم پیش‌ثبتش تقلب است.
# این‌ها اکتشافی می‌مانند و با خانوادهٔ کامل و دوطرفه داوری می‌شوند.


def one_sided_threshold(m, alpha=0.05):
    """آستانهٔ z یک‌طرفهٔ Šidák برای m فرضیهٔ **جهت‌دارِ پیش‌ثبت‌شده**.

    جهت‌دار بودن نصف دم را حذف می‌کند و خانوادهٔ کوچک آستانه را پایین
    می‌آورد — این دقیقاً پاداشِ پیش‌ثبت است، نه تخفیفِ خودسرانه: فقط
    فرضیه‌ای که جهتش **قبل** از داده نوشته شده حق دارد یک‌طرفه آزموده
    شود."""
    from statistics import NormalDist
    per = 1.0 - (1.0 - alpha) ** (1.0 / max(1, m))
    return round(NormalDist().inv_cdf(1.0 - per), 3)


def multiple_test_threshold(m):
    """آستانهٔ t وقتی m ویژگی هم‌زمان آزموده می‌شوند — Šidák.

    یک پیاده‌سازی، دو مصرف‌کننده: همان تابعِ scenario_backtest، تا آستانهٔ
    دو گزارش با هم اختلاف پیدا نکند."""
    from hamid.scenario_backtest import multiple_test_penalty
    return multiple_test_penalty(m)


def collect_events(cd, minutes_by_t, horizon=HORIZON, kinds=None):
    """رویدادهای ساختار را با سطر عمقِ همان دقیقه جفت می‌کند.

    خروجی: (نمونه‌ها، آمار حذف) — هر حذف دلیل دارد و شمرده می‌شود."""
    st = MS.structure(cd)
    drop = {"بی‌سطر عمق": 0, "برچسب حل‌نشده": 0, "خارج افق": 0}
    if not st:
        return [], drop
    out = []
    n = len(cd)
    for ev in st["events"]:
        if kinds and ev["kind"] not in kinds:
            continue
        i = ev["i"]
        if i + 1 + horizon > n:
            drop["خارج افق"] += 1
            continue
        row = minutes_by_t.get(cd[i]["t"])
        if row is None:
            drop["بی‌سطر عمق"] += 1
            continue
        y = label_break(cd, i, ev["dir"], horizon=horizon)
        if y is None:
            drop["برچسب حل‌نشده"] += 1
            continue
        out.append({"t": ev["t"], "kind": ev["kind"], "dir": ev["dir"],
                    "session": ev["session"], "y": y,
                    "f": event_features(row, ev["dir"])})
    return out, drop


def analyse(samples, min_group=MIN_GROUP):
    """تفاوت هر ویژگی بین شکست واقعی و کاذب، با CI و تصحیح چندآزمونی."""
    real = [s for s in samples if s["y"] == 1]
    fake = [s for s in samples if s["y"] == 0]
    res = {"n_real": len(real), "n_fake": len(fake),
           "n": len(samples), "features": [], "verdict": None}
    if len(real) < min_group or len(fake) < min_group:
        res["verdict"] = (f"نمونه کافی نیست (واقعی {len(real)}، کاذب "
                          f"{len(fake)}؛ کف {min_group}) — هیچ CI گزارش نمی‌شود")
        return res
    names = sorted(samples[0]["f"])
    pre = [k for k in names if k in PREREGISTERED]
    exp = [k for k in names if k not in PREREGISTERED]
    # دو خانوادهٔ جدا: تأییدی (پیش‌ثبت‌شده، جهت‌دار، یک‌طرفه) و اکتشافی
    # (بقیه، دوطرفه، با خانوادهٔ کامل). قاطی کردنشان یعنی همان تقلبی که
    # پیش‌ثبت برای جلوگیری از آن هست.
    thr_pre = one_sided_threshold(len(pre)) if pre else None
    thr_exp = multiple_test_threshold(len(exp)) if exp else None
    res["t_threshold_preregistered"] = thr_pre
    res["t_threshold_exploratory"] = thr_exp
    res["t_threshold"] = thr_exp        # سازگاری با مصرف‌کنندهٔ قبلی
    for k in names:
        a = [s["f"][k] for s in real]
        b = [s["f"][k] for s in fake]
        lo, hi = diff_ci(a, b)
        t = welch_t(a, b)
        clears = lo is not None and (lo > 0 or hi < 0)
        row = {
            "feature": k,
            "mean_real": round(sum(a) / len(a), 6),
            "mean_fake": round(sum(b) / len(b), 6),
            "diff": round(sum(a) / len(a) - sum(b) / len(b), 6),
            "ci95": [round(lo, 6), round(hi, 6)] if lo is not None else None,
            "t": round(t, 3) if t is not None else None,
            "ci_clears_zero": clears}
        if k in PREREGISTERED:
            sign, src, why = PREREGISTERED[k]
            row["kind"] = "preregistered"
            row["predicted_sign"] = sign
            row["source"] = src
            row["rationale"] = why
            # تأیید فقط وقتی جهت هم **همانی** باشد که از قبل نوشته شده.
            # عددی که بزرگ است ولی خلاف پیش‌بینی، فرضیه را رد می‌کند نه
            # تأیید — و همان‌طور هم ثبت می‌شود.
            right_way = t is not None and (t * sign) > 0
            row["direction_as_predicted"] = bool(right_way)
            row["survives_multiple_testing"] = bool(
                right_way and clears and abs(t) >= thr_pre)
            row["refutes_prediction"] = bool(
                t is not None and not right_way and clears
                and abs(t) >= thr_pre)
        else:
            row["kind"] = "exploratory"
            row["survives_multiple_testing"] = bool(
                clears and t is not None and abs(t) >= thr_exp)
        res["features"].append(row)
    res["features"].sort(key=lambda x: (x["kind"] != "preregistered",
                                        -abs(x["t"] or 0)))
    conf = [f["feature"] for f in res["features"]
            if f["kind"] == "preregistered" and f["survives_multiple_testing"]]
    ref = [f["feature"] for f in res["features"] if f.get("refutes_prediction")]
    disc = [f["feature"] for f in res["features"]
            if f["kind"] == "exploratory" and f["survives_multiple_testing"]]
    res["confirmed"] = conf
    res["refuted"] = ref
    res["exploratory_hits"] = disc
    res["survivors"] = conf + disc
    parts = []
    if conf:
        parts.append(f"تأیید شد ({len(conf)} از {len(pre)} فرضیهٔ پیش‌ثبت‌شده، "
                     f"یک‌طرفه |t|≥{thr_pre}): {conf}")
    if ref:
        parts.append(f"**خلافِ پیش‌بینی** و معنادار: {ref} — فرضیه رد شد، "
                     f"نه اینکه چیزی پیدا نشده باشد")
    if disc:
        parts.append(f"اکتشافی (دوطرفه |t|≥{thr_exp}، فرضیه نیست و باید "
                     f"جدا تأیید شود): {disc}")
    if not parts:
        parts.append(f"هیچ ویژگی عمقی شکست واقعی را از کاذب جدا نکرد — نه "
                     f"{len(pre)} فرضیهٔ پیش‌ثبت‌شده، نه {len(exp)} ویژگی "
                     f"اکتشافی")
    res["verdict"] = " · ".join(parts)
    return res


def run(symbols=None, horizon=HORIZON, kinds=None, quiet=False, outdir=None):
    import sources
    syms = symbols or DC.symbols_on_disk(outdir)
    if not syms:
        raise RuntimeError("هیچ نماد دارای عمق روی دیسک نیست — اول برداشت")
    allsamples, drops, per = [], {}, {}
    for s in syms:
        mins = DC.read_minutes(s, outdir=outdir)
        if not mins:
            continue
        by_t = {r["t"]: r for r in mins}
        span_min = (mins[-1]["t"] - mins[0]["t"]) // 60000 + 1
        # فقط همان بازه‌ای که عمق دارد — کندل بیشتر فقط رویدادِ بی‌عمق
        # می‌سازد و آمار حذف را بی‌دلیل باد می‌کند.
        bars = min(1000, span_min + 60)
        cd = [{"t": k[0], "o": float(k[1]), "h": float(k[2]), "l": float(k[3]),
               "c": float(k[4]), "v": float(k[5])}
              for k in sources.klines(s, "1m", bars)]
        smp, dr = collect_events(cd, by_t, horizon=horizon, kinds=kinds)
        allsamples += smp
        per[s] = {"minutes": len(mins), "events": len(smp)}
        for k, v in dr.items():
            drops[k] = drops.get(k, 0) + v
    res = analyse(allsamples)
    res["per_symbol"] = per
    res["dropped"] = drops
    res["horizon"] = horizon
    res["kinds"] = kinds or ["BOS", "CHoCH"]
    res["struct_version"] = MS.STRUCT_VERSION
    res["at"] = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())
    if not quiet:
        print(f"نماد: {len(per)} · رویداد قابل‌استفاده: {res['n']} "
              f"(واقعی {res['n_real']} / کاذب {res['n_fake']})")
        print(f"حذف‌شده: {drops}")
        print()
        if res["features"]:
            print(f"  {'ویژگی':<16} {'نوع':<5} {'واقعی':>9} {'کاذب':>9} "
                  f"{'اختلاف':>9} {'t':>7}  CI95")
            for f in res["features"]:
                if f.get("refutes_prediction"):
                    mark = "✗"          # معنادار ولی خلاف پیش‌بینی
                elif f["survives_multiple_testing"]:
                    mark = "★"
                elif f["ci_clears_zero"]:
                    mark = "·"
                else:
                    mark = " "
                kind = "پیش" if f["kind"] == "preregistered" else "اکتش"
                print(f"{mark} {f['feature']:<16} {kind:<5} "
                      f"{f['mean_real']:>9.4f} {f['mean_fake']:>9.4f} "
                      f"{f['diff']:>9.4f} {(f['t'] or 0):>7.2f}  {f['ci95']}")
            print("\n★ تأیید · ✗ خلافِ پیش‌بینی · · CI پاک ولی زیر آستانه\n")
        print(res["verdict"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--horizon", type=int, default=HORIZON)
    ap.add_argument("--kinds", default="", help="BOS / CHoCH / خالی = هر دو")
    ap.add_argument("--symbols", default="")
    a = ap.parse_args()
    run(symbols=[s.strip() for s in a.symbols.split(",") if s.strip()] or None,
        horizon=a.horizon,
        kinds=[k.strip() for k in a.kinds.split(",") if k.strip()] or None)
