"""ارسال آپدیت تحلیل به موتور ۱ دقیقه — دهانهٔ ایجنت به سمت موتور.

دستور حمید (۲۴ اوت): «با آن در ارتباط باشی که بتوانی آپدیت‌های تحلیل‌ها
را بهش بدی.»

این طرفِ **فرستنده** است؛ طرفِ گیرنده `hamid/scalp1m.analysis_for` است.
پیام از خط امنِ موجود می‌رود: HMAC-SHA256، `seq` صعودی، انقضا، فهرست
سفید (`liam9_link`). بدون کلید در محیط، هیچ‌چیز فرستاده نمی‌شود — و این
نبودِ کلید یعنی **رد**، نه عبور.

## چرا فقط می‌تواند سخت‌گیرتر کند

من (ایجنت) بستر می‌بینم، خبر می‌خوانم، و گاهی چیزی می‌فهمم که موتور
نمی‌بیند. ولی خروجی من شاهد است، نه واقعیت (قانون ۰۱ بند ۱۱). اگر
می‌توانستم اطمینان را بالا ببرم، عملاً یک مسیرِ دورزنندهٔ دروازه‌ها
ساخته بودم: هر ستاپی که موتور ردش می‌کند با یک پیامِ من قبول می‌شد.

پس دو اهرم بیشتر ندارم، هر دو محافظه‌کارانه:

    avoid=True            این نماد را فعلاً معامله نکن
    confidence_delta<0    اطمینانش را این‌قدر پایین بیاور (سقف −۴۰)

`confidence_delta` مثبت در دو لایه بریده می‌شود (این‌جا و در
`liam9_link.apply`) و آزمونش هر دو را می‌سنجد.

اجرا:
    python3 -m hamid.analysis_push BTCUSDT --note "خبر SEC، نوسان بالا" \\
        --confidence -20
    python3 -m hamid.analysis_push ETHUSDT --avoid --note "OB مصرف شد"
"""
import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
if str(PY) not in sys.path:
    sys.path.insert(0, str(PY))
ROOT = HERE.parents[2]

import liam9_link as LINK                            # noqa: E402

STORE = ROOT / "signals" / "analysis-updates.json"
MAX_KEEP = 100
MAX_DELTA = -40.0


def clamp(delta):
    """فقط منفی. مثبت = صفر، نه خطا — تا یک اشتباهِ تایپی سیگنال نسازد."""
    try:
        d = float(delta)
    except (TypeError, ValueError):
        return 0.0
    return max(MAX_DELTA, min(0.0, d))


def build(sym, note="", avoid=False, confidence_delta=0.0, now_ms=None):
    return {"sym": str(sym).upper()[:20], "note": str(note)[:400],
            "avoid": bool(avoid),
            "confidence_delta": clamp(confidence_delta),
            "at": int(now_ms or time.time() * 1000)}


def store(update, path=None, max_keep=MAX_KEEP):
    """نگه‌داری محلی برای موتور. تازه‌ترینِ هر نماد را موتور می‌خواند."""
    p = Path(path) if path else STORE
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        doc = {}
    ups = [u for u in (doc.get("updates") or []) if isinstance(u, dict)]
    ups.append(update)
    doc = {"panel": "لیام تریدر ۹", "updates": ups[-max_keep:],
           "note": ("آپدیت تحلیلِ مشورتیِ ایجنت. فقط محدودکننده است: "
                    "هیچ ردیفی نمی‌تواند دروازه‌ای را باز کند یا "
                    "اطمینان را بالا ببرد.")}
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=1),
                 encoding="utf-8")
    return doc


def push(sym, note="", avoid=False, confidence_delta=0.0, quiet=False,
         path=None, sign=True):
    """→ (update, signed_or_None). نبودِ کلید = فقط ذخیرهٔ محلی، بی‌صدا نه."""
    up = build(sym, note, avoid, confidence_delta)
    store(up, path=path)
    cmd = None
    if sign:
        try:
            cmd = LINK.make_command("analysis", LINK.next_seq(), **up)
            LINK.push_command(cmd)
        except Exception as e:                        # noqa: BLE001
            if not quiet:
                print(f"خط امن نرفت ({type(e).__name__}: {e}) — آپدیت فقط "
                      "محلی ذخیره شد. کلید LIAM9_LINK_SECRET لازم است.")
            cmd = None
    if not quiet:
        print(f"آپدیت تحلیل → {up['sym']}: "
              + ("پرهیز" if up["avoid"] else f"اطمینان {up['confidence_delta']:+}")
              + (f" · {up['note']}" if up["note"] else "")
              + (" · امضا شد" if cmd else " · بدون امضا (محلی)"))
    return up, cmd


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("sym")
    ap.add_argument("--note", default="")
    ap.add_argument("--avoid", action="store_true")
    ap.add_argument("--confidence", type=float, default=0.0,
                    help="فقط منفی؛ مثبت به صفر بریده می‌شود")
    a = ap.parse_args()
    push(a.sym, a.note, a.avoid, a.confidence)
