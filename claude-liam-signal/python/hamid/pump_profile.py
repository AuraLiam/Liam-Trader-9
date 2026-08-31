"""پروفایل پامپ‌های گذشته + مقایسهٔ نامزدها — روش پیشنهادی خود حمید (۳۱ اوت).

«بهترین راه حل این است که هفته‌های گذشته را ببینی که ارزهایی که پامپ
داشتند دقیقاً چه خصوصیاتی داشتند و نکتهٔ مشترکشان چه بود، بعد با این
ارزها یک مقایسه بکنی.»

## داده — همه از دفترهای خودمان، صفر حدس

- `brain/pump-history.json` — رویدادهای پامپ ۴ساعتهٔ ثبت‌شده (ret، vol_z)
- `brain/coins/<SYM>.json` — پروندهٔ تاریخی هر ارز (حرکت، حجم، بازگشت،
  هم‌حرکتی با BTC)
- دفتر بستهٔ پیپر — کارنامهٔ معاملاتی خودمان روی همان نماد (خالص، با
  کارمزد منبع‌واحد)
- `signals/watchlist.json` — گشت چند-صرافی همین الان (رتبهٔ گینر)
- `signals/btc-sensitivity.json` — کلاس هم‌حرکتی با BTC
- `signals/latest.json` — وضعیت ساختاری اسکن فعلی

## دو سنجهٔ کلیدی که «نکتهٔ مشترک» را عددی می‌کنند

۱. **چسبندگی پامپ (repeat)**: از رویدادهای هفته‌های گذشته می‌شماریم —
   احتمال پامپ در هفتهٔ بعد برای ارزی که این هفته پامپ کرده، در برابر
   ارزی که نکرده. اگر این نسبت بالا باشد، «پامپِ اخیر» بهترین پیش‌بین
   پامپِ بعدی است؛ اگر نه، دنبال‌کردن پامپ‌های قبلی توهم است.
۲. **بازگشت (retrace)**: میانهٔ درصدِ پس‌دادنِ حرکت — چند درصدِ پامپ
   پس گرفته می‌شود. این تعیین می‌کند «ارزش ریسک» یعنی چه: پامپی که
   ۸۰٪ پس داده می‌شود فقط با ورود منضبط (پولبک، نه تعقیب) ارزش دارد.

## مرز — این تحلیل شاهد است، نه سیگنال

خروجی این فایل هیچ سیگنالی صادر نمی‌کند و هیچ دروازه‌ای را دور نمی‌زند.
پامپِ محتمل ≠ ورودِ معتبر؛ ورود فقط از مسیر ستاپ ساختاری + همان
دروازه‌های همیشگی (قانون ۰۷: موفقیتِ توصیفیِ پامپ ≠ ورود قابل‌معامله).

اجرا: `python3 -m hamid.pump_profile PUMP DASH NEAR ...` (بی‌آرگومان:
فهرست ۳۱ اوت حمید)
"""
import json
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent
WEEK = 7 * 86_400_000

DEFAULT = ["PUMP", "DASH", "NEAR", "AAVE", "ZEC", "LIT", "ETHFI", "LINK",
           "SUI", "HYPE", "LDO"]


def _j(rel, default=None):
    try:
        return json.loads((ROOT / rel).read_text(encoding="utf-8"))
    except Exception:                                # noqa: BLE001
        return default


def pump_events(weeks=6, now_ms=None):
    """رویدادهای پامپ ثبت‌شدهٔ N هفتهٔ اخیر، از دفتر تاریخچهٔ پامپ."""
    now = now_ms or int(time.time() * 1000)
    d = _j("brain/pump-history.json", {}) or {}
    out = []
    for sym, rec in (d.get("symbols") or {}).items():
        for e in rec.get("events") or []:
            if now - (e.get("t") or 0) <= weeks * WEEK:
                out.append({"sym": sym, **e})
    return out


def repeat_stat(events, now_ms=None):
    """چسبندگی پامپ: P(پامپ هفتهٔ بعد | پامپ این هفته) در برابر پایه.

    شمارش روی جفت‌های (نماد، هفته) — هر جفت یک مشاهده؛ هفتهٔ آخرِ ناقص
    کنار گذاشته می‌شود چون «هفتهٔ بعد»ش هنوز تمام نشده."""
    now = now_ms or int(time.time() * 1000)
    by = {}
    for e in events:
        wk = (now - e["t"]) // WEEK          # 0 = هفتهٔ جاری
        by.setdefault(e["sym"], set()).add(int(wk))
    weeks_seen = sorted({w for s in by.values() for w in s} | {0})
    max_wk = max(weeks_seen) if weeks_seen else 0
    a = b = c = d = 0                        # a: پامپ→پامپ · b: پامپ→هیچ
    syms = set(by)
    for sym in syms:
        wks = by[sym]
        for w in range(1, max_wk + 1):       # w=هفتهٔ قبل، w-1=هفتهٔ بعدش
            prev, nxt = (w in wks), ((w - 1) in wks)
            if prev and nxt:
                a += 1
            elif prev:
                b += 1
            elif nxt:
                c += 1
            else:
                d += 1
    p_after = a / (a + b) if a + b else None
    p_base = (a + c) / (a + b + c + d) if a + b + c + d else None
    return {"p_repeat": p_after, "p_base": p_base,
            "n_repeat": a + b, "n_all": a + b + c + d}


def profile(events):
    """خصوصیات مشترک پامپ‌های ثبت‌شده — فقط شمارش."""
    if not events:
        return {"n": 0}
    vz = [e["vol_z"] for e in events if e.get("vol_z") is not None]
    rets = [e["ret_4h_pct"] for e in events if e.get("ret_4h_pct") is not None]
    per_sym = {}
    for e in events:
        per_sym.setdefault(e["sym"], []).append(e)
    return {"n": len(events), "symbols": len(per_sym),
            "vol_z_median": round(statistics.median(vz), 1) if vz else None,
            "ret4h_median": round(statistics.median(rets), 1) if rets else None,
            "multi_pumpers": sum(1 for v in per_sym.values() if len(v) >= 2),
            "repeat": repeat_stat(events)}


def career(sym_usdt):
    """کارنامهٔ معاملاتی خودمان روی این نماد — خالصِ منبع‌واحد."""
    from hamid.direction_autopsy import load
    rows = [r for r in load("sig-") + load("vetoed") + load("practice")
            if r["sym"] == sym_usdt]
    if not rows:
        return {"n": 0}
    xs = [r["R_net"] for r in rows]
    return {"n": len(xs), "net_mean": round(statistics.mean(xs), 3),
            "win": round(100 * sum(1 for r in rows if r["R"] > 0) / len(rows))}


def candidate(sym, events, wl_rows, sens, latest):
    s = sym.upper().replace("USDT", "")
    su = s + "USDT"
    ev = sorted((e for e in events if e["sym"] == su), key=lambda e: e["t"])
    coin = _j(f"brain/coins/{su}.json", {}) or {}
    summ = coin.get("summary") or {}
    wl = next((r for r in wl_rows if r.get("sym") == su), None)
    sc = (sens.get("coins") or {}).get(su) or {}
    row = next((r for r in latest if r.get("sym") == su), None)
    out = {
        "sym": su,
        "pumps_6w": len(ev),
        "last_pump_days": round((time.time() * 1000 - ev[-1]["t"]) / 86_400_000, 1) if ev else None,
        "pump_volz_med": round(statistics.median([e["vol_z"] for e in ev]), 1) if ev else None,
        "retrace_med": summ.get("median_retrace_pct"),
        "solo_pct": summ.get("solo_pct"),
        # پوشش‌نداشتن «نمی‌دانم» است، نه «مستقل» (قانون ۲۹ اوت)
        "btc_class": (sc or {}).get("cls") or (sc or {}).get("class")
                     or "UNKNOWN (پوشش ندارد)",
        "scout_now": {"score": wl.get("score"), "chg24": wl.get("chg24_med"),
                      "tags": (wl.get("tags") or [])[:2]} if wl else None,
        "scan_now": ({"stage": row.get("stage"), "dir": row.get("dir"),
                      "quality": row.get("quality"),
                      "strategy": row.get("strategy")} if row
                     else "در اسکن فعلی ستاپ ندارد"),
        "career": career(su),
    }
    return out


def main(argv=()):
    syms = [a for a in argv if not a.startswith("-")] or DEFAULT
    events = pump_events()
    prof = profile(events)
    print("### پروفایل پامپ‌های ۶ هفتهٔ اخیر (دفتر تاریخچهٔ پامپ)")
    print(f"  {prof['n']} رویداد از {prof['symbols']} نماد · "
          f"میانهٔ حجم {prof['vol_z_median']}× نرمال · "
          f"میانهٔ حرکت ۴س {prof['ret4h_median']}٪")
    rp = prof["repeat"]
    if rp["p_repeat"] is not None and rp["p_base"] is not None:
        lift = rp["p_repeat"] / rp["p_base"] if rp["p_base"] else None
        print(f"  چسبندگی: P(پامپ هفتهٔ بعد | پامپ این هفته) = "
              f"{rp['p_repeat']:.0%} در برابر پایهٔ {rp['p_base']:.0%} "
              f"(×{lift:.1f}) · n={rp['n_repeat']}/{rp['n_all']}")
    print(f"  چندباره‌پامپ‌ها: {prof['multi_pumpers']} از {prof['symbols']} نماد\n")

    wl_rows = (_j("signals/watchlist.json", {}) or {}).get("rows") or []
    sens = _j("signals/btc-sensitivity.json", {}) or {}
    latest = ((_j("signals/latest.json", {}) or {}).get("setups")
              or (_j("signals/latest.json", {}) or {}).get("rows") or [])

    print("### نامزدها")
    out = []
    for s in syms:
        c = candidate(s, events, wl_rows, sens, latest)
        out.append(c)
        car = c["career"]
        print(f"— {c['sym']}")
        print(f"    پامپ ۶ هفته: {c['pumps_6w']}"
              + (f" (آخری {c['last_pump_days']} روز پیش، حجم {c['pump_volz_med']}×)"
                 if c["pumps_6w"] else "")
              + f" · بازگشت میانه: {c['retrace_med']}٪"
              + f" · حرکت مستقل: {c['solo_pct']}٪ · کلاس BTC: {c['btc_class']}")
        print(f"    گشت الان: {c['scout_now']} · اسکن الان: {c['scan_now']}")
        print(f"    کارنامهٔ خودمان: n={car.get('n', 0)}"
              + (f" برد {car.get('win')}٪ خالص {car.get('net_mean')}R"
                 if car.get("n") else " — معامله‌ای نداشتیم"))
    print("\n### مرز صادقانه")
    print("  این شاهد است نه سیگنال: پامپِ محتمل ≠ ورود معتبر (قانون ۰۷).")
    print("  ورود فقط از مسیر ستاپ ساختاری + دروازه‌های همیشگی.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
