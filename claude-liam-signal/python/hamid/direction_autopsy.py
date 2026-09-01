"""کالبدشکافی جهت — چرا شورت بد به نظر می‌رسد، و آیا واقعاً بد است.

دستور حمید (۳۰ اوت شب): «وقتی می‌گویی سطلی هست که بازهٔ اطمینانش زیر صفر
است عصبی می‌شوم. باید علت‌یابی شود. ما در این مجموعه هیچ چیزی را بدون
دلیل قبول نمی‌کنیم.»

## خطای روشی که این فایل برای بستنش نوشته شد

گزارش قبلی گفت «شورت تنها سطلی است که CI‌اش کاملاً زیر صفر است» و از آن
نتیجه گرفت شورت بد است. **این استنتاج غلط بود** و علتش یک خطای پایه است:

«CI شورت زیر صفر است» یک ادعای **تک‌نمونه‌ای** است (میانگین شورت در برابر
عدد صفر). ادعای «شورت بدتر از لانگ است» یک ادعای **دونمونه‌ای** است و
آزمون خودش را می‌خواهد. این دو یکی نیستند: وقتی هر دو جهت زیانده‌اند،
ممکن است یکی از نویز جدا شود و دیگری نه، بی‌آن‌که تفاوتی بینشان اثبات
شده باشد.

آزمون درست، وقتی انجام شد، این شد — داخل `sig-ibs` که استاپ هر دو جهت
عملاً یکی است (۰.۳۵۹٪ در برابر ۰.۳۴۱٪)، با کارمزدِ درست (۰.۱۵٪):

| | n | خالص R | CI 95٪ |
|---|---|---|---|
| SHORT | ۶۸ | −۰.۳۱۴ | [−۰.۵۰۵, −۰.۱۲۲] |
| LONG | ۸۲ | −۰.۱۶۷ | [−۰.۳۳۵, +۰.۰۰۱] |
| **اختلاف (S−L)** | | **−۰.۱۴۷** | **[−۰.۴۰۲, +۰.۱۰۸]** — شامل صفر، ‎\|t\|=۱.۱۳ |

یعنی **هیچ تفاوت اثبات‌شده‌ای بین شورت و لانگ نداریم.** روی کل دفتر هم
با کنترلِ استراتژی اختلاف −۰.۱۱۱ است با CI‏ [−۰.۳۹۲, +۰.۱۶۹].

## پس آن عددِ تجمعی از کجا می‌آمد — پارادوکس سیمپسون

ترکیب استراتژی دو جهت اصلاً یکی نیست:

| استراتژی | سهم از شورت | سهم از لانگ | میانهٔ استاپ | کارمزد |
|---|---|---|---|---|
| `sig-ibs` | **۸۱.۹٪** | ۵۳.۹٪ | ~۰.۳۵٪ | **۰.۲۳R** |
| `sig-smc` | ۸.۴٪ | **۴۲.۸٪** | ~۲.۸٪ (لانگ) | کم |

`sig-smc` تقریباً هرگز شورت نمی‌دهد (۷ در برابر ۶۵ = ۹.۷٪) و استاپش
گشاد است، پس کارمزد سهم کمی از R می‌گیرد. نتیجه: استخرِ لانگ با
معامله‌های کم‌کارمزدِ smc **رقیق** می‌شود و استخرِ شورت نمی‌شود. وقتی
ترکیبِ لانگ را به ترکیبِ شورت استاندارد می‌کنیم، خالصِ لانگ از −۰.۱۴۷
به **−۰.۲۱۰** می‌رود — بخشی از شکاف فقط ترکیب است، و بقیه‌اش از نویز
جدا نیست.

## عیبِ دومی که سرِ راه پیدا شد — و همهٔ اعداد را عوض کرد

`paper._settle_one` خالص را با **۰.۱٪** حساب می‌کرد، در حالی که نردبان
تریلِ همان تابع با **۰.۱۵٪** کار می‌کرد و مدل رسمی و اعداد
راستی‌آزمایی‌شدهٔ بیت‌یونیکس هم ۰.۱۵٪ است. دو ثابتِ ناسازگار در یک
تابع. رفع در `paper.py` (منبع واحد `hamid/fees.py`)، و این فایل خالص را
از `entry`/`sl` **بازمحاسبه** می‌کند تا یک تعریف بیشتر نداشته باشیم.

جابه‌جایی میانه: **−۰.۰۹۴R در هر معامله**. یعنی هر بازهٔ اطمینانی که تا
دیشب روی `R_net` ساخته شد — از جمله حکم‌های شبانه — سوگیری مثبت داشت.

## علتِ واقعی که پیدا شد — هندسه، نه جهت

روی کل دفتر، بر حسب فاصلهٔ استاپ، با کارمزد درست:

| فاصلهٔ استاپ | n | کارمزد | ناخالص | **خالص** | حکم |
|---|---|---|---|---|---|
| ۰–۰.۵٪ | ۱۱۵ | **۰.۴۵۴R** | +۰.۱۶۳ | **−۰.۲۹۱** | **زیر صفر** |
| ۰.۵–۰.۸٪ | ۲۴ | ۰.۲۳۷R | −۰.۰۵۰ | −۰.۲۸۷ | شامل صفر |
| **۰.۸–۱.۵٪** | ۲۹ | ۰.۱۳۸R | +۰.۱۱۷ | **−۰.۰۲۱** | شامل صفر |
| >۱.۵٪ | ۶۷ | ۰.۰۵۲R | −۰.۰۶۶ | −۰.۱۱۷ | شامل صفر |

دو بیماریِ جدا، در دو سر طیف:
- **استاپ تنگ**: لبهٔ ناخالص هست (+۰.۱۶۳) ولی کارمزد ۰.۴۵R می‌خورَدش —
  و این تنها سطلی است که حکمِ **قطعیِ زیر صفر** دارد. همان بیماریِ
  ثبت‌شدهٔ میز ۱ دقیقه و میز شوک: `کارمزد٪ ÷ استاپ٪`.
- **استاپ گشاد**: کارمزد بی‌اهمیت است ولی خودِ لبهٔ ناخالص منفی می‌شود
  (تارگتِ دور، مومنتوم خرج‌شده).

بهترین باند ۰.۸–۱.۵٪ است و آن هم فقط **شامل صفر** — یعنی با کارمزدِ
واقعی، هیچ باندی سود اثبات‌شده ندارد. این یافته به هیچ جهتی گره نخورده.

## مرز

این فایل فقط می‌شمارد و بازه می‌سازد؛ هیچ دروازه‌ای را عوض نمی‌کند.
«فقط در باند ۰.۸–۱.۵٪ معامله کن» یک **فرضیه** است نه قاعده (n=۲۹، CI
شاملِ صفر)، و ورودش به تصمیم از مسیر قانون ۰۳ می‌گذرد: بک‌تست
بیرون-از-نمونه روی کندل واقعی، CI بالای صفر، و تأیید صریح حمید.

اجرا: `python3 -m hamid.direction_autopsy`
"""
import collections
import json
import math
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent
CLOSED = ROOT / "brain" / "paper" / "closed.jsonl"

STOP_BANDS = ((0, 0.5), (0.5, 0.8), (0.8, 1.5), (1.5, 99))


def _identity(r):
    """هویت معامله برای یکتاسازی — **همان کلید قطعیِ دفتر**، نه نسخهٔ دست‌ساز.

    عیبِ اندازه‌گیری‌شدهٔ ۳۱ اوت: این‌جا کلید دست‌ساز
    `(sym, dir, opened, entry)` بود — بدون `stage`. برای عیبِ ۲۴ اوت
    (تسویهٔ دوبارهٔ یک معامله) کافی بود، ولی نمونه‌گیر شورت **عمداً** دو
    بازوی A/B را روی *یک نامزد* باز می‌کند: همان نماد، همان جهت، همان
    ورود، همان میلی‌ثانیه — فقط استاپ فرق دارد. آن کلید این دو را «یک
    معامله» می‌دید و بازوی دوم را دور می‌ریخت.

    اندازهٔ اثر روی همان آزمایشی که برای سنجشش ساخته شده بود: از ۱۲۸
    ردیفِ پُرشدهٔ باند دوم فقط ۵۵ تا به تحلیل می‌رسید — ۷۳ تا (۵۷٪) بی‌صدا
    حذف می‌شد، و حذف تصادفی نبود: فقط بازویی می‌ماند که جفتِ باند اولش
    نداشت. یعنی CIِ باند دوم روی زیرنمونهٔ سوگیرانه ساخته می‌شد.

    درسِ کلاس: محافظِ یک عیب، خودش می‌تواند عیبِ بعدی باشد. علاجش این
    است که هویتِ معامله **یک تعریف** داشته باشد — `paper.trade_key`، که
    `stage` داخلش هست — و هیچ ماژول تحلیلی نسخهٔ خودش را نسازد.
    """
    from hamid import paper
    return (paper.trade_key(r), r.get("dir"))


def load(stage_prefix="sig-"):
    """معامله‌های بستهٔ یکتا از دفتر — یکتاسازی بر هویتِ معامله.

    درس ۲۴ اوت: CI فرض می‌کند هر ردیف یک مشاهدهٔ مستقل است؛ ردیف تکراری
    بازه را به‌دروغ تنگ می‌کند. پس یکتاسازی **قبل** از هر آماری."""
    out, seen = [], set()
    for line in CLOSED.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            r = json.loads(line)
        except Exception:                            # noqa: BLE001
            continue
        stage = str((r.get("why") or {}).get("stage")
                    or r.get("stage_tag") or "")
        if not stage.startswith(stage_prefix) or r.get("R_net") is None:
            continue
        k = _identity(r)
        if k in seen:
            continue
        seen.add(k)
        r["_stage"] = stage
        try:
            r["_stop_pct"] = abs(r["entry"] - r["sl"]) / r["entry"] * 100
        except Exception:                            # noqa: BLE001
            r["_stop_pct"] = None
        # خالصِ **بازمحاسبه‌شده** با منبع واحد کارمزد.
        #
        # چرا به `R_net` ذخیره‌شده اعتماد نمی‌کنیم: تا ۳۰ اوت شب،
        # `paper._settle_one` خالص را با ۰.۱٪ می‌ساخت در حالی که مدل رسمی
        # و اعداد راستی‌آزمایی‌شدهٔ صرافی ۰.۱۵٪ است. پس دفتر دو تعریفِ
        # «خالص» دارد: ردیف‌های قدیم با ۰.۱٪، ردیف‌های تازه با ۰.۱۵٪.
        # مقایسهٔ دو گروه با دو تعریف، خودش یک مخدوش‌کننده است — و چون
        # سهم کارمزد برابر `کارمزد٪ ÷ استاپ٪` است، اثرش روی استاپ‌های
        # تنگ بزرگ‌تر می‌شود، یعنی دقیقاً روی همان چیزی که می‌سنجیم.
        # ردیف‌های گذشته بازنویسی نمی‌شوند (دادهٔ runtime دست‌نخورده،
        # قانون ضد-merge)؛ فقط این‌جا یک‌بار و یکنواخت بازمحاسبه می‌شوند.
        # بازمحاسبه از **یک** پیاده‌سازی (`fees.apply_net`) — تا ۱ سپتامبر
        # همین منطق این‌جا کپی شده بود و گزارش کار نسخهٔ خودش را داشت،
        # یعنی «منبع واحد» عملاً دو جا بود.
        try:
            from hamid import fees as _fees
            _fees.apply_net([r])
        except Exception:                            # noqa: BLE001
            r["_R_net_stored"] = r.get("R_net")
            r["_fee_r"] = r.get("fee_r")
        out.append(r)
    return out


def ci95(xs):
    n = len(xs)
    if n < 2:
        return None, None, None, n
    m = statistics.mean(xs)
    se = statistics.stdev(xs) / math.sqrt(n)
    return m, m - 1.96 * se, m + 1.96 * se, n


def verdict(lo, hi):
    return "بالای صفر" if lo > 0 else "زیر صفر" if hi < 0 else "شامل صفر"


def line(label, xs, w=30):
    m, lo, hi, n = ci95(xs)
    if n < 2:
        return f"  {label:<{w}} n={n} — نمونه کم"
    return (f"  {label:<{w}} n={n:<4} {m:+.4f}  CI[{lo:+.4f}, {hi:+.4f}]  "
            f"{verdict(lo, hi)}")


def two_sample(a, b):
    """اختلاف دو گروه مستقل با CI — آزمونی که ادعای «بدتر است» می‌خواهد.

    این همان چیزی است که در گزارش قبلی جا افتاده بود: «CI گروه A زیر صفر
    است» ادعای تک‌نمونه‌ای است و «A بدتر از B است» را اثبات نمی‌کند."""
    if len(a) < 2 or len(b) < 2:
        return None
    d = statistics.mean(a) - statistics.mean(b)
    se = math.sqrt(statistics.stdev(a) ** 2 / len(a)
                   + statistics.stdev(b) ** 2 / len(b))
    if se == 0:
        return None
    return {"diff": d, "lo": d - 1.96 * se, "hi": d + 1.96 * se,
            "t": abs(d / se), "n_a": len(a), "n_b": len(b)}


def stratified_diff(rows, by, key="R_net", a="SHORT", b="LONG"):
    """اختلاف جهت با کنترلِ یک متغیر مخدوش‌کننده (استراتژی یا باند استاپ).

    وزنِ هر طبقه = سهمش از کل نمونه؛ واریانس از جمعِ وزن‌دار. طبقه‌ای که
    یک سمتش کمتر از ۲ نمونه دارد کنار می‌رود و صریح اعلام می‌شود — طبقهٔ
    تک‌نمونه‌ای اختلاف نمی‌سازد، فقط وزن را خراب می‌کند."""
    strata = collections.defaultdict(lambda: {"a": [], "b": []})
    for r in rows:
        s = by(r)
        if s is None:
            continue
        if r["dir"] == a:
            strata[s]["a"].append(r[key])
        elif r["dir"] == b:
            strata[s]["b"].append(r[key])
    num = var = wsum = 0.0
    used, skipped = [], []
    for s, g in strata.items():
        if len(g["a"]) < 2 or len(g["b"]) < 2:
            skipped.append((s, len(g["a"]), len(g["b"])))
            continue
        w = len(g["a"]) + len(g["b"])
        d = statistics.mean(g["a"]) - statistics.mean(g["b"])
        se2 = (statistics.stdev(g["a"]) ** 2 / len(g["a"])
               + statistics.stdev(g["b"]) ** 2 / len(g["b"]))
        num += w * d
        var += (w ** 2) * se2
        wsum += w
        used.append((s, len(g["a"]), len(g["b"]), d))
    if not wsum:
        return None
    d = num / wsum
    se = math.sqrt(var) / wsum
    return {"diff": d, "lo": d - 1.96 * se, "hi": d + 1.96 * se,
            "t": abs(d / se) if se else None, "used": used, "skipped": skipped}


def standardize(rows, by, key="R_net", target="SHORT", source="LONG"):
    """میانگینِ گروه `source` اگر ترکیبش مثل `target` بود — سنجهٔ سیمپسون."""
    wt = collections.Counter(by(r) for r in rows if r["dir"] == target)
    n = sum(wt.values())
    acc = cov = 0.0
    for k, w in wt.items():
        g = [r[key] for r in rows if r["dir"] == source and by(r) == k]
        if len(g) >= 2:
            acc += (w / n) * statistics.mean(g)
            cov += w / n
    return (acc / cov, cov) if cov else (None, 0.0)


def band(r):
    p = r.get("_stop_pct")
    if p is None:
        return None
    for lo, hi in STOP_BANDS:
        if lo <= p < hi:
            return f"{lo:g}–{hi:g}٪"
    return None


def main(argv=()):
    rows = load()
    sh = [r for r in rows if r["dir"] == "SHORT"]
    lo = [r for r in rows if r["dir"] == "LONG"]
    print(f"دفتر سیگنالِ ارسالیِ بستهٔ یکتا: {len(rows)} "
          f"({len(sh)} شورت / {len(lo)} لانگ)")
    shift = [r["R_net"] - r["_R_net_stored"] for r in rows
             if r.get("_R_net_stored") is not None]
    if shift:
        print(f"خالص با منبع واحد کارمزد بازمحاسبه شد — جابه‌جایی میانه "
              f"{statistics.median(shift):+.4f}R نسبت به عددِ ذخیره‌شده "
              f"(عیبِ دو ثابت کارمزد، رفع ۳۰ اوت شب)\n")

    print("### ۱) ادعای تک‌نمونه‌ای در برابر ادعای دونمونه‌ای")
    print(line("SHORT در برابر صفر", [r["R_net"] for r in sh]))
    print(line("LONG در برابر صفر", [r["R_net"] for r in lo]))
    ts = two_sample([r["R_net"] for r in sh], [r["R_net"] for r in lo])
    print(f"\n  اختلاف خام (شورت − لانگ): {ts['diff']:+.4f}  "
          f"CI[{ts['lo']:+.4f}, {ts['hi']:+.4f}]  "
          f"{verdict(ts['lo'], ts['hi'])}  |t|={ts['t']:.2f}")
    print("  ↳ «CI شورت زیر صفر است» ادعای شورت در برابر **صفر** است،")
    print("    نه در برابر لانگ. ادعای «بدتر است» همین خط بالاست.\n")

    print("### ۲) مخدوش‌کننده: ترکیب استراتژی اصلاً یکی نیست")
    for name, g in (("شورت", sh), ("لانگ", lo)):
        c = collections.Counter(r["_stage"] for r in g)
        print(f"  {name}: " + " · ".join(f"{k} {v/len(g):.1%}"
                                         for k, v in c.most_common()))
    std, cov = standardize(rows, lambda r: r["_stage"])
    print(f"\n  خالص لانگ (واقعی)          : "
          f"{statistics.mean([r['R_net'] for r in lo]):+.4f}")
    print(f"  خالص لانگ با ترکیبِ شورت   : {std:+.4f}  (پوشش {cov:.0%})")
    print(f"  خالص شورت (واقعی)          : "
          f"{statistics.mean([r['R_net'] for r in sh]):+.4f}")
    print("  ↳ بخشی از شکاف فقط ترکیب است، نه جهت.\n")

    print("### ۳) اختلاف جهت با کنترلِ مخدوش‌کننده")
    for lbl, by in (("استراتژی", lambda r: r["_stage"]),
                    ("باند فاصلهٔ استاپ", band)):
        s = stratified_diff(rows, by)
        if not s:
            print(f"  {lbl}: طبقه‌ای با نمونهٔ کافی نماند")
            continue
        print(f"  کنترل بر {lbl:<18} {s['diff']:+.4f}  "
              f"CI[{s['lo']:+.4f}, {s['hi']:+.4f}]  "
              f"{verdict(s['lo'], s['hi'])}  |t|={s['t']:.2f}")
        if s["skipped"]:
            print(f"      ↳ طبقهٔ کنارگذاشته (نمونهٔ کم): "
                  + ", ".join(f"{k}({a}/{b})" for k, a, b in s["skipped"]))
    print()

    print("### ۴) درون یک استراتژی — جایی که استاپ هم یکسان است")
    for stg in sorted({r["_stage"] for r in rows}):
        a = [r for r in sh if r["_stage"] == stg]
        b = [r for r in lo if r["_stage"] == stg]
        if len(a) < 2 or len(b) < 2:
            continue
        ms = statistics.median([r["_stop_pct"] for r in a if r["_stop_pct"]])
        ml = statistics.median([r["_stop_pct"] for r in b if r["_stop_pct"]])
        print(f"  — {stg}  (میانهٔ استاپ: شورت {ms:.3f}٪ / لانگ {ml:.3f}٪)")
        print(line("    ناخالص شورت", [r["R"] for r in a], 26))
        print(line("    ناخالص لانگ", [r["R"] for r in b], 26))
        print(line("    خالص شورت", [r["R_net"] for r in a], 26))
        print(line("    خالص لانگ", [r["R_net"] for r in b], 26))
        d = two_sample([r["R_net"] for r in a], [r["R_net"] for r in b])
        if d:
            print(f"      اختلاف خالص: {d['diff']:+.4f}  "
                  f"CI[{d['lo']:+.4f}, {d['hi']:+.4f}]  "
                  f"{verdict(d['lo'], d['hi'])}  |t|={d['t']:.2f}")
        print()

    print("### ۵) علتِ واقعی: هندسه — کارمزد در برابر فاصلهٔ استاپ")
    for b_lo, b_hi in STOP_BANDS:
        g = [r for r in rows
             if r["_stop_pct"] is not None and b_lo <= r["_stop_pct"] < b_hi]
        if len(g) < 5:
            continue
        fee = [r["_fee_r"] for r in g if r.get("_fee_r") is not None]
        m, clo, chi, n = ci95([r["R_net"] for r in g])
        print(f"  استاپ {b_lo:g}–{b_hi:g}٪  n={n:<4} "
              f"کارمزد={statistics.mean(fee):.3f}R  "
              f"ناخالص={statistics.mean([r['R'] for r in g]):+.4f}  "
              f"خالص={m:+.4f} CI[{clo:+.4f}, {chi:+.4f}] {verdict(clo, chi)}")
    print("  ↳ کارمزد سهمی ثابت از R نیست؛ برابرِ کارمزد٪ ÷ استاپ٪ است.")
    print("    استاپِ تنگ = کارمزدخوار. استاپِ گشاد = لبهٔ ناخالص خرج‌شده.\n")

    print("### ۶) عدم‌تقارنی که واقعاً هست و دلیل می‌خواهد")
    for stg in sorted({r["_stage"] for r in rows}):
        a = sum(1 for r in sh if r["_stage"] == stg)
        b = sum(1 for r in lo if r["_stage"] == stg)
        if a + b >= 5:
            print(f"  {stg:<12} شورت={a:<4} لانگ={b:<4} "
                  f"سهم شورت={a/(a+b):.1%}")
    print("  ↳ چرا یک استراتژی تقریباً هرگز شورت نمی‌دهد، سؤالِ باز است.")

    print("\n### مرز صادقانه")
    print("  هیچ‌کدام از این اعداد دروازه نشد. باندِ ۰.۸–۱.۵٪ فقط n=۲۹ دارد")
    print("  و CI‌اش صفر را در بر می‌گیرد — فرضیه است، نه قاعده (قانون ۰۳).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
