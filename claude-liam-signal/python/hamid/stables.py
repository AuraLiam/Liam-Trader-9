"""تحلیل دامیننس تتر **در کنار کل استیبل‌کوین‌ها** (دستور حمید، ۸ سپتامبر).

حمید: «باید دامیننس تتر رو در کنار کل استیبل‌کوین‌ها تحلیل کنی. بعضی وقتا
افزایش تتر می‌تونه به دلیل چنج کردن یو‌اس‌دی‌سی یا بقیهٔ استیبل‌کوین‌ها به
تتر باشه که بتونن باهاش ترید کنند. بررسی کن اگه این استدلال درسته.»

## استدلال درست است — ولی نه به آن دلیلی که در نگاه اول به نظر می‌رسد

USDT.D یک **نسبت** است:

    USDT.D = عرضهٔ تتر ÷ کل ارزش بازار

پس بالا رفتنش دست‌کم چهار ریشهٔ کاملاً متفاوت دارد، و سه‌تایشان «بازار
نزولی» نیستند:

| ریشه | چه اتفاقی افتاده | معنی برای جهت |
|---|---|---|
| `MARKET_FALL` | عرضه ثابت، مخرج (کل بازار) ریخته | ریسک‌آف واقعی — شورت |
| `NEW_MONEY` | عرضهٔ استیبل بالا رفته، پول تازه وارد شده و هنوز نخریده | باروتِ خشک — نه شورت |
| `ROTATION` | عرضهٔ تتر ↑ و عرضهٔ یواس‌دی‌سی ↓ — همان چیزی که حمید گفت | **خنثی** — هیچ پولی وارد یا خارج نشده |
| `REDEMPTION` | عرضهٔ استیبل پایین آمده، پول از اکوسیستم بیرون رفته | ریسک‌آف عمیق‌تر |

`ROTATION` دقیقاً همان حالتی است که حمید توصیف کرد: کسی یواس‌دی‌سی‌اش را
تتر می‌کند تا بتواند ترید کند. در این حالت USDT.D بالا می‌رود بی‌آنکه یک
دلار از بازار خارج شده باشد — و خواندنش به‌عنوان «بازار نزولی» غلط است.

## سنجهٔ ایمن: STABLE.D به‌جای USDT.D

    STABLE.D = USDT.D + USDC.D

چرخشِ بین دو استیبل، این عدد را **اصلاً تکان نمی‌دهد** (آنچه از یکی کم
می‌شود به دیگری اضافه می‌شود). پس ریسک‌آفِ واقعی را باید با STABLE.D
سنجید، نه با USDT.D تنها. این خاصیت ساختاری است، نه یافتهٔ آماری.

## اندازه‌گیری ۸ سپتامبر — مرزِ صادقانه

روی `brain/dominance-series.json`، ۲٬۸۶۶ نقطهٔ دارای u+c+m، بازهٔ
۲۹ اوت تا ۸ سپتامبر (~۱۰ روز)، پنجره‌های **بدون هم‌پوشانی**:

| افق | «USDT.D بالا رفت» | چرخش | پول تازه | ریزشِ مخرج |
|---|---|---|---|---|
| ۱ ساعت | ۵۶ مورد | **۰ (۰٪)** | ۸ (۱۴٪) | ۳۲ (۵۷٪) |
| ۴ ساعت | ۱۰ مورد | **۰ (۰٪)** | ۰ | ۹ (۹۰٪) |

یعنی: **در این ۱۰ روز حالت چرخش یک بار هم رخ نداده.** ریشهٔ غالبِ بالا
رفتن USDT.D همان ریزشِ بازار بوده — پس خواندنِ سادهٔ امروز در این پنجره
اتفاقاً درست بوده، ولی **به‌خاطر رژیم، نه به‌خاطر درستیِ سنجه**.

دو چیز که این عدد **اثبات نمی‌کند**:
  · «چرخش هرگز رخ نمی‌دهد» — ۱۰ روز پنجرهٔ کوچکی است و رویدادهای
    شناخته‌شدهٔ چرخشِ استیبل (نمونهٔ کلاسیک: بحران یواس‌دی‌سی مارس ۲۰۲۳)
    در آن نیست.
  · «STABLE.D پیش‌بینِ بهتری است» — در همین پنجره همبستگی هر دو با
    بازدهٔ آیندهٔ بازار عملاً یکی است (۰.۱۲ در برابر ۰.۱۲ روی افق ۳۰د).
    برتری STABLE.D **ساختاری** است (مصونیت از چرخش)، نه اثبات‌شدهٔ آماری.

پس این ماژول یک **طبقه‌بند** است، نه یک ادعای تازه: هر بار علتِ حرکت را
می‌شمارد و می‌نویسد، تا روزی که چرخش واقعاً رخ داد، موتور آن را
«بازار نزولی» نخواند.

## محدودیت دقتِ داده

دامیننس با سه رقم اعشار ذخیره می‌شود (`round(...,3)`). روی USDT.D≈۶.۸،
یک تیک = ۰.۰۱۵٪ نسبی. پس کفِ حرکتِ لگاریتمی (`MIN_LOG_MOVE`) پنج برابرِ
همان تیک گرفته شده تا نویزِ گردکردن، «چرخش» جعل نکند.

## مرز

خروجی این ماژول برای مسیرِ **سیگنالِ زندهٔ پنل** شاهد است، نه دروازه
(قانون ۰۳). تنها جایی که دروازه است، موتور شورتِ داشبورد است — با دستور
صریح حمید («اولویت روند پوزیشن باز کردن باید با تشخیص روند حرکت دامیننس
تتر باشد») و همان‌جا هم PRODUCTION_APPROVED خاموش می‌ماند تا CI بالای
صفر بیاید.
"""
import math

# فقط استیبل‌هایی که منبع (CoinGecko global) در سهم‌های ده‌تایی‌اش گزارش
# می‌کند. DAI و بقیه در آن فهرست نیستند؛ نبودشان **اعلام** می‌شود، حدس
# زده نمی‌شود (قانون ۰۱ بند ۱).
STABLE_KEYS = ("u", "c")            # u=USDT.D · c=USDC.D
STABLE_NAMES = {"u": "USDT", "c": "USDC"}
COVERAGE_NOTE = ("فقط USDT و USDC — منبع فقط همین دو را در سهم‌های "
                 "ده‌تایی گزارش می‌کند؛ DAI و بقیه شمرده نمی‌شوند")

# کفِ حرکت: پنج برابرِ تیکِ گردکردنِ منبع (۰.۰۰۱ روی ~۶.۸ ⇒ ۱.۵e-۴)
MIN_LOG_MOVE = 0.0008
# کفِ حرکتِ نسبت تا «USDT.D بالا رفت» شمرده شود (واحد درصدِ دامیننس)
MIN_DOM_MOVE = 0.004
# پشتیبانِ آستانهٔ رژیم وقتی سری برای کالیبراسیون کوتاه است — از میانهٔ
# اندازه‌گیری‌شدهٔ ۸ سپتامبر (۱س: ۰.۰۱۶۵ · ۴س: ۰.۰۳۸۰)
REGIME_FALLBACK = {60: 0.017, 240: 0.038}
MIN_CALIB_N = 20


def stable_d(p):
    """STABLE.D = مجموعِ دامیننسِ استیبل‌های گزارش‌شده، یا None."""
    vals = [p.get(k) for k in STABLE_KEYS]
    if any(v is None for v in vals):
        return None
    return sum(vals)


def supplies(p):
    """عرضهٔ دلاریِ هر استیبل از نسبت و مخرج — مخرجِ مشترک حذف می‌شود.

    این نکتهٔ کلیدیِ سنجش است: روی **نسبت‌ها**، USDT.D و USDC.D همبستگی
    +۰.۹۸۹ دارند و چرخش اصلاً دیده نمی‌شود — چون هر دو یک مخرج دارند و
    ریزشِ بازار هر دو را با هم بالا می‌برد. چرخش فقط روی **عرضه** دیده
    می‌شود (همبستگی روی عرضه: +۰.۸۸ در ۱س، +۰.۴۴ در ۴س)."""
    m = p.get("m")
    if not m:
        return None
    out = {}
    for k in STABLE_KEYS:
        v = p.get(k)
        if v is None:
            return None
        out[STABLE_NAMES[k]] = v / 100.0 * m
    return out


def _at(points, t_target, tol_ms=8 * 60_000):
    """آخرین نقطهٔ **قبل از** لحظهٔ هدف — هرگز جلوتر.

    نسخهٔ اول «نزدیک‌ترین» نقطه را می‌گرفت و می‌توانست تا ۸ دقیقه جلوتر
    از هدف باشد. روی مسیر زنده بی‌ضرر است (نقطهٔ آینده وجود ندارد) ولی
    در بازپخشِ بک‌تست همان **نگاه به آینده** است — و بک‌تستی که ۸ دقیقه
    آینده را ببیند، عددش دروغ می‌گوید. پس عقب‌نگر، بی‌استثنا.
    """
    ok = [p for p in points
          if p.get("m") and stable_d(p) is not None and p["t"] <= t_target]
    if not ok:
        return None
    p = max(ok, key=lambda x: x["t"])
    return p if t_target - p["t"] <= tol_ms else None


def _log(a, b):
    return math.log(b / a) if (a and b and a > 0 and b > 0) else None


def regime_threshold(points, minutes):
    """آستانهٔ «حرکتِ معنادار» روی STABLE.D = **میانهٔ همان افق**.

    عدد ثابت این‌جا سلیقه است: ۰.۰۲ روی افق ۴ساعته حرکتِ کوچکی است
    (میانهٔ اندازه‌گیری‌شده ۰.۰۳۸) ولی روی افق ۱ساعته بزرگ. پس مثل
    `dom_tf.delta_threshold` از توزیعِ خودِ سری می‌آید: نصفِ حرکت‌ها
    زیر میانه‌اند، پس «بالاتر از میانه» یعنی «بزرگ‌تر از حرکتِ معمول».
    نمونهٔ کم → پشتیبانِ اندازه‌گیری‌شده، نه حدس."""
    if not points:
        return REGIME_FALLBACK.get(minutes, 0.02)
    step = minutes * 60_000
    ds, t = [], points[0]["t"] + step
    while t <= points[-1]["t"]:
        a, b = _at(points, t - step), _at(points, t)
        t += step
        if a and b:
            sa, sb = stable_d(a), stable_d(b)
            if sa is not None and sb is not None:
                ds.append(abs(sb - sa))
    if len(ds) < MIN_CALIB_N:
        return REGIME_FALLBACK.get(minutes, 0.02)
    ds.sort()
    return round(ds[len(ds) // 2], 4)


def classify(points, minutes=60, now_ms=None):
    """علتِ حرکتِ USDT.D در بازهٔ داده‌شده. → dict با `cause` و شواهد.

    `cause` ∈ INSUFFICIENT · ROTATION · NEW_MONEY · REDEMPTION ·
    MARKET_FALL · MARKET_RISE · FLAT · MIXED
    """
    if not points:
        return {"cause": "INSUFFICIENT", "why": "سری خالی است"}
    now = now_ms or points[-1]["t"]
    b = _at(points, now)
    a = _at(points, now - minutes * 60_000)
    if not a or not b:
        return {"cause": "INSUFFICIENT", "window_min": minutes,
                "why": f"نقطهٔ دارای عرضه در دو سرِ پنجرهٔ {minutes}د نیست "
                       "— عدد ساخته نمی‌شود (قانون ۰۱ بند ۱)"}
    sa, sb = supplies(a), supplies(b)
    if not sa or not sb:
        return {"cause": "INSUFFICIENT", "window_min": minutes,
                "why": "عرضه محاسبه نشد (کل بازار روی نقطه نیست)"}

    g = {n: _log(sa[n], sb[n]) for n in sa}
    g_tot = _log(sum(sa.values()), sum(sb.values()))
    g_m = _log(a["m"], b["m"])
    d_u = b.get("u", 0) - a.get("u", 0)
    d_s = stable_d(b) - stable_d(a)
    if any(v is None for v in list(g.values()) + [g_tot, g_m]):
        return {"cause": "INSUFFICIENT", "window_min": minutes,
                "why": "لگاریتمِ رشد محاسبه نشد (عددِ نامعتبر)"}

    up = [n for n, v in g.items() if v > MIN_LOG_MOVE]
    down = [n for n, v in g.items() if v < -MIN_LOG_MOVE]
    if up and down:
        cause = "ROTATION"
        why = (f"عرضهٔ {'/'.join(up)} بالا و {'/'.join(down)} پایین — چرخشِ "
               "بین استیبل‌ها؛ پولی وارد یا خارج نشده")
    elif g_tot > MIN_LOG_MOVE:
        cause = "NEW_MONEY"
        why = "کلِ عرضهٔ استیبل بالا رفته — پولِ تازه وارد شده و هنوز نخریده"
    elif g_tot < -MIN_LOG_MOVE:
        cause = "REDEMPTION"
        why = "کلِ عرضهٔ استیبل پایین آمده — پول از اکوسیستم بیرون رفته"
    elif g_m < -MIN_LOG_MOVE:
        cause = "MARKET_FALL"
        why = "عرضه ثابت و کل بازار ریخته — مخرج کوچک شده، ریسک‌آفِ واقعی"
    elif g_m > MIN_LOG_MOVE:
        cause = "MARKET_RISE"
        why = "عرضه ثابت و کل بازار بالا رفته — مخرج بزرگ شده، ریسک‌آن"
    elif abs(d_u) < MIN_DOM_MOVE:
        cause = "FLAT"
        why = "نه عرضه تکان خورده نه مخرج — حرکتِ معناداری نیست"
    else:
        cause = "MIXED"
        why = "هیچ ریشه‌ای غالب نیست — حکمِ تک‌علتی صادر نمی‌شود"

    return {
        "cause": cause, "why": why, "window_min": minutes,
        "d_usdt_d": round(d_u, 4), "d_stable_d": round(d_s, 4),
        "supply_growth": {n: round(v, 6) for n, v in g.items()},
        "supply_growth_total": round(g_tot, 6),
        "mcap_growth": round(g_m, 6),
        "usdt_d": round(b.get("u", 0), 3), "stable_d": round(stable_d(b), 3),
        "misleading": cause in ("ROTATION", "NEW_MONEY"),
        "coverage": COVERAGE_NOTE,
    }


def regime(points, minutes=240, now_ms=None):
    """جهتِ بازار از **STABLE.D**، نه از USDT.D تنها.

    چرا STABLE.D: چرخشِ بین استیبل‌ها این عدد را تکان نمی‌دهد، پس
    «پول به حاشیه رفت» را با «پول از یواس‌دی‌سی به تتر رفت» اشتباه
    نمی‌گیرد. رشدِ STABLE.D یعنی سهمِ بیشتری از بازار نقد نشسته =
    ریسک‌آف = سوگیریِ شورت؛ افتش یعنی پول به دارایی رفته = سوگیری لانگ.
    """
    if not points:
        return {"bias": "INSUFFICIENT", "why": "سری خالی است"}
    now = now_ms or points[-1]["t"]
    b = _at(points, now)
    a = _at(points, now - minutes * 60_000)
    if not a or not b:
        return {"bias": "INSUFFICIENT", "window_min": minutes,
                "why": f"نقطهٔ دارای استیبل در دو سرِ پنجرهٔ {minutes}د نیست"}
    sd_a, sd_b = stable_d(a), stable_d(b)
    d = sd_b - sd_a
    thr = regime_threshold(points, minutes)
    cls = classify(points, minutes, now_ms=now)
    if d > thr:
        bias, why = "SHORT_BIAS", (
            f"STABLE.D از {sd_a:.3f} به {sd_b:.3f} رفت (+{d:.3f}، بالاتر از "
            f"میانهٔ {thr}) — سهمِ نقدِ نشسته بیشتر شده، ریسک‌آف")
    elif d < -thr:
        bias, why = "LONG_BIAS", (
            f"STABLE.D از {sd_a:.3f} به {sd_b:.3f} آمد ({d:.3f}، بزرگ‌تر از "
            f"میانهٔ {thr}) — پول از حاشیه به دارایی رفته، ریسک‌آن")
    else:
        bias, why = "NEUTRAL", (
            f"STABLE.D تقریباً ثابت ({d:+.3f}، زیر میانهٔ {thr}) — "
            "بستر جهت نمی‌دهد")

    # هشدارِ کلیدیِ حمید: اگر USDT.D تنها را می‌خواندیم چه می‌گفت؟
    d_u = b.get("u", 0) - a.get("u", 0)
    naive = ("SHORT_BIAS" if d_u > thr else
             "LONG_BIAS" if d_u < -thr else "NEUTRAL")
    return {
        "bias": bias, "why": why, "window_min": minutes, "threshold": thr,
        "stable_d": round(sd_b, 3), "d_stable_d": round(d, 4),
        "usdt_d": round(b.get("u", 0), 3), "d_usdt_d": round(d_u, 4),
        "cause": cls.get("cause"), "cause_why": cls.get("why"),
        "naive_usdt_only": naive,
        "disagrees_with_naive": naive != bias,
        "coverage": COVERAGE_NOTE,
    }


# نقشهٔ دو-بعدی: STABLE.D (پولِ نشسته) × BTC.D (چرخشِ داخلِ بازار).
# دستور حمید: «اولویت با دامیننس تتر، و بقیهٔ دامیننس‌ها» — پس تتر
# (در قالبِ STABLE.D) اول تصمیم می‌گیرد و BTC.D **درجهٔ** آن را روی
# آلت‌ها تعیین می‌کند، نه برعکس.
def alt_stance(points, minutes=240, now_ms=None):
    """سوگیریِ جهت برای **آلت‌ها**، از ترکیبِ STABLE.D و BTC.D."""
    r = regime(points, minutes, now_ms=now_ms)
    if r["bias"] == "INSUFFICIENT":
        return {"stance": "INSUFFICIENT", "why": r["why"]}
    now = now_ms or points[-1]["t"]
    b, a = _at(points, now), _at(points, now - minutes * 60_000)
    d_b = (b.get("b") or 0) - (a.get("b") or 0) if (a and b) else None
    if d_b is None:
        return {"stance": r["bias"], "why": r["why"] + " · BTC.D در دسترس نیست",
                **{k: r[k] for k in ("stable_d", "d_stable_d", "cause")}}
    thr = r.get("threshold") or regime_threshold(points, minutes)
    btc_up = d_b > thr
    btc_dn = d_b < -thr
    if r["bias"] == "SHORT_BIAS" and btc_up:
        stance, why = "SHORT_ALT_STRONG", (
            "هم پول به استیبل رفته هم BTC.D بالا — بدترین بسترِ آلت")
    elif r["bias"] == "SHORT_BIAS":
        stance, why = "SHORT_ALT", "پول به استیبل رفته — ریسک‌آف"
    elif r["bias"] == "LONG_BIAS" and btc_dn:
        stance, why = "LONG_ALT_STRONG", (
            "پول از استیبل بیرون آمده و BTC.D هم پایین — چرخش به آلت")
    elif r["bias"] == "LONG_BIAS" and btc_up:
        stance, why = "LONG_BTC_ONLY", (
            "پول وارد شده ولی BTC.D بالا — پول به بیت‌کوین می‌رود نه آلت")
    elif r["bias"] == "LONG_BIAS":
        stance, why = "LONG_ALT", "پول از استیبل بیرون آمده — ریسک‌آن"
    else:
        stance, why = "NEUTRAL", r["why"]
    return {"stance": stance, "why": why, "bias": r["bias"],
            "d_btc_d": round(d_b, 4), "cause": r["cause"],
            "disagrees_with_naive": r["disagrees_with_naive"],
            "stable_d": r["stable_d"], "d_stable_d": r["d_stable_d"],
            "usdt_d": r["usdt_d"], "d_usdt_d": r["d_usdt_d"],
            "window_min": minutes, "coverage": COVERAGE_NOTE}


def build(points, now_ms=None):
    """بستهٔ کاملِ استیبل برای `signals/dominance.json` و متخصصان E03/E04."""
    out = {"coverage": COVERAGE_NOTE,
           "boundary": ("شاهد است نه دروازه در مسیر سیگنالِ زندهٔ پنل "
                        "(قانون ۰۳)؛ در موتور شورتِ داشبورد با دستور صریح "
                        "حمید (۸ سپتامبر) دروازه است."),
           "method": ("چرخش فقط روی **عرضه** دیده می‌شود نه روی نسبت — "
                      "دو نسبت مخرجِ مشترک دارند و ریزشِ بازار هر دو را "
                      "با هم بالا می‌برد (همبستگیِ نسبت‌ها +۰.۹۸۹)."),
           "measured": ("۸ سپتامبر روی ۲٬۸۶۶ نقطه (۲۹ اوت–۸ سپتامبر): از "
                        "۵۶ موردِ رشدِ USDT.D در افق ۱س، صفر مورد چرخش بود "
                        "و ۳۲ مورد (۵۷٪) ریزشِ مخرج. یعنی چرخش در این "
                        "پنجره رخ نداده — نه این‌که ناممکن باشد.")}
    now = now_ms or (points[-1]["t"] if points else None)
    sd = stable_d(points[-1]) if points else None
    if sd is not None:
        out["stable_d"] = round(sd, 3)
        out["parts"] = {STABLE_NAMES[k]: points[-1].get(k) for k in STABLE_KEYS}
    for mins, label in ((60, "1h"), (240, "4h")):
        out.setdefault("cause", {})[label] = classify(points, mins, now_ms=now)
        out.setdefault("regime", {})[label] = regime(points, mins, now_ms=now)
    out["alt_stance"] = alt_stance(points, 240, now_ms=now)
    return out


def fa_lines(v):
    """چند خط فارسی برای گزارش ساعتی دامیننس."""
    if not v:
        return []
    L = []
    if v.get("stable_d") is not None:
        parts = " + ".join(f"{n} {x:.3f}" for n, x in (v.get("parts") or {}).items()
                           if x is not None)
        L.append(f"🏦 کلِ استیبل‌ها (STABLE.D): {v['stable_d']:.3f} ({parts})")
    st_ = v.get("alt_stance") or {}
    if st_.get("stance") and st_["stance"] != "INSUFFICIENT":
        L.append(f"   سوگیریِ آلت: {st_['stance']} — {st_.get('why', '')}")
    c4 = (v.get("cause") or {}).get("4h") or {}
    if c4.get("cause") and c4["cause"] != "INSUFFICIENT":
        L.append(f"   ریشهٔ حرکتِ ۴ساعتهٔ USDT.D: {c4['cause']} — {c4.get('why','')}")
    if st_.get("disagrees_with_naive"):
        L.append("   ⚠️ خواندنِ سادهٔ «USDT.D تنها» این‌جا جهتِ دیگری می‌دهد "
                 "— مبنا STABLE.D است (مصون از چرخشِ استیبل‌ها)")
    return L
