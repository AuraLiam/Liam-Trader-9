"""آزمایشگاه شورت — تست شورت روی هر شورتی که تا امروز باز کرده‌ایم.

دستور حمید (۳۰ اوت شب): «استراتژی را بیشتر روی شورت در پیپرمود تست
بگیرید.»

## چرا اول این، بعد نمونه‌گیری تازه

دفتر سیگنالِ ارسالی فقط **۸۳ شورتِ بسته** دارد. با انحراف معیارِ
اندازه‌گیری‌شدهٔ ~۰.۹R، برای بازهٔ اطمینان با نیم‌پهنای ۰.۱R حدود
**۳۰۰ نمونه در هر سلول** لازم است. یعنی با نرخ ارسال زنده، جواب ماه‌ها
طول می‌کشد.

ولی شورت‌های بسته‌شده در دفترهای دیگر از قبل موجودند و **هیچ‌وقت
تحلیل نشده بودند**:

| دفتر | شورتِ بستهٔ یکتا | چیست |
|---|---|---|
| `sig-*` | ۸۳ | آنچه واقعاً برای حمید رفت |
| `vetoed` | **۸۸۲** | ستاپی که premortem رد کرد — گروه ضدواقع |
| `practice` | ۲۵۹ | تمرین |
| `first` | ۱۹۲ | پولبک اول (آزمایش) |
| `second` | ۳۵ | پولبک دوم |
| **جمع** | **۱٬۴۵۱** | ۱۷ برابرِ دفتر ارسالی |

دفتر `vetoed` مخصوصاً باارزش است: ستاپ‌هایی که رد شدند ولی نتیجه‌شان
دنبال شد. یعنی جواب «اگر رد نمی‌کردیم چه می‌شد» را از قبل داریم.

## چیزی که این فایل **نمی‌کند**

نمونهٔ تازه نمی‌سازد و هیچ دروازه‌ای را عوض نمی‌کند. و مهم‌تر: بیشتر
کردنِ شورت با **همان هندسه** فقط بازهٔ منفی را تنگ‌تر می‌کند، نه این‌که
چیزی یاد بدهد. سؤالِ درست «شورت یا لانگ؟» نیست — «کدام هندسه؟» است.
پس همه‌چیز این‌جا بر حسب **فاصلهٔ استاپ** تفکیک می‌شود.

## کارمزد

خالص از `entry`/`sl` با منبع واحد (`hamid/fees.py`) **بازمحاسبه**
می‌شود، نه از `R_net` ذخیره‌شده — چون تا ۳۰ اوت شب دفتر با ۰.۱٪ حساب
می‌کرد و مدل رسمی ۰.۱۵٪ است (عیب رفع‌شده). دو تعریف در یک نمونه، خودش
یک مخدوش‌کننده است.

اجرا: `python3 -m hamid.short_lab`
"""
import collections
import statistics
import sys

from hamid.direction_autopsy import (STOP_BANDS, band, ci95, load,
                                     two_sample, verdict)

LEDGERS = (("sig-", "ارسالی"), ("vetoed", "وتوشده"), ("practice", "تمرین"),
           ("first", "پولبک ۱"), ("second", "پولبک ۲"),
           # دفتر نمونه‌گیر باندی (دستور ۳۰ اوت) — hamid/short_sampler.py
           ("exp-short", "آزمایش باندی"))

# انحراف معیارِ اندازه‌گیری‌شدهٔ خالصِ شورت — برای برآورد n لازم
TARGET_HALFWIDTH = 0.10


def need_n(xs, half=TARGET_HALFWIDTH):
    """چند نمونه لازم است تا نیم‌پهنای CI به `half` برسد."""
    if len(xs) < 2:
        return None
    sd = statistics.stdev(xs)
    return int(round((1.96 * sd / half) ** 2))


def pool(dirs=("SHORT",)):
    """همهٔ شورت‌های بستهٔ یکتا از همهٔ دفترها، با برچسب دفتر."""
    out = []
    for pre, name in LEDGERS:
        for r in load(pre):
            if r["dir"] in dirs:
                r["_ledger"] = name
                out.append(r)
    return out


def _row(label, xs, w=24):
    m, lo, hi, n = ci95(xs)
    if n < 2:
        return f"  {label:<{w}} n={n} — نمونه کم"
    return (f"  {label:<{w}} n={n:<5} {m:+.4f}  CI[{lo:+.4f}, {hi:+.4f}]  "
            f"{verdict(lo, hi)}")


def main(argv=()):
    shorts = pool()
    longs = pool(("LONG",))
    print(f"شورتِ بستهٔ یکتا در همهٔ دفترها: {len(shorts)} "
          f"(در برابر {len(longs)} لانگ)")
    print("خالص از entry/sl با منبع واحد کارمزد بازمحاسبه شده — نه از "
          "عددِ ذخیره‌شده\n")

    print("### ۱) هر دفتر جدا — شورت")
    for _, name in LEDGERS:
        g = [r["R_net"] for r in shorts if r["_ledger"] == name]
        if g:
            print(_row(name, g))
    print()

    print("### ۲) سؤالِ درست: کدام هندسه؟ — شورت، همهٔ دفترها")
    for b_lo, b_hi in STOP_BANDS:
        g = [r for r in shorts
             if r["_stop_pct"] is not None and b_lo <= r["_stop_pct"] < b_hi]
        if len(g) < 5:
            continue
        fee = [r["_fee_r"] for r in g if r.get("_fee_r") is not None]
        gross = statistics.mean([r["R"] for r in g])
        print(_row(f"استاپ {b_lo:g}–{b_hi:g}٪", [r["R_net"] for r in g])
              + f"  · کارمزد={statistics.mean(fee):.3f}R · ناخالص={gross:+.4f}")
    print()

    print("### ۳) همان تفکیک برای لانگ — تا معلوم شود مسئله جهت نیست")
    for b_lo, b_hi in STOP_BANDS:
        g = [r for r in longs
             if r["_stop_pct"] is not None and b_lo <= r["_stop_pct"] < b_hi]
        if len(g) < 5:
            continue
        print(_row(f"استاپ {b_lo:g}–{b_hi:g}٪", [r["R_net"] for r in g]))
    print()

    print("### ۴) اختلاف جهت، داخل هر باند استاپ")
    for b_lo, b_hi in STOP_BANDS:
        a = [r["R_net"] for r in shorts
             if r["_stop_pct"] is not None and b_lo <= r["_stop_pct"] < b_hi]
        b = [r["R_net"] for r in longs
             if r["_stop_pct"] is not None and b_lo <= r["_stop_pct"] < b_hi]
        d = two_sample(a, b)
        if not d:
            continue
        print(f"  استاپ {b_lo:g}–{b_hi:g}٪  شورت−لانگ = {d['diff']:+.4f}  "
              f"CI[{d['lo']:+.4f}, {d['hi']:+.4f}]  "
              f"{verdict(d['lo'], d['hi'])}  |t|={d['t']:.2f}  "
              f"(n={d['n_a']}/{d['n_b']})")
    print()

    print("### ۵) ناخالص در برابر خالص — کجا لبه هست و کارمزد می‌خورَدش")
    for b_lo, b_hi in STOP_BANDS:
        g = [r for r in shorts
             if r["_stop_pct"] is not None and b_lo <= r["_stop_pct"] < b_hi]
        if len(g) < 5:
            continue
        gm, glo, ghi, gn = ci95([r["R"] for r in g])
        print(f"  استاپ {b_lo:g}–{b_hi:g}٪  ناخالص n={gn:<5} {gm:+.4f} "
              f"CI[{glo:+.4f}, {ghi:+.4f}] {verdict(glo, ghi)}")
    print()

    print("### ۶) چقدر نمونه لازم است — و چقدر داریم")
    allshort = [r["R_net"] for r in shorts]
    print(f"  انحراف معیار خالصِ شورت: {statistics.stdev(allshort):.4f}")
    print(f"  برای نیم‌پهنای ±{TARGET_HALFWIDTH}R لازم است: "
          f"n ≈ {need_n(allshort)}")
    for b_lo, b_hi in STOP_BANDS:
        g = [r["R_net"] for r in shorts
             if r["_stop_pct"] is not None and b_lo <= r["_stop_pct"] < b_hi]
        if len(g) >= 2:
            nn = need_n(g)
            gap = max(0, nn - len(g))
            print(f"  استاپ {b_lo:g}–{b_hi:g}٪: داریم {len(g):<5} "
                  f"لازم {nn:<6} کمبود {gap}")
    print()

    print("### ۷) نمادهایی که سطلِ شورت را می‌سازند")
    c = collections.Counter(r["sym"] for r in shorts)
    print("  " + " · ".join(f"{k}×{v}" for k, v in c.most_common(10)))
    print()

    print("### مرز صادقانه")
    print("  دفترهای غیرارسالی گروه ضدواقع‌اند، نه محصول: ستاپی که رد شد و")
    print("  فقط نتیجه‌اش دنبال شد. پس این اعداد می‌گویند «اگر می‌رفت چه")
    print("  می‌شد»، نه «چه فرستادیم». هیچ دروازه‌ای با این اعداد عوض")
    print("  نمی‌شود؛ ورود به تصمیم فقط از مسیر قانون ۰۳ — بک‌تست")
    print("  بیرون-از-نمونه روی کندل واقعی، CI بالای صفر، تأیید حمید.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
