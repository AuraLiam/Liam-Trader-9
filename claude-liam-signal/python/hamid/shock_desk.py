#!/usr/bin/env python3
"""میز شوک — اجرای قانون تازهٔ حمید روی بازار، با دفتر پیپر جدا.

هر نوبت:
  ۱. بیت‌کوین را روی هر پنج تایم برای شوک می‌گردد (قانون: «هر تایم‌فریمی»).
  ۲. اگر شوکی بود، روی نمادهای برتر دنبال ستاپ می‌گردد — اردر بلاکِ ایمپالس
     با اهرم ۵–۶، یا شکار پامپ با اهرم ۱۵ و تأیید حجمی ۱۰۰٪.
  ۳. نتیجهٔ هر معامله را با کندل‌های بعدی می‌بندد و در دفتر `stage="shock"`
     می‌نشاند — جدا از سیگنال‌گرید، پس روی وتوها اثر ندارد.
  ۴. هر چیزی که دید و هر دلیلی که رد کرد، روی خط زندهٔ امن گزارش می‌دهد.

قانون تازه ردپای قابل‌سنجش دارد: سشن، حالت (شکار/دنبال‌رو)، اهرم، امتیاز
حجمی و تازگی OB روی هر ردیف ثبت می‌شوند، پس ماشین بونفرونی شبانه می‌تواند
بگوید کدامش واقعاً کار کرده.
"""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import liam9_shock as SH                                     # noqa: E402
import liam9_link as LINK                                    # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
STATE = ROOT / "brain" / "paper" / "shock-state.json"
OUT = ROOT / "signals" / "shock.json"
HOLD_BARS = SH.P["max_hold_bars"]
TF_SCAN = ["5m", "15m", "1h"]        # تایم‌های اجرا؛ شوک ۱د/۴س فقط بستر است


def simulate(cd, i, sig):
    """نتیجه با کندل‌های بعدی — بدترین حالت درون‌کندلی: استاپ اول."""
    entry, sl0, tp1 = sig["entry"], sig["sl"], sig["tp1"]
    long = sig["action"] == "LONG"
    risk = abs(entry - sl0)
    sl = sl0
    trail_at = sig["trail"]["step1_at"]
    pad = entry * (1.0015 if long else 0.9985)
    for k in cd[i + 1: i + 1 + HOLD_BARS]:
        if (long and k["l"] <= sl) or (not long and k["h"] >= sl):
            r = ((sl - entry) if long else (entry - sl)) / risk
            return ("trail" if abs(sl - sl0) > 1e-12 else "stop"), r
        if (long and k["h"] >= tp1) or (not long and k["l"] <= tp1):
            return "target", (abs(tp1 - entry) / risk)
        if (long and k["h"] >= trail_at) or (not long and k["l"] <= trail_at):
            sl = pad if long else pad
    last = cd[min(i + HOLD_BARS, len(cd) - 1)]["c"]
    return "timeout", ((last - entry) if long else (entry - last)) / risk


def replay_symbol(sym, cd, tf, after_ms=0, cap=3):
    """ریپلی رو به جلو روی کندل‌های تازه — بدون نگاه به آینده."""
    rows, i = [], 80
    limit = len(cd) - HOLD_BARS - 2
    while i < limit and len(rows) < cap:
        now = cd[i]["t"]
        if now <= after_ms:
            i += 1
            continue
        sig = SH.decide(sym, cd[:i + 1], tf)
        if sig["action"] == "NO_SIGNAL":
            i += 1
            continue
        outcome, r = simulate(cd, i, sig)
        fee = sig["fee_r"]
        rows.append({
            "sym": sym, "dir": sig["action"], "entry": sig["entry"],
            "sl": sig["sl"], "tp1": sig["tp1"], "tp2": None,
            "opened": now, "filled": now,
            "closed": min(now + HOLD_BARS * SH.TF_MS[tf],
                          int(time.time() * 1000)),
            "outcome": outcome, "R": round(r, 3), "fee_r": fee,
            "R_net": round(r - fee, 3), "tf": tf,
            "why": {"stage": "shock", "replay": 1, "tf": tf,
                    "dir": sig["action"], "mode": sig["mode"],
                    "lev": sig["leverage"], "stop_pct": sig["stop_pct"],
                    "vol_score": sig["volume_score"],
                    "vol_full": sig["volume_full"],
                    "shock_tf": sig["shock"]["tf"],
                    "shock_pct": sig["shock"]["move_pct"],
                    "shock_atr": sig["shock"]["atr_mult"],
                    "ob_age": (sig.get("ob") or {}).get("age_bars"),
                    "pnl_pct_lev": round((r - fee) * sig["stop_pct"]
                                         * sig["leverage"], 2)}})
        i += HOLD_BARS
    frontier = cd[limit - 1]["t"] if limit > 0 else after_ms
    return rows, max(frontier, after_ms)


def run(symbols=None, quiet=False, link=None):
    from hamid import paper
    import sources

    lk = link or LINK.Link(role="shock-desk", remote=True)
    cmds = lk.pull()
    if cmds:
        lk.apply(cmds, params=SH.P)
    if lk.paused:
        lk.event("PAUSED", {"note": "با فرمان امضاشده متوقف شده"})
        if not quiet:
            print("میز شوک با فرمان متوقف است")
        return 0

    if symbols is None:
        from hamid.trainer import top_symbols
        symbols = top_symbols(60)

    def fetch(sym, tf, n):
        try:
            rows = sources.klines(sym, tf, n)
        except Exception:                                # noqa: BLE001
            return None
        return [{"t": k[0], "o": k[1], "h": k[2], "l": k[3], "c": k[4],
                 "v": k[5]} for k in (rows or [])]

    btc = {}
    for tf in SH.TFS:
        cd = fetch("BTCUSDT", tf, 200)
        if not cd:
            continue
        s = SH.detect_shock(cd, tf)
        if s:
            s["volume"] = SH.volume_confirmation(cd, s)
            btc[tf] = s
    lk.heartbeat({"btc_shocks": {tf: {"dir": s["dir"], "pct": s["move_pct"],
                                      "vol": s["vol_mult"]}
                                 for tf, s in btc.items()},
                  "symbols": len(symbols)})

    try:
        st = json.loads(STATE.read_text())
    except Exception:                                    # noqa: BLE001
        st = {}
    total, live = 0, []
    for sym in symbols:
        for tf in TF_SCAN:
            cd = fetch(sym, tf, 200)
            if not cd or len(cd) < 120:
                continue
            key = f"{sym}|{tf}"
            rows, frontier = replay_symbol(sym, cd, tf, st.get(key, 0))
            for r in rows:
                paper._append(paper.CLOSED, r)
            st[key] = frontier
            total += len(rows)
            now_sig = SH.decide(sym, cd, tf, btc_shock=btc.get(tf))
            if now_sig["action"] != "NO_SIGNAL":
                live.append({k: now_sig[k] for k in
                             ("symbol", "tf", "action", "mode", "entry", "sl",
                              "tp1", "leverage", "stop_pct", "volume_score")})
                lk.event("SIGNAL", now_sig)
            elif now_sig.get("state") == "WAITING_OB":
                lk.event("WAITING_OB", {"symbol": sym, "tf": tf,
                                        "why": now_sig["why"]})

    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st))

    closed = [t for t in paper._read(paper.CLOSED)
              if (t.get("why") or {}).get("stage") == "shock"]
    by_mode = {}
    for t in closed:
        m = (t.get("why") or {}).get("mode") or "?"
        b = by_mode.setdefault(m, {"n": 0, "wins": 0, "sum_r": 0.0})
        b["n"] += 1
        b["wins"] += 1 if (t.get("R") or 0) > 0 else 0
        b["sum_r"] = round(b["sum_r"] + (t.get("R_net") or 0), 2)

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({
        "generated": int(time.time() * 1000), "panel": "لیام تریدر ۹",
        "engine": SH.P["version"],
        "note": ("قانون شوک حمید — اهرم ۵–۶ روی اردر بلاک، اهرم ۱۵ فقط با "
                 "تأیید حجمی ۱۰۰٪. پیپر؛ تا CI بالای صفر نشود پول واقعی نه."),
        "btc_shocks": btc, "live_setups": live,
        "book": {"n": len(closed), "by_mode": by_mode},
        "recent": closed[-15:],
    }, ensure_ascii=False))
    lk.event("CYCLE_DONE", {"new_trades": total, "book": len(closed),
                            "live": len(live)})
    if not quiet:
        print(f"میز شوک: {len(btc)} شوک بیت‌کوین، {total} معاملهٔ تازه، "
              f"{len(live)} ستاپ زنده، دفتر {len(closed)}")
    return total


if __name__ == "__main__":
    run()
