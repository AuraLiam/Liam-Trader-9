#!/usr/bin/env python3
"""پل اسکلپ → داشبورد: سیگنال مناسب اسکلپ را فوری به سفارش فیوچرز تبدیل کن.

دستور حمید (۱۹ اوت): «مرتب با داشبورد در ارتباط باش... اگر سیگنالی دیدی
برای اسکلپ مناسب است، سریع دستور بده به داشبورد که آن پوزیشن فیوچرز را
اجرا کند. و داشبورد جوری باشد که برای فیوچرز طراحی شده باشد فقط.»

مسیر: میز اسکلپ ۱د و میز شوک ستاپ زنده می‌سازند → این‌جا دروازهٔ
«مناسبِ اسکلپ» را می‌گذرانند → فرمان امضاشدهٔ `open_position` (فقط
futures) در دفتر پایین-رو می‌نشیند → داشبورد آن را می‌خواند و اجرا می‌کند.

دروازهٔ «مناسب اسکلپ» — هر شرط دلیل دارد، نه سلیقه:
  ۱. تازگی: ستاپ زیر ۳ دقیقه سن داشته باشد (اسکلپِ کهنه = ورود بد)
  ۲. کارمزد: fee_r < ۰.۳۰ — اندازه‌گیری‌شده که استاپ تنگ‌تر از ~۰.۵٪
     کارمزد را روی R سوار می‌کند
  ۳. کیفیت ≥ ۶۵ و سشن london/ny/overlap — دفتر اسکلپ نشان داد آسیا
     بدترین است (n=۲۱، ‎−۰.۳۰۹R)
  ۴. اهرم داخل محافظ لیکویید و سقف داشبورد
  ۵. ضدتکرار: هر نماد هر ۱۵ دقیقه فقط یک سفارش
  ۶. سقف باز: بیش از N سفارش فعال هم‌زمان نه (هم‌سو با سقف ۵ پوزیشن)

⚠️ mode پیش‌فرض **demo** است. پول واقعی فقط وقتی که خودِ حمید روی ماشین
داشبورد `LIAM9_ALLOW_LIVE=1` بگذارد — این فایل هرگز آن را روشن نمی‌کند.
"""
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import liam9_link as LINK                                    # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
STATE = ROOT / "brain" / "paper" / "exec-state.json"
OUT = ROOT / "signals" / "scalp-exec.json"

GATES = {
    "max_age_s": 180,          # ستاپ تازه؛ اسکلپ کهنه بی‌ارزش است
    "max_fee_r": 0.30,
    "min_quality": 65,
    "sessions": ("london", "ny", "overlap"),
    "cooldown_s": 900,         # یک سفارش در ۱۵ دقیقه برای هر نماد
    "max_open": 3,             # زیر سقف ۵ پوزیشن داشبورد
    "equity_default": 1000.0,
}


def _load(path, default):
    try:
        return json.loads(Path(path).read_text())
    except Exception:                                        # noqa: BLE001
        return default


def scalp_ready(setup, now_ms=None):
    """آیا این ستاپ «مناسب اسکلپ» است؟ خروجی: (bool، دلیل)."""
    now = now_ms or int(time.time() * 1000)
    age_s = (now - (setup.get("t") or now)) / 1000
    if age_s > GATES["max_age_s"]:
        return False, f"کهنه است ({age_s:.0f} ثانیه)"
    fee_r = setup.get("fee_r")
    if fee_r is not None and fee_r >= GATES["max_fee_r"]:
        return False, f"دام کارمزد (fee_r={fee_r})"
    q = setup.get("quality")
    if q is not None and q < GATES["min_quality"]:
        return False, f"کیفیت {q} زیر کف {GATES['min_quality']}"
    ses = setup.get("session")
    if ses and ses not in GATES["sessions"]:
        return False, f"سشن {ses} برای اسکلپ انتخاب نشده (دفتر: آسیا ضعیف)"
    lev, stop = setup.get("leverage"), setup.get("stop_pct")
    if not lev or not stop:
        return False, "اهرم یا استاپ ناموجود"
    if lev > min(LINK.EXEC_MAX_LEVERAGE, int(LINK.EXEC_LIQ_GUARD / stop)):
        return False, "اهرم از محافظ لیکویید/سقف داشبورد رد می‌کند"
    return True, "مناسب اسکلپ"


def notional_for(equity, stop_pct, risk_pct=2.0):
    """سایز از قانون ریسک، با سقف سخت کانال."""
    n = (equity * risk_pct / 100.0) / (stop_pct / 100.0)
    return min(n, LINK.EXEC_MAX_NOTIONAL_USD)


def collect_setups():
    """ستاپ‌های زندهٔ هر دو میز، با برچسب منبع."""
    out = []
    for path, src in ((ROOT / "signals" / "scalp.json", "scalp"),
                      (ROOT / "signals" / "shock.json", "shock")):
        d = _load(path, {})
        gen = d.get("generated") or 0
        for s in (d.get("live_setups") or []):
            s = dict(s)
            s.setdefault("t", gen)
            s["source"] = src
            s.setdefault("action", s.get("dir") or s.get("action"))
            out.append(s)
    return out


def run(equity=None, mode="demo", quiet=False, link=None, now_ms=None):
    lk = link or LINK.Link(role="scalp-exec", remote=True)
    # سکوت ممنوع: نبودِ کلید یعنی هیچ سفارشی نمی‌رود. این باید فریاد بزند،
    # نه این‌که بی‌صدا صفر برگرداند — درس ۱۹ اوت (شش ساعت هیچ‌کس نفهمید).
    if not os.environ.get("LIAM9_LINK_SECRET"):
        lk.event("EXEC_BLOCKED", {"why": "کلید LIAM9_LINK_SECRET تنظیم نیست — "
                                         "هیچ سفارشی به داشبورد نمی‌رود",
                                  "action": "سکرت را در گیت‌هاب و روی ماشین "
                                            "داشبورد بگذار"})
        if not quiet:
            print("⛔ کلید LIAM9_LINK_SECRET نیست — سفارشی فرستاده نمی‌شود")
    st = _load(STATE, {"last": {}, "open": []})
    now = now_ms or int(time.time() * 1000)
    eq = equity or GATES["equity_default"]

    st["open"] = [o for o in st.get("open", [])
                  if now - o.get("t", 0) < 3600_000]
    sent, skipped = [], []
    for s in collect_setups():
        sym = s.get("symbol") or s.get("sym")
        side = s.get("action") or s.get("dir")
        if not sym or side not in ("LONG", "SHORT"):
            continue
        ok, why = scalp_ready(s, now)
        if not ok:
            skipped.append({"symbol": sym, "why": why})
            continue
        last = st["last"].get(sym, 0)
        if now - last < GATES["cooldown_s"] * 1000:
            skipped.append({"symbol": sym, "why": "ضدتکرار ۱۵ دقیقه"})
            continue
        if len(st["open"]) >= GATES["max_open"]:
            skipped.append({"symbol": sym, "why": "سقف سفارش باز پر است"})
            continue
        try:
            cmd = LINK.make_exec_command(
                LINK.next_seq(), sym, side, s["entry"], s["sl"], s.get("tp1"),
                s["stop_pct"], s["leverage"],
                notional_for(eq, s["stop_pct"]), mode=mode,
                source=s.get("source"), tf=s.get("tf"),
                quality=s.get("quality"), session=s.get("session"))
        except ValueError as e:                              # noqa: BLE001
            skipped.append({"symbol": sym, "why": str(e)})
            continue
        if "sig" not in cmd:
            skipped.append({"symbol": sym,
                            "why": "کلید LIAM9_LINK_SECRET نیست — "
                                   "سفارش بدون امضا فرستاده نمی‌شود"})
            continue
        LINK.push_command(cmd)
        st["last"][sym] = now
        st["open"].append({"symbol": sym, "t": now})
        sent.append(cmd["order"])
        lk.event("EXEC_SENT", cmd["order"])

    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "generated": now, "panel": "لیام تریدر ۹", "mode": mode,
        "note": ("پل اسکلپ→داشبورد؛ فقط فیوچرز. mode=demo مگر حمید روی "
                 "ماشین داشبورد LIAM9_ALLOW_LIVE=1 گذاشته باشد."),
        "gates": GATES, "sent": sent, "skipped": skipped[:30],
    }, ensure_ascii=False))
    if not quiet:
        print(f"پل اسکلپ: {len(sent)} سفارش فرستاده شد، "
              f"{len(skipped)} ستاپ رد شد")
        for o in sent:
            print(f"  → {o['symbol']} {o['side']} اهرم {o['leverage']}× "
                  f"نوشنال {o['notional_usd']}$ ({o['mode']})")
    return len(sent)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--equity", type=float, default=None)
    ap.add_argument("--mode", default="demo", choices=("demo", "live"))
    a = ap.parse_args()
    run(equity=a.equity, mode=a.mode)
