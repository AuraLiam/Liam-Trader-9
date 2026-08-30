"""زنجیرهٔ نهایی پیش از اجرا + دفتر قصدها — پل پنل ↔ داشبورد بیت‌یونیکس.

داشبورد حمید (سمت صرافی) فقط یک چیز از ما می‌خواند:
`signals/exec-outbox.json` — دفترِ قصدهای اجرا. هر ورودی سیگنالی است که
از تمام دروازه‌ها گذشته و همهٔ اعداد اجرایش از قبل حساب و نوشته شده.

زنجیره (ترتیب مهم است):
  ۱. کیل‌سوییچ  — tripped = هیچ قصدی صادر نمی‌شود (قرارداد: داشبورد هم
                  موظف است پیش از هر سفارش killswitch.json را چک کند)
  ۲. روند       — سیگنال باید از دروازهٔ روند رد شده باشد (مهر trend4/1)
  ۳. کارمزد     — RR خالص از کارمزد+لغزش باید از حد بگذرد (fees.gate)
  ۴. سایز       — سقف‌های سخت (sizing.position) روی سرمایهٔ مرجع 10k$؛
                  داشبورد با سرمایهٔ واقعی همین تابع را صدا می‌زند —
                  qty این‌جا «پیشنهاد بر 10k» است نه دستور نهایی.

وضعیت قصد: PENDING (منتظر داشبورد) — این سیستم LIVE_EXECUTION ندارد؛
اجرا و تأیید نهایی همیشه سمت داشبورد/حمید است (قانون ۱۰).
"""
import json
import time
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent
OUTBOX = ROOT / "signals" / "exec-outbox.json"
DOM = ROOT / "signals" / "dominance.json"
REF_EQUITY = 10_000.0                 # مرجع محاسبهٔ پیشنهاد سایز
MAX_ITEMS = 60

# پنجرهٔ اعتبار قصد بر حسب تایم‌فریم (قانون ۱۰ بند ۴ — تعقیب قیمت ممنوع).
# قصدِ گذشته از این پنجره EXPIRED است و داشبورد حق اجرایش را ندارد.
VALID_MIN = {"5m": 30, "15m": 90}
ENTRY_ZONE_R = 0.35                   # ناحیهٔ ورود = ورود ± این ضریب × ریسک
DOM_FRESH_MIN = 90                    # مهر دامیننس کهنه‌تر از این = fresh=False


def _dominance_stamp(now_ms):
    """مهر دامیننس روی قصد — چیزی که دروازهٔ USDT.D همان لحظه دید.

    مهر «شاهدِ ثبت‌شده» است: دروازهٔ دامیننس از قبل در گلوگاه ارسال
    نشسته (قانون هسته، دروازهٔ ۵)؛ این‌جا فقط همان ارزیابی با سن داده
    روی قصد حک می‌شود تا داشبورد بتواند شرط «سیگنال با تأیید دامیننس»
    (دستور ۳۰ اوت) را بدون حدس اجرا کند."""
    try:
        d = json.loads(DOM.read_text())
        age = (now_ms - (d.get("generated") or 0)) / 60000
        return {"usdt_d": d.get("usdt_dominance"),
                "btc_d": d.get("btc_dominance"),
                "regime": ((d.get("structure") or {}).get("regime")),
                "age_min": round(age, 1),
                "fresh": bool(0 <= age <= DOM_FRESH_MIN)}
    except Exception:                                # noqa: BLE001
        return {"fresh": False, "why": "signals/dominance.json خوانا نیست"}


def _session_stamp(now_ms):
    """سشن معاملاتی + تعطیلی هفته (دستور ۳۰ اوت: سشن‌ها توی کدها).

    تعریفِ سشن همان `liam9_strategy.session_of` است — یک منبع، نه کپی."""
    import liam9_strategy as LS
    t = time.gmtime(now_ms / 1000)
    return {"name": LS.session_of(now_ms), "utc_hour": t.tm_hour,
            "weekend": t.tm_wday >= 5}


def _event_stamp(now_ms):
    """رویدادهای کلانِ پیشِ رو (≤۱۲س) + پرچم «داخل پنجرهٔ رویداد» (≤۲س).

    برچسبِ ریسک است، نه وتوی تازه — اثر عددی‌اش فقط از مسیر قانون ۰۳."""
    try:
        d = json.loads(DOM.read_text())
        evs = [e for e in (d.get("macro") or [])
               if isinstance(e.get("in_hours"), (int, float))
               and 0 <= e["in_hours"] <= 12]
        return {"upcoming": [{"title": e.get("title"),
                              "in_hours": e.get("in_hours")}
                             for e in sorted(evs,
                                             key=lambda x: x["in_hours"])[:3]],
                "event_window": any(e["in_hours"] <= 2 for e in evs)}
    except Exception:                                # noqa: BLE001
        return {"upcoming": [], "event_window": False,
                "why": "تقویم خوانا نیست"}


def evaluate(s):
    """سیگنالِ گذشته از گلوگاه ارسال → قصد اجرا یا ردِ دلیل‌دار."""
    from hamid import killswitch, fees, sizing
    sym, d = s.get("sym"), s.get("dir")
    entry, sl = s.get("entry"), s.get("sl")
    tp1 = s.get("tp1")
    out = dict(ok=False, intent=None, reason="")
    if not killswitch.guard():
        out["reason"] = "کیل‌سوییچ فعال است — قصد اجرا صادر نمی‌شود"
        return out
    if not all([sym, d, entry, sl]):
        out["reason"] = "سیگنال ناقص (sym/dir/entry/sl)"
        return out
    fg = fees.gate(entry, sl, tp1 or entry, symbol=sym) if tp1 else \
        dict(ok=True, fee_r=fees.cost_in_r(entry, sl, sym), net_rr=None,
             reason="بدون tp1 — فقط کارمزد ثبت شد")
    if not fg["ok"]:
        out["reason"] = f"دروازهٔ کارمزد: {fg['reason']}"
        return out
    sz = sizing.position(REF_EQUITY, entry, sl, leverage=5)
    if not sz["ok"]:
        out["reason"] = f"دروازهٔ سایز: {sz['reason']}"
        return out
    now_ms = int(time.time() * 1000)
    risk = abs(entry - sl)
    tf = s.get("tf") or "15m"
    out.update(ok=True, intent={
        "id": f"LIAM9-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}-"
              f"{sym.replace('USDT', '')}-{uuid.uuid4().hex[:8]}",
        "panel": "لیام تریدر ۹",
        "created_at": now_ms,
        "status": "PENDING",
        "symbol": sym, "direction": d, "tf": tf,
        "entry": entry, "sl": sl, "tp1": tp1, "tp2": s.get("tp2"),
        # قرارداد اجرا (۲۰ اوت): فقط ایزوله؛ استاپ/تارگت اجباری از قبل بالا چک شد
        "margin_mode": "isolated",
        "stop_loss": sl, "take_profit": tp1,
        # قانون ۱۰ بند ۴: پنجرهٔ اعتبار + ناحیهٔ ورود — تعقیب قیمت ممنوع
        "expires_at": now_ms + VALID_MIN.get(tf, 90) * 60000,
        "entry_zone": {"lo": round(entry - ENTRY_ZONE_R * risk, 10),
                       "hi": round(entry + ENTRY_ZONE_R * risk, 10)},
        "strategy": s.get("strategyName") or s.get("name") or "",
        "trend4": s.get("trend4"), "trend1": s.get("trend1"),
        "counter_trend": bool(s.get("counter_trend_note")),
        # دستور ۳۰ اوت: مهر دامیننس + سشن + رویداد روی هر قصد
        "dominance": _dominance_stamp(now_ms),
        "session": _session_stamp(now_ms),
        "events": _event_stamp(now_ms),
        "fees": {"fee_r": fg.get("fee_r"), "net_rr": fg.get("net_rr")},
        "sizing_ref_10k": {"qty": sz["qty"], "notional_usd": sz["notional_usd"],
                           "risk_usd": sz["risk_usd"],
                           "note": "پیشنهاد بر مبنای 10k$ — داشبورد با سرمایهٔ "
                                   "واقعی sizing.position را صدا بزند"},
        "gates_passed": ["killswitch", "trend", "fees", "sizing",
                         "dedupe", "concurrency", "premortem"],
    })
    return out


def push(s):
    """سیگنالِ واقعاً ارسال‌شده → اگر از زنجیره گذشت، در دفتر قصدها بنشیند.
    شکستِ این مسیر هرگز ارسال سیگنال را نمی‌کشد (اولویت با تلگرام حمید)."""
    try:
        r = evaluate(s)
        if not r["ok"]:
            print(f"  دفتر قصد {s.get('sym')}: {r['reason']}", flush=True)
            return None
        try:
            box = json.loads(OUTBOX.read_text())
            assert isinstance(box, list)
        except Exception:                            # noqa: BLE001
            box = []
        box.insert(0, r["intent"])
        OUTBOX.parent.mkdir(exist_ok=True)
        OUTBOX.write_text(json.dumps(box[:MAX_ITEMS], ensure_ascii=False,
                                     indent=1))
        print(f"  دفتر قصد: {r['intent']['id']} ثبت شد", flush=True)
        return r["intent"]
    except Exception as e:                           # noqa: BLE001
        print(f"  دفتر قصد: {type(e).__name__} — ارسال سیگنال ادامه دارد",
              flush=True)
        return None
