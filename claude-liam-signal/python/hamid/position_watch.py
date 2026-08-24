"""پاسبان پوزیشنِ مانده — دستور حمید (۲۳ اوت).

«یک ایجنت باید به صورت مداوم وضعیت داشبورد و نتایج ترید را بررسی کند که
یک پوزیشن بیش از حد باز نماند — وقتی بر اساس کندل‌شناسی در کندلِ درست
ورود کنی، نتیجه زودتر حاصل می‌شود.»

منطقش همان حرف حمید است، به‌صورت عدد: ستاپ اسکلپ اگر درست باشد در چند
کندل جواب می‌دهد؛ پوزیشنی که از `max_hold` گذشته و هنوز باز است، دیگر
همان ستاپ نیست — دلیلِ ورودش منقضی شده و ماندنش فقط ریسکِ بی‌دلیل است.

## مرز صادقانه

این پاسبان **پوزیشن نمی‌بندد** — LIVE_EXECUTION=false و بستن پوزیشن
اجرای زنده است (قانون ۰۵). کارش: دفترهای باز را می‌گردد، هر پوزیشنِ
مانده را با سن و حکم صریح در `signals/position-watch.json` منتشر می‌کند
و اگر تلگرام وصل باشد آلارم می‌دهد. عمل بستن یا با قابلیت خود داشبورد
است یا دست حمید.

سقف نگهداری بر اساس تایم‌فریم (هم‌خوان با max_hold_min خروجی استراتژی):
1m=۴۵د · 5m=۴ساعت · 15m=۱۲ساعت · 1h=۴۸ساعت. جدولش این‌جاست تا عدد
جادویی پخش نشود.

اجرا:  python3 -m hamid.position_watch            (گزارش)
       python3 -m hamid.position_watch --alert    (+ تلگرام اگر مانده هست)
"""
import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
ROOT = HERE.parents[2]
OPEN = ROOT / "brain" / "paper" / "open.jsonl"
OUT = ROOT / "signals" / "position-watch.json"

# سقف نگهداری به دقیقه، بر اساس تایم‌فریم ورود.
MAX_HOLD_MIN = {"1m": 45, "3m": 90, "5m": 240, "15m": 720, "1h": 2880}
DEFAULT_HOLD_MIN = 720


def max_hold_for(tf):
    return MAX_HOLD_MIN.get(tf, DEFAULT_HOLD_MIN)


# سطل‌های بزرگیِ مشکل — کلید آلارم از این‌جا می‌آید تا نوسانِ جزئی
# (بسته‌شدن دو پوزیشن) پیام تازه نسازد.
BUCKETS = ((5, "۱-۵"), (20, "۶-۲۰"), (50, "۲۱-۵۰"), (200, "۵۱-۲۰۰"))


def stale_bucket(n):
    """تعداد پوزیشنِ مانده → برچسب سطل. صفر یعنی کلیدِ خالی (رفع شده)."""
    if n <= 0:
        return ""
    for hi, label in BUCKETS:
        if n <= hi:
            return f"stale:{label}"
    return "stale:۲۰۰+"


def scan(rows, now_ms=None):
    """پوزیشن‌های **پرشده** → (مانده‌ها، سالم‌ها). مانده = سن > سقفِ تایم‌فریمش.

    سفارش‌های هنوز پرنشده این‌جا شمرده نمی‌شوند؛ کارِ `scan_pending` است.
    قبل از ۲۴ اوت این تابع `filled or opened` می‌گرفت و لیمیتِ پرنشده را
    «پوزیشن باز» جا می‌زد — یعنی هم آمارِ مانده را باد می‌کرد و هم خودِ
    مشکلِ لیمیتِ منقضی را پنهان می‌کرد.
    """
    now = now_ms or int(time.time() * 1000)
    stale, ok = [], []
    for r in rows:
        opened = r.get("filled")
        if not opened:
            continue
        age_min = (now - opened) / 60000
        cap = max_hold_for(r.get("tf"))
        rec = {"sym": r.get("sym"), "dir": r.get("dir"), "tf": r.get("tf"),
               "age_min": round(age_min), "max_hold_min": cap,
               "over_by_min": round(age_min - cap)}
        (stale if age_min > cap else ok).append(rec)
    stale.sort(key=lambda x: -x["over_by_min"])
    return stale, ok


# سقف مطلقِ انتظارِ یک لیمیت — همان عددی که paper.py با آن سفارش پرنشده
# را کنسل می‌کند. این‌جا دوباره تعریف نمی‌شود تا دو جا از هم دور نیفتند.
def _fill_cap_min(tf):
    """مهلت انتظار یک لیمیتِ پرنشده، به دقیقه.

    منطق: سفارش دقیقاً به اندازهٔ همان ستاپی معتبر است که ساختش. ستاپ
    اسکلپ ۱د بعد از ۴۵ دقیقه دیگر همان ستاپ نیست، پس لیمیتش هم نیست.
    سقف مطلق `paper.FILL_HOURS` است تا هیچ سفارشی برای همیشه نماند.
    """
    try:
        from hamid.paper import FILL_HOURS
    except Exception:                              # noqa: BLE001
        FILL_HOURS = 24
    return min(max_hold_for(tf), FILL_HOURS * 60)


def scan_pending(rows, now_ms=None):
    """سفارش‌های لیمیتِ هنوز پرنشده → (منقضی‌ها، هنوز-معتبرها).

    دستور حمید (۲۴ اوت): «از همین پوزیشن‌ها برای لیمیت گذاشتن هم
    استفاده کن.» نتیجهٔ مستقیمش این است که حالا سفارشِ واقعی روی صرافی
    می‌نشیند؛ پس پاسبان باید بگوید کدام سفارش دیگر پشتوانهٔ تحلیلی
    ندارد. لیمیتی که ستاپش منقضی شده، سفارشِ بی‌صاحب است: اگر بعداً پر
    شود، روی تحلیلی پر شده که دیگر وجود ندارد.

    این‌جا هم چیزی لغو نمی‌شود — اعلام است، نه اجرا (قانون ۰۵).
    """
    now = now_ms or int(time.time() * 1000)
    expired, waiting = [], []
    for r in rows:
        if r.get("filled"):
            continue                                # پر شده — کار scan است
        opened = r.get("opened")
        if not opened:
            continue
        age_min = (now - opened) / 60000
        cap = _fill_cap_min(r.get("tf"))
        rec = {"sym": r.get("sym"), "dir": r.get("dir"), "tf": r.get("tf"),
               "entry": r.get("entry"), "sl": r.get("sl"),
               "age_min": round(age_min), "valid_min": cap,
               "over_by_min": round(age_min - cap)}
        (expired if age_min > cap else waiting).append(rec)
    expired.sort(key=lambda x: -x["over_by_min"])
    return expired, waiting


def load_open(path=None):
    p = Path(path) if path else OPEN
    if not p.exists():
        return []
    out = []
    for line in p.read_text().splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def run(alert=False, quiet=False, path=None, now_ms=None):
    rows = load_open(path)
    stale, ok = scan(rows, now_ms=now_ms)
    dead, waiting = scan_pending(rows, now_ms=now_ms)
    verdicts = []
    if stale:
        verdicts.append(f"{len(stale)} پوزیشن بیش از سقفِ نگهداری باز مانده")
    if dead:
        verdicts.append(f"{len(dead)} سفارش لیمیتِ پرنشده منقضی شده")
    res = {"at": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
           "open_total": len(stale) + len(ok),
           "stale": stale, "ok_count": len(ok),
           "pending_total": len(dead) + len(waiting),
           "expired_pending": dead, "pending_ok_count": len(waiting),
           "verdict": ("؛ ".join(verdicts) if verdicts else
                       "هیچ پوزیشنِ مانده و هیچ لیمیتِ منقضی‌ای نداریم"),
           "note": ("این پاسبان فقط اعلام می‌کند؛ بستن پوزیشن یا لغو سفارش "
                    "اجرای زنده است و بیرون از مرز این بسته (قانون ۰۵).")}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    if not quiet:
        print(res["verdict"])
        for s_ in stale[:10]:
            print(f"  ⏰ {s_['sym']} {s_['dir']} {s_['tf']}: "
                  f"{s_['age_min']}د باز (سقف {s_['max_hold_min']}د، "
                  f"{s_['over_by_min']}د اضافه)")
        for d_ in dead[:10]:
            print(f"  📋 {d_['sym']} {d_['dir']} {d_['tf']}: لیمیت "
                  f"{d_['age_min']}د منتظر (اعتبار {d_['valid_min']}د، "
                  f"{d_['over_by_min']}د گذشته)")
    if alert:
        # دروازهٔ مشترک آلارم (۲۳ اوت): تا امروز این پیام هر چرخه — یعنی
        # ۲۴ بار در روز — تکرار می‌شد، چون دفتر باز روزها همان است.
        #
        # کلید عمداً **سطلی** است، نه فهرست نماد و نه شمارش دقیق. نسخهٔ
        # اول همین رفع، کلید را از مجموعهٔ نمادها ساخت و باز اسپم می‌شد:
        # هر چرخه چند پوزیشن بسته می‌شود، مجموعه عوض می‌شود، و «کلید
        # تازه» یعنی پیام تازه. سطل یعنی فقط وقتی خبر می‌دهیم که وضعیت
        # از نظر بزرگی عوض شده باشد — نه با هر جابه‌جاییِ جزئی.
        from hamid import alert_gate
        key = stale_bucket(len(stale))
        lines = [f"⏰ {s_['sym']} {s_['dir']} ({s_['tf']}): "
                 f"{s_['over_by_min']}د بیش از سقف باز است" for s_ in stale[:6]]
        more = f"\n… و {len(stale) - 6} پوزیشن دیگر" if len(stale) > 6 else ""
        alert_gate.send(
            "position_watch", key,
            "⏰ لیام تریدر ۹ — پوزیشنِ مانده:\n" + "\n".join(lines) + more
            + "\nستاپش منقضی شده — بستن/بازبینی دستی لازم است.",
            recovered_text="✅ لیام تریدر ۹ — دیگر پوزیشنِ ماندهٔ بیش از سقف نداریم.")
        # سفارش‌های لیمیتِ منقضی — آلارمِ جدا با کلیدِ جدا. اگر با آلارم
        # بالا یک کلید داشتند، رفع‌شدنِ یکی «سلامتیِ» دیگری را هم اعلام
        # می‌کرد؛ دو مشکلِ متفاوت، دو کلید.
        dead_lines = [f"📋 {d_['sym']} {d_['dir']} ({d_['tf']}): لیمیت "
                      f"{d_['over_by_min']}د از اعتبارش گذشته"
                      for d_ in dead[:6]]
        dead_more = f"\n… و {len(dead) - 6} سفارش دیگر" if len(dead) > 6 else ""
        alert_gate.send(
            "pending_limits", stale_bucket(len(dead)).replace("stale:", "limit:"),
            "📋 لیام تریدر ۹ — سفارش لیمیتِ منقضی:\n" + "\n".join(dead_lines)
            + dead_more + "\nستاپِ تحلیلی‌اش منقضی شده — اگر روی صرافی "
            "گذاشته‌ای، لغوش کن؛ پر شدنش یعنی ورود روی تحلیلی که دیگر نیست.",
            recovered_text="✅ لیام تریدر ۹ — دیگر سفارش لیمیتِ منقضی نداریم.")
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--alert", action="store_true")
    run(alert=ap.parse_args().alert)
