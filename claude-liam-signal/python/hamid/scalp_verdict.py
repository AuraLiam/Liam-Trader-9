"""ماشینِ حکمِ میز ۱ دقیقه — «مجزا برویم جلو تا به نتیجه برسد».

دستور حمید (۲۴ اوت): «آن سیستم سیگنال‌دهی و پیپر تریدینگ همان‌طور مثل
قبل برود جلو، ولی این سیستم یک دقیقه‌ای باید به صورت مجزا برویم جلو تا
به نتیجه برسد.»

«به نتیجه رسیدن» تا امروز تعریف نداشت — و چیزی که تعریف ندارد، هرگز
تمام نمی‌شود. این فایل تعریفش می‌کند، **از پیش**، تا بعداً کسی آستانه را
جابه‌جا نکند:

    PROMOTE  — بازهٔ اطمینانِ **خالص از کارمزد** کاملاً بالای صفر،
               روی n ≥ MIN_N. تازه آن‌وقت پیشنهادِ ورود به تولید.
    REJECT   — بازهٔ خالص کاملاً زیر صفر روی n ≥ REJECT_N.
    UNDECIDED— هر چیز دیگر. همراهش برآوردِ «چند معاملهٔ دیگر تا
               تصمیم‌پذیری» می‌آید تا معلوم باشد جواب چقدر دور است.

## حکم به **پیکربندی** می‌خورد، نه به «ایدهٔ ۱ دقیقه»

این تفکیک حیاتی است و گرنه یک REJECT کلِ پروژه را می‌کشد. هر حکم با
اثرانگشتِ پارامترهایی که قضاوتشان کرده ثبت می‌شود (`config`). عوض‌شدنِ
هر پارامتر یعنی **دفترِ حکم از صفر شروع می‌شود** — چون داده‌ای که با
هندسهٔ قبلی جمع شده، دربارهٔ هندسهٔ جدید چیزی نمی‌گوید.

پس REJECT یعنی «این هندسه را دیگر اجرا نکن»، نه «۱ دقیقه را رها کن».
اگر تشخیص بگوید لبهٔ ناخالص هست و کارمزد می‌خوردش، قدمِ بعد روشن است:
هندسهٔ بزرگ‌تر، نه صبرِ بیشتر.

## چرا معیار «خالص» است نه «ناخالص»

چون همان جایی است که این میز می‌بازد. اندازه‌گیری ۲۴ اوت روی دفتر
اسکلپ: ناخالص +۰.۰۴۶R، کارمزد ۰.۲۱۵R، خالص −۰.۱۶۹R. لبه‌ای که کارمزد
را رد نکند، لبه نیست — پولش را حمید می‌دهد نه بک‌تست.

## مرز صادقانه

این فایل **هیچ‌چیز را به تولید نمی‌برد**. حتی PROMOTE فقط یک پیشنهاد
است؛ ورود به تولید تأیید صریح حمید می‌خواهد (قانون ۱۲). و هیچ ربطی به
دفتر سیگنال ندارد: فقط `stage="scalp"` خوانده می‌شود، پس روشن و خاموش
شدنش روی مسیر سیگنال اثر ندارد (قانون ۹).

اجرا:  python3 -m hamid.scalp_verdict
       python3 -m hamid.scalp_verdict --alert     (+ تلگرام روی تغییر حکم)
"""
import argparse
import json
import random
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
ROOT = HERE.parents[2]
CLOSED = ROOT / "brain" / "paper" / "closed.jsonl"
OUT = ROOT / "signals" / "scalp-verdict.json"

STAGE = "scalp"
MIN_N = 400              # زیر این، هیچ حکمی — نه مثبت نه منفی
REJECT_N = 3000          # برای «مُرد» نمونهٔ بزرگ‌تر می‌خواهیم تا فرضیه
                         # با یک دورهٔ بد دفن نشود
N_BOOT, SEED = 3000, 7   # بازتولیدپذیر: عدد امروز فردا هم همان است


def config():
    """اثرانگشتِ هندسه‌ای که این حکم دربارهٔ آن است.

    از خودِ `liam9_strategy.SCALP` خوانده می‌شود، نه کپیِ دستی — تا
    عوض‌شدنِ پارامتر خودبه‌خود در اثرانگشت دیده شود و حکمِ کهنه به
    هندسهٔ جدید نچسبد.
    """
    try:
        import liam9_strategy as ST
        S = ST.SCALP
        return {k: S[k] for k in
                ("rr_target", "max_fee_r", "fee_round_trip_pct",
                 "ibs_long_max", "ibs_short_min", "hold_bars", "liq_guard")
                if k in S}
    except Exception as e:                           # noqa: BLE001
        return {"error": str(e)}


def load(path=None, stage=STAGE):
    p = Path(path) if path else CLOSED
    if not p.exists():
        return []
    out = []
    with p.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if (r.get("why") or {}).get("stage") != stage:
                continue
            if r.get("R") is None:
                continue
            out.append(r)
    return out


def net_of(r):
    """R خالص از کارمزد. نبودش یعنی ردیف قدیمی — با fee_r بازسازی می‌شود."""
    if r.get("R_net") is not None:
        return float(r["R_net"])
    fee = r.get("fee_r")
    return float(r["R"]) - float(fee) if fee is not None else None


def boot_ci(xs, n_boot=N_BOOT, seed=SEED, alpha=0.05):
    if len(xs) < 2:
        return None
    rnd = random.Random(seed)
    m = [statistics.fmean(rnd.choices(xs, k=len(xs))) for _ in range(n_boot)]
    m.sort()
    lo = m[int(n_boot * alpha / 2)]
    hi = m[int(n_boot * (1 - alpha / 2)) - 1]
    return [round(lo, 4), round(hi, 4)]


def needed_n(xs, target_half_width=None):
    """برآوردِ «چند معاملهٔ دیگر تا تصمیم‌پذیری».

    عرضِ بازه با ۱/√n کوچک می‌شود. برای اینکه بازه صفر را رها کند، باید
    نصفِ عرض از |میانگین| کمتر شود. پس:

        n_لازم ≈ n × (نصفِ‌عرضِ‌فعلی ÷ |میانگین|)²

    این برآورد است نه وعده: فرض می‌کند میانگینِ واقعی همین بماند. اگر
    میانگین به صفر نزدیک باشد عدد به‌سرعت نجومی می‌شود — و همان خودش
    جواب است: «با این اندازهٔ اثر، هرگز.»
    """
    if len(xs) < 30:
        return None
    mean = statistics.fmean(xs)
    ci = boot_ci(xs)
    if not ci or mean == 0:
        return None
    half = (ci[1] - ci[0]) / 2
    if half <= abs(mean):
        return 0
    need = len(xs) * (half / abs(mean)) ** 2
    return None if need > 10_000_000 else int(need - len(xs))


def decide(rows):
    """→ دیکشنری حکم. تنها جایی که قاعدهٔ توقف تعریف می‌شود.

    ردیفِ بی‌نمره این‌جا هم دور ریخته می‌شود، نه فقط در `load` — چون
    `decide` نقطهٔ ورودِ عمومی است و ممکن است مستقیم صدا زده شود.
    """
    rows = [r for r in rows if r.get("R") is not None]
    nets = [v for v in (net_of(r) for r in rows) if v is not None]
    gross = [float(r["R"]) for r in rows]
    n = len(nets)
    res = {"stage": STAGE, "n": n, "n_min_for_verdict": MIN_N,
           "n_min_for_reject": REJECT_N}
    if n < MIN_N:
        res.update(verdict="UNDECIDED",
                   why=f"نمونه {n} از کف {MIN_N} کمتر است — هیچ حکمی، "
                       "نه مثبت نه منفی",
                   more_trades_needed=MIN_N - n)
        if n:
            res["mean_net"] = round(statistics.fmean(nets), 4)
        return res

    mean_net = statistics.fmean(nets)
    ci_net = boot_ci(nets)
    fees = [float(r["fee_r"]) for r in rows if r.get("fee_r") is not None]
    res.update(
        win_pct=round(sum(1 for g in gross if g > 0) / len(gross) * 100, 1),
        mean_gross=round(statistics.fmean(gross), 4),
        ci95_gross=boot_ci(gross),
        mean_fee=round(statistics.fmean(fees), 4) if fees else None,
        mean_net=round(mean_net, 4), ci95_net=ci_net,
        sum_net=round(sum(nets), 1))

    if ci_net and ci_net[0] > 0:
        res.update(verdict="PROMOTE",
                   why=f"بازهٔ خالص [{ci_net[0]:+}, {ci_net[1]:+}] کاملاً "
                       f"بالای صفر روی n={n} — پیشنهادِ ورود به تولید، "
                       "با تأیید صریح حمید (قانون ۱۲)")
    elif ci_net and ci_net[1] < 0 and n >= REJECT_N:
        res.update(verdict="REJECT",
                   why=f"بازهٔ خالص [{ci_net[0]:+}, {ci_net[1]:+}] کاملاً "
                       f"زیر صفر روی n={n} ≥ {REJECT_N} — **این هندسه** "
                       "مُرد. ادامهٔ اجرایش با همین پارامترها فقط سوزاندن "
                       "رانر است؛ قدم بعد عوض‌کردن هندسه است، نه صبر بیشتر")
    else:
        need = needed_n(nets)
        res.update(verdict="UNDECIDED",
                   why=f"بازهٔ خالص [{ci_net[0]:+}, {ci_net[1]:+}] صفر را "
                       "در بر می‌گیرد یا هنوز کف رد را ندارد",
                   more_trades_needed=need)
        if need == 0:
            res["why"] += " — بازه از صفر رد شده ولی کفِ نمونه هنوز نه"
        elif need is None:
            res["why"] += (" — با این اندازهٔ اثر، نمونهٔ لازم عملاً "
                           "بی‌نهایت است؛ یعنی پارامترها باید عوض شوند، "
                           "نه اینکه بیشتر صبر کنیم")
    # تشخیصِ بیماری: لبهٔ ناخالص هست ولی کارمزد می‌خورَدش؟
    cg = res.get("ci95_gross")
    if cg and cg[0] > 0 and (ci_net is None or ci_net[0] <= 0):
        res["diagnosis"] = (
            "لبهٔ ناخالص واقعی است (CI بالای صفر) ولی کارمزد آن را می‌خورد. "
            "درمانش هندسهٔ بزرگ‌تر است — استاپ و تارگتِ متناسباً بزرگ‌تر، "
            "چون سهم کارمزد = کارمزد٪ ÷ استاپ٪. اهرم در این کسر نیست و "
            "حجمِ بیشتر هم جوابش نیست: کارمزد دقیقاً با حجم بزرگ می‌شود.")
    elif cg and cg[1] <= 0:
        res["diagnosis"] = ("لبهٔ ناخالص هم وجود ندارد — مشکل کارمزد نیست، "
                            "خودِ پیش‌بینی است.")
    return res


def run(alert=False, quiet=False, path=None):
    res = decide(load(path))
    res["at"] = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())
    res["panel"] = "لیام تریدر ۹"
    res["config"] = config()
    res["scope"] = ("حکم دربارهٔ همین هندسه است، نه دربارهٔ «ایدهٔ ۱ دقیقه». "
                    "هر تغییرِ پارامتر یعنی دفترِ حکم از صفر.")
    res["boundary"] = ("این میز مجزاست: فقط stage=scalp خوانده می‌شود و "
                       "هیچ اثری روی دفتر سیگنال و وتوها ندارد (قانون ۹). "
                       "PROMOTE هم فقط پیشنهاد است؛ ورود به تولید تأیید "
                       "صریح حمید می‌خواهد (قانون ۱۲).")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    if not quiet:
        print(f"میز ۱ دقیقه — حکم: {res['verdict']}  (n={res['n']})")
        if res.get("mean_net") is not None:
            print(f"  ناخالص {res.get('mean_gross')}R · کارمزد "
                  f"{res.get('mean_fee')}R · خالص {res['mean_net']}R "
                  f"CI {res.get('ci95_net')}")
        print(f"  {res['why']}")
        if res.get("more_trades_needed"):
            print(f"  ≈ {res['more_trades_needed']} معاملهٔ دیگر تا تصمیم‌پذیری")
        if res.get("diagnosis"):
            print(f"  🔍 {res['diagnosis']}")
    # تلگرام برای میز ۱ دقیقه **کاملاً بسته است** (دستور صریح حمید،
    # ۲۷ اوت: «اصلاً قرار نبود هیچ پیامی از ترید در تایم یک دقیقه بیاد؛
    # ترید یک دقیقه فقط در پیپرمود است و وقتی عملکردش بهتر شد از آن
    # استفاده می‌کنیم»). حکم فقط در signals/scalp-verdict.json و پنل
    # می‌نشیند؛ اگر روزی PROMOTE شد، خودِ حمید در گزارش کار می‌بیندش.
    # پارامتر alert عمداً نگه داشته شده تا فراخوان‌های قدیمی نشکنند —
    # ولی دیگر هیچ پیامی نمی‌فرستد.
    del alert
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--alert", action="store_true")
    run(alert=ap.parse_args().alert)
