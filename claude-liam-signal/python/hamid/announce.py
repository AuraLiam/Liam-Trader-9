"""دفترِ «اعلام‌شده» — هر نتیجه دقیقاً یک بار ریپلای می‌گیرد (۸ سپتامبر).

خواستِ حمید از ۲۶ اوت: «نتیجه (استاپ/تارگت/تریل/منقضی) ریپلای همان پیام
سیگنال است.» تا امروز اعلان فقط «تسویه‌های همین اجرا» را می‌دید
(`closed >= t_mark` در `cycle.settle_books`). دو عیبِ یک کلاس، هر دو
اندازه‌گیری‌شده در ممیزی E25 (پنجرهٔ ۱۶.۶ ساعت):

  · تسویه‌ای که رانرِ زنجیرهٔ دیگر انجام داد هرگز ریپلای نگرفت
    (۸ از ۱۵ تسویهٔ دارای شناسهٔ پیام).
  · دو رانرِ هم‌پوشان یک معامله را جدا بستند و **دو بار** اعلام کردند
    (۴ مورد: ASTER، SNDKB، GIGGLE، SOXLB).

یعنی «هر نتیجه ریپلای همان پیام» فقط ~۴۷٪ اجرا می‌شد. علت، نه حادثه:
ملاکِ اعلام «چه کسی بست» بود، در حالی که باید «به این پیام قبلاً جواب
داده شده یا نه» باشد.

هویتِ اعلام = (شناسهٔ پیام تلگرام، نتیجه). چند ردیفِ دفتر می‌توانند یک
شناسه را داشته باشند (alarm + sig-alarm، بازوهای آینهٔ تریل که `why` را
کپی می‌کنند) — همه یک پیام‌اند و یک ریپلای می‌گیرند؛ ردیفِ `sig-*` مقدم
است چون همان چیزی است که برای حمید رفت.

دفتر append-only است (`brain/telegram/announced.jsonl`)؛ ادغامش اجتماع
بر هویتِ معامله است (قاعدهٔ فراگیرِ `brain/*.jsonl`). فقط تسویه‌های بعد
از `ANNOUNCE_FROM` نامزدند، وگرنه اولین اجرا هر چه را پیش از وجودِ این
دفتر اعلام شده بود دوباره می‌فرستاد.

مرز صادقانه: دو رانر که در یک دقیقه یک تسویهٔ اعلام‌نشده را ببینند هنوز
می‌توانند هر دو بفرستند — دفتر بعد از push دیده می‌شود. پنجره از «هر
هم‌پوشانی» به «همان دقیقه» کوچک شد؛ صفر نشد. رفعِ صفر، یک نویسندهٔ
تحویل است (قانون ۰۵) که با استقرار سرویس محلی می‌آید.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LEDGER = ROOT / "brain" / "telegram" / "announced.jsonl"

# لحظهٔ استقرار دفتر — تسویهٔ پیش از آن با مسیرِ قدیمی اعلام شده (یا نشده)
# و دیگر دست نمی‌خورد. عددِ ثابت روی خودِ فایل، همان قراردادِ
# `msg_budget.EFFECTIVE_FROM`.
ANNOUNCE_FROM = 1788827000000          # 2026-09-08 00:23 UTC
LOOKBACK_H = 48
OUTCOMES = ("target", "stop", "trail", "expired")


def _not_signal():
    try:
        from hamid.paper import _NOT_SIGNAL
        return tuple(_NOT_SIGNAL)
    except Exception:                                # noqa: BLE001
        return ("first", "inducement", "practice", "vetoed", "gate-vetoed",
                "stage-vetoed", "v2", "scalp", "shock")


def key(t):
    """(شناسهٔ پیام، نتیجه) — یا None اگر ردیف اصلاً پیامی نداشته."""
    mid = (t.get("why") or {}).get("tg_msg_id")
    if not mid or not t.get("outcome"):
        return None
    return (int(mid), str(t["outcome"]))


def done_keys(path=None):
    p = Path(path) if path else LEDGER
    out = set()
    if not p.exists():
        return out
    for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            r = json.loads(ln)
        except Exception:                            # noqa: BLE001
            continue
        if r.get("mid") and r.get("outcome"):
            out.add((int(r["mid"]), str(r["outcome"])))
    return out


def pending(closed_rows, outcomes=OUTCOMES, now_ms=None, path=None,
            since_ms=None, lookback_h=LOOKBACK_H):
    """تسویه‌های سیگنال‌گرید که هنوز ریپلای نگرفته‌اند — یکی بر پیام.

    ترتیب: قدیمی‌ترین بسته اول، تا اگر سقفِ هر اجرا خورد، اجرای بعد
    ادامه دهد نه این‌که تازه‌ها همیشه جلو بزنند.
    """
    now = int(now_ms or time.time() * 1000)
    lo = max(int(ANNOUNCE_FROM if since_ms is None else since_ms),
             now - int(lookback_h * 3_600_000))
    done = done_keys(path)
    skip = _not_signal()
    best = {}
    for t in closed_rows:
        k = key(t)
        if k is None or k in done or k[1] not in outcomes:
            continue
        closed = t.get("closed")
        if not isinstance(closed, (int, float)) or closed < lo:
            continue
        stage = str((t.get("why") or {}).get("stage") or "")
        if stage in skip or stage.startswith("exp-"):
            continue
        cur = best.get(k)
        if cur is None or (stage.startswith("sig-")
                           and not str((cur.get("why") or {}).get("stage") or
                                       "").startswith("sig-")):
            best[k] = t
    return sorted(best.values(), key=lambda t: t.get("closed") or 0)


def mark(t, via, path=None, now_ms=None):
    """بعد از ارسالِ **موفق** — هرگز پیش از آن (وگرنه ریپلایِ شکست‌خورده
    برای همیشه «اعلام‌شده» می‌ماند)."""
    k = key(t)
    if k is None:
        return False
    p = Path(path) if path else LEDGER
    try:
        import brain
        if brain.blocked(p):
            return False
    except Exception:                                # noqa: BLE001
        pass
    row = {"at": int(now_ms or time.time() * 1000), "mid": k[0],
           "outcome": k[1], "sym": t.get("sym"), "dir": t.get("dir"),
           "entry": t.get("entry"), "opened": t.get("opened"),
           "closed": t.get("closed"), "R": t.get("R"), "via": via,
           "stage": (t.get("why") or {}).get("stage")}
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return True
