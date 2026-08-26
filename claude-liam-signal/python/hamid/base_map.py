"""نقشهٔ پایهٔ روش حمید — زیر هر تحلیل، قبل از هر استراتژی (دستور ۲۶ اوت).

حمید: «این کانال‌ها، این خطوط، اردر بلاک‌ها، روی همهٔ چارت‌ها و هر
تایم‌فریمی که قرار است ترید کنیم انجام می‌شود و بعد از آن از استراتژی
استفاده می‌کنیم.» این ماژول همان سه ابزار دستی او را قطعی می‌کند:

۱. **حمایت/مقاومت افقی (horizontal ray)**: خوشهٔ اکسترمم‌های سوینگ با
   شمارِ برخورد — برخورد ویک و پذیرش بدنه جدا (قانون شخصی‌سازی).
   خط معتبر ≥۳ برخورد (قانون حمید + Edwards&Magee/Murphy در
   trendlines-canon).
۲. **کانال موازی + میدلاین**: رگرسیون خطی روی پنجره، لبه‌ها موازی از
   بیشینهٔ انحراف سقف/کف؛ جای قیمت در کانال (٪)، فاصله تا میدلاین،
   و شمار برخورد لبه‌ها — قاعدهٔ تجربی حمید: برگشت به کانال ⇒ لمس
   میدلاین؛ عبور از میدلاین ⇒ لبهٔ مقابل.
۳. **اردر بلاک به تعریف خود حمید**: بعد از ریزش، کندل‌ها را برمی‌گردیم
   بالا تا اولین کندل سبزِ قوی که «بدنه‌اش از شدوهایش بزرگ‌تر» است —
   آن OB بالایی است؛ قرینه برای پایین. زون = بدنهٔ همان کندل.

مرز صادقانه (قانون ۰۳): این نقشه فعلاً **شاهد** است، نه دروازه — روی
کپشن/پکت می‌نشیند و قاعده‌های عملی‌اش (میدلاین، لبه‌ها) فقط بعد از
بک‌تست ۳ ساله و CI بالای صفر وارد تصمیم می‌شوند.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
sys.path.insert(0, str(PY))

SR_TOL_PCT = 0.25             # هم‌خوشگی سطح‌ها
MIN_TOUCHES = 3               # خط معتبر (قانون حمید)
PIVOT_K = 2


def pivots(cd, k=PIVOT_K):
    """سوینگ‌های اکید تأییدشده → ([(i, high)], [(i, low)]) — بی‌آینده:
    پیوت i فقط وقتی شمرده می‌شود که k کندل بعدش در پنجره باشند."""
    his, los = [], []
    for i in range(k, len(cd) - k):
        win = cd[i - k:i + k + 1]
        if cd[i]["h"] > max(x["h"] for j, x in enumerate(win) if j != k):
            his.append((i, cd[i]["h"]))
        if cd[i]["l"] < min(x["l"] for j, x in enumerate(win) if j != k):
            los.append((i, cd[i]["l"]))
    return his, los


def sr_levels(cd, tol_pct=SR_TOL_PCT, max_levels=6):
    """سطح‌های افقی از خوشهٔ پیوت‌ها + شمار برخورد ویک/بدنه.

    برخورد ویک: ویک کندل سطح را لمس کند؛ پذیرش بدنه: کلوز آن‌سوی سطح.
    فقط سطح‌های ≥ MIN_TOUCHES برمی‌گردند، مرتب بر تعداد برخورد."""
    his, los = pivots(cd)
    pts = sorted(p for _, p in his + los)
    if not pts:
        return []
    clusters = []
    for p in pts:
        if clusters and abs(p - clusters[-1][-1]) / p * 100 <= tol_pct:
            clusters[-1].append(p)
        else:
            clusters.append([p])
    px = cd[-1]["c"]
    out = []
    for c in clusters:
        lvl = sum(c) / len(c)
        band = lvl * tol_pct / 100
        wick = body = 0
        for k in cd:
            if k["l"] <= lvl + band and k["h"] >= lvl - band:
                wick += 1
                lo_b, hi_b = min(k["o"], k["c"]), max(k["o"], k["c"])
                if lo_b <= lvl + band and hi_b >= lvl - band:
                    body += 1
        if wick < MIN_TOUCHES:
            continue
        out.append({"level": round(lvl, 10), "touches_wick": wick,
                    "touches_body": body,
                    "role": "resistance" if lvl > px else "support",
                    "dist_pct": round(abs(lvl - px) / px * 100, 3)})
    out.sort(key=lambda x: -x["touches_wick"])
    return out[:max_levels]


def channel(cd, tol_pct=SR_TOL_PCT):
    """کانال موازی: خط میانی = رگرسیون کلوزها؛ لبه‌ها موازی از بیشینهٔ
    انحراف سقف/کف. خروجی: شیب، جای قیمت (۰=کف تا ۱۰۰=سقف)، فاصله تا
    میدلاین، پهنا، و شمار برخورد هر لبه."""
    n = len(cd)
    if n < 40:
        return None
    xs = list(range(n))
    cs = [k["c"] for k in cd]
    mx = (n - 1) / 2
    my = sum(cs) / n
    den = sum((x - mx) ** 2 for x in xs)
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, cs)) / den
    mid0 = my - slope * mx
    up_off = max(k["h"] - (mid0 + slope * i) for i, k in enumerate(cd))
    dn_off = max((mid0 + slope * i) - k["l"] for i, k in enumerate(cd))
    def top(i):
        return mid0 + slope * i + up_off
    def bot(i):
        return mid0 + slope * i - dn_off
    last = n - 1
    px = cd[-1]["c"]
    width = top(last) - bot(last)
    if width <= 0:
        return None
    pos = (px - bot(last)) / width * 100
    mid = (top(last) + bot(last)) / 2
    band = px * tol_pct / 100
    t_top = sum(1 for i, k in enumerate(cd) if abs(k["h"] - top(i)) <= band)
    t_bot = sum(1 for i, k in enumerate(cd) if abs(k["l"] - bot(i)) <= band)
    t_mid = sum(1 for i, k in enumerate(cd)
                if min(k["o"], k["c"]) - band <= mid0 + slope * i + (up_off - dn_off) / 2
                <= max(k["o"], k["c"]) + band)
    slope_pct_bar = slope / px * 100
    direction = ("up" if slope_pct_bar > 0.01 else
                 "down" if slope_pct_bar < -0.01 else "flat")
    return {"dir": direction, "slope_pct_per_bar": round(slope_pct_bar, 4),
            "pos_pct": round(pos, 1),
            "mid_dist_pct": round((px - mid) / px * 100, 3),
            "width_pct": round(width / px * 100, 3),
            "touches_top": t_top, "touches_bottom": t_bot,
            "touches_mid": t_mid,
            "top": round(top(last), 10), "bottom": round(bot(last), 10),
            "mid": round(mid, 10)}


def _strong_body(k):
    """کندل قوی به تعریف حمید: بدنه از مجموع شدوها بزرگ‌تر."""
    body = abs(k["c"] - k["o"])
    shadows = (k["h"] - max(k["o"], k["c"])) + (min(k["o"], k["c"]) - k["l"])
    return body > shadows and body > 0


def order_block_hamid(cd, side, lookback=120):
    """اردر بلاک به روش خود حمید (۲۶ اوت).

    side="above": بعد از ریزش، از انتها برمی‌گردیم عقب/بالا تا اولین
    کندل **سبزِ** قوی (بدنه > شدوها) — زون عرضهٔ بالای قیمت.
    side="below": قرینه — اولین کندل **قرمزِ** قوی زیر قیمت.
    زون = بدنهٔ همان کندل. برمی‌گرداند {lo, hi, i, touched} یا None."""
    win = cd[-lookback:]
    px = win[-1]["c"]
    for j in range(len(win) - 2, 1, -1):
        k = win[j]
        green = k["c"] > k["o"]
        if side == "above":
            if not (green and _strong_body(k) and min(k["o"], k["c"]) > px):
                continue
        else:
            if not ((not green) and _strong_body(k)
                    and max(k["o"], k["c"]) < px):
                continue
        lo, hi = min(k["o"], k["c"]), max(k["o"], k["c"])
        touched = sum(1 for x in win[j + 1:]
                      if x["l"] <= hi and x["h"] >= lo)
        return {"lo": round(lo, 10), "hi": round(hi, 10),
                "i": len(cd) - lookback + j, "touched": touched,
                "dist_pct": round((abs((lo if side == "above" else hi) - px)
                                   / px * 100), 3)}
    return None


def base_map(frames):
    """نقشهٔ کامل چندتایمی. frames = {"4h": cd, "1h": cd, "15m": cd, ...}
    خروجی هر تایم: سطح‌ها + کانال + دو OB؛ به‌اضافهٔ هم‌رسی خطوط بین
    تایم‌ها (نقطه‌ای که چند خط در ±۰.۳٪ جمع‌اند = جای واکنش، حرف حمید)."""
    out = {}
    all_lines = []
    for tf, cd in frames.items():
        if not cd or len(cd) < 60:
            out[tf] = {"error": "سری کوتاه"}
            continue
        levels = sr_levels(cd)
        ch = channel(cd)
        m = {"levels": levels, "channel": ch,
             "ob_above": order_block_hamid(cd, "above"),
             "ob_below": order_block_hamid(cd, "below")}
        out[tf] = m
        for lv in levels:
            all_lines.append((tf, "S/R", lv["level"]))
        if ch:
            for name in ("top", "bottom", "mid"):
                all_lines.append((tf, f"channel_{name}", ch[name]))
    conf = []
    for a in range(len(all_lines)):
        for b in range(a + 1, len(all_lines)):
            (tfa, na, pa), (tfb, nb, pb) = all_lines[a], all_lines[b]
            if tfa != tfb and abs(pa - pb) / pa * 100 <= 0.3:
                conf.append({"price": round((pa + pb) / 2, 10),
                             "lines": [f"{na}@{tfa}", f"{nb}@{tfb}"]})
    out["confluence"] = conf[:8]
    return out
