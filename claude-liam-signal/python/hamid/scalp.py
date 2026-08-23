"""میز اسکلپ — IBS+پولبک‌پلاس روی تایم ۱ دقیقه (دستور حمید، ۱۸ اوت).

پیپرمود حرفه‌ای مثل بقیهٔ دفترها: دفتر جدا (stage=scalp — قانون ۹)،
ریپلی بدون look-ahead روی کندل واقعی ۱ دقیقه، قانون تریل، کارمزد، و
ثبت کامل زمینه برای ماشین بونفرونی.

ویژه‌های تایم ۱ دقیقه (دستور حمید):
  · **سشن معاملاتی** هر ورود ثبت می‌شود (asia/london/ny/overlap) — در
    تایم پایین سشن‌ها مهم‌اند.
  · **بدنه و شدوی کندل‌های قبلی**: بدنهٔ قاطع هم‌جهت (≥۶۰٪ رنج) و
    سوییپ-شدو (ویکِ کندل قبل زیر کف اخیر و کلوز برگشته) تأییدند.
  · **اهرم ۴۵ تا ۹۰ (فقط پیپر — دستور صریح حمید ۱۸ اوت)**: پایه ۴۵؛
    هر تأیید (بدنهٔ قاطع، سوییپ-شدو، سشن پرنقد) +۱۵ تا سقف ۹۰.
    محافظ لیکویید: فاصلهٔ استاپ باید < نصفِ فاصلهٔ لیکویید (100/lev) باشد.
  · تایم ۳۰ ثانیه: موتور تایم‌فریم-مستقل است؛ منابع REST عمومی کندل ۳۰s
    نمی‌دهند — با اتصال WebSocket سرویس محلی (قانون ۰۲) همین کد اجرا
    می‌شود؛ عدد ۳۰ثانیه جعل نمی‌شود.

    python3 -m hamid.scalp                 # ریپلی + عکس‌فوری پنل
"""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

ROOT = HERE.parent.parent.parent
STATE = ROOT / "brain" / "paper" / "scalp-state.json"
OUT = ROOT / "signals" / "scalp.json"

N_1M = 900                 # ~۱۵ ساعت تاریخ ۱ دقیقه در هر نوبت
CAP_PER_SYMBOL = 25
FEE_RT_PCT = 0.15          # رفت‌وبرگشت + لغزش — در ۱ دقیقه حاکمِ بازی است
IBS_LONG, IBS_SHORT = 0.30, 0.70
RR_TARGET = 1.5            # اسکلپ: تارگت نزدیک، خروج سریع
HOLD_BARS = 45             # حداکثر نگهداری ~۴۵ دقیقه
# قانون اهرم واحد (دستور حمید، ۲۳ اوت): ۱۵ + ۲۴×اطمینان، بازهٔ ۱۵–۳۹ —
# از منبع حقیقت (liam9_strategy) خوانده می‌شود تا دو عددِ واگرا نسازیم.
# باند پیپر ۴۵–۹۰ (۱۸ اوت) نسخ شد؛ اطمینانِ این میز = سهم تأییدها از ۳
# (بدنهٔ قاطع، سوییپ-شدو، سشن هم‌پوشان).
import liam9_strategy as _ST
LEV_BASE, LEV_MAX = _ST.LEV_MIN, _ST.LEV_MAX_CONF
_N_CONFIRM = 3


def session_of(ms):
    h = time.gmtime(ms / 1000).tm_hour
    if 12 <= h < 16:
        return "overlap"       # هم‌پوشانی لندن/نیویورک — پرنقدترین
    if 7 <= h < 16:
        return "london"
    if 12 <= h < 21:
        return "ny"
    return "asia"


def _ibs(k):
    r = k["h"] - k["l"]
    return (k["c"] - k["l"]) / r if r > 0 else 0.5


def candle_feats(win, direction):
    """تأییدهای کندل‌های قبلی: بدنهٔ قاطع هم‌جهت + سوییپ-شدو."""
    long = direction == "LONG"
    prev = win[-2]
    rng = prev["h"] - prev["l"]
    body = prev["c"] - prev["o"]
    decisive = rng > 0 and abs(body) / rng >= 0.6 and (body > 0) == long
    lows = [k["l"] for k in win[-12:-2]]
    his = [k["h"] for k in win[-12:-2]]
    if long:
        sweep = bool(lows) and prev["l"] < min(lows) and prev["c"] > min(lows)
    else:
        sweep = bool(his) and prev["h"] > max(his) and prev["c"] < max(his)
    return decisive, sweep


def decide(win, now_ms=None):
    """تصمیم اسکلپ روی پنجرهٔ ۱ دقیقه (آخرین کندل = لحظهٔ تصمیم)."""
    if len(win) < 80:
        return None
    closes = [k["c"] for k in win]
    e21 = sum(closes[-21:]) / 21
    e55 = sum(closes[-55:]) / 55
    px = closes[-1]
    if e21 > e55 and px > e55:
        direction = "LONG"
    elif e21 < e55 and px < e55:
        direction = "SHORT"
    else:
        return None
    i = _ibs(win[-1])
    if direction == "LONG" and i > IBS_LONG:
        return None
    if direction == "SHORT" and i < IBS_SHORT:
        return None
    # پولبک: فاصله از اکسترمم اخیر در جهت روند
    if direction == "LONG":
        hi = max(k["h"] for k in win[-30:])
        lo = min(k["l"] for k in win[-8:])
        if hi <= lo or (hi - px) / (hi - lo + 1e-12) < 0.2:
            return None
        sl = lo
        risk = px - sl
    else:
        lo = min(k["l"] for k in win[-30:])
        hi = max(k["h"] for k in win[-8:])
        if hi <= lo or (px - lo) / (hi - lo + 1e-12) < 0.2:
            return None
        sl = hi
        risk = sl - px
    if risk <= 0:
        return None
    stop_pct = risk / px * 100
    fee_r = (FEE_RT_PCT / 100) * px / risk
    if fee_r >= 0.30:
        return None                    # دام اسکالپ: کارمزد بازی را می‌خورد
    decisive, sweep = candle_feats(win, direction)
    sess = session_of(now_ms or win[-1]["t"])
    conf01 = (int(decisive) + int(sweep) + int(sess == "overlap")) / _N_CONFIRM
    lev = LEV_BASE + round((LEV_MAX - LEV_BASE) * conf01)
    # محافظ لیکویید: استاپ باید < نصف فاصلهٔ لیکویید بماند؛ به‌جای رد کردن
    # معامله، اهرم تا حد امن پایین می‌آید (lev < 50/stop_pct). اگر حتی
    # اهرم پایه هم امن نیست، استاپ برای اسکلپ اهرمی زیادی گشاد است — رد.
    lev = min(lev, LEV_MAX, int(50.0 / stop_pct) if stop_pct > 0 else LEV_MAX)
    if lev < LEV_BASE:
        return None
    tp = px + RR_TARGET * risk if direction == "LONG" else px - RR_TARGET * risk
    return {"dir": direction, "entry": px, "sl": sl, "tp1": tp,
            "stop_pct": round(stop_pct, 3), "fee_r": round(fee_r, 3),
            "ibs": round(i, 2), "session": sess, "lev": lev,
            "decisive_prev": decisive, "shadow_sweep": sweep}


def simulate(cd, i, s):
    """نتیجه با قانون تریل (⅓ → سربه‌سرِ کارمزددار) — بدون خوش‌بینی درون‌کندلی."""
    long = s["dir"] == "LONG"
    risk = abs(s["entry"] - s["sl"])
    sl = s["sl"]
    be = s["entry"] * (1 + 0.0015) if long else s["entry"] * (1 - 0.0015)
    third = s["entry"] + risk * RR_TARGET / 3 * (1 if long else -1)
    trailed = False
    for k in cd[i + 1: i + 1 + HOLD_BARS]:
        if (long and k["l"] <= sl) or (not long and k["h"] >= sl):
            return ("trail", (sl - s["entry"]) / risk * (1 if long else -1)) \
                if trailed else ("stop", -1.0)
        if (long and k["h"] >= s["tp1"]) or (not long and k["l"] <= s["tp1"]):
            return ("target", RR_TARGET)
        if not trailed and ((long and k["h"] >= third)
                            or (not long and k["l"] <= third)):
            sl, trailed = be, True
    last = cd[min(i + HOLD_BARS, len(cd) - 1)]["c"]
    return ("timeout", (last - s["entry"]) / risk * (1 if long else -1))


def replay_symbol(sym, cd, after_ms=0, cap=CAP_PER_SYMBOL):
    # کندل‌های انتهایی (HOLD_BARS+2 آخر) آیندهٔ کافی برای شبیه‌سازی ندارند؛
    # مرز فقط تا آخرین کندلِ واقعاً ارزیابی‌شده جلو می‌رود، نه cd[-1] —
    # وگرنه هر اجرا کندل‌های تازه را بدون ارزیابی می‌سوزاند و دفتر یخ می‌زند.
    rows, i = [], 80
    limit = len(cd) - HOLD_BARS - 2
    while i < limit and len(rows) < cap:
        now = cd[i]["t"]
        if now <= after_ms:
            i += 2
            continue
        s = decide(cd[:i + 1], now)
        if not s:
            i += 2
            continue
        outcome, r = simulate(cd, i, s)
        fee = s["fee_r"]
        rows.append({"sym": sym, "dir": s["dir"], "entry": s["entry"],
                     "sl": s["sl"], "tp1": s["tp1"], "tp2": None,
                     "opened": now, "filled": now,
                     "closed": min(now + HOLD_BARS * 60_000,
                                   int(time.time() * 1000)),
                     "outcome": outcome, "R": round(r, 3),
                     "fee_r": fee, "R_net": round(r - fee, 3),
                     "tf": "1m",
                     "why": {"stage": "scalp", "replay": 1, "tf": "1m",
                             "dir": s["dir"], "session": s["session"],
                             "lev": s["lev"], "ibs_1m": s["ibs"],
                             "stop_pct": s["stop_pct"],
                             "decisive_prev": s["decisive_prev"],
                             "shadow_sweep": s["shadow_sweep"],
                             "pnl_pct_lev": round((r - fee) * s["stop_pct"]
                                                  * s["lev"], 2)}})
        i += HOLD_BARS
    if len(rows) >= cap and i < limit:
        frontier = cd[i - 1]["t"] if i > 0 else after_ms
    else:
        frontier = cd[limit - 1]["t"] if limit > 0 else after_ms
    return rows, max(frontier, after_ms)


def run(symbols=None, quiet=False):
    from hamid import paper
    import sources

    if symbols is None:
        from hamid.trainer import top_symbols
        symbols = top_symbols(40)
    try:
        st = json.loads(STATE.read_text())
    except Exception:                                # noqa: BLE001
        st = {}
    total, live = 0, []
    for sym in symbols:
        try:
            rows_k = sources.klines(sym, "1m", N_1M)
        except Exception:                            # noqa: BLE001
            continue
        cd = [{"t": k[0], "o": k[1], "h": k[2], "l": k[3], "c": k[4]}
              for k in (rows_k or [])]
        if len(cd) < 120:
            continue
        rows, frontier = replay_symbol(sym, cd, st.get(sym, 0))
        for r in rows:
            paper._append(paper.CLOSED, r)
        total += len(rows)
        st[sym] = frontier
        s_now = decide(cd)
        if s_now:
            live.append({"sym": sym, **{k: s_now[k] for k in
                         ("dir", "entry", "sl", "tp1", "stop_pct",
                          "session", "lev", "ibs")}})
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st))
    closed = [t for t in paper._read(paper.CLOSED)
              if (t.get("why") or {}).get("stage") == "scalp"]
    by_sess = {}
    for t in closed:
        ss = (t.get("why") or {}).get("session") or "?"
        b = by_sess.setdefault(ss, {"n": 0, "wins": 0, "sum_r": 0.0})
        b["n"] += 1
        b["wins"] += 1 if (t.get("R") or 0) > 0 else 0
        b["sum_r"] = round(b["sum_r"] + (t.get("R_net") or t.get("R") or 0), 2)
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({
        "generated": int(time.time() * 1000),
        "panel": "لیام تریدر ۹", "tf": "1m",
        "note": ("میز اسکلپ — پیپر با اهرم ۴۵–۹۰ (دستور حمید)؛ "
                 "عدد پیپر سقف خوش‌بینانه است، ادعای سود زنده نیست"),
        "book": {"n": len(closed),
                 "wins": sum(1 for t in closed if (t.get("R") or 0) > 0),
                 "mean_r_net": round(sum((t.get("R_net") or 0) for t in closed)
                                     / len(closed), 3) if closed else None,
                 "by_session": by_sess},
        "live_setups": live,
        "recent": [{k: t.get(k) for k in ("sym", "dir", "entry", "outcome",
                                          "R_net", "closed")}
                   | {"lev": (t.get("why") or {}).get("lev"),
                      "session": (t.get("why") or {}).get("session")}
                   for t in sorted(closed, key=lambda x: x.get("closed") or 0,
                                   reverse=True)[:20]],
    }, ensure_ascii=False, indent=1))
    if not quiet:
        print(f"میز اسکلپ: {total} معاملهٔ ریپلی تازه · {len(live)} ستاپ زنده"
              f" · دفتر {len(closed)}")
    return total


if __name__ == "__main__":
    run()
