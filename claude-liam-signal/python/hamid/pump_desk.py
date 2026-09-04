#!/usr/bin/env python3
"""میز پامپ — تاریخچه از روز اول، همراهان، و ضدتکرارِ گزارش (دستور حمید، ۳ سپتامبر).

حمید: «انجین پامپ ارزهایی که پامپ می‌شوند را بلافاصله بررسی کند و
تاریخچهٔ آن ارز را از روز اول بخواند که دقیقاً بداند کِی پامپ شده و چه
چیزی روی پامپش تأثیر گذاشته و چه ارزهایی با آن پامپ شده‌اند و چه
ارزهایی روی پامپش تأثیر داشته‌اند، و تاپ گینرزها را پایش کند و روند
رشدشان را زیر نظر بگیرد و گزارش کاملی از گذشتهٔ آن ارز بدهد. **ولی از
اطلاعات تکراری جلوگیری کند** — تا وقتی آن ارز در صدر تاپ گینرز است
نیازی نیست هر لحظه گزارش پامپ بفرستد.»

## چهار کار این میز

| کار | خروجی | بند |
|---|---|---|
| تاریخچهٔ کامل یک ارز از اولین پامپِ ثبت‌شده | `history()` | H9.1 |
| چه ارزهایی با آن پامپ شدند و چه ارزهایی جلوترش حرکت کردند | `cohort()` | H9.2 |
| پایش تاپ گینرز و روند رشد | `gainers_watch()` | H9.3 |
| ضدتکرارِ گزارش تا وقتی همان ارز در صدر است | `should_report()` | H9.4 |

## چرا ضدتکرار سخت‌تر از «هر ۶ ساعت یک بار» است

پنجرهٔ زمانی تنها کافی نیست: ارزی که ۱۲ ساعت در صدر می‌ماند، با پنجرهٔ
۶ ساعته دو بار گزارش می‌شود و بارِ دوم **هیچ خبر تازه‌ای ندارد**. پس
معیار، تغییرِ داستان است نه گذشتِ زمان:

- از صدر بیرون رفت و دوباره برگشت → خبر تازه است.
- رشدش از آخرین گزارش **معنادار** جابه‌جا شد (پیش‌فرض ۱۵ واحد درصد) →
  خبر تازه است.
- ایمپالسِ تازه‌ای ثبت شد (شمارِ پامپش بالا رفت) → خبر تازه است.
- هیچ‌کدام، و هنوز در صدر است → **سکوت**، با دلیلِ ثبت‌شده.

و یک سقفِ زمانیِ بلند (پیش‌فرض ۱۲ ساعت) تا ارزی که روزها در صدر می‌ماند
یک بار در روز یادآوری شود، نه هیچ‌وقت.

## مرز

این میز **گزارش می‌سازد و تصمیمِ ارسال می‌گیرد**؛ خودش چیزی نمی‌فرستد
و هیچ دروازهٔ سیگنالی را عوض نمی‌کند. کادنس پنج‌نوبتهٔ پامپ (قانون ۰۷)
سر جایش است؛ این ضدتکرار **داخل** همان نوبت‌ها عمل می‌کند، نه به‌جایشان.

    python3 -m hamid.pump_desk --write
"""
import json
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

ROOT = HERE.parents[2]
BRAIN = ROOT / "brain" / "pump-desk"
STATE = BRAIN / "reported.json"
RADAR = ROOT / "signals" / "pump-radar.json"
HISTORY = ROOT / "brain" / "pump-history.json"
OUT = ROOT / "signals" / "pump-desk.json"

ENGINE = "E12"
PANEL = "لیام تریدر ۹"

TOP_N = 5                     # «صدر تاپ گینرز» یعنی این‌قدر ردیف اول
MOVE_PCT = 15.0               # جابه‌جایی معنادار رشد از آخرین گزارش
MAX_SILENCE_H = 12.0          # سقف سکوت — روزها سکوت هم درست نیست
COHORT_H = 24.0               # پنجرهٔ «با هم پامپ شدند»
LEAD_H = 12.0                 # پنجرهٔ «جلوتر حرکت کرد»
TEHRAN_OFFSET_S = 3.5 * 3600


def _j(p, default):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:                                # noqa: BLE001
        return default


def tehran(ms):
    return time.strftime("%Y-%m-%d %H:%M", time.gmtime(ms / 1000 + TEHRAN_OFFSET_S))


# ── H9.1 تاریخچهٔ کامل، از اولین پامپِ ثبت‌شده ──────────────────────────
def history(sym, hist=None, now_ms=None):
    """هرچه از این ارز ثبت شده — نه پنجرهٔ چند هفته‌ای.

    مرز صادقانه: «از روز اول» یعنی از اولین رویدادی که **دفتر ما** دیده،
    نه از روز پیدایش خودِ ارز. اگر دفتر کوتاه است، همان صریح گفته
    می‌شود؛ عددِ نداشته ساخته نمی‌شود (قانون ۱).
    """
    now = int(now_ms if now_ms is not None else time.time() * 1000)
    d = hist if hist is not None else _j(HISTORY, {})
    rec = ((d or {}).get("symbols") or {}).get(sym) or {}
    ev = sorted([e for e in (rec.get("events") or []) if e.get("t")],
                key=lambda e: e["t"])
    if not ev:
        return {"symbol": sym, "n": 0,
                "why": "هیچ پامپی از این ارز در دفتر ما ثبت نشده — «تاریخچه ندارد» "
                       "یعنی دفتر ندیده، نه این‌که رخ نداده"}
    rets = [e["ret_4h_pct"] for e in ev if isinstance(e.get("ret_4h_pct"), (int, float))]
    vz = [e["vol_z"] for e in ev if isinstance(e.get("vol_z"), (int, float))]
    gaps = [round((ev[i]["t"] - ev[i - 1]["t"]) / 86_400_000, 2) for i in range(1, len(ev))]
    hours = [time.gmtime(e["t"] / 1000 + TEHRAN_OFFSET_S).tm_hour for e in ev]
    big = max(ev, key=lambda e: e.get("ret_4h_pct") or 0)
    return {
        "symbol": sym, "n": len(ev),
        "first_t": ev[0]["t"], "first_when": tehran(ev[0]["t"]),
        "last_t": ev[-1]["t"], "last_when": tehran(ev[-1]["t"]),
        "span_days": round((ev[-1]["t"] - ev[0]["t"]) / 86_400_000, 2),
        "since_last_h": round((now - ev[-1]["t"]) / 3_600_000, 2),
        "ret_median_pct": round(statistics.median(rets), 1) if rets else None,
        "ret_max_pct": big.get("ret_4h_pct"),
        "biggest_when": tehran(big["t"]),
        "vol_z_median": round(statistics.median(vz), 1) if vz else None,
        "gap_median_days": round(statistics.median(gaps), 2) if gaps else None,
        "typical_hour_tehran": (max(set(hours), key=hours.count) if hours else None),
        "events": [{"t": e["t"], "when": tehran(e["t"]),
                    "ret_4h_pct": e.get("ret_4h_pct"), "vol_z": e.get("vol_z")}
                   for e in ev[-12:]],
        "boundary": "«از روز اول» یعنی از اولین رویدادِ دفترِ ما، نه پیدایش ارز",
    }


# ── H9.2 همراهان و پیش‌روها ─────────────────────────────────────────────
def cohort(sym, hist=None, cohort_h=COHORT_H, lead_h=LEAD_H):
    """چه ارزهایی با آن پامپ شدند، و چه ارزهایی **قبلش** حرکت کردند.

    شمارش است، نه علیت: «۵ بار از ۹ بار» یعنی همین، نه «باعثش شد».
    """
    d = hist if hist is not None else _j(HISTORY, {})
    syms = (d or {}).get("symbols") or {}
    mine = sorted([e["t"] for e in (syms.get(sym) or {}).get("events") or [] if e.get("t")])
    if not mine:
        return {"symbol": sym, "n_events": 0, "with": [], "before": [],
                "why": "بدون رویدادِ ثبت‌شده، همراه و پیش‌رو معنا ندارد"}
    with_c, before_c = {}, {}
    for other, rec in syms.items():
        if other == sym:
            continue
        for e in rec.get("events") or []:
            t = e.get("t")
            if not t:
                continue
            for m in mine:
                dt_h = (t - m) / 3_600_000
                if abs(dt_h) <= cohort_h:
                    with_c[other] = with_c.get(other, 0) + 1
                if -lead_h <= dt_h < 0:
                    before_c[other] = before_c.get(other, 0) + 1
                    break
    n = len(mine)
    top = lambda c: [{"symbol": k, "times": v, "share_pct": round(100 * v / n, 1)}  # noqa: E731
                     for k, v in sorted(c.items(), key=lambda x: -x[1])[:8]]
    return {"symbol": sym, "n_events": n,
            "with": top(with_c), "before": top(before_c),
            "window_h": {"with": cohort_h, "before": lead_h},
            "boundary": "هم‌زمانی است نه علیت — «چند بار با هم» شمرده می‌شود، "
                        "«باعث شد» ادعا نمی‌شود"}


# ── H9.3 پایش تاپ گینرز ─────────────────────────────────────────────────
def gainers_watch(gainers, top_n=TOP_N):
    """صدرنشین‌ها با سن حضورشان در صدر و روند رشد."""
    rows = []
    for i, g in enumerate(gainers or []):
        sym = g.get("symbol") or g.get("sym")
        if not sym:
            continue
        rows.append({"rank": i + 1, "symbol": sym,
                     "change_pct": g.get("change_pct"),
                     "top_age_h": g.get("top_age_h"),
                     "stale": bool(g.get("stale")),
                     "in_top": i < top_n})
    return rows[:20]


# ── H9.4 ضدتکرار: تا وقتی در صدر است و خبری نیست، سکوت ─────────────────
def _load_state(path=None):
    d = _j(path or STATE, {})
    return d if isinstance(d, dict) else {}


def should_report(sym, change_pct=None, in_top=True, pump_n=None,
                  state=None, now_ms=None, move_pct=MOVE_PCT,
                  max_silence_h=MAX_SILENCE_H):
    """آیا این ارز گزارش تازه لازم دارد؟ تصمیم + دلیلِ صریح."""
    now = int(now_ms if now_ms is not None else time.time() * 1000)
    st = (state or {}).get(sym) or {}
    last_t = st.get("t")
    if not last_t:
        return True, "اولین گزارش این ارز"
    since_h = (now - last_t) / 3_600_000
    if not st.get("in_top") and in_top:
        return True, "از صدر بیرون رفته بود و برگشت — خبرِ تازه است"
    prev = st.get("change_pct")
    if isinstance(prev, (int, float)) and isinstance(change_pct, (int, float)):
        if abs(change_pct - prev) >= move_pct:
            return True, (f"رشد از {prev}٪ به {change_pct}٪ رفت "
                          f"(≥{move_pct} واحد جابه‌جایی) — داستان عوض شد")
    prev_n = st.get("pump_n")
    if isinstance(prev_n, int) and isinstance(pump_n, int) and pump_n > prev_n:
        return True, f"ایمپالس تازه ثبت شد ({prev_n} → {pump_n})"
    if since_h >= max_silence_h:
        return True, f"{round(since_h, 1)} ساعت از آخرین گزارش گذشت — یادآوری دوره‌ای"
    if in_top:
        return False, (f"هنوز در صدر تاپ گینرز است و از {round(since_h, 1)} ساعت پیش "
                       f"خبر تازه‌ای ندارد — گزارش تکراری فرستاده نمی‌شود (دستور حمید)")
    return False, f"از صدر بیرون است و {round(since_h, 1)} ساعت پیش گزارش شد"


def mark_reported(sym, change_pct=None, in_top=True, pump_n=None,
                  state=None, now_ms=None, path=None, save=True):
    """ثبت این‌که گزارش رفت — پایهٔ ضدتکرار بعدی."""
    now = int(now_ms if now_ms is not None else time.time() * 1000)
    st = dict(state if state is not None else _load_state(path))
    st[sym] = {"t": now, "when": tehran(now), "change_pct": change_pct,
               "in_top": bool(in_top), "pump_n": pump_n}
    if save:
        p = Path(path or STATE)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(st, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return st


# ── تابلو ────────────────────────────────────────────────────────────────
def build(radar=None, hist=None, state=None, now_ms=None):
    now = int(now_ms if now_ms is not None else time.time() * 1000)
    r = radar if radar is not None else _j(RADAR, {})
    h = hist if hist is not None else _j(HISTORY, {})
    st = state if state is not None else _load_state()
    watch = gainers_watch((r or {}).get("gainers") or [])
    cards = []
    for g in watch[:TOP_N]:
        sym = g["symbol"]
        hi = history(sym, h, now)
        ok, why = should_report(sym, g.get("change_pct"), g["in_top"],
                                hi.get("n"), st, now)
        cards.append({**g, "history": hi, "cohort": cohort(sym, h),
                      "report_now": ok, "report_why": why})
    return {"generated": now, "engine": ENGINE, "panel": PANEL,
            "watch": watch, "cards": cards,
            "counts": {"watched": len(watch),
                       "due": sum(1 for c in cards if c["report_now"]),
                       "silenced": sum(1 for c in cards if not c["report_now"])},
            "rules": {"top_n": TOP_N, "move_pct": MOVE_PCT,
                      "max_silence_h": MAX_SILENCE_H},
            "boundary": "این میز گزارش می‌سازد و تصمیمِ ارسال می‌گیرد؛ خودش چیزی "
                        "نمی‌فرستد و هیچ دروازهٔ سیگنالی را عوض نمی‌کند. کادنس "
                        "پنج‌نوبتهٔ پامپ (قانون ۰۷) سر جایش است."}


def main(argv=None):
    argv = list(argv if argv is not None else sys.argv[1:])
    b = build()
    if "--write" in argv:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(b, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"میز پامپ نوشته شد: {OUT.relative_to(ROOT)}")
    c = b["counts"]
    print(f"میز پامپ — {c['watched']} صدرنشین · {c['due']} گزارشِ لازم · "
          f"{c['silenced']} ساکت (تکراری)")
    for card in b["cards"]:
        hi = card["history"]
        past = (f"{hi['n']} پامپ از {hi.get('first_when')}" if hi["n"]
                else "بی‌سابقه در دفتر")
        print(f"  {'📣' if card['report_now'] else '🤫'} {card['symbol']} "
              f"({card.get('change_pct')}٪، صدر {card.get('top_age_h')}س) · {past}")
        print(f"      {card['report_why']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
