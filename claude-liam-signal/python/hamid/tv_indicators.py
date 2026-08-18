"""اندیکاتورهای سنجشی — EMA200 · Supertrend · ICT (دستور حمید، ۱۸ اوت).

سه ابزار پرمصرف تریدینگ‌ویو، پیاده‌سازی قطعی و بدون وابستگی، فقط برای
**اندازه‌گیری**: هم‌جهتی هر کدام با سیگنال روی پرونده ثبت می‌شود و حکم
(مفید/مضر/بی‌اثر) را ماشین بونفرونی شبانه با CI می‌دهد — هیچ‌کدام تا
عبور CI از صفر وارد تصمیم نمی‌شوند (قانون ۰۳). نتیجهٔ ICT طبق دستور
حمید جدا گزارش می‌شود.

- ema(values, n): میانگین متحرک نمایی کلاسیک.
- supertrend(candles, period=10, mult=3): همان «Supertrend» تریدینگ‌ویو —
  باندهای ATR؛ خروجی جهت 'up'/'down' برای هر لحظهٔ آخر سری.
- ict_align(candles, direction): برداشت قطعی از سه رکن ICT که در موتور
  خودمان هم مبنا هستند: (۱) سوییپ نقدینگی اخیر (شکست کف/سقف قبلی و
  بازگشت)، (۲) displacement هم‌جهت، (۳) FVG تازهٔ هم‌جهت. ≥۲ رکن هم‌جهت
  = 'with'، ≥۲ رکن مخالف = 'against'، غیر آن None.
"""


def ema(values, n):
    if not values or len(values) < n:
        return None
    k = 2.0 / (n + 1)
    e = sum(values[:n]) / n
    for v in values[n:]:
        e = v * k + e * (1 - k)
    return e


def _atr(cd, period):
    trs = []
    for i in range(1, len(cd)):
        h, l, pc = cd[i]["h"], cd[i]["l"], cd[i - 1]["c"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    if len(trs) < period:
        return None
    a = sum(trs[:period]) / period
    for t in trs[period:]:
        a = (a * (period - 1) + t) / period
    return a


def supertrend(cd, period=10, mult=3.0):
    """جهت سوپرترند در انتهای سری: 'up' یا 'down'؛ دادهٔ کم = None."""
    if not cd or len(cd) < period + 2:
        return None
    dir_, ub, lb = None, None, None
    trs, a = [], None
    for i in range(1, len(cd)):
        h, l, c = cd[i]["h"], cd[i]["l"], cd[i]["c"]
        pc = cd[i - 1]["c"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
        if len(trs) < period:
            continue
        a = (sum(trs[:period]) / period if len(trs) == period
             else (a * (period - 1) + trs[-1]) / period)
        mid = (h + l) / 2
        bu, bl = mid + mult * a, mid - mult * a
        ub = bu if ub is None or bu < ub or pc > ub else ub
        lb = bl if lb is None or bl > lb or pc < lb else lb
        if dir_ is None:
            dir_ = "up" if c > ub else "down"
        elif dir_ == "up" and c < lb:
            dir_, ub = "down", bu
        elif dir_ == "down" and c > ub:
            dir_, lb = "up", bl
    return dir_


def _swings(cd, lb=3):
    his, los = [], []
    for i in range(lb, len(cd) - lb):
        if cd[i]["h"] == max(k["h"] for k in cd[i - lb:i + lb + 1]):
            his.append((i, cd[i]["h"]))
        if cd[i]["l"] == min(k["l"] for k in cd[i - lb:i + lb + 1]):
            los.append((i, cd[i]["l"]))
    return his, los


def _ict_parts(cd, direction, window=60):
    """سه رکن ICT در پنجرهٔ اخیر؛ خروجی: تعداد هم‌جهت و مخالف."""
    win = cd[-window:]
    if len(win) < 30:
        return 0, 0
    his, los = _swings(win)
    px = win[-1]["c"]
    long = direction == "LONG"
    pro = con = 0
    # ۱) سوییپ نقدینگی: ویک زیر آخرین کف سوینگ (لانگ) و کلوز بالای آن
    recent = win[-12:]
    if los:
        last_lo = los[-1][1]
        swept_lo = any(k["l"] < last_lo and k["c"] > last_lo for k in recent)
        if swept_lo:
            pro += 1 if long else 0
            con += 0 if long else 1
    if his:
        last_hi = his[-1][1]
        swept_hi = any(k["h"] > last_hi and k["c"] < last_hi for k in recent)
        if swept_hi:
            pro += 0 if long else 1
            con += 1 if long else 0
    # ۲) displacement: کندل بدنه‌بزرگ (>۱.۸× میانگین بدنه) هم‌جهت در ۱۲ کندل
    bodies = [abs(k["c"] - k["o"]) for k in win]
    avg_b = sum(bodies) / len(bodies) if bodies else 0
    for k in recent:
        b = k["c"] - k["o"]
        if avg_b and abs(b) > 1.8 * avg_b:
            if (b > 0) == long:
                pro += 1
            else:
                con += 1
            break
    # ۳) FVG تازهٔ هم‌جهت (گپ سه‌کندلی پرنشده در ۲۰ کندل اخیر)
    for i in range(max(2, len(win) - 20), len(win)):
        a, c = win[i - 2], win[i]
        if a["h"] < c["l"]:                      # گپ صعودی
            unfilled = all(k["l"] > a["h"] for k in win[i + 1:])
            if unfilled and px >= a["h"]:
                pro += 1 if long else 0
                con += 0 if long else 1
                break
        if a["l"] > c["h"]:                      # گپ نزولی
            unfilled = all(k["h"] < a["l"] for k in win[i + 1:])
            if unfilled and px <= a["l"]:
                pro += 0 if long else 1
                con += 1 if long else 0
                break
    return pro, con


def ict_align(cd, direction):
    """'with' / 'against' / None — طبق سه رکن، با آستانهٔ ≥۲ رکن."""
    if not cd or direction not in ("LONG", "SHORT"):
        return None
    pro, con = _ict_parts(cd, direction)
    if pro >= 2 and pro > con:
        return "with"
    if con >= 2 and con > pro:
        return "against"
    return None


def snapshot(cd, direction):
    """سه هم‌جهتی برای مهر روی پرونده — دادهٔ کم = None، نه حدس."""
    out = {"ema200_align": None, "supertrend_align": None, "ict_align": None}
    if not cd or direction not in ("LONG", "SHORT"):
        return out
    closes = [k["c"] for k in cd]
    e200 = ema(closes, 200)
    if e200 is not None:
        above = closes[-1] > e200
        out["ema200_align"] = ("with" if above == (direction == "LONG")
                               else "against")
    st = supertrend(cd)
    if st is not None:
        out["supertrend_align"] = ("with" if (st == "up") == (direction == "LONG")
                                   else "against")
    out["ict_align"] = ict_align(cd, direction)
    return out
