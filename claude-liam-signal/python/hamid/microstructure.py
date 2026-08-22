"""ریزساختار تایم پایین (۱د/۳د) — پیوت، BOS، CHoCH، سشن. توسعهٔ E07.

دستور حمید (۲۲ اوت): «در جهت‌شناسی و تشخیص BOS و CHoCH باید انجین مربوطه
اطلاعاتش را افزایش دهد و کندل‌شناسی در تایم‌فریم‌های پایین به‌خوبی انجام
شود.» این ماژول همان لایهٔ گمشده است: تا امروز BOS فقط داخل ob_intel و
trainer به‌صورت موضعی تعریف شده بود، هیچ‌جا تعریفِ واحدِ نسخه‌دارِ
قابل‌آزمون نداشتیم.

## تعریف‌ها (نسخه‌دار — تغییرشان یعنی نسخهٔ تازه، نه ویرایش خاموش)

**پیوت (فرکتال L/R)**: سقف پیوت = کندلی که high آن از high تمام L کندل
چپ و R کندل راست بیشتر باشد. **پیوت فقط R کندل بعد از خودش تأیید
می‌شود** — به همین دلیل این ماژول هرگز پیوتِ تأییدنشده را به تصمیم راه
نمی‌دهد؛ همان چیزی که «بدون نگاه به آینده» را واقعی می‌کند نه شعاری.

**BOS (Break of Structure)** — ادامهٔ روند: در ساختار صعودی، **بستنِ**
کندل بالای آخرین سقفِ پیوتِ تأییدشده. (نزولی قرینه.) ویک کافی نیست —
انضباط Brandt در `trendlines-canon.md`، همان‌جا که برای خط روند هم
کلوزِ قاطع خواستیم.

**CHoCH (Change of Character)** — تغییر کاراکتر: در ساختار صعودی،
**بستنِ** کندل زیر آخرین کفِ پیوتِ تأییدشده. طبق قانون ۵
(`01-trading-non-negotiables.md`) و `trading-core.md`، CHoCH به‌تنهایی
مجوز برگشت نیست — این ماژول فقط رویداد را **تشخیص و ثبت** می‌کند؛
تصمیم‌گیری با لایهٔ بالاتر (scenarios/E17) است.

**سشن**: بازار کریپتو تعطیلی ندارد ولی نقدشوندگی‌اش سشن دارد. برچسب
سشن روی هر رویداد ثبت می‌شود تا بعداً کارنامهٔ هر سشن جدا سنجیده شود
(دستور حمید: «با توجه به سشن‌های مختلف»).

خروجی هر تحلیل یک dict قطعی است — هیچ عددی حدس زده نمی‌شود؛ دادهٔ ناکافی
یعنی None، نه تخمین (قانون ۱).
"""

STRUCT_VERSION = "e07-micro-1.0"

# فرکتال ۲/۲ روی ۱د: کوچک‌ترین پنجره‌ای که هنوز نویزِ تک‌کندلی را پیوت
# حساب نمی‌کند. R=2 یعنی هر پیوت دقیقاً ۲ کندل بعد از خودش قطعی می‌شود.
PIVOT_L = 2
PIVOT_R = 2
# کف طولِ لگ (بر حسب ATR) برای اینکه یک پیوت «ساختار» حساب شود.
# پیش‌فرض اولیه، هنوز اعتبارسنجی‌نشده — بک‌تست باید بهترینش را پیدا کند.
MIN_LEG_ATR = 1.0


def session_of(ms):
    """سشن معاملاتی از ساعت UTC — همان تقسیم‌بندی liam9_strategy، این‌جا
    مرکزی شد تا هر دو موتور یک تعریف داشته باشند."""
    h = (ms // 3600000) % 24
    if 12 <= h < 16:
        return "overlap"        # لندن+نیویورک — پرنقدشوندگی‌ترین
    if 7 <= h < 16:
        return "london"
    if 16 <= h < 21:
        return "ny"
    return "asia"


def _atr_at(cd, i, n=14):
    """ATR با کندل‌های ≤ i — عمداً محلی، چون برجستگیِ پیوت باید با نوسانِ
    همان لحظه سنجیده شود نه نوسانِ کل سری (که از آینده خبر دارد)."""
    if i < n:
        return None
    tr = []
    for j in range(i - n + 1, i + 1):
        h, l, pc = cd[j]["h"], cd[j]["l"], cd[j - 1]["c"]
        tr.append(max(h - l, abs(h - pc), abs(l - pc)))
    return sum(tr) / len(tr) if tr else None


def pivots(cd, left=PIVOT_L, right=PIVOT_R, min_leg_atr=MIN_LEG_ATR):
    """سقف/کف‌های پیوتِ **تأییدشده** و **معنادار**.

    خروجی: (highs, lows) که هر عضو {"i","t","px","confirmed_at_i","leg"} است.
    `confirmed_at_i` = i+right — یعنی زودترین اندیسی که این پیوت در آن
    قابل‌استفاده است. هر مصرف‌کننده‌ای که این فیلد را نادیده بگیرد، عملاً
    از آینده خبر دارد.

    **معناداری بر پایهٔ «لگِ سوینگ»** (min_leg_atr): فرکتال خالص روی ۱
    دقیقه هر چند کندل یک پیوت می‌سازد و BOS تقریباً هر کندل شلیک می‌شود
    (اندازه‌گیری‌شده: ۳۵۴ رویداد در ۴۰۰ کندل — یعنی «ساختار» عملاً نویز
    بود). فیلترِ درست، فاصلهٔ پیوت از **همسایهٔ بلافصلش** نیست — روی هر
    نقطهٔ برگشتِ نرم آن فاصله ذاتاً صفر است و همه‌چیز را حذف می‌کند (این
    را اول اشتباه پیاده کردم و همان‌جا با اندازه‌گیری معلوم شد). معیارِ
    ساختاریِ درست، **طول لگ** است: هر سقف پیوت باید دست‌کم این کسر از ATR
    بالاتر از آخرین کفِ پیوتِ پیش از خودش باشد (و قرینه برای کف‌ها) —
    یعنی واقعاً یک نوسان را تمام کرده باشد، نه یک تکان.
    مقدار پیش‌فرض هنوز **اعتبارسنجی‌نشده** است؛ کارِ بک‌تست است که بهترینش
    را پیدا کند، نه حدس."""
    raw_hi, raw_lo = [], []
    n = len(cd)
    for i in range(left, n - right):
        h, l = cd[i]["h"], cd[i]["l"]
        if all(cd[j]["h"] < h for j in range(i - left, i)) and \
           all(cd[j]["h"] < h for j in range(i + 1, i + right + 1)):
            raw_hi.append({"i": i, "t": cd[i]["t"], "px": h,
                           "confirmed_at_i": i + right, "kind": "H"})
        if all(cd[j]["l"] > l for j in range(i - left, i)) and \
           all(cd[j]["l"] > l for j in range(i + 1, i + right + 1)):
            raw_lo.append({"i": i, "t": cd[i]["t"], "px": l,
                           "confirmed_at_i": i + right, "kind": "L"})

    # فیلتر زیگ‌زاگ کلاسیک: زنجیره باید سقف/کف یک‌درمیان باشد.
    #   • پیوتِ هم‌نوعِ پشت‌سرهم → فقط تندروترین می‌ماند (سقف بالاتر جای
    #     سقف پایین‌تر را می‌گیرد) — یک نوسان به چند پیوت خرد نمی‌شکند.
    #   • پیوتِ نوعِ مخالف → فقط اگر لگش از کف ATR رد شود پذیرفته می‌شود؛
    #     وگرنه تکانِ داخل نوسان است، نه ساختار.
    chain = []
    for p in sorted(raw_hi + raw_lo, key=lambda x: x["i"]):
        a = _atr_at(cd, p["i"])
        if a is None or a <= 0:
            continue
        need = a * min_leg_atr
        if not chain:
            p["leg"] = None
            chain.append(p)
            continue
        last = chain[-1]
        if p["kind"] == last["kind"]:
            better = p["px"] > last["px"] if p["kind"] == "H" else p["px"] < last["px"]
            if better:
                p["leg"] = last.get("leg")
                chain[-1] = p
            continue
        leg = (p["px"] - last["px"]) if p["kind"] == "H" else (last["px"] - p["px"])
        if leg >= need:
            p["leg"] = round(leg, 8)
            chain.append(p)
    hi = [p for p in chain if p["kind"] == "H"]
    lo = [p for p in chain if p["kind"] == "L"]
    return hi, lo


def _last_confirmed(seq, upto_i):
    """آخرین پیوتی که تا اندیس upto_i **تأیید شده** — نه صرفاً رخ داده."""
    out = None
    for p in seq:
        if p["confirmed_at_i"] <= upto_i:
            out = p
        else:
            break
    return out


def structure(cd, left=PIVOT_L, right=PIVOT_R, min_leg_atr=MIN_LEG_ATR):
    """وضعیت ساختار در آخرین کندلِ بستهٔ سری.

    روی کل سری جلو می‌رود و هر BOS/CHoCH را با همان قواعد بالا ثبت می‌کند.
    هیچ تصمیمی نمی‌گیرد — فقط «چه شد» را برمی‌گرداند.

    خروجی: dict یا None اگر کندل کافی نیست.
        bias           "up"/"down"/None  — ساختار فعلی
        last_event     "BOS"/"CHoCH"/None
        last_event_dir "up"/"down"/None
        last_event_i   اندیس کندلی که رویداد را بست
        swing_high/low آخرین پیوت تأییدشده (سطحی که شکستنش رویداد بعدی است)
        events         فهرست کامل رویدادها (برای بک‌تست/کارنامه)
    """
    n = len(cd)
    if n < (left + right + 6):
        return None
    hi, lo = pivots(cd, left, right, min_leg_atr)
    if not hi or not lo:
        return None

    bias = None
    events = []
    # سطحِ شکسته‌شده **مصرف می‌شود**: تا وقتی پیوتِ تازه‌تری تأیید نشده،
    # همان سطح دوباره رویداد نمی‌سازد. بدون این، در یک روند صاف موتور هر
    # کندل یک BOS اعلام می‌کرد (اندازه‌گیری‌شده: ۳۵۴ رویداد از ۳ پیوت) —
    # یعنی «ساختار» عملاً شمارشِ کندل بود، نه ساختار.
    used_hi_i = used_lo_i = None
    for i in range(left + right, n):
        ph = _last_confirmed(hi, i - 1)      # سطح باید *قبل* از این کندل قطعی شده باشد
        pl = _last_confirmed(lo, i - 1)
        c = cd[i]["c"]
        if ph and c > ph["px"] and ph["i"] != used_hi_i:
            ev = "BOS" if bias == "up" else ("CHoCH" if bias == "down" else "BOS")
            events.append({"i": i, "t": cd[i]["t"], "kind": ev, "dir": "up",
                           "level": ph["px"], "close": c,
                           "session": session_of(cd[i]["t"])})
            bias, used_hi_i = "up", ph["i"]
        elif pl and c < pl["px"] and pl["i"] != used_lo_i:
            ev = "BOS" if bias == "down" else ("CHoCH" if bias == "up" else "BOS")
            events.append({"i": i, "t": cd[i]["t"], "kind": ev, "dir": "down",
                           "level": pl["px"], "close": c,
                           "session": session_of(cd[i]["t"])})
            bias, used_lo_i = "down", pl["i"]

    last = events[-1] if events else None
    return {"formula_version": STRUCT_VERSION,
            "bias": bias,
            "last_event": last["kind"] if last else None,
            "last_event_dir": last["dir"] if last else None,
            "last_event_i": last["i"] if last else None,
            "swing_high": _last_confirmed(hi, n - 1),
            "swing_low": _last_confirmed(lo, n - 1),
            "session": session_of(cd[-1]["t"]),
            "events": events}
