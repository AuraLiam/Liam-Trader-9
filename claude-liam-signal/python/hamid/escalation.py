"""ماشین آستانه و ارجاع خودکار — دستور حمید، ۲۵ اوت.

«می‌خواهم یک حد برای هر قسمت بگذاری که تا به کف یا سقف آن حد از نوسانات
یا اشتباهات رسید، سریع به قسمت‌های بالاتر اتوماتیک اطلاع بدهند و بررسی
بشود و مشکل برطرف بشود.»

هر چرخه دفتر بستهٔ سیگنال (پنجرهٔ اخیر) خوانده می‌شود و سه حدِ
پیش‌ثبت‌شده سنجیده می‌شوند. رد شدن از حد = «ارجاع» (escalation):
یک دستور کار مکتوب با معامله‌های شاهد در signals/escalation.json
می‌نشیند، اتاق‌های مسئول نام برده می‌شوند، ناظر کل (E26) همان را در
دستور تمرکزش می‌بیند، و یک پیام کوتاه (از دروازهٔ آلارم، ضدتکرار ۶ساعته)
به حمید می‌رود — چون خودش خواست بداند.

حدها (تغییر فقط با دستور صریح حمید):

  E1. سه استاپِ سیگنالِ پیاپی (بدون تارگت/تریل بینشان) → علت‌یابی
      همگانی: post-trade-learning + order-block + market-structure.
  E2. استاپِ هم‌جهت در ≥۳ ارز مختلف در پنجره → «الگوی تکراری» —
      بازبینی اردر بلاک (E08) و ترندلاین/ساختار (E07).
  E3. نرخ برد پنجره زیر ۳۵٪ با n≥۱۰ → بازبینی استراتژی/دروازه‌ها
      (E17 کمیتهٔ سیگنال + E22 بهبود).

مرز صادقانه: این ماشین فقط «ارجاع می‌دهد»، تصمیم نمی‌گیرد و پارامتری را
خودش عوض نمی‌کند — تغییر از مسیر همیشگی (یک تغییر کنترل‌شده در چرخه +
سنجش) می‌رود. حدِ رد نشده = سکوت؛ فایل همیشه نوشته می‌شود تا قابل‌ممیزی
باشد.
"""
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
CLOSED = ROOT / "brain" / "paper" / "closed.jsonl"
OUT = ROOT / "signals" / "escalation.json"

WINDOW_H = 24            # پنجرهٔ سنجش
CONSEC_STOPS = 3         # E1
PATTERN_SYMS = 3         # E2
WINRATE_FLOOR = 35.0     # E3 (درصد)
WINRATE_MIN_N = 10


def _sig_rows(path=None, now_ms=None, window_h=WINDOW_H):
    now = now_ms or int(time.time() * 1000)
    rows = []
    p = Path(path) if path else CLOSED
    try:
        with open(p, encoding="utf-8") as fh:
            for ln in fh:
                try:
                    r = json.loads(ln)
                except Exception:                    # noqa: BLE001
                    continue
                st = ((r.get("why") or {}).get("stage") or "")
                if not st.startswith("sig"):
                    continue
                if now - (r.get("closed") or 0) <= window_h * 3600_000:
                    rows.append(r)
    except FileNotFoundError:
        pass
    rows.sort(key=lambda r: r.get("closed") or 0)
    return rows


def _tag(r):
    return (f"{r.get('sym')} {r.get('dir')} "
            f"{time.strftime('%m-%d %H:%M', time.gmtime((r.get('closed') or 0) / 1000))}UTC "
            f"{r.get('outcome')}")


def assess(rows, now_ms=None):
    """حدها روی ردیف‌های پنجره → فهرست ارجاع‌ها (شاید خالی). خالص شمارش."""
    esc = []
    # E1 — استاپ پیاپی از انتهای دفتر
    consec = []
    for r in reversed(rows):
        if r.get("outcome") == "stop":
            consec.append(r)
        else:
            break
    if len(consec) >= CONSEC_STOPS:
        esc.append({
            "rule": "E1", "sev": "high",
            "title": f"{len(consec)} استاپ سیگنالِ پیاپی",
            "rooms": ["post-trade-learning", "order-block", "market-structure"],
            "evidence": [_tag(r) for r in consec[:6]],
            "directive": "علت‌یابی همگانی: هر سه اتاق پروندهٔ همین معامله‌ها "
                         "را بخوانند و یافته را در brain/cases ثبت کنند؛ "
                         "تغییر فقط از مسیر یک-تغییر-در-چرخه."})
    # E2 — استاپ هم‌جهت در چند ارز مختلف
    for d in ("LONG", "SHORT"):
        stops = [r for r in rows
                 if r.get("outcome") == "stop" and r.get("dir") == d]
        syms = sorted({r.get("sym") for r in stops})
        if len(syms) >= PATTERN_SYMS:
            esc.append({
                "rule": "E2", "sev": "high",
                "title": f"استاپ {d} در {len(syms)} ارز مختلف در پنجره",
                "rooms": ["order-block", "market-structure"],
                "evidence": [_tag(r) for r in stops[:6]],
                "directive": "الگوی تکراری بین‌ارزی: کیفیت اردر بلاک‌ها و "
                             "خطوط روند همین ستاپ‌ها بازبینی شود — همان "
                             "مثال حمید (OB و ترندلاین دوباره وارد عمل)."})
    # E3 — نرخ برد پنجره
    done = [r for r in rows if r.get("outcome") in ("stop", "target", "trail")]
    if len(done) >= WINRATE_MIN_N:
        won = sum(1 for r in done if (r.get("R") or 0) > 0)
        wr = 100.0 * won / len(done)
        if wr < WINRATE_FLOOR:
            esc.append({
                "rule": "E3", "sev": "high",
                "title": f"نرخ برد پنجره {wr:.0f}٪ (کف {WINRATE_FLOOR:.0f}٪، n={len(done)})",
                "rooms": ["signal-committee", "improvement"],
                "evidence": [_tag(r) for r in done[-6:]],
                "directive": "بازبینی دروازه‌ها و کیفیت ستاپ در همین پنجره؛ "
                             "نتیجه با CI گزارش شود، نه با حس."})
    return esc


def run(closed_path=None, out_path=None, now_ms=None, quiet=False):
    rows = _sig_rows(closed_path, now_ms)
    esc = assess(rows, now_ms)
    report = {"generated": now_ms or int(time.time() * 1000),
              "panel": "لیام تریدر ۹",
              "window_h": WINDOW_H, "sig_rows": len(rows),
              "escalations": esc,
              "note": ("ماشین آستانه فقط ارجاع می‌دهد؛ تصمیم و تغییر از "
                       "مسیر یک-تغییر-کنترل‌شده-در-چرخه می‌رود (قانون ۰۳).")}
    op = Path(out_path) if out_path else OUT
    op.parent.mkdir(parents=True, exist_ok=True)
    op.write_text(json.dumps(report, ensure_ascii=False, indent=1),
                  encoding="utf-8")
    if esc and not quiet:
        # خبرِ کوتاه به حمید — از دروازهٔ آلارم (کلید درشت: قانون‌های فعال)
        try:
            from hamid import alert_gate
            key = "escalation|" + ",".join(sorted({e["rule"] for e in esc}))
            lines = [f"🚨 ارجاع خودکار ({e['rule']}): {e['title']}" for e in esc]
            alert_gate.send("escalation", key,
                            "لیام تریدر ۹ — ماشین آستانه\n"
                            + "\n".join(lines)
                            + "\nجزئیات و دستور کار روی پنل: escalation.json")
        except Exception as e:                       # noqa: BLE001
            print(f"آلارم ارجاع نرفت: {type(e).__name__}")
    if not quiet:
        print(f"ماشین آستانه: {len(rows)} معاملهٔ سیگنال در {WINDOW_H}س · "
              f"{len(esc)} ارجاع")
    return report


if __name__ == "__main__":
    run()
