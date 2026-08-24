"""پاسبان سیو سود — «TRUMP خیلی توی سود بود اما سیو سود نشد اصلاً» (۲۴ اوت).

## شکافی که این فایل می‌بندد

قانون تریل حمید (۱۲ و ۲۱ اوت) در دفتر کاغذی خودکار اجرا می‌شود و همان شب
TRUMP را با +۰.۷۴R بست. ولی روی پوزیشنِ واقعیِ داشبورد، فایل استراتژی
فقط عددهای نردبان را **لحظهٔ سیگنال** چاپ می‌کند و هیچ‌کس **لحظهٔ رسیدنِ
قیمت به پله** را اعلام نمی‌کند — پس حمید وسط کار خبر نمی‌شود و سود
برمی‌گردد.

این پاسبان هر نوبتِ اسکنِ زنده، پوزیشن‌های **پرشدهٔ سیگنالِ ارسالی**
(sig-*) را با قیمتِ لحظه می‌سنجد و به محض عبور از هر پله، **یک بار**
پیام عملی می‌فرستد: «الان استاپ را بیاور به X». سه پله، همان قانون:

    پلهٔ ۱ — ⅓ مسیر تا TP1  → استاپ به سودِ کارمزددار (ورود±۰.۱۵٪)
    پلهٔ ۲ — ⅔ مسیر         → استاپ به سطح ⅓ مسیر
    پلهٔ ۳ — TP1             → ⅓ حجم بسته، استاپِ باقی به ورود+کارمزد

## مرزها

- **اعلام است، نه اجرا.** استاپ را این کد جابه‌جا نمی‌کند —
  LIVE_EXECUTION=false (قانون ۰۵). پیام دقیقاً می‌گوید چه بکن.
- فقط sig-* — سفارشی که واقعاً برای حمید رفته. دفترهای داخلی پیام
  نمی‌سازند (درسِ سیل ۱۲۴پیامی).
- هر پله برای هر معامله **یک بار** (state خودش) و بعد هم از دروازهٔ
  آلارم رد می‌شود — دو قفل، نه یکی.
- قیمتِ گیرنیامده = آن پوزیشن رد می‌شود و شمرده می‌شود؛ عدد ساخته
  نمی‌شود (قانون ۱).

اجرا:  python3 -m hamid.trail_alert            (گزارش)
       python3 -m hamid.trail_alert --alert    (+ تلگرام)
"""
import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE.parent) not in sys.path:
    sys.path.insert(0, str(HERE.parent))
ROOT = HERE.parents[2]
OPEN = ROOT / "brain" / "paper" / "open.jsonl"
STATE = ROOT / "brain" / "trail-state.json"
OUT = ROOT / "signals" / "trail-alert.json"

FEE_BUF_PCT = 0.15          # همان بافر کارمزد دو سر قانون تریل
MAX_PRICE_FETCH = 30        # سقف پوزیشن در هر نوبت — پاسبان نباید اسکن را کند کند


def rungs(entry, tp1, direction):
    """سه پلهٔ قانون تریل + دستورِ هر پله. → [(سطحِ ماشه، استاپِ جدید، متن)]"""
    d = 1 if direction == "LONG" else -1
    dist = (tp1 - entry) * d
    if dist <= 0:
        return []
    fee = entry * FEE_BUF_PCT / 100
    third = entry + d * dist / 3
    return [
        (third,
         entry + d * fee,
         "⅓ مسیر تارگت رد شد — استاپ را بیاور به سودِ کارمزددار"),
        (entry + d * 2 * dist / 3,
         third,
         "⅔ مسیر رد شد — استاپ را بیاور به سطحِ ⅓ مسیر"),
        (tp1,
         entry + d * fee,
         "TP1 زده شد — ⅓ حجم را ببند؛ استاپِ باقی‌مانده به ورود+کارمزد"),
    ]


def crossed(price, level, direction):
    return price >= level if direction == "LONG" else price <= level


def trade_id(p):
    return f"{p.get('sym')}|{p.get('opened')}|{p.get('entry')}"


def _load_state(path=None):
    p = Path(path) if path else STATE
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_state(state, path=None):
    p = Path(path) if path else STATE
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, ensure_ascii=False, indent=1),
                 encoding="utf-8")


def open_signal_positions(path=None):
    """پوزیشن‌های پرشدهٔ سیگنالِ ارسالی — یکتا بر هویت معامله."""
    p = Path(path) if path else OPEN
    if not p.exists():
        return []
    out, seen = [], set()
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not r.get("filled"):
            continue
        if not str((r.get("why") or {}).get("stage", "")).startswith("sig-"):
            continue
        if None in (r.get("entry"), r.get("tp1")) or r.get("dir") not in ("LONG", "SHORT"):
            continue
        k = trade_id(r)
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out


def default_price(sym):
    """آخرین کلوزِ بستهٔ ۱ دقیقه. شکست = None، نه حدس."""
    try:
        import sources
        kl = sources.klines(sym, "1m", 3)
        if len(kl) >= 2:
            return float(kl[-2][4])                  # کندلِ بسته، نه باز
        return float(kl[-1][4]) if kl else None
    except Exception:                                # noqa: BLE001
        return None


def run(alert=False, quiet=False, open_path=None, state_path=None,
        price_fn=None, now_ms=None):
    price_of = price_fn or default_price
    state = _load_state(state_path)
    positions = open_signal_positions(open_path)[:MAX_PRICE_FETCH]
    fired, skipped_price = [], 0

    for p in positions:
        px = price_of(p["sym"])
        if px is None:
            skipped_price += 1
            continue
        tid = trade_id(p)
        done_rung = int(state.get(tid, 0))
        for i, (level, new_sl, msg) in enumerate(rungs(p["entry"], p["tp1"],
                                                       p["dir"]), start=1):
            if i <= done_rung or not crossed(px, level, p["dir"]):
                continue
            state[tid] = i
            done_rung = i
            base = p["sym"].replace("USDT", "")
            text = (f"🪜 لیام تریدر ۹ — سیو سود {base} {p['dir']}\n"
                    f"{msg}\n"
                    f"استاپ جدید: <code>{new_sl:.10g}</code>\n"
                    f"قیمت الان <code>{px:.10g}</code> · ورود "
                    f"<code>{p['entry']:.10g}</code> · TP1 "
                    f"<code>{p['tp1']:.10g}</code>\n"
                    f"<i>جابه‌جایی استاپ با داشبورد/خودت است — این فقط "
                    f"اعلامِ لحظه است.</i>")
            rec = {"sym": p["sym"], "dir": p["dir"], "rung": i,
                   "price": px, "new_sl": round(new_sl, 10), "text": msg}
            fired.append(rec)
            if alert:
                # قفل دوم: دروازهٔ آلارم. کلید شامل معامله+پله است، پس
                # «تازه» فقط یک بار — state بالا قفل اول است.
                from hamid import alert_gate
                alert_gate.send("trail_alert", f"{tid}|r{i}", text)
            if not quiet:
                print(f"🪜 {base} {p['dir']} پلهٔ {i}: {msg} → استاپ {new_sl:.10g}")

    # نگه‌داری state: معامله‌ای که دیگر باز نیست از قفل پاک می‌شود
    live = {trade_id(p) for p in positions}
    state = {k: v for k, v in state.items() if k in live}
    _save_state(state, state_path)

    res = {"at": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
           "open_signal_positions": len(positions),
           "price_unavailable": skipped_price,
           "alerts": fired,
           "note": ("اعلامِ پله‌های قانون تریل روی سیگنال‌های ارسالی — "
                    "اجرا نیست (قانون ۰۵).")}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    if not quiet and not fired:
        print(f"سیو سود: {len(positions)} پوزیشن سیگنال زیر نظر — "
              f"هیچ پله‌ای تازه رد نشده"
              + (f" · {skipped_price} بی‌قیمت" if skipped_price else ""))
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--alert", action="store_true")
    run(alert=ap.parse_args().alert)
