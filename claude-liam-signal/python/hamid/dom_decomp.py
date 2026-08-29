"""تجزیهٔ دامیننس تتر — صورت در برابر مخرج (بند ۲، دستور حمید ۲۹ اوت).

مسئله‌ای که این ماژول حل می‌کند: **USDT.D یک عدد است با دو معنیِ کاملاً
متضاد.** چون

    USDT.D = عرضهٔ تتر ÷ کل ارزش بازار

بالا رفتنش دو ریشهٔ کاملاً متفاوت دارد:

  · **صورت بزرگ شده** (تتر تازه mint شده) — پولِ تازه وارد اکوسیستم شده و
    هنوز نخریده. این «باروتِ خشک» است؛ خبرِ بدی نیست.
  · **مخرج کوچک شده** (کل بازار ریخته) — کسی پول تازه نیاورده، فقط قیمت
    همه چیز پایین آمده. این ریزش است.

تا امروز موتور فقط عددِ نسبت را می‌دید و هر دو حالت را «USDT.D بالا →
بازار نزولی» می‌خواند. برای حالت اول این تفسیر می‌تواند دقیقاً برعکس
باشد.

## روش — تجزیهٔ لگاریتمی (دقیق، نه تقریبی)

از ln(D) = ln(S) − ln(T) نتیجه می‌شود:

    Δln(D) = Δln(S) − Δln(T)

یعنی تغییر نسبت **دقیقاً** جمعِ دو اثر است؛ سهم هر کدام قابل شمارش است
و چیزی «تقریب زده» نمی‌شود. سهم‌ها با قدرمطلق نرمال می‌شوند تا وقتی دو
اثر خلاف هم عمل می‌کنند هم قابل خواندن بمانند.

## مرز صادقانه

- منبع هر دو عدد یک فراخوان است (CoinGecko global): نسبت و کل بازار.
  عرضهٔ تتر مستقیم خوانده نمی‌شود، از همان دو ساخته می‌شود
  (S = D × T). پس خطای اندازه‌گیریِ منبع در هر دو مشترک است.
- این ماژول **شاهد** است نه دروازه: هیچ سیگنالی را وتو یا تأیید
  نمی‌کند. ورودش به تصمیم فقط از مسیر قانون ۰۳ (بک‌تست، CI بالای صفر،
  تأیید حمید).
- نقطه‌های قدیمیِ سری فیلد کل بازار (`m`) ندارند؛ تا وقتی تاریخچهٔ کافی
  جمع نشود خروجی INSUFFICIENT است — عدد ساخته نمی‌شود (قانون ۱).
"""
import math

# کف تغییر برای این‌که «حرکت» شمرده شود (لگاریتمی، ~۰.۰۵٪)
MIN_LOG_MOVE = 0.0005
# سهمِ لازم برای این‌که یک ریشه «غالب» اعلام شود
DOMINANT_SHARE = 0.65


def _at(points, t_target, tol_ms):
    """نزدیک‌ترین نقطه به زمان هدف، اگر داخل تحمل باشد — وگرنه None."""
    ok = [p for p in points if "m" in p and p.get("m")]
    if not ok:
        return None
    p = min(ok, key=lambda x: abs(x["t"] - t_target))
    return p if abs(p["t"] - t_target) <= tol_ms else None


def decompose(points, minutes=240):
    """تجزیهٔ تغییر USDT.D در بازهٔ داده‌شده به سهم صورت و مخرج.

    خروجی: dict با status و — در صورت کافی بودن داده — سهم‌ها و تفسیر."""
    pts = [p for p in (points or []) if p.get("m") and p.get("u")]
    if len(pts) < 2:
        return {"status": "INSUFFICIENT",
                "why": "سری هنوز کل ارزش بازار را ذخیره نکرده — "
                       "تجزیه بدون مخرج ممکن نیست (قانون ۱)"}
    now = pts[-1]
    tol = max(minutes * 60000 * 0.25, 15 * 60000)
    past = _at(pts, now["t"] - minutes * 60000, tol)
    if past is None or past["t"] >= now["t"]:
        return {"status": "INSUFFICIENT",
                "why": f"نقطهٔ {minutes} دقیقه قبل با کل بازار در سری نیست"}

    d0, d1 = past["u"] / 100.0, now["u"] / 100.0
    t0, t1 = float(past["m"]), float(now["m"])
    if min(d0, d1, t0, t1) <= 0:
        return {"status": "INSUFFICIENT", "why": "عدد نامعتبر در سری"}
    s0, s1 = d0 * t0, d1 * t1            # عرضهٔ تتر، از خود نسبت و کل بازار

    dl_d = math.log(d1 / d0)             # تغییر نسبت
    dl_s = math.log(s1 / s0)             # اثر صورت (عرضه)
    dl_t = -math.log(t1 / t0)            # اثر مخرج (کل بازار)، با علامت اثرش

    if abs(dl_d) < MIN_LOG_MOVE:
        label, story = "FLAT", "دامیننس تتر در این بازه تکان معناداری نخورد"
    else:
        tot = abs(dl_s) + abs(dl_t)
        share_s = abs(dl_s) / tot if tot else 0.0
        if share_s >= DOMINANT_SHARE:
            label = "SUPPLY_DRIVEN"
            story = ("عرضهٔ تتر عوض شده، نه قیمتِ بازار — "
                     + ("تترِ تازه وارد شده (باروتِ خشک؛ خودش ریزش نیست)"
                        if dl_s > 0 else
                        "تتر از سیستم خارج شده (پول رفته یا خرج شده)"))
        elif share_s <= 1 - DOMINANT_SHARE:
            label = "MARKET_DRIVEN"
            story = ("کل ارزش بازار عوض شده، نه عرضهٔ تتر — "
                     + ("بازار ریخته و سهم تتر خودبه‌خود بالا رفته "
                        "(ریزشِ واقعی)" if dl_t > 0 else
                        "بازار بالا رفته و سهم تتر خودبه‌خود کم شده"))
        else:
            label = "MIXED"
            story = "هر دو ریشه هم‌زمان اثر دارند — تفسیر یک‌طرفه ممنوع"

    tot = abs(dl_s) + abs(dl_t)
    return {
        "status": "OK",
        "minutes": minutes,
        "usdt_d_from": round(past["u"], 3), "usdt_d_to": round(now["u"], 3),
        "d_dom_pct": round(100 * dl_d, 3),
        "supply_effect_pct": round(100 * dl_s, 3),
        "mcap_effect_pct": round(100 * dl_t, 3),
        "supply_share": round(abs(dl_s) / tot, 3) if tot else None,
        "mcap_share": round(abs(dl_t) / tot, 3) if tot else None,
        "supply_usd_from": round(s0), "supply_usd_to": round(s1),
        "mcap_usd_from": round(t0), "mcap_usd_to": round(t1),
        "label": label,
        "story": story,
        "limit": ("عرضهٔ تتر مستقیم خوانده نشده؛ از نسبت × کل بازار ساخته "
                  "شده. شاهد است نه دروازه (قانون ۰۳)."),
    }


def line(dec):
    """یک خط فارسی برای کپشن — یا None اگر داده کافی نیست."""
    if not dec or dec.get("status") != "OK" or dec["label"] == "FLAT":
        return None
    icon = {"SUPPLY_DRIVEN": "🧪", "MARKET_DRIVEN": "📉",
            "MIXED": "🔀"}.get(dec["label"], "🔍")
    return (f"{icon} تجزیهٔ USDT.D ({dec['minutes']}د): "
            f"{dec['d_dom_pct']:+g}٪ = عرضه {dec['supply_effect_pct']:+g}٪ "
            f"+ کل بازار {dec['mcap_effect_pct']:+g}٪ — {dec['story']}")


def stable_split(points, minutes=240):
    """USDT.D در برابر USDC.D — بند ۳ (دستور حمید، ۲۹ اوت).

    چرا تفکیک لازم است: «پول به استیبل رفت» یک جمله است ولی دو جریانِ
    متفاوت دارد. تتر عمدتاً آفشور و معاملاتی است؛ یواس‌دی‌سی بیشتر
    آمریکایی/نهادی. اگر **هر دو** بالا بروند، یعنی واقعاً از ریسک
    فرار شده. اگر فقط یکی بالا برود و دیگری پایین، احتمالاً **چرخش
    بین خودِ استیبل‌ها** است — نه ترسِ بازار؛ و خواندنش به‌عنوان
    ریسک‌آف، خطای تفسیر است.

    خروجی شاهد است نه دروازه (قانون ۰۳)."""
    pts = [p for p in (points or []) if p.get("u") and p.get("c")]
    if len(pts) < 2:
        return {"status": "INSUFFICIENT",
                "why": "سری هنوز USDC.D را ذخیره نکرده — تفکیک ممکن نیست"}
    now = pts[-1]
    tol = max(minutes * 60000 * 0.25, 15 * 60000)
    past = min(pts, key=lambda x: abs(x["t"] - (now["t"] - minutes * 60000)))
    if abs(past["t"] - (now["t"] - minutes * 60000)) > tol or past["t"] >= now["t"]:
        return {"status": "INSUFFICIENT",
                "why": f"نقطهٔ {minutes} دقیقه قبل با USDC.D در سری نیست"}

    du = round(now["u"] - past["u"], 3)
    dc = round(now["c"] - past["c"], 3)
    thr = 0.02                               # کفِ حرکت روی واحد دامیننس
    su = 0 if abs(du) < thr else (1 if du > 0 else -1)
    sc = 0 if abs(dc) < thr else (1 if dc > 0 else -1)
    if su == sc == 0:
        label, story = "FLAT", "هیچ‌کدام از دو استیبل تکان معناداری نخوردند"
    elif su == sc == 1:
        label, story = "RISK_OFF", ("هر دو استیبل بالا — فرار از ریسکِ "
                                    "واقعی، نه چرخش بین استیبل‌ها")
    elif su == sc == -1:
        label, story = "RISK_ON", ("هر دو استیبل پایین — پول از حاشیه "
                                   "به بازار برگشته")
    elif su * sc == -1:
        label, story = "STABLE_ROTATION", (
            "یکی بالا و دیگری پایین — چرخش بین خودِ استیبل‌ها؛ "
            "خواندنش به‌عنوان ریسک‌آف خطای تفسیر است")
    else:
        label, story = "PARTIAL", ("فقط یکی از دو استیبل حرکت کرده — "
                                   "شاهدِ ضعیف، نه حکم")
    return {"status": "OK", "minutes": minutes,
            "usdt_d_delta": du, "usdc_d_delta": dc,
            "usdt_d": round(now["u"], 3), "usdc_d": round(now["c"], 3),
            "label": label, "story": story,
            "limit": "شاهد است نه دروازه؛ منبع: CoinGecko global."}


def split_line(sp):
    if not sp or sp.get("status") != "OK" or sp["label"] == "FLAT":
        return None
    icon = {"RISK_OFF": "🛡", "RISK_ON": "🔥",
            "STABLE_ROTATION": "🔁", "PARTIAL": "◐"}.get(sp["label"], "🔍")
    return (f"{icon} استیبل‌ها ({sp['minutes']}د): USDT.D "
            f"{sp['usdt_d_delta']:+g} · USDC.D {sp['usdc_d_delta']:+g} — "
            f"{sp['story']}")


def summary(points):
    """تجزیه روی چند بازه — کوتاه و بلند، چون معنی‌شان یکی نیست."""
    out = {f"{m}m": decompose(points, m) for m in (60, 240, 1440)}
    out["stable_split"] = {f"{m}m": stable_split(points, m)
                           for m in (240, 1440)}
    return out
