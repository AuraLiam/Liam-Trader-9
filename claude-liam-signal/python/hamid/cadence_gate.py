#!/usr/bin/env python3
"""دروازهٔ کادنس — «این گزارش دوره‌ای، الان حق رفتن دارد؟»

## چرا این فایل هست (شکایت حمید، ۷ سپتامبر: «روزانه بارها پیام می‌آید»)

گزارش ساعتی دامیننس ضدتکرارِ ۵۰دقیقه‌ای داشت و باز روزی ۳۳ تا ۴۲ بار
می‌رفت. اندازه‌گیری روی دفترِ خودِ محصول (`signals/archive/
telegram-feed-*.jsonl`، از ۱ سپتامبر، n=۲۰۶): در ۵۹ ساعت از ۱۳۶ ساعت
**۲ پیام یا بیشتر** رفت، یکی ۴ تا، و کمینهٔ فاصله ۳۰ **ثانیه** بود.

علت، آستانه نبود؛ **حافظه** بود. نشانگرِ ضدتکرار یک فایل جهش‌پذیر در
`signals/` بود و دو تولیدکنندهٔ هم‌زمان داشت (ورک‌فلوی ساعتی + زنجیرهٔ
پیوسته). هر اجرا چک‌اوتِ کم‌عمقِ تازه دارد؛ اجرایی که چند دقیقه قبل
شروع شده نشانگرِ تازه را نمی‌بیند، و هر تلاشِ ناموفقِ push هم نشانگر را
به نسخهٔ origin برمی‌گرداند. یعنی «۵۰ دقیقه» عملاً یعنی «۵۰ دقیقه، اگر
گیت به‌موقع رسیده باشد».

**این دقیقاً همان کلاسِ عیبِ PAXG×۵ است** (۲۶ اوت): حافظهٔ ضدتکرار
وابسته به push. آن‌جا برای سیگنال با حافظهٔ سه‌منبعی رفع شد و همان‌جا
ماند؛ گزارش‌های دوره‌ای هرگز آن رفع را نگرفتند. طبق «قانون رفع قطعی»
بند ۲، تکرارِ یک کلاس یعنی شکستِ محافظِ قبلی — پس درمان این‌بار
**مشترک** است، نه دوباره داخل همان ماژول.

## سه منبع (بیشینه برنده است)

۱. **نشانگرِ خودِ ماژول** (اختیاری) — همان فایل قبلی، دست‌نخورده.
۲. **کنارگذاشتهٔ `/tmp`** — از push مستقل است؛ دو اجرا روی یک رانر و
   تلاش‌های پیاپیِ push را می‌گیرد.
۳. **دفترِ append-only فید** — منبعِ حقیقتِ محصول. ناشر مشترک این
   پرونده‌ها را «اجتماع» می‌کند (قانون ۱۴)، پس ردیفِ رفته با reset
   گم نمی‌شود.

هیچ‌کدام به‌تنهایی کافی نیست؛ **بیشینهٔ هر سه** ملاک است. منبعی که
خطا بدهد نادیده گرفته می‌شود، نه اینکه دروازه را باز کند — سکوتِ ناشی
از فایلِ خراب بهتر از سیلِ پیام است، ولی برعکسش فاجعه است.

## مرز

فقط برای گزارش‌های **دوره‌ای**. سیگنال محصول است و همان لحظه می‌رود
(دستور حمید: «هیچ تأخیری در ارسال سیگنال»)؛ آلارم‌ها دروازهٔ خودشان را
دارند (`alert_gate`). محافظ `test_cadence_gate` مطمئن می‌شود مسیر
سیگنال از این‌جا رد نشود.
"""
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
ROOT = HERE.parents[2]
FEED = ROOT / "signals" / "telegram-feed.json"
ARCHIVE = ROOT / "signals" / "archive"
SIDECAR = Path(os.environ.get("LIAM9_CADENCE_SIDECAR",
                              "/tmp/liam9-cadence.json"))

# کادنسِ اعلام‌شدهٔ هر گزارش دوره‌ای — منبع واحد، تا سند و کد از هم جدا
# نیفتند. فاصلهٔ کمینه کمی زیر خودِ دوره است تا لرزشِ زمان‌بند یک نوبت را
# نیندازد (۵۵ دقیقه برای ساعتی، نه ۶۰).
MIN_GAP_MIN = {
    "dom_report": 55,      # ساعتی (قانون ۱۱)
    "pump_report": 240,    # پنج نوبت در روز (قانون ۰۷)
    "work_report": 300,    # سه نوبت در روز (قانون ۱۱)
}


def _from_sidecar(kind):
    try:
        return int((json.loads(SIDECAR.read_text()) or {}).get(kind) or 0)
    except Exception:                                # noqa: BLE001
        return 0


def _from_marker(marker_path, field="last_sent"):
    if not marker_path:
        return 0
    try:
        return int((json.loads(Path(marker_path).read_text())
                    or {}).get(field) or 0)
    except Exception:                                # noqa: BLE001
        return 0


def _from_feed(kind, now_ms=None):
    """آخرین ردیفِ همین نوع در دفترِ محصول.

    امروز و دیروزِ UTC خوانده می‌شود (کافی است: بلندترین کادنسِ جدول ۵
    ساعت است) به‌اضافهٔ حلقهٔ زندهٔ `telegram-feed.json` که ممکن است
    تازه‌تر از آرشیوِ چک‌اوت‌شده باشد.
    """
    now = now_ms or int(time.time() * 1000)
    best = 0
    for delta in (0, 86400_000):
        day = time.strftime("%Y%m%d", time.gmtime((now - delta) / 1000))
        f = ARCHIVE / f"telegram-feed-{day}.jsonl"
        if not f.exists():
            continue
        try:
            for ln in f.read_text(encoding="utf-8").splitlines():
                ln = ln.strip()
                if not ln or f'"{kind}"' not in ln:
                    continue
                r = json.loads(ln)
                if r.get("kind") == kind:
                    best = max(best, int(r.get("at") or 0))
        except Exception:                            # noqa: BLE001
            continue
    try:
        for r in (json.loads(FEED.read_text()).get("rows") or []):
            if r.get("kind") == kind:
                best = max(best, int(r.get("at") or 0))
    except Exception:                                # noqa: BLE001
        pass
    return best


def last_sent_ms(kind, marker_path=None, now_ms=None):
    """بیشینهٔ سه منبع. صفر یعنی «هیچ ردی نیست»."""
    return max(_from_marker(marker_path), _from_sidecar(kind),
               _from_feed(kind, now_ms=now_ms))


def allow(kind, min_gap_min=None, marker_path=None, now_ms=None):
    """→ (send: bool, reason: str, age_min: float|None).

    reason ∈ never/aged/too-soon. `age_min=None` یعنی هرگز نرفته.
    """
    gap = MIN_GAP_MIN.get(kind) if min_gap_min is None else min_gap_min
    if gap is None:
        raise KeyError(f"cadence_gate: کادنسِ «{kind}» اعلام نشده")
    now = now_ms or int(time.time() * 1000)
    last = last_sent_ms(kind, marker_path=marker_path, now_ms=now)
    if not last:
        return True, "never", None
    age = (now - last) / 60000.0
    if age >= gap:
        return True, "aged", age
    return False, "too-soon", age


def mark(kind, now_ms=None):
    """مهرِ ارسال روی کنارگذاشته. ردیفِ دفتر را `telegram.record_out`
    خودش می‌زند؛ این‌جا دوباره نوشته نمی‌شود (قانون ۰۵: یک نویسنده)."""
    now = now_ms or int(time.time() * 1000)
    try:
        cur = json.loads(SIDECAR.read_text()) if SIDECAR.exists() else {}
        if not isinstance(cur, dict):
            cur = {}
    except Exception:                                # noqa: BLE001
        cur = {}
    cur[kind] = now
    try:
        SIDECAR.write_text(json.dumps(cur, ensure_ascii=False))
    except Exception:                                # noqa: BLE001
        pass
    return now


def main(argv):
    kind = argv[1] if len(argv) > 1 else "dom_report"
    ok, why, age = allow(kind)
    a = "—" if age is None else f"{age:.1f} دقیقه"
    print(f"{kind}: {'می‌رود' if ok else 'نمی‌رود'} ({why}) · از آخرین: {a}"
          f" · سقف: {MIN_GAP_MIN.get(kind)} دقیقه")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
