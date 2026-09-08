"""محافظِ «هر نتیجه دقیقاً یک بار ریپلای می‌گیرد» (۸ سپتامبر).

    python3 -m hamid.test_announce
"""
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
sys.path.insert(0, str(PY))

from hamid import announce as AN                     # noqa: E402

OK = 0
FAIL = []
NOW = AN.ANNOUNCE_FROM + 6 * 3_600_000
H = 3_600_000


def check(name, cond, extra=""):
    global OK
    if cond:
        OK += 1
        print(f"  ✓ {name}")
    else:
        FAIL.append(name)
        print(f"  ✗ {name}")
        if extra:
            print(f"      ↳ {extra}")


def row(mid, outcome="stop", stage="sig-ibs", closed=NOW - H, sym="AAAUSDT",
        entry=1.0, opened=None):
    return {"sym": sym, "dir": "LONG", "entry": entry, "R": -1.0,
            "opened": opened or (closed - H), "closed": closed,
            "outcome": outcome,
            "why": {"stage": stage, "tg_msg_id": mid} if mid else {"stage": stage}}


tmp = Path(tempfile.mkdtemp(prefix="announce-")) / "announced.jsonl"

# ── نامزدها ────────────────────────────────────────────────────────────
rows = [row(1), row(2, "trail"), row(None), row(3, stage="practice"),
        row(4, stage="exp-trail-g80"), row(5, closed=AN.ANNOUNCE_FROM - 1000),
        row(6, "expired")]
p = AN.pending(rows, now_ms=NOW, path=tmp)
mids = sorted(AN.key(t)[0] for t in p)
check("ردیفِ بی‌شناسهٔ پیام نامزد نیست", 0 not in mids and None not in mids)
check("دفترِ داخلی (practice) و بازوی آینه (exp-*) نامزد نیستند",
      3 not in mids and 4 not in mids, str(mids))
check("تسویهٔ پیش از ANNOUNCE_FROM دست نمی‌خورد", 5 not in mids, str(mids))
check("سیگنال‌های واقعی با هر نتیجه نامزدند", mids == [1, 2, 6], str(mids))
check("فیلترِ نتیجه کار می‌کند",
      [AN.key(t)[0] for t in AN.pending(rows, outcomes=("expired",),
                                        now_ms=NOW, path=tmp)] == [6])

# ── دقیقاً یک بار ───────────────────────────────────────────────────────
check("قبل از هر اعلام، دفتر خالی است", AN.done_keys(tmp) == set())
AN.mark(rows[0], "reply", path=tmp, now_ms=NOW)
p2 = AN.pending(rows, now_ms=NOW, path=tmp)
check("بعد از اعلام، همان پیام دیگر نامزد نیست",
      1 not in [AN.key(t)[0] for t in p2])
check("ولی بقیه هستند", sorted(AN.key(t)[0] for t in p2) == [2, 6])

# دو رانرِ هم‌پوشان: رانر B همان دفتر را می‌خواند و چیزی برای اعلام ندارد
for t in p2:
    AN.mark(t, "reply", path=tmp, now_ms=NOW + 1)
check("رانرِ دوم روی همان تسویه‌ها هیچ نامزدی ندارد (دقیقاً یک بار)",
      AN.pending(rows, now_ms=NOW, path=tmp) == [])

# ردیفِ اعلام هویتِ معامله را دارد (برای اجتماعِ ادغام بر trade_key)
last = json.loads(tmp.read_text().splitlines()[-1])
check("ردیفِ دفتر هویتِ معامله (نماد/ورود/opened) و via دارد",
      last.get("sym") and last.get("entry") is not None
      and last.get("opened") and last.get("via") == "reply", str(last))

# ── یک پیام، چند ردیف (alarm + sig-alarm) → یک اعلام، ردیفِ sig مقدم ──
dup = [row(9, stage="alarm", entry=2.0), row(9, stage="sig-alarm", entry=2.0)]
p3 = AN.pending(dup, now_ms=NOW, path=tmp)
check("چند ردیف با یک شناسهٔ پیام = یک نامزد", len(p3) == 1)
check("و نسخهٔ sig-* مقدم است",
      p3 and (p3[0]["why"]["stage"] == "sig-alarm"), str(p3))

# همان پیام با نتیجهٔ دیگر (منطقاً یک معامله یک نتیجه دارد؛ اگر دفتر
# دو نتیجه بدهد، هر کدام جدا شمرده می‌شود — اطلاعات گم نشود)
check("هویت شامل نتیجه است", AN.key(row(1, "stop")) != AN.key(row(1, "trail")))

# ── پنجرهٔ نگاه به عقب ─────────────────────────────────────────────────
old = row(11, closed=NOW - (AN.LOOKBACK_H + 1) * H)
check("تسویهٔ کهنه‌تر از پنجره نامزد نیست",
      AN.pending([old], now_ms=NOW, path=tmp,
                 since_ms=NOW - 100 * H) == [])

# ── ترتیب: قدیمی‌ترین اول ─────────────────────────────────────────────
seq = [row(21, closed=NOW - H), row(22, closed=NOW - 3 * H), row(23, closed=NOW - 2 * H)]
check("قدیمی‌ترین تسویه اول اعلام می‌شود",
      [AN.key(t)[0] for t in AN.pending(seq, now_ms=NOW, path=tmp)] == [22, 23, 21])

# ── سیم‌کشی در چرخه (خاصیت، نه شکل) ───────────────────────────────────
src = (HERE / "cycle.py").read_text(encoding="utf-8")
check("چرخه نامزدهای اعلام را از دفترِ اعلام‌شده می‌گیرد",
      "announce.pending(" in src or "_ann.pending(" in src)
check("و فقط بعد از ارسالِ موفق علامت می‌زند",
      src.count("_ann.mark(") >= 2
      and src.index("record_out(\"outcome\"") < src.index("_ann.mark("))
check("ریپلای انقضا هم دفترِ پنل می‌گیرد (پیام بی‌دفتر ممنوع)",
      "expired" in src[src.index("ورود ممنوع"):src.index("ورود ممنوع") + 2500]
      and src.count("record_out(\"outcome\"") >= 2)
check("ملاکِ «تسویهٔ همین اجرا» دیگر ملاکِ اعلام نیست",
      "exp_just = [t for t in paper._read(paper.CLOSED)" not in src)
check("ANNOUNCE_FROM عددِ ثابت روی فایل است",
      isinstance(AN.ANNOUNCE_FROM, int) and AN.ANNOUNCE_FROM > 1_780_000_000_000)

print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
sys.exit(1 if FAIL else 0)
