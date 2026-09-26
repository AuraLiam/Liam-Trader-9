"""دفترِ هفتگی‌پاره — هیچ دفترِ append-only به سقفِ ۱۰۰ مگابایتیِ گیت‌هاب نمی‌رسد.

## چرا (۲۶ سپتامبر، اندازه‌گیری‌شده)

گیت‌هاب push هر فایلِ بزرگ‌تر از ۱۰۰MB را رد می‌کند (GH001). دفترهای
append-only فقط بزرگ می‌شوند:

| دفتر | اندازه | رشد | تا دیوار |
|---|---|---|---|
| `brain/paper/closed.jsonl` | ۹۱.۷MB | +۴.۲MB/روز | ~۲ روز |
| `brain/guardians/live-votes.jsonl` | ۷۳.۲MB | +۵.۲MB/روز | ~۵ روز |

و همین دیوار از قبل یک ورک‌فلو را کشته بود: `guardian-lab` سه هفتهٔ
پیاپی با GH001 شکست خورد و تابلویش ۲۲ روز کهنه ماند. روزی که `closed.jsonl`
از ۱۰۰ بگذرد، **هر** ناشری که آن را می‌نویسد (چرخه، زنجیرهٔ سیگنال) رد
می‌شود — یعنی کلِ سامانه.

## طرح — چرا هفتگی و نه «وقتی بزرگ شد تغییرِ نام بده»

چند رانر هم‌زمان همین دفترها را منتشر می‌کنند و ناشر آن‌ها را با **اجتماع
بر هویت** ادغام می‌کند. پاره‌کردنِ اندازه‌محور (rename وقتی از X گذشت) در
دو رانرِ هم‌زمان دو تصمیمِ متفاوت می‌سازد و اجتماع، ردیف‌ها را در دو فایل
نگه می‌دارد — همان بادِ تکراری ۲۴ اوت (۷۲.۹٪ دفتر تکراری).

پاره‌کردنِ **تاریخ‌محور** قطعی است: هر رانر برای هر ردیف همان فایل را
انتخاب می‌کند (هفتهٔ ISO از زمانِ خودِ ردیف). پس:

- فایلِ قدیمی (`closed.jsonl`) **یخ می‌زند** — دیگر رشد نمی‌کند، زیر سقف می‌ماند.
- ردیفِ تازه در `closed-2026-W39.jsonl` می‌نشیند (~۳۰MB در هفته، زیر سقف).
- خواننده همه را می‌خواند و بر **هویتِ ردیف** یکتا می‌کند، تا ردیفی که
  رانرِ هنوز-قدیمی به فایلِ یخ‌زده افزوده دوبار شمرده نشود.

هیچ بازنویسی و هیچ ادغامِ متنی نیست (قانون ضد-merge): فایل‌ها کنار هم،
شماره‌دار، append-only.

هویتِ ردیف دوباره پیاده نمی‌شود — `paper.trade_key` تنها تعریف است و
`test_paper_dedupe` هم‌ارزی‌اش را با ناشر می‌سنجد.
"""
from __future__ import annotations

import json
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

LIMIT_BYTES = 100_000_000     # سقفِ سختِ گیت‌هاب برای یک فایل (GH001)
RUNWAY_DAYS = 14              # کمتر از این تا دیوار = چرخه سرخ

# پاره‌کردن فقط برای دفترهایی که گیت منتشرشان می‌کند (سقفِ ۱۰۰MB فقط آن‌جاست).
# دفترِ موقتِ آزمون‌ها (tempfile) مثل قبل روی همان فایل append می‌شود تا
# صدها آزمونِ موجود که فایل را مستقیم می‌خوانند معنایشان عوض نشود.
REPO = Path(__file__).resolve().parents[3]
PUBLISHED = [REPO / "brain", REPO / "signals"]

# دفترهایی که نویسنده‌شان از `append` همین ماژول می‌گذرد: فایلِ پایه‌شان
# یخ‌زده است و رشد نمی‌کند؛ رشد در پاره‌هاست و هر پاره فقط یک هفته می‌گیرد.
FROZEN = {"brain/paper/closed.jsonl", "brain/guardians/live-votes.jsonl",
          "brain/memory/retired.jsonl"}
_PART_RE = __import__("re").compile(r"-\d{4}-W\d{2}\.jsonl$")


def week_tag(ms):
    d = datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isocalendar()
    return f"{d[0]}-W{d[1]:02d}"


def part_for(base, ms=None):
    base = Path(base)
    ms = time.time() * 1000 if ms is None else ms
    return base.with_name(f"{base.stem}-{week_tag(ms)}{base.suffix}")


def parts(base):
    base = Path(base)
    return sorted(base.parent.glob(f"{base.stem}-[0-9][0-9][0-9][0-9]-W[0-9][0-9]{base.suffix}"))


def files(base):
    """فایلِ یخ‌زده (اگر هست) و بعد پاره‌ها به ترتیبِ زمان — قدیمی‌ترین اول."""
    base = Path(base)
    return ([base] if base.exists() else []) + parts(base)


def _lines(p):
    try:
        text = p.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return []
    return text.splitlines()


def _line_key(r):
    return json.dumps(r, sort_keys=True, ensure_ascii=False)


def _key_for(base):
    """هویتِ ردیف بسته به نوعِ دفتر.

    دفتر بسته: `paper.trade_key` — دو تسویهٔ یک معامله متنِ متفاوت دارند
    (closed فرق می‌کند) ولی یک معامله‌اند. هر دفترِ دیگر (رأی‌ها، لاگ‌ها):
    متنِ کاملِ ردیف — `trade_key` روی ردیفِ رأی می‌شود (نماد، None، None،
    None) و همهٔ رأی‌های یک نماد را یکی می‌کرد. تکرارِ واقعی این‌جا یعنی
    همان خطِ عیناً دوباره‌افزوده‌شده.
    """
    if Path(base).name == "closed.jsonl":
        from hamid.paper import trade_key              # تنها تعریفِ هویت معامله
        return trade_key
    return _line_key


def read(base, key="trade", tail=None):
    """همهٔ ردیف‌های دفتر، قدیمی‌ترین اول، یکتا بر هویت.

    key: "trade" (پیش‌فرض — هویتِ مناسبِ همین دفتر، `_key_for`)، یک تابع، یا None.
    tail: فقط n ردیفِ آخر — از تازه‌ترین پاره به عقب، بی‌خواندنِ کلِ تاریخ.
    """
    fs = files(base)
    # تک‌فایل = رفتارِ پیشین دقیقاً (بی‌یکتاسازی)؛ یکتاسازی فقط برای هم‌پوشانیِ
    # فایلِ یخ‌زده و پاره‌هاست — وگرنه جای‌گذاری معنای خواننده را عوض می‌کرد.
    kf = (_key_for(base) if len(fs) > 1 else None) if key == "trade" else key
    if tail is not None:
        picked, need = [], tail
        for p in reversed(fs):
            ls = _lines(p)
            picked = ls[-need:] + picked if need < len(ls) else ls + picked
            need = tail - len(picked)
            if need <= 0:
                break
        lines = picked[-tail:] if tail else []
    else:
        lines = [ln for p in fs for ln in _lines(p)]
    out, seen = [], set()
    for ln in lines:
        if not ln.strip():
            continue
        try:
            r = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if not isinstance(r, dict):
            continue
        if kf is not None:
            try:
                k = kf(r)
                hash(k)
            except Exception:                        # noqa: BLE001 - ردیفِ بی‌هویت می‌ماند
                k = None
            if k is not None:
                if k in seen:
                    continue
                seen.add(k)
        out.append(r)
    return out


def text_lines(base):
    """خطوطِ خامِ همهٔ فایل‌های دفتر — برای خواننده‌هایی که خودشان JSON می‌خوانند.

    برای فایلی که پاره ندارد دقیقاً همان `read_text().splitlines()` است، پس
    جای‌گذاری‌اش در هر خواننده رفتارِ فایل‌های دیگر را عوض نمی‌کند. وقتی پاره
    هست، ردیفِ تکراری (هویتِ یکسان در فایلِ یخ‌زده و پاره) یک بار می‌آید.
    """
    fs = files(base)
    if len(fs) <= 1:
        return _lines(fs[0]) if fs else []
    kf = _key_for(base)
    out, seen = [], set()
    for p in fs:
        for ln in _lines(p):
            try:
                k = kf(json.loads(ln))
                hash(k)
            except Exception:                        # noqa: BLE001
                out.append(ln)
                continue
            if k in seen:
                continue
            seen.add(k)
            out.append(ln)
    return out


@contextmanager
def opened(base):
    """جایگزینِ `open(path)` برای خواننده‌های خط‌به‌خط — همان خطوطِ `text_lines`."""
    yield text_lines(base)


def exists(base):
    return bool(files(base))


def _published(base):
    try:
        b = Path(base).resolve()
    except Exception:                                # noqa: BLE001
        return False
    return any(r.resolve() in b.parents for r in PUBLISHED)


def append(base, row, ts_field="closed"):
    """ردیف به پارهٔ هفتهٔ خودش — هرگز به فایلِ یخ‌زده.

    ts_field: میدانِ زمانِ خودِ ردیف (دفتر بسته: closed؛ رأی‌ها: at). همین
    میدان است که پاره را قطعی می‌کند: دو رانر برای یک ردیف یک فایل را می‌گزینند.
    """
    if not _published(base):
        Path(base).parent.mkdir(parents=True, exist_ok=True)
        with Path(base).open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        return Path(base)
    ms = row.get(ts_field) if isinstance(row, dict) else None
    if not isinstance(ms, (int, float)) or ms < 1e12:
        ms = None
    p = part_for(base, ms)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return p


def runway(root, days=7):
    """هر فایلِ دفترِ زیرِ brain/ و signals/: اندازه، رشدِ روزانه، روز تا سقف.

    رشد از **مهرِ زمانِ خودِ ردیف‌ها** سنجیده می‌شود، نه از تاریخچهٔ git
    (کلونِ کم‌عمق تاریخچه ندارد و همان عدد را دوبار نشان می‌دهد — درسِ همین
    عیب‌یابی). فایلِ بی‌مهرِ زمان با اندازهٔ خودش سنجیده می‌شود.
    """
    root = Path(root)
    now = time.time() * 1000
    keys = ("closed", "at", "ts", "t", "time", "opened", "retired_at", "generated")
    out = []
    for sub in ("brain", "signals"):
        for p in (root / sub).rglob("*.jsonl"):
            size = p.stat().st_size
            if size < 10_000_000:
                continue
            recent = 0
            for ln in _lines(p):
                try:
                    r = json.loads(ln)
                except Exception:                    # noqa: BLE001
                    continue
                if not isinstance(r, dict):
                    continue
                ts = None
                for k in keys:
                    v = r.get(k)
                    if isinstance(v, (int, float)):
                        ts = v if v > 1e12 else (v * 1000 if 1e9 < v < 1e10 else None)
                        if ts:
                            break
                if ts and now - ts < days * 86400e3:
                    recent += len(ln) + 1
            per_day = recent / days
            rel = str(p.relative_to(root))
            kind = "grows"
            if rel in FROZEN:
                kind, left = "frozen", float("inf")        # دیگر append نمی‌گیرد
            elif _PART_RE.search(rel):
                # پارهٔ هفتگی: بدترین حالت = یک هفتهٔ کامل با همین نرخ
                kind = "part"
                left = float("inf") if per_day * 7 < LIMIT_BYTES * 0.8 else 0.0
            else:
                left = (LIMIT_BYTES - size) / per_day if per_day > 0 else float("inf")
            out.append({"path": rel, "mb": round(size / 1e6, 1), "kind": kind,
                        "mb_per_day": round(per_day / 1e6, 2),
                        "days_left": round(left, 1) if left != float("inf") else None})
    return sorted(out, key=lambda r: (r["days_left"] is None, r["days_left"] or 0))
