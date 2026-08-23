"""دروازهٔ مشترک آلارم — «آلارمِ بی‌حافظه» دیگر ساخته نمی‌شود.

## چرا این فایل هست (دستور حمید، ۲۳ اوت: «مرتب پیام می‌آید، باید همیشه
## برطرف شود»)

سه پاسبان مستقل داشتیم و هر کدام جدا تصمیم می‌گرفت پیام بدهد یا نه:

- `watchdog` درست بود: کلید خرابی + پنجرهٔ ۶ ساعت.
- `medic` درست بود: فقط روی تغییر وضعیت.
- **`sentinel` و `position_watch` اصلاً حافظه نداشتند** — هر اجرا، اگر
  شرط برقرار بود، پیام می‌رفت. چرخه هر ۳۰ دقیقه می‌دود، یعنی ۲۴ بار در
  روز؛ و چون وضعیتِ زیربنایی روزها ثابت می‌ماند (۵۰ پوزیشن مانده، یک
  ورک‌فلوی ثبت‌نشده)، همان یک خبر ۲۴ بار در روز تکرار می‌شد.

درسِ گران‌ترش: آلارمی که تکرار می‌شود، خوانده نمی‌شود — و آن‌وقت آلارمِ
*واقعیِ* بعدی هم گم می‌شود. پس تکرار فقط آزاردهنده نیست، خطرناک است.

## قرارداد

`decide(name, key)` → `(send, reason)`

- `key` امضای وضعیتِ فعلی است، نه متن پیام. مثال: «۵۰ پوزیشن مانده» و
  «۵۱ پوزیشن مانده» باید یک کلید بدهند وگرنه هر تغییر جزئی دوباره پیام
  می‌فرستد — کلید را درشت بساز (دسته‌بندی، نه شمارش دقیق).
- کلید تازه → می‌رود (`new`).
- همان کلید داخل پنجره → نمی‌رود (`duplicate`).
- همان کلید بعد از پنجره → می‌رود، به‌عنوان یادآور (`reminder`).
- `key=""` یعنی مشکل رفع شده: وضعیت پاک می‌شود و اگر قبلاً آلارمی رفته
  بود، یک‌بار خبرِ سلامتی می‌دهد (`recovered`).

## مرز صادقانه

این دروازه **فقط برای آلارم‌هاست، نه برای سیگنال**. سیگنال محصول است و
باید همان لحظه برود (دستور حمید: «هیچ تأخیری در ارسال سیگنال»). پاسبان
`test_alert_gate` مطمئن می‌شود هیچ مسیر سیگنالی از این‌جا رد نشود.
"""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
ROOT = HERE.parents[2]
STATE = ROOT / "brain" / "alert-state.json"

# پنجرهٔ پیش‌فرض یادآوری: مشکلِ پابرجا حداکثر هر ۶ ساعت یک بار یادآوری
# می‌شود — همان عددی که دیده‌بان از قبل داشت و جواب داده بود.
REPEAT_H = 6.0


def _load():
    try:
        d = json.loads(STATE.read_text())
        return d if isinstance(d, dict) else {}
    except Exception:                                # noqa: BLE001
        # حالتِ خراب/غایب: یک بار می‌فرستیم و وضعیت را از نو می‌سازیم.
        # سکوتِ ناشی از فایلِ خراب بدترین حالت است — آلارم واقعی گم می‌شود.
        return {}


def _save(d):
    try:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(d, ensure_ascii=False, indent=1))
    except Exception:                                # noqa: BLE001
        pass


def decide(name, key, now_ms=None, repeat_h=REPEAT_H, state_path=None):
    """→ (send: bool, reason: str). reason ∈ new/reminder/duplicate/
    recovered/quiet."""
    global STATE
    if state_path is not None:
        STATE = Path(state_path)
    now = now_ms or int(time.time() * 1000)
    d = _load()
    prev = d.get(name) or {}
    prev_key, prev_at = prev.get("key"), prev.get("at") or 0

    if not key:                                      # مشکل رفع شده
        if prev_key:
            d.pop(name, None)
            _save(d)
            return True, "recovered"
        return False, "quiet"

    if prev_key != key:
        d[name] = {"key": key, "at": now, "n": 1}
        _save(d)
        return True, "new"

    if now - prev_at >= repeat_h * 3600_000:
        d[name] = {"key": key, "at": now, "n": (prev.get("n") or 1) + 1}
        _save(d)
        return True, "reminder"

    return False, "duplicate"


def send(name, key, text, now_ms=None, repeat_h=REPEAT_H, state_path=None,
         recovered_text=None, quiet=False):
    """تصمیم + ارسال. → (sent: bool, reason: str).

    متنِ رفع‌شدن اختیاری است؛ اگر ندهی، خبرِ سلامتی فرستاده نمی‌شود ولی
    وضعیت پاک می‌شود تا آلارم بعدی «تازه» حساب شود."""
    ok, reason = decide(name, key, now_ms=now_ms, repeat_h=repeat_h,
                        state_path=state_path)
    if not ok:
        if not quiet:
            print(f"[{name}] آلارم نرفت ({reason})")
        return False, reason
    body = recovered_text if reason == "recovered" else text
    if not body:
        return False, reason
    try:
        import telegram as TG
        TG.send_text(body)
    except Exception as e:                           # noqa: BLE001
        if not quiet:
            print(f"[{name}] ارسال آلارم شکست: {type(e).__name__}")
        return False, f"{reason}/send-failed"
    if not quiet:
        print(f"[{name}] آلارم رفت ({reason})")
    return True, reason
