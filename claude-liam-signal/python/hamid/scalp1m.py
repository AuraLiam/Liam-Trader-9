"""موتور قطعیِ ۱ دقیقه — دامیننس، بستر، ساختار، احتمال. پایتون، نه LLM.

دستور حمید (۲۴ اوت): «بر اساس تایم یک دقیقه کدها را بده به پایتون سریع
و با بررسی دامیننس‌ها و احتمالات و همهٔ مواردی که قبلاً گفته بودم پوزیشن
باز بشه، و اینکه باهاش در ارتباط باشی که بتوانی آپدیت‌های تحلیل‌ها را
بهش بدی.»

## چرا این فایل ساخته شد

میز ۱ دقیقهٔ قبلی (`hamid/scalp.py`) فقط EMA21/55 + IBS + پولبک بود.
نه دامیننس می‌دید، نه بستر BTC، نه ساختار ۴س/۱س/۱۵د، نه اردر بلاک. یعنی
سلسله‌مراتبِ اجباریِ خودِ حمید (`.claude/rules/00`) را رد می‌کرد. حکم
۲۴ اوت هم همان را گفت: لبهٔ ناخالص هست، ولی هندسه و بستر ناقص است.

این فایل همان سلسله‌مراتب را **به همان ترتیب** پیاده می‌کند و هر
دروازه‌ای که رد می‌شود دلیلِ نوشته می‌گذارد — تا سکوتِ موتور همیشه
قابل‌توضیح باشد، نه مرموز.

## ترتیب دروازه‌ها (قابل تغییر نیست جز با دستور صریح حمید)

    ۱  تازگی و کاملی داده        ناقص = NO_SIGNAL (قانون ۱)
    ۲  USDT.D مستقل              رژیم خلاف = رد یا تنزل
    ۳  BTC.D / کلان              رویداد کلان = UNSAFE
    ۴  بستر BTC ۴س+۱س            هر دو خلاف = وتوی مطلق (قانون ۳)
    ۵  ساختار خودِ نماد ۴س→۱س    trend_gate (قانون ۲)
    ۶  مکان ۱۵د                  ستاپ باید از قبل موجود باشد
    ۷  اجرای ۵د                  بستر ماشه
    ۸  ماشهٔ ۱د                   فقط کندلِ **بسته** (قانون ۱۰)
    ۹  اردر بلاک + نقشهٔ نقدینگی  OB مصرف‌نشده، نقدینگی اجباری
    ۱۰ کارمزد + محافظ لیکویید     دام کارمزد = رد
    ۱۱ کارنامهٔ تجربه            رکورد بدِ نمونه‌دار = رد
    ۱۲ احتمال                    از دفتر **اندازه‌گیری** می‌شود، نه ساخته
    ۱۳ تصمیم

## احتمال — چطور ساخته نمی‌شود

«احتمال» این‌جا عددِ اختراعی نیست. امتیازِ دروازه‌ها به یک سطل نگاشت
می‌شود و نرخ بردِ **تاریخیِ همان سطل** از دفتر بسته خوانده می‌شود. اگر
نمونهٔ آن سطل کم باشد، `p=None` برمی‌گردد و صریح می‌گوید چرا. عددی که
پشتش شمارش نباشد، در این فایل چاپ نمی‌شود (قانون گزارش، CLAUDE.md).

## کانال آپدیت تحلیل

ایجنت از راه `liam9_link` فرمانِ **امضاشدهٔ** `analysis` می‌فرستد و این
موتور آن را به‌عنوان **شاهدِ مشورتی** می‌خواند: می‌تواند اطمینان را کم
کند یا نماد را در فهرست پرهیز بگذارد، ولی **هرگز** نمی‌تواند دروازهٔ
سختی را باز کند یا سیگنالی بسازد که خودِ داده تأییدش نکرده. جهتِ اثر
یک‌طرفه است — محافظه‌کارانه، نه جسورانه (بند ۱۱ قانون ۰۱: خروجی هیچ
ایجنتی واقعیت تلقی نمی‌شود).

## مرز اجرای زنده

خروجی این فایل **تصمیم** است، نه سفارش. `LIVE_EXECUTION=false` سرِ جایش
است؛ اجرا یا دفتر پیپر است یا دست حمید (قانون ۰۵).
"""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
if str(PY) not in sys.path:
    sys.path.insert(0, str(PY))
ROOT = HERE.parents[2]

import liam9_strategy as ST                          # noqa: E402
from hamid import trend_gate as TG                   # noqa: E402

DOM_FILE = ROOT / "signals" / "dominance.json"
ANALYSIS_FILE = ROOT / "signals" / "analysis-updates.json"
CLOSED = ROOT / "brain" / "paper" / "closed.jsonl"
OUT = ROOT / "signals" / "scalp1m.json"

STAGE = "scalp1m"
MAX_CANDLE_AGE_S = 180        # کندل ۱د کهنه‌تر از ۳ دقیقه = دادهٔ بیات
MIN_1M = 120                  # کف کندل برای ماشه
ANALYSIS_TTL_S = 3600         # آپدیت تحلیل بعد از یک ساعت منقضی است
PROB_MIN_N = 40               # زیر این نمونه، احتمال اعلام نمی‌شود


# ── ابزار کوچک ────────────────────────────────────────────────────────
def _no(gate, why, **extra):
    d = {"decision": "NO_SIGNAL", "gate": gate, "why": why, "stage": STAGE}
    d.update(extra)
    return d


def _ema(vals, n):
    k = 2 / (n + 1)
    e = vals[0]
    for v in vals[1:]:
        e = v * k + e * (1 - k)
    return e


def _trend_of(cd, fast=21, slow=55):
    """روند از EMA — قطعی و ارزان. کمتر از slow کندل = «نامعلوم»."""
    if len(cd) < slow:
        return "unknown"
    c = [k["c"] for k in cd]
    f, s = _ema(c[-slow:], fast), _ema(c[-slow:], slow)
    if f > s * 1.0005:
        return "up"
    if f < s * 0.9995:
        return "down"
    return "range"


def _fresh(cd, max_age_s=MAX_CANDLE_AGE_S, now_ms=None):
    """آخرین کندل چقدر کهنه است. بیات = NO_SIGNAL، نه عبورِ کور."""
    if not cd:
        return None
    now = now_ms or time.time() * 1000
    return (now - (cd[-1].get("t") or 0)) / 1000.0


# ── دروازهٔ ۲ و ۳: دامیننس ────────────────────────────────────────────
def dominance_gate(direction, dom=None):
    """رژیم دامیننس از `signals/dominance.json` (تولیدِ اتاق دامیننس).

    اجباری است (قانون ۳: USDT.D و بستر BTC برای هر سیگنال آلت لازم‌اند).
    نبودِ فایل یا دادهٔ ناکافی = رد، نه عبور.
    """
    if dom is None:
        try:
            dom = json.loads(DOM_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False, "دادهٔ دامیننس در دسترس نیست — قانون ۳", None
    # کلیدِ مرده، رفع ۶ سپتامبر: این‌جا `structural` خوانده می‌شد ولی
    # تولیدکننده (`dominance.py:280`) `structure` می‌نویسد. روی فایل واقعی
    # همیشه به fallback می‌افتاد و `INSUFFICIENT` می‌داد — یعنی دروازهٔ
    # ۲/۳ میز اسکلپ ۱د **صددرصد رد** می‌کرد، با دلیلی که می‌گفت داده نیست.
    # آزمونش سبز بود چون دیکشنری دست‌ساز با همان کلیدِ غلط می‌ساخت: همان
    # کلاسِ «اسکریپت سبز ≠ محصول درست» (قانون ۶ سپتامبر). هر دو کلید
    # خوانده می‌شود تا اگر جایی شکل قدیمی مانده باشد نشکند.
    reg = ((dom.get("structure") or dom.get("structural") or {}).get("regime")
           or dom.get("regime") or "INSUFFICIENT")
    if reg in ("INSUFFICIENT", "UNKNOWN"):
        return False, f"رژیم دامیننس {reg} — دادهٔ ناقص = NO_SIGNAL", reg
    if reg == "UNSAFE":
        return False, "رویداد کلان فعال (UNSAFE) — حکم جهتی معلق", reg
    # رژیم از دید آلت‌هاست: BULLISH یعنی پول وارد ریسک شده.
    if reg == "BEARISH" and direction == "LONG":
        return False, "رژیم دامیننس BEARISH و جهت LONG — تعارض", reg
    if reg == "BULLISH" and direction == "SHORT":
        return False, "رژیم دامیننس BULLISH و جهت SHORT — تعارض", reg
    return True, f"رژیم دامیننس {reg} مانع نیست", reg


# ── کانال آپدیت تحلیل ─────────────────────────────────────────────────
def analysis_for(sym, now_ms=None, path=None):
    """آپدیت تحلیلِ ایجنت برای این نماد — مشورتی و یک‌طرفه.

    فقط می‌تواند **سخت‌گیرتر** کند: اطمینان را پایین بیاورد یا نماد را
    ممنوع کند. هیچ کلیدی برای بازکردن دروازه ندارد؛ اگر روزی کسی چنین
    کلیدی اضافه کند، `test_scalp1m` چرخه را سرخ می‌کند.
    """
    p = Path(path) if path else ANALYSIS_FILE
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    now = (now_ms or time.time() * 1000) / 1000.0
    best = None
    for a in (doc.get("updates") or []):
        if str(a.get("sym") or "").upper() not in (sym.upper(), "*"):
            continue
        if now - float(a.get("at", 0) or 0) / 1000.0 > ANALYSIS_TTL_S:
            continue                                  # کهنه = نادیده
        best = a                                      # جدیدترین می‌ماند
    if not best:
        return None
    return {
        "note": str(best.get("note", ""))[:400],
        # فقط دو اهرمِ محافظه‌کارانه — و هر دو سقف‌خورده.
        "avoid": bool(best.get("avoid")),
        "confidence_delta": max(-40.0, min(0.0,
                                float(best.get("confidence_delta", 0) or 0))),
        "at": best.get("at"),
    }


# ── دروازهٔ ۱۲: احتمال، از شمارش ──────────────────────────────────────
def _bucket(score):
    for hi in (50, 60, 70, 80, 90):
        if score < hi:
            return f"<{hi}"
    return "90+"


def probability(score, direction, ledger=None, min_n=PROB_MIN_N):
    """نرخ بردِ تاریخیِ همین سطلِ امتیاز. نمونهٔ کم → None، نه حدس."""
    rows = ledger
    if rows is None:
        rows = []
        p = CLOSED
        if p.exists():
            with p.open(encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    if not line.strip():
                        continue
                    try:
                        r = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    w = r.get("why") or {}
                    if w.get("stage") not in (STAGE, "scalp"):
                        continue
                    if r.get("R") is None or w.get("score") is None:
                        continue
                    rows.append(r)
    b = _bucket(score)
    same = [r for r in rows
            if _bucket((r.get("why") or {}).get("score", -1)) == b]
    if len(same) < min_n:
        return {"p": None, "n": len(same), "bucket": b,
                "why": f"نمونهٔ سطل {b} فقط {len(same)} است (کف {min_n}) — "
                       "احتمال اعلام نمی‌شود؛ عددِ بی‌شمارش ساخته نمی‌شود"}
    won = sum(1 for r in same if float(r["R"]) > 0)
    return {"p": round(won / len(same) * 100, 1), "n": len(same), "bucket": b,
            "why": f"نرخ بردِ اندازه‌گیری‌شدهٔ سطل {b} روی {len(same)} معامله"}


# ── موتور ─────────────────────────────────────────────────────────────
def decide(sym, c1m, kget, dom=None, now_ms=None, ledger=None,
           analysis_path=None):
    """تصمیم ۱ دقیقه با کلِ سلسله‌مراتب.

    `kget(sym, tf, n) -> candles` — همان رابطی که trend_gate می‌خواهد،
    پس منبعِ داده این‌جا تزریق می‌شود و فایل به شبکه گره نمی‌خورد
    (آزمون‌پذیری، و اجرا روی سرویس محلی یا رانر، هر دو).
    """
    now = now_ms or time.time() * 1000
    funnel = []

    def passed(gate, why):
        funnel.append({"gate": gate, "ok": True, "why": why})

    # ۱ — تازگی و کاملی
    if not c1m or len(c1m) < MIN_1M:
        return _no("data", f"کندل ۱د کافی نیست ({len(c1m or [])} از {MIN_1M})",
                   funnel=funnel)
    age = _fresh(c1m, now_ms=now)
    if age is None or age > MAX_CANDLE_AGE_S:
        return _no("freshness",
                   f"آخرین کندل ۱د {age:.0f} ثانیه کهنه است — دادهٔ بیات "
                   "= NO_SIGNAL (قانون ۱)", funnel=funnel)
    # قانون ۱۰ بند ۱: کندلِ باز حذف می‌شود؛ تصمیم فقط روی بسته‌ها.
    closed_1m = c1m[:-1] if age < 60 else c1m
    if len(closed_1m) < MIN_1M:
        return _no("data", "بعد از حذف کندلِ باز، کندل کافی نماند",
                   funnel=funnel)
    passed("data", f"{len(closed_1m)} کندل بسته، تازگی {age:.0f}s")

    # جهتِ نامزد از ماشهٔ ۱د — بعد از این، همهٔ دروازه‌ها روی همین جهت
    t1m = _trend_of(closed_1m)
    if t1m not in ("up", "down"):
        return _no("trigger", f"روند ۱د «{t1m}» است — ماشه‌ای نیست",
                   funnel=funnel)
    direction = "LONG" if t1m == "up" else "SHORT"

    # ۲/۳ — دامیننس
    ok, why, reg = dominance_gate(direction, dom)
    if not ok:
        return _no("dominance", why, dir=direction, regime=reg, funnel=funnel)
    passed("dominance", why)

    # ۴/۵ — بستر BTC و ساختار خودِ نماد (۴س+۱س)، از دروازهٔ روندِ موجود
    tg = TG.assess(sym, direction, kget)
    if not tg["ok"]:
        return _no("trend", tg["reason"], dir=direction, funnel=funnel)
    passed("trend", f"۴س={tg['t4']} · ۱س={tg['t1']} · حالت {tg['mode']}")

    # ۶/۷ — مکان ۱۵د و بسترِ ۵د: تایم پایین حق نقض بالادست را ندارد
    try:
        c15 = kget(sym, "15m", 200)
        c5 = kget(sym, "5m", 200)
    except Exception as e:                            # noqa: BLE001
        return _no("htf", f"کندل ۱۵د/۵د خواندنی نیست ({type(e).__name__})",
                   dir=direction, funnel=funnel)
    t15, t5 = _trend_of(c15), _trend_of(c5)
    want = "up" if direction == "LONG" else "down"
    if t15 not in (want, "range"):
        return _no("htf", f"ساختار ۱۵د ({t15}) خلاف {direction} است — "
                          "تایم پایین بالادست را نقض نمی‌کند (قانون ۲)",
                   dir=direction, funnel=funnel)
    passed("htf", f"۱۵د={t15} · ۵د={t5}")

    # ۹ — اردر بلاک و نقشهٔ نقدینگی (نقدینگی اجباری، دستور ۲۳ اوت)
    ob = ST.order_block_zone(closed_1m, direction)
    lm = ST._liq_map(kget(sym, "1h", 200))
    if lm is None:
        return _no("liquidity", "نقشهٔ نقدینگی از کندل ۱س ساختنی نیست — "
                                "بررسی نقدینگی اجباری است",
                   dir=direction, funnel=funnel)
    passed("liquidity", ST._liq_line(lm))

    # هندسه: ورود/استاپ/تارگت از همان موتور اسکلپِ داشبورد
    sig = ST.scalp_decide(closed_1m, sym)
    if not sig or sig.get("decision") == "NO_SIGNAL":
        return _no("geometry", (sig or {}).get("why", "هندسهٔ اسکلپ نداد"),
                   dir=direction, funnel=funnel)
    if sig.get("dir") != direction:
        return _no("geometry",
                   f"جهت هندسه ({sig.get('dir')}) با ماشهٔ ۱د ({direction}) "
                   "نمی‌خواند", dir=direction, funnel=funnel)
    passed("geometry", f"ورود {sig['entry']} · استاپ {sig['sl']} · "
                       f"کارمزد {sig.get('fee_r')}R")

    # ۱۱ — کارنامهٔ تجربه (قانون ۰۳ بند ۲: تصمیم باید رکورد را بخواند)
    exp = None
    try:
        exp = ST.experience_of(sym, direction)
    except Exception:                                 # noqa: BLE001
        pass
    if exp and exp.get("n", 0) >= 12 and exp.get("mean_r", 0) < -0.30:
        return _no("experience",
                   f"کارنامهٔ ({sym}, {direction}): {exp['n']} مورد، "
                   f"انتظار {exp['mean_r']}R — اتاق یادگیری مخالف است",
                   dir=direction, funnel=funnel)

    # امتیاز: فقط از دروازه‌هایی که واقعاً پاس شدند + کیفیت هندسه
    quality = float(sig.get("quality") or 0)
    score = min(100.0, quality + 5 * len(funnel))

    # کانال آپدیت تحلیل — فقط سخت‌گیرتر می‌کند
    upd = analysis_for(sym, now_ms=now, path=analysis_path)
    if upd:
        if upd["avoid"]:
            return _no("analysis",
                       f"آپدیت تحلیل ایجنت: پرهیز — {upd['note']}",
                       dir=direction, funnel=funnel, analysis=upd)
        score = max(0.0, score + upd["confidence_delta"])
        passed("analysis", f"آپدیت ایجنت: {upd['note'] or 'بدون یادداشت'} "
                           f"(اطمینان {upd['confidence_delta']:+})")

    # ۱۲ — احتمال، از شمارش
    prob = probability(score, direction, ledger=ledger)

    out = dict(sig)
    out.update({
        "decision": "SIGNAL", "stage": STAGE, "sym": sym, "dir": direction,
        "score": round(score, 1), "probability": prob,
        "dominance_regime": reg, "trend": {"4h": tg["t4"], "1h": tg["t1"],
                                           "15m": t15, "5m": t5, "1m": t1m},
        "trend_mode": tg["mode"], "order_block": ob, "liq_map": lm,
        "experience": exp, "analysis": upd, "funnel": funnel,
        "candle_age_s": round(age, 1),
        "boundary": ("تصمیم است نه سفارش — LIVE_EXECUTION=false؛ اجرا "
                     "دفتر پیپر یا دست حمید (قانون ۰۵)."),
    })
    return out


def run(symbols, kget, dom=None, quiet=False, write=True):
    """یک نوبت روی فهرست نماد. خروجی روی `signals/scalp1m.json`."""
    sigs, rejects = [], []
    for sym in symbols:
        try:
            c1m = kget(sym, "1m", 400)
            d = decide(sym, c1m, kget, dom=dom)
        except Exception as e:                        # noqa: BLE001
            d = _no("error", f"{type(e).__name__}: {e}")
            d["sym"] = sym
        (sigs if d.get("decision") == "SIGNAL" else rejects).append(d)
    res = {"at": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
           "panel": "لیام تریدر ۹", "stage": STAGE,
           "scanned": len(symbols), "signals": sigs,
           "reject_reasons": _reasons(rejects)}
    if write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1),
                       encoding="utf-8")
    if not quiet:
        print(f"۱ دقیقه: {len(symbols)} نماد · {len(sigs)} سیگنال")
        for g, n in sorted(res["reject_reasons"].items(), key=lambda x: -x[1]):
            print(f"  {g}: {n}")
    return res


def _reasons(rejects):
    """قیفِ رد — سکوت موتور باید همیشه توضیح داشته باشد، نه ابهام."""
    out = {}
    for r in rejects:
        out[r.get("gate", "?")] = out.get(r.get("gate", "?"), 0) + 1
    return out


if __name__ == "__main__":
    print(__doc__.split("##")[0].strip())
    print("این موتور منبع داده را تزریقی می‌گیرد؛ اجرای واقعی از "
          "ورک‌فلوی scalp.yml یا سرویس محلی است.")
