"""دفتر سناریو — همهٔ احتمالات، آماده پیش از بسته شدن کندل بعدی.

دستور صریح حمید (۲۲ اوت): «در تایم ۱ یا ۳ دقیقه تمام سناریوهای احتمالی
بعد از بسته شدن کندل در هر قیمتی بررسی شده باشد — مثلاً اگر BOS زد چه
پوزیشنی باز شود یا اگر CHoCH بود چه پوزیشنی... بلافاصله بعد از بسته شدن
کندل، تحلیل‌ها و احتمالات آماده باشند و سریع وارد شوند.»

## چرا این ماژول جدا از موتور اسکلپ است

موتور فعلی (`liam9_strategy.scalp_decide`) بعد از بسته شدن کندل **شروع
به فکر کردن** می‌کند. این ماژول برعکس کار می‌کند: روی کندلِ بستهٔ فعلی،
**قبل** از اینکه کندل بعدی بسته شود، جدول شاخه‌ها را می‌سازد:

    اگر بالای X بست  → BOS صعودی  → لانگ با این استاپ/تارگت/اهرم
    اگر زیر Y بست    → CHoCH نزولی → شورت با این استاپ/تارگت/اهرم
    غیر این          → NO_TRADE، دلیلش هم نوشته شده

لحظهٔ بسته شدن کندل بعدی، کاری جز یک مقایسهٔ عددی و `resolve()` نمانده —
همان «سریع وارد شوند» که حمید خواست.

## مرز صادقانه

قیمت دقیق ورود در لحظهٔ **برنامه‌ریزی** قابل‌دانستن نیست (کلوزِ کندلِ
ماشه هنوز رخ نداده). پس شاخه‌ها **فاصله‌ها** را از پیش حساب می‌کنند
(استاپ ساختاری، سقف نویز ATR، ضریب RR، اهرم) و `resolve(branch, close)`
در لحظهٔ ماشه با یک ضرب و جمع، ورود/استاپ/تارگت قطعی می‌دهد. هیچ‌جا
قیمت آینده لازم نیست — همین است که بک‌تستش بدون نگاه به آینده می‌ماند.

اهرم: پیش‌فرض ۵ (دستور حمید برای این آزمایش). یادآوری اندازه‌گیری‌شدهٔ
پروژه: اهرم **لبه را عوض نمی‌کند** — R، نرخ برد و سهم کارمزد از R
دست‌نخورده می‌مانند؛ اهرم فقط مارجین و فاصلهٔ لیکویید را جابه‌جا می‌کند.
پس کارنامه هم به R گزارش می‌شود هم به درصد حساب با همان اهرم، تا هر دو
دیده شوند.
"""

from hamid import microstructure as MS

PLAN_VERSION = "scen-1.0"

# کارمزدهای راستی‌آزمایی‌شدهٔ بیت‌یونیکس (config/fees.json، ۱۶ اوت):
# میکر ۰.۰۲٪ · تیکر ۰.۰۶٪ · لغزش ۰.۰۱۵٪ بر هر پا.
MAKER_PCT = 0.02
TAKER_PCT = 0.06
SLIP_PCT = 0.015

# دو مدل کارمزد — تفاوتشان همان چیزی است که بک‌تست اول نشان داد گلوگاه است.
#   taker: ورود و خروج هر دو مارکت  →  ۰.۰۶×۲ + ۰.۰۱۵×۲ = ۰.۱۵٪
#   maker_entry: ورود لیمیت روی خودِ سطح (بدون لغزش)، تارگت هم لیمیت،
#     ولی **استاپ همیشه مارکت است** (استاپ لیمیت یعنی استاپِ اجرانشده).
#     پس کارمزد به نتیجه بستگی دارد:
#        تارگت → ۰.۰۲ + ۰.۰۲            = ۰.۰۴٪
#        استاپ → ۰.۰۲ + ۰.۰۶ + ۰.۰۱۵    = ۰.۰۹۵٪
# هزینهٔ واقعیِ میکر جای دیگری است: سفارش لیمیت ممکن است **پر نشود** —
# و دقیقاً روی حرکت‌های تندِ برنده پر نمی‌شود (انتخاب نامساعد). بک‌تستی که
# فرض کند لیمیت همیشه پر می‌شود، خودش را گول زده. مدل‌سازی‌اش در
# scenario_backtest.maker_fill.
FEE_MODELS = {
    "taker": {"entry": TAKER_PCT + SLIP_PCT,
              "exit_target": TAKER_PCT + SLIP_PCT,
              "exit_stop": TAKER_PCT + SLIP_PCT},
    "maker_entry": {"entry": MAKER_PCT,
                    "exit_target": MAKER_PCT,
                    "exit_stop": TAKER_PCT + SLIP_PCT},
}

P = {
    "atr_n": 14,
    "atr_stop_mult": 1.2,        # استاپ بیرون نویز (همان ضریب موتور سوینگ)
    "rr_target": 1.5,            # هدف اسکلپ (همان SCALP["rr_target"])
    "fee_model": "taker",
    "fee_round_trip_pct": 0.15,  # تیکر دو سر + لغزش — برای دروازهٔ max_fee_r
    "max_fee_r": 0.30,           # استاپ تنگ = دام کارمزد → شاخه باطل
    "leverage": 5,               # دستور حمید برای این آزمایش
    "liq_guard": 50.0,           # اهرم ≤ ۵۰/استاپ٪ — محافظ فاصلهٔ لیکویید
    "max_stop_pct": 1.6,         # سقف استاپ اسکلپ (RISK_CONTRACT)
    "min_stop_pct": 0.10,        # زیر این، استاپ داخل اسپرد/نویز است
    "maker_wait_bars": 3,        # لیمیت چند کندل منتظر پر شدن می‌ماند
}


def round_trip_pct(model, outcome="target"):
    """کارمزد رفت‌وبرگشت برای یک مدل و یک نتیجه — درصد، نه R."""
    f = FEE_MODELS[model]
    return f["entry"] + (f["exit_stop"] if outcome == "stop" else f["exit_target"])


def atr(cd, n=14):
    if len(cd) < n + 1:
        return None
    tr = []
    for i in range(len(cd) - n, len(cd)):
        h, l, pc = cd[i]["h"], cd[i]["l"], cd[i - 1]["c"]
        tr.append(max(h - l, abs(h - pc), abs(l - pc)))
    return sum(tr) / len(tr) if tr else None


def _leverage(stop_pct, want):
    """اهرم هرگز از محافظ لیکویید رد نمی‌شود (قانون ۳ شوک، ۱۹ اوت)."""
    if stop_pct <= 0:
        return None
    return max(1, min(int(want), int(P["liq_guard"] / stop_pct)))


def plan(cd, symbol="?", params=None):
    """جدول شاخه‌ها روی آخرین کندلِ بسته.

    خروجی: dict با `branches` — هر شاخه یک ماشهٔ عددی و یک نقشهٔ کامل
    دارد. اگر ساختار/داده کافی نباشد، `branches` خالی است و `why` می‌گوید
    چرا (ردشدن در سکوت ممنوع)."""
    q = dict(P, **(params or {}))
    out = {"formula_version": PLAN_VERSION, "symbol": symbol,
           "branches": [], "why": None}
    if not cd or len(cd) < q["atr_n"] + 12:
        out["why"] = "کندل ناکافی برای ساختار و ATR — قانون ۱"
        return out

    st = MS.structure(cd)
    if st is None:
        out["why"] = "ساختار قابل‌سنجش نیست (پیوت تأییدشده نداریم)"
        return out
    a = atr(cd, q["atr_n"])
    if not a or a <= 0:
        out["why"] = "ATR صفر/نامعتبر — بازار بی‌حرکت یا دادهٔ خراب"
        return out

    out.update({"at_i": len(cd) - 1, "at_t": cd[-1]["t"],
                "bias": st["bias"], "session": st["session"],
                "last_event": st["last_event"],
                "last_event_dir": st["last_event_dir"],
                "atr": round(a, 8)})

    sh, sl_piv = st["swing_high"], st["swing_low"]
    if not sh or not sl_piv:
        out["why"] = "هنوز هر دو سمت پیوت تأییدشده نداریم"
        return out

    # شاخهٔ صعودی: بستن بالای سقف پیوت. اگر ساختار از قبل صعودی است این
    # BOS (ادامه) است؛ اگر نزولی است CHoCH (تغییر کاراکتر) — و طبق قانون ۵
    # CHoCH به‌تنهایی برگشت نیست، پس برچسبش را حمل می‌کند تا لایهٔ بالاتر
    # (و کارنامهٔ بک‌تست) بتواند این دو را جدا بسنجد.
    for direction, lvl, struct_stop in (
            ("LONG", sh["px"], sl_piv["px"]),
            ("SHORT", sl_piv["px"], sh["px"])):
        kind = _kind_for(st["bias"], direction)
        br = _build(direction, kind, lvl, struct_stop, a, q, st)
        if br:
            out["branches"].append(br)
    if not out["branches"]:
        out["why"] = "هر دو شاخه با دروازه‌های ریسک/کارمزد باطل شدند"
    return out


def _kind_for(bias, direction):
    if direction == "LONG":
        return "BOS" if bias == "up" else ("CHoCH" if bias == "down" else "BOS")
    return "BOS" if bias == "down" else ("CHoCH" if bias == "up" else "BOS")


def _build(direction, kind, level, struct_stop, a, q, st):
    """یک شاخه — یا نقشهٔ کامل، یا None با دلیلِ ثبت‌شده در rejected."""
    noise = q["atr_stop_mult"] * a
    if direction == "LONG":
        stop = min(struct_stop, level - noise)     # هرکدام دورتر = امن‌تر
        risk = level - stop
    else:
        stop = max(struct_stop, level + noise)
        risk = stop - level
    if risk <= 0:
        return None
    # درصدها نسبت به سطح ماشه تخمین زده می‌شوند؛ ورود واقعی در resolve()
    # جای level می‌نشیند و اعداد دقیق همان‌جا دوباره حساب می‌شوند.
    stop_pct = risk / level * 100
    if not (q["min_stop_pct"] <= stop_pct <= q["max_stop_pct"]):
        return None
    # دروازهٔ کارمزد با **بدترین حالتِ همان مدل** سنجیده می‌شود (خروج با
    # استاپ)، نه با حالت خوش‌بینانه — وگرنه دروازه خودش را گول می‌زند.
    rt = round_trip_pct(q["fee_model"], "stop")
    fee_r = (rt / 100) * level / risk
    if fee_r > q["max_fee_r"]:
        return None
    lev = _leverage(stop_pct, q["leverage"])
    if not lev:
        return None
    return {
        "trigger": f"{kind}_{'UP' if direction == 'LONG' else 'DOWN'}",
        "kind": kind,                       # BOS یا CHoCH — جدا سنجیده می‌شود
        "condition": ("close > level" if direction == "LONG" else "close < level"),
        "level": round(level, 8),
        "action": direction,
        "stop_dist": round(risk, 8),
        "stop_pct_at_level": round(stop_pct, 3),
        "rr_target": q["rr_target"],
        "rr_net": round(q["rr_target"] - fee_r, 3),
        "fee_r": round(fee_r, 3),
        "leverage": lev,
        "session": st["session"],
        "bias_at_plan": st["bias"],
    }


def resolve(branch, close):
    """لحظهٔ ماشه: کلوزِ کندلِ شکست را می‌گیرد، نقشهٔ قطعی می‌دهد.

    فاصله‌ها از قبل حساب شده‌اند، پس این تابع فقط یک ضرب و جمع است — همان
    «سریع وارد شوند». استاپ/تارگت اجباری‌اند (قرارداد اجرا، ۲۰ اوت)."""
    d = branch["stop_dist"]
    if branch["action"] == "LONG":
        sl, tp1 = close - d, close + branch["rr_target"] * d
    else:
        sl, tp1 = close + d, close - branch["rr_target"] * d
    stop_pct = d / close * 100
    return {"action": branch["action"], "kind": branch["kind"],
            "trigger": branch["trigger"],
            "entry": round(close, 8), "sl": round(sl, 8), "tp1": round(tp1, 8),
            "stop_loss": round(sl, 8), "take_profit": round(tp1, 8),
            "sl_tp_mandatory": True, "product": "futures",
            "margin_mode": "isolated",
            "stop_pct": round(stop_pct, 3),
            "leverage": _leverage(stop_pct, branch["leverage"]),
            "rr_net": branch["rr_net"], "session": branch["session"],
            "bias_at_plan": branch["bias_at_plan"],
            "version": PLAN_VERSION, "panel": "لیام تریدر ۹"}


def check(branches, candle):
    """آیا کندلِ تازه‌بسته یکی از شاخه‌ها را زد؟ اولین ماشهٔ منطبق برمی‌گردد.

    ماشه = **بستن** آن‌سوی سطح (نه ویک) — همان انضباطی که برای خط روند و
    BOS هم گذاشتیم."""
    c = candle["c"]
    for b in branches:
        if b["action"] == "LONG" and c > b["level"]:
            return b
        if b["action"] == "SHORT" and c < b["level"]:
            return b
    return None
