#!/usr/bin/env python3
"""میز ریسک و ورود — «این پوزیشن ارزش ورود دارد؟» (دستور حمید، ۳ سپتامبر).

حمید: «ایجنت‌ها باید در نظر بگیرند که آیا این پوزیشن در این شرایط ارزش
ورود دارد یا نه، برای شورت یا لانگ؛ و با بررسی شرایط و میزان اطمینان از
نتیجهٔ احتمالی، پول و اهرمی که این پوزیشن ارزشش را دارد مشخص کنند، طبق
مدیریت ریسک و سرمایه و اطلاعاتی که در آن لحظه دریافت کرده‌اند… این
انجین نتایج رأی‌گیری دامیننس و رویدادها و نظریهٔ ۱۲ متخصص را بررسی و
تصمیم می‌گیرد.»

## ترتیب دروازه‌ها (تغییر فقط با دستور صریح حمید)

| # | دروازه | قاعده |
|---|---|---|
| ۱ | هندسهٔ کامل | ورود/استاپ/تارگت هر سه عدد مثبت (قرارداد اجرا، ۲۰ اوت) |
| ۲ | جهت با هندسه بخواند | لانگ با استاپ بالای ورود = ستاپ خراب، نه ریسکِ زیاد |
| ۳ | کارمزد | کارمزد ≥ ۰.۲۵R = دامِ اسکالپ (قانون ۱۶، مراقب میزان) |
| ۴ | RR خالص | زیر کف، رد — سود اسمی که کارمزد می‌خوردش سود نیست |
| ۵ | محافظ لیکویید | اهرم ≤ min(سقف داشبورد ۲۰، ۵۰÷استاپ٪) — حاکم مطلق |
| ۶ | شواهد ورودی | دامیننس + رویداد + رأی شورا؛ نبودشان اطمینان را پایین می‌آورد، جعل نمی‌شود |
| ۷ | سایز | از **قانون ریسک** می‌آید نه از اهرم |

## دو چیزی که این میز عمداً نمی‌کند

**اهرم را از اطمینان بالا نمی‌برد تا سایز بزرگ شود.** سایز از ریسکِ
ثابتِ درصدی می‌آید (`RISK_PCT`)؛ اهرم فقط مارجینِ قفل‌شده را کم می‌کند.
این تفکیک، همان چیزی است که میز ۱ دقیقه با نداشتنش باخت: ضرر استاپ
همیشه همان درصد می‌ماند، چه اهرم ۵ باشد چه ۲۰.

**اطمینان را از شواهدِ نبوده نمی‌سازد.** دادهٔ ناموجود اطمینان را
**پایین** می‌آورد و دلیلش نوشته می‌شود؛ هرگز «فرضِ خنثی» نمی‌شود
(قانون ۱).

## مرز

خروجی این میز **پیشنهاد** است. LIVE_EXECUTION خاموش است و این ماژول
هیچ سفارشی نمی‌فرستد (قانون ۰۵). ورود هر عددش به مسیر خودکار فقط با CI
بالای صفر و تأیید حمید (قانون ۰۳/۱۲).

    python3 -m hamid.risk_desk --demo
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from hamid import council as CN                      # noqa: E402

# اعداد از همان منابع موجود — این‌جا بازتعریف نمی‌شوند، نقل می‌شوند.
MAX_LEVERAGE = 20              # سقف داشبورد حمید (liam9_link.EXEC_MAX_LEVERAGE)
LIQ_GUARD = 50.0               # اهرم ≤ ۵۰÷استاپ٪ (liam9_link.EXEC_LIQ_GUARD)
RISK_PCT = 2.0                 # ریسک هر معامله از سرمایه (قانون ۱۹ اوت بند ۳)
MAX_CONCURRENT = 3             # سقف پوزیشن هم‌زمان (قانون ۱۰)
FEE_TRAP_R = 0.25              # کارمزد از این بالاتر = دام اسکالپ (قانون ۱۶)
MIN_NET_RR = 1.5               # کف RR خالص از کارمزد
FEE_ROUND_TRIP_PCT = 0.15      # تیکر دو سر + لغزش، عدد راستی‌آزمایی‌شدهٔ ۱۶ اوت

# نگاشت اطمینان → سهم سایز. اهرم این‌جا نیست و عمداً نیست.
SIZE_BANDS = ((0.70, 1.00, "اطمینان بالا — سایز کامل"),
              (0.45, 0.50, "اطمینان متوسط — نصف"),
              (0.25, 0.25, "اطمینان کم — یک‌چهارم، فقط تجربه"),
              (0.00, 0.00, "اطمینان ناکافی — ورود ندارد"))

# وزن هر شاهد در اطمینان. جمعشان ۱ است؛ شاهدِ نبوده سهمش را از دست
# می‌دهد و اطمینان پایین می‌آید — به مخرج برنمی‌گردد.
EVIDENCE_W = {"structure": 0.30, "dominance": 0.20, "council": 0.25,
              "memory": 0.15, "events": 0.10}


def fee_in_r(entry, sl, round_trip_pct=FEE_ROUND_TRIP_PCT):
    """سهم کارمزد از یک R. کوچک‌شدن استاپ این عدد را بزرگ می‌کند."""
    if not entry or not sl or entry <= 0:
        return None
    stop_pct = abs(entry - sl) / entry * 100
    if stop_pct <= 0:
        return None
    return round(round_trip_pct / stop_pct, 4)


def net_rr(entry, sl, tp, round_trip_pct=FEE_ROUND_TRIP_PCT):
    """RR بعد از کارمزد — عددی که واقعاً به جیب می‌رسد."""
    if not (entry and sl and tp):
        return None
    risk = abs(entry - sl)
    if risk <= 0:
        return None
    f = fee_in_r(entry, sl, round_trip_pct) or 0.0
    return round(abs(tp - entry) / risk - f, 3)


def leverage_cap(entry, sl):
    """سقف اهرم — محافظ لیکویید حاکم مطلق است، اطمینان از آن رد نمی‌شود."""
    if not entry or not sl or entry <= 0:
        return None, "ورود یا استاپ ناموجود"
    stop_pct = abs(entry - sl) / entry * 100
    if stop_pct <= 0:
        return None, "استاپ صفر"
    liq = int(LIQ_GUARD / stop_pct)
    cap = max(1, min(MAX_LEVERAGE, liq))
    return cap, (f"استاپ {round(stop_pct, 3)}٪ → محافظ لیکویید {liq}× · "
                 f"سقف داشبورد {MAX_LEVERAGE}× → مجاز {cap}×")


def confidence(evidence):
    """اطمینان از شواهدِ **موجود**. شاهدِ نبوده سهمش را می‌سوزاند.

    مخرج ثابت ۱ می‌ماند: اگر نصف شواهد نیامده باشد، اطمینان نمی‌تواند از
    ۵۰٪ بالاتر برود. جایگزینِ رایج (نرمال‌کردن روی شواهد موجود) دقیقاً
    همان چیزی است که «یک شاهدِ خوب» را به «اطمینان کامل» ترجمه می‌کند.
    """
    got, missing, parts = 0.0, [], []
    for key, w in EVIDENCE_W.items():
        e = (evidence or {}).get(key)
        v = e.get("v") if isinstance(e, dict) else e
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            missing.append(key)
            continue
        v = max(-1.0, min(1.0, float(v)))
        got += w * (v + 1) / 2                       # [−۱,+۱] → [۰,۱]
        parts.append({"key": key, "v": round(v, 3), "w": w,
                      "why": (e.get("why") if isinstance(e, dict) else None)})
    return round(got, 4), parts, missing


def size_band(conf):
    for lo, share, why in SIZE_BANDS:
        if conf >= lo:
            return share, why
    return 0.0, "اطمینان ناکافی"


def assess(setup, evidence=None, equity=None, open_positions=0,
           round_trip_pct=FEE_ROUND_TRIP_PCT):
    """حکمِ ورود + پول و اهرمِ پیشنهادی. هر رد، دلیلِ خودش را دارد."""
    d = {"symbol": setup.get("symbol") or setup.get("sym"),
         "direction": (setup.get("direction") or setup.get("dir") or "").lower(),
         "entry": setup.get("entry"), "sl": setup.get("sl") or setup.get("stop"),
         "tp": setup.get("tp") or setup.get("tp1") or setup.get("target")}
    reject = []

    # ۱ هندسهٔ کامل
    for k in ("entry", "sl", "tp"):
        v = d[k]
        if not isinstance(v, (int, float)) or isinstance(v, bool) or v <= 0:
            reject.append(f"{k} عددِ مثبت نیست — سیگنال بی‌استاپ/تارگت باطل است (قرارداد اجرا)")
    if d["direction"] not in ("long", "short"):
        reject.append("جهت مشخص نیست (long/short)")

    # ۲ جهت با هندسه بخواند
    if not reject:
        if d["direction"] == "long" and not (d["sl"] < d["entry"] < d["tp"]):
            reject.append("لانگ ولی ترتیب استاپ<ورود<تارگت برقرار نیست — ستاپ خراب است")
        if d["direction"] == "short" and not (d["tp"] < d["entry"] < d["sl"]):
            reject.append("شورت ولی ترتیب تارگت<ورود<استاپ برقرار نیست — ستاپ خراب است")

    fee_r = fee_in_r(d["entry"], d["sl"], round_trip_pct) if not reject else None
    nrr = net_rr(d["entry"], d["sl"], d["tp"], round_trip_pct) if not reject else None
    cap, cap_why = leverage_cap(d["entry"], d["sl"]) if not reject else (None, "هندسه ناقص")

    # ۳ و ۴ کارمزد و RR خالص
    if fee_r is not None and fee_r >= FEE_TRAP_R:
        reject.append(f"کارمزد {fee_r}R از {FEE_TRAP_R}R بالاتر است — دامِ اسکالپ (قانون ۱۶)")
    if nrr is not None and nrr < MIN_NET_RR:
        reject.append(f"RR خالص {nrr} زیر کف {MIN_NET_RR} — سودی که کارمزد بخوردش سود نیست")

    # ۵ سقف پوزیشن هم‌زمان
    if open_positions >= MAX_CONCURRENT:
        reject.append(f"{open_positions} پوزیشن باز — سقف هم‌زمان {MAX_CONCURRENT} (قانون ۱۰)")

    # ۶ اطمینان از شواهد
    conf, parts, missing = confidence(evidence)
    share, share_why = size_band(conf)

    # ۷ سایز از قانون ریسک، نه از اهرم
    notional = margin = None
    lev = None
    if not reject and cap:
        lev = cap                                     # سقفِ مجاز؛ بالاتر رفتن ممنوع
        if isinstance(equity, (int, float)) and equity > 0 and share > 0:
            stop_pct = abs(d["entry"] - d["sl"]) / d["entry"] * 100
            risk_money = equity * (RISK_PCT / 100.0) * share
            notional = round(risk_money / (stop_pct / 100.0), 2)
            margin = round(notional / lev, 2)

    ok = not reject and share > 0
    return {
        **d,
        "verdict": "ENTER" if ok else "NO_ENTRY",
        "why": (f"{share_why} · کارمزد {fee_r}R · RR خالص {nrr}" if ok
                else " · ".join(reject) or share_why),
        "rejects": reject,
        "confidence": conf, "confidence_parts": parts, "missing_evidence": missing,
        "confidence_note": ("مخرج ثابت است: شاهدِ نیامده سهمش را می‌سوزاند و "
                            "اطمینان را پایین می‌آورد، نه این‌که خنثی فرض شود (قانون ۱)"),
        "fee_r": fee_r, "net_rr": nrr,
        "leverage": lev, "leverage_cap": cap, "leverage_why": cap_why,
        "size_share": share, "risk_pct": RISK_PCT,
        "notional_usd": notional, "margin_usd": margin,
        "size_note": ("سایز از قانون ریسک می‌آید نه از اهرم: ضررِ استاپ همیشه "
                      f"{RISK_PCT}٪×سهم می‌ماند و اهرم فقط مارجین را کم می‌کند"),
        "boundary": "پیشنهاد است، نه سفارش. LIVE_EXECUTION خاموش است (قانون ۰۵)؛ "
                    "ورود خودکار فقط با CI بالای صفر و تأیید حمید (قانون ۰۳/۱۲).",
    }


def from_council(engine="risk", setup=None, evidence=None, proposal=None,
                 equity=None, open_positions=0, scores=None, now_ms=None):
    """رأی شورا را به‌عنوان یکی از شواهد وارد می‌کند — نه به‌عنوان دروازه.

    حمید خواست نتیجهٔ رأی ۱۲ متخصص ورودیِ همین تصمیم باشد. ورودی، نه
    وتو: امتیاز شورا فقط سهمِ خودش (۲۵٪) را در اطمینان دارد و هیچ ردی
    را لغو نمی‌کند — دروازه‌های ۱ تا ۵ بالاتر از هر رأیی‌اند.
    """
    ev = dict(evidence or {})
    sess = CN.session(engine, proposal or {"subject": (setup or {}).get("symbol"),
                                           "evidence": {}},
                      scores=scores, now_ms=now_ms)
    if sess.get("ok"):
        ev["council"] = {"v": sess["score"],
                         "why": f"شورا: {sess['decision']} · اکثریت {sess['majority']} "
                                f"({sess['n_for']}–{sess['n_against']}، "
                                f"{sess['n_abstain']} ممتنع)"}
    r = assess(setup or {}, ev, equity=equity, open_positions=open_positions)
    r["council"] = {k: sess.get(k) for k in
                    ("decision", "score", "majority", "n_for", "n_against",
                     "n_abstain", "split_warning")} if sess.get("ok") else None
    return r


def main(argv=None):
    argv = list(argv if argv is not None else sys.argv[1:])
    if "--demo" in argv or not argv:
        r = from_council(
            setup={"symbol": "BTCUSDT", "direction": "long",
                   "entry": 100.0, "sl": 97.0, "tp": 108.0},
            evidence={"structure": {"v": 0.6, "why": "ساختار ۴س هم‌جهت"},
                      "dominance": {"v": 0.3, "why": "USDT.D نزولی"},
                      "memory": {"v": 0.1, "why": "کارنامهٔ نماد خنثی"}},
            proposal={"subject": "BTCUSDT",
                      "evidence": {"trend_4h": {"v": 0.6, "why": "روند ۴س صعودی"},
                                   "risk": {"v": 0.4, "why": "RR ۲.۵"},
                                   "dominance": {"v": 0.3, "why": "USDT.D نزولی"},
                                   "data_quality": {"v": 0.8, "why": "کندل تازه"},
                                   "order_block": {"v": 0.5, "why": "OB تازه زیر ورود"}}},
            equity=1000.0)
        print(f"{r['symbol']} {r['direction']} → {r['verdict']}")
        print(f"  دلیل: {r['why']}")
        print(f"  اطمینان {r['confidence']} (نیامده: {r['missing_evidence'] or '—'})")
        print(f"  اهرم {r['leverage']}× — {r['leverage_why']}")
        print(f"  سهم سایز {r['size_share']} · نامی {r['notional_usd']}$ · "
              f"مارجین {r['margin_usd']}$")
        if r.get("council"):
            print(f"  شورا: {r['council']}")
        return 0
    print("استفاده: python3 -m hamid.risk_desk --demo")
    return 0


if __name__ == "__main__":
    sys.exit(main())
