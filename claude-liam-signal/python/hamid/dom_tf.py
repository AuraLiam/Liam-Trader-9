"""دامیننس در همان تایم‌فریمِ ستاپ — و آستانه از توزیع، نه از عدد ثابت.

## دو عیبی که این ماژول می‌بندد (اندازه‌گیری ۳۰ اوت شب)

دستور حمید: «وقتی شاخص دلار را در تایم ۱۵ دقیقه و دامیننس تتر را تایم
۱۵ دقیقه تحلیل می‌کنی، باید ارزها را در همان تایم‌فریم تحلیل کنی و
استراتژی را در همان تایم‌فریم بررسی کنی.» و پیش از آن: «چرا وقتی مارکت
رنج است از دامیننس تتر کمک نمی‌گیری؟»

**عیب یک — ناهم‌ترازی تایم‌فریم.** سریِ دامیننس ما گامِ میانهٔ ۳.۲ دقیقه
دارد، ولی `dominance._bars` فقط کندلِ **۱ ساعته و ۴ ساعته** می‌ساخت. پس
ستاپِ ۱۵دقیقه‌ای با خوانشِ ۱ساعته سنجیده می‌شد. سری رزولوشنش را داشت؛
کندلش را هرگز نساخته بودیم:

| کندل | سطل بسته | نقطه در هر کندل (میانه) | کندلِ واقعی؟ |
|---|---|---|---|
| ۵ دقیقه | ۲۵۸۵ | **۱** | ❌ o=h=l=c، کندل نیست |
| ۱۵ دقیقه | ۱۱۰۹ | **۴** | ✅ |
| ۱ ساعت | ۲۹۰ | ۱۴ | ✅ |
| ۴ ساعت | ۷۴ | ۵۲ | ✅ |

پس ۱۵ دقیقه از همین امشب شدنی است؛ **۵ دقیقه نه** — و جعل نمی‌شود.
راهش همان قانون ۰۲ است: نمونه‌بردارِ سریع‌ترِ سرویس محلی. تا آن روز
ستاپ ۵د صراحتاً «خوانشِ ۱۵د، برچسب‌خورده» می‌گیرد، نه عددِ ساختگی.

**عیب دو — آستانهٔ ثابت ۰.۱۵ که ~۱۰ برابر حرکتِ معمول است.**
`premortem` وقتی رژیم ساختاری جهت‌دار نبود به دلتای ۱ساعته برمی‌گشت و
فقط با `|Δ| ≥ 0.15` چیزی می‌گفت. توزیع واقعی روی ۳٬۹۵۸ پنجرهٔ یک‌ساعته:

| سنجه | مقدار |
|---|---|
| میانهٔ ‎\|Δ USDT.D در ۱ ساعت\| | ۰.۰۱۵ |
| صدک ۹۰ | ۰.۰۵۷ |
| زیر آستانهٔ ۰.۱۵ | **۹۷.۵٪** |

یعنی مسیر پشتیبان عملاً مرده بود — نه فقط «در رنج»، بلکه تقریباً همیشه.
درمانش همان کاری است که ۲۹ اوت برای افق‌های پیش‌بینی شد: آستانه از
**توزیعِ همان تایم‌فریم** می‌آید (صدک ۷۵)، نه از عددی که یک بار حدس
زده شده و بعد هرگز بازبینی نشده.

## مرز — این ماژول دروازه نیست

هر دو خروجی فعلاً فقط **شاهد** است و روی پروندهٔ معامله ثبت می‌شود
(`dom_tf_*` روی دفتر پیپر). هیچ آستانه‌ای در `premortem` جابه‌جا نشده و
هیچ سیگنالی به‌خاطر این ماژول رد یا صادر نمی‌شود. ورودش به دروازه فقط
از مسیر قانون ۰۳: بک‌تست بی‌آینده → CI بالای صفر → تأیید صریح حمید.
سنجشِ بازنگرِ همین امشب در `hamid/dom_tf_study.py` است و قابل اجرای
دوباره.
"""
import statistics

TF_MS = {"5m": 300_000, "15m": 900_000, "1h": 3_600_000, "4h": 14_400_000}

MIN_BARS = 60          # زیر این، حکم ساختاری صادر نمی‌شود (هم‌تراز dominance.py)
MIN_PTS_PER_BAR = 2.0  # کندلی که میانهٔ نقاطش زیر ۲ است، کندل نیست
MIN_DELTA_N = 30       # زیر این تعداد نمونه، آستانه از توزیع ساخته نمی‌شود
PCTL = 0.75            # صدکِ آستانهٔ «حرکت معنادار»
FLOOR = 0.002          # کف مطلق — زیرش نویزِ گردکردنِ خودِ سری است
# ترتیب جانشینی وقتی تایم‌فریمِ خواسته‌شده رزولوشن ندارد (فقط رو به بالا)
FALLBACK = {"5m": "15m", "15m": "1h", "1h": "4h", "4h": None}


def bars(points, key, tf):
    """کندلِ همان تایم‌فریم + رزولوشنِ واقعی‌اش.

    برمی‌گرداند `(bars, median_pts_per_bar)`. سطلِ آخر باز است و کندل
    نیست — حذف می‌شود (همان قاعدهٔ `dominance._bars`)."""
    bar_ms = TF_MS.get(tf)
    if not bar_ms:
        return [], 0.0
    bucket = {}
    for p in points:
        try:
            bucket.setdefault(p["t"] // bar_ms, []).append(p[key])
        except (KeyError, TypeError):
            continue
    keys = sorted(bucket)[:-1]
    out = []
    for b in keys:
        vs = bucket[b]
        out.append({"t": b * bar_ms, "o": vs[0], "h": max(vs), "l": min(vs),
                    "c": vs[-1], "v": float(len(vs))})
    res = statistics.median([len(bucket[b]) for b in keys]) if keys else 0.0
    return out, float(res)


def delta_threshold(bs, pctl=PCTL):
    """آستانهٔ «حرکت معنادار» از توزیعِ خودِ همین تایم‌فریم.

    نمونه = قدرمطلقِ تغییرِ کلوز بین دو کندلِ پیاپی. آستانه = صدک `pctl`
    همان توزیع، با کفِ مطلق. زیر `MIN_DELTA_N` نمونه، آستانه ساخته
    نمی‌شود و دلیلش برگردانده می‌شود — عددِ بی‌پشتوانه چاپ نمی‌شود."""
    ds = [abs(bs[i]["c"] - bs[i - 1]["c"]) for i in range(1, len(bs))]
    if len(ds) < MIN_DELTA_N:
        return None, {"n": len(ds), "why": f"نمونه کم ({len(ds)}/{MIN_DELTA_N})"}
    ds.sort()
    idx = min(len(ds) - 1, max(0, int(round(pctl * (len(ds) - 1)))))
    thr = max(ds[idx], FLOOR)
    return round(thr, 4), {"n": len(ds), "pctl": pctl,
                           "median": round(statistics.median(ds), 4),
                           "p90": round(ds[min(len(ds) - 1,
                                               int(round(0.9 * (len(ds) - 1))))], 4)}


def read(points, tf, key="u"):
    """خوانشِ دامیننس در یک تایم‌فریمِ مشخص — رژیم + دلتا + آستانهٔ خودش.

    رژیم از دید آلت‌هاست، دقیقاً مثل `dominance.structural`: USDT.D نزولی
    = پول وارد ریسک = BULLISH؛ صعودی = BEARISH؛ بی‌جهت = RANGE.
    (برای BTC.D همین جهت‌ها معنای «آلت» می‌دهند نه «بازار»، پس رژیم فقط
    برای USDT.D برگردانده می‌شود و BTC.D فقط روند و دلتا دارد.)"""
    from hamid import structure as st

    bs, res = bars(points, key, tf)
    out = {"tf": tf, "bars": len(bs), "pts_per_bar": res,
           "resolution_ok": res >= MIN_PTS_PER_BAR}
    if not out["resolution_ok"]:
        out["regime"] = "LOW_RESOLUTION"
        out["note"] = (f"سریِ دامیننس برای کندل {tf} رزولوشن ندارد "
                       f"(میانهٔ {res:g} نقطه در هر کندل، حداقل {MIN_PTS_PER_BAR}) — "
                       f"عدد جعل نمی‌شود (قانون ۱)")
        return out
    if len(bs) < MIN_BARS:
        out["regime"] = "INSUFFICIENT"
        out["note"] = f"کندل کافی نیست ({len(bs)}/{MIN_BARS})"
        return out

    tr = st.trend(bs)
    out["trend"] = tr
    out["px"] = round(bs[-1]["c"], 3)
    thr, stats = delta_threshold(bs)
    out["threshold"] = thr
    out["threshold_stats"] = stats
    out["delta"] = round(bs[-1]["c"] - bs[-2]["c"], 4)
    out["meaningful"] = bool(thr is not None and abs(out["delta"]) >= thr)

    if key == "u":
        out["regime"] = ("BULLISH" if tr == "down"
                         else "BEARISH" if tr == "up" else "RANGE")
        out["note"] = (f"USDT.D در {tf}: روند {tr} → رژیم {out['regime']}؛ "
                       f"تغییر آخرین کندل {out['delta']:+.4f} در برابر آستانهٔ "
                       + (f"{thr:.4f} (صدک {PCTL:g} همین تایم‌فریم)"
                          if thr is not None else "نامعلوم"))
    else:
        out["note"] = (f"BTC.D در {tf}: روند {tr}؛ تغییر آخرین کندل "
                       f"{out['delta']:+.4f}")
    return out


def map_all(points):
    """نقشهٔ چهار تایم‌فریم — همان چیزی که روی `signals/dominance.json` می‌نشیند."""
    return {tf: {"usdt": read(points, tf, "u"), "btc_d": read(points, tf, "b")}
            for tf in TF_MS}


def _usable(tf_map, tf):
    """نزدیک‌ترین تایم‌فریمِ قابل‌استفاده از همین تایم به بالا — با نامش."""
    seen = set()
    cur = tf
    while cur and cur not in seen:
        seen.add(cur)
        e = (tf_map.get(cur) or {}).get("usdt") or {}
        if e.get("regime") not in (None, "LOW_RESOLUTION", "INSUFFICIENT"):
            return cur, e
        cur = FALLBACK.get(cur)
    return None, {}


def for_signal(dom, tf, direction):
    """شاهدِ دامیننسِ هم‌تراز، برای ثبت روی پروندهٔ همین سیگنال.

    خروجی هیچ دروازه‌ای را باز/بسته نمی‌کند؛ فقط ثبت می‌شود تا ماشین
    شبانه بتواند بپرسد «هم‌ترازی دامیننس در تایم خودِ ستاپ، نتیجه را
    عوض کرد یا نه؟». `aligned=None` یعنی نمی‌دانیم — و «نمی‌دانم» هرگز
    «هم‌جهت» خوانده نمی‌شود."""
    tf_map = (dom or {}).get("tf_map") or {}
    used, e = _usable(tf_map, tf)
    out = {"tf_asked": tf, "tf_used": used,
           "same_tf": bool(used is not None and used == tf)}
    if used is None:
        out.update({"regime": None, "aligned": None,
                    "why": "هیچ تایم‌فریمی از این ستاپ به بالا خوانشِ معتبر ندارد"})
        return out
    reg = e.get("regime")
    out.update({"regime": reg, "delta": e.get("delta"),
                "threshold": e.get("threshold"),
                "meaningful": e.get("meaningful"), "why": e.get("note")})
    if reg in ("BULLISH", "BEARISH"):
        out["aligned"] = ((reg == "BULLISH") == (direction == "LONG"))
        out["basis"] = "regime"
    elif reg == "RANGE" and e.get("meaningful"):
        # در رنج، حرکتِ معنادارِ همین تایم‌فریم حرف می‌زند — دقیقاً همان
        # سؤال حمید. آستانه از توزیع می‌آید، پس «معنادار» تعریف دارد.
        risk_off = (e.get("delta") or 0) > 0        # USDT.D بالا = پول از ریسک بیرون
        out["aligned"] = (risk_off != (direction == "LONG"))
        out["basis"] = "delta"
    else:
        out["aligned"] = None
        out["basis"] = "none"
    return out
