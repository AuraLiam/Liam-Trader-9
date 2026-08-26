"""پاسبان دروازهٔ آلارم — و پاسبانِ کلاسِ عیب «آلارم بی‌حافظه».

دو کار می‌کند. اولی معمولی است (خودِ دروازه درست کار می‌کند؟). دومی
مهم‌تر است: **می‌گردد ببیند ماژول تازه‌ای بدون دروازه آلارم می‌فرستد یا
نه.** چون عیب امروز از نبودِ یک تابع نبود؛ از این بود که هر پاسبان جدا
تصمیم می‌گرفت و دو تایشان یادشان رفت. رفعِ تک‌موردی، همین فردا با
پاسبانِ بعدی برمی‌گردد.

اجرا:  python3 -m hamid.test_alert_gate
"""
import json
import re
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
sys.path.insert(0, str(PY))
from hamid import alert_gate as AG                   # noqa: E402

OK = 0
FAIL = []
NOW = 1_700_000_000_000
H = 3600_000


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


print("— خودِ دروازه:")
with tempfile.TemporaryDirectory() as td:
    sp = Path(td) / "alert-state.json"

    def d(key, at, name="t", repeat_h=6.0):
        return AG.decide(name, key, now_ms=at, repeat_h=repeat_h, state_path=sp)

    check("کلید تازه می‌رود", d("A", NOW) == (True, "new"))
    check("همان کلید بلافاصله نمی‌رود", d("A", NOW + 60_000) == (False, "duplicate"))
    check("همان کلید بعد از ۵ ساعت هنوز نمی‌رود",
          d("A", NOW + 5 * H) == (False, "duplicate"))
    check("همان کلید بعد از ۶ ساعت یادآوری می‌شود",
          d("A", NOW + 6 * H) == (True, "reminder"))
    check("یادآوری پنجره را از نو می‌شمارد",
          d("A", NOW + 7 * H) == (False, "duplicate"))
    check("کلید عوض‌شده فوراً می‌رود (خبر تازه معطل نمی‌ماند)",
          d("B", NOW + 7 * H) == (True, "new"))
    check("رفع مشکل یک بار خبر می‌دهد", d("", NOW + 8 * H) == (True, "recovered"))
    check("و بعدش ساکت می‌ماند", d("", NOW + 9 * H) == (False, "quiet"))
    check("بعد از رفع، آلارم بعدی «تازه» است نه تکراری",
          d("B", NOW + 10 * H) == (True, "new"))

    # دو پاسبان مستقل نباید همدیگر را ساکت کنند
    check("نام‌ها از هم جدایند", d("Z", NOW + 10 * H, name="other") == (True, "new"))
    check("و اولی هنوز حافظهٔ خودش را دارد",
          d("B", NOW + 10 * H) == (False, "duplicate"))
    disk = json.loads(sp.read_text())
    check("وضعیت روی دیسک با کلید هر پاسبان جدا ذخیره می‌شود",
          set(disk) == {"t", "other"}, str(disk))

with tempfile.TemporaryDirectory() as td:
    bad = Path(td) / "broken.json"
    bad.write_text("{ این JSON نیست")
    check("وضعیتِ خراب باعث سکوت نمی‌شود (آلارم واقعی گم نشود)",
          AG.decide("x", "K", now_ms=NOW, state_path=bad)[0] is True)

print("\n— پاسبانِ کلاسِ عیب: هیچ آلارمی بی‌دروازه نماند:")

# ماژول‌هایی که حق دارند مستقیم بفرستند، با دلیل. هر کدام یا محصول‌اند
# (سیگنال/رسید — باید فوراً برود) یا حافظهٔ اختصاصی خودشان را دارند.
DIRECT_OK = {
    "telegram.py": "خودِ لایهٔ ارسال",
    "tg_batch.py": "لایهٔ ارسال",
    "tg_health.py": "لایهٔ ارسال",
    "cycle.py": "سیگنال و رسید — محصول است، فوری می‌رود",
    "pump_radar.py": "گزارش نوبت‌دار (قانون ۰۷: ۵ نوبت در روز)",
    "pump_watchlist.py": "گزارش نوبت‌دار",
    "pump_probe.py": "اجرای دستی",
    "btc_patterns.py": "گزارش نوبت‌دار",
    "deep_run.py": "اجرای دستی",
    "local_scanner.py": "سرویس محلی",
    "live_service.py": "سرویس محلی",
    "notif_bridge.py": "پل اعلان",
    "conformance.py": "حافظهٔ اختصاصی خودش را دارد",
    "killswitch.py": "کیل‌سوییچ — عمداً بی‌دروازه، باید همیشه برسد",
    "watchdog.py": "حافظهٔ اختصاصی (brain/watchdog-alerted.json، پنجرهٔ ۶ ساعت)",
    "medic.py": "حافظهٔ اختصاصی (alert_decision: تغییر وضعیت)",
    "alert_gate.py": "خودِ دروازه",
    "work_report.py": "گزارش نوبت‌دار نتیجه — دستور صریح حمید ۲۶ اوت: «دائم ترید کن و نتیجه و استراتژی‌های جدید را بگو»؛ هر نوبت محتوای تازه",
    "dominance_report.py": "گزارش ساعتی دامیننس — دستور صریح حمید ۲۶ اوت شب: «هر یک ساعت نظریهٔ دامیننس‌ها با چارت یک‌ساعته»؛ ضدتکرار ۵۰دقیقه‌ای خودش را دارد",
}
SEND_PAT = re.compile(r"send_text\s*\(|sendMessage|_post\s*\(\s*token")

offenders = []
for p in sorted(list((PY / "hamid").glob("*.py")) + list(PY.glob("*.py"))):
    if p.name.startswith("test_") or p.name in DIRECT_OK:
        continue
    src = p.read_text(encoding="utf-8", errors="ignore")
    if not SEND_PAT.search(src):
        continue
    if "alert_gate" not in src:
        offenders.append(p.name)

check("هر ماژولِ آلارم‌فرست یا از دروازه رد می‌شود یا دلیلِ ثبت‌شده دارد",
      not offenders,
      "بی‌دروازه: " + ", ".join(offenders) + " — یا alert_gate را صدا بزن "
      "یا با دلیل به DIRECT_OK اضافه کن")

pw = (PY / "hamid" / "position_watch.py").read_text(encoding="utf-8")
sn = (PY / "hamid" / "sentinel.py").read_text(encoding="utf-8")
check("پاسبان پوزیشن از دروازه رد می‌شود (عیب اصلی ۲۳ اوت)",
      "alert_gate" in pw)
check("نگهبان یکپارچگی از دروازه رد می‌شود (عیب دوم ۲۳ اوت)",
      "alert_gate" in sn)
check("کلید پاسبان پوزیشن سطلی است، نه فهرست نماد و نه شمارش دقیق",
      "stale_bucket(len(stale))" in pw,
      "کلیدِ ریز یعنی با هر بسته‌شدن پوزیشن، کلید عوض و اسپم برمی‌گردد")

sys.path.insert(0, str(PY / "hamid"))
from hamid import position_watch as PW               # noqa: E402
check("سطل: نوسان جزئی کلید را عوض نمی‌کند (۶۰ و ۷۵ یک سطل‌اند)",
      PW.stale_bucket(60) == PW.stale_bucket(75) != "")
check("سطل: جهش بزرگ کلید را عوض می‌کند (۶۰ → ۳۰۰)",
      PW.stale_bucket(60) != PW.stale_bucket(300))
check("سطل: صفر یعنی کلیدِ خالی = رفع‌شده", PW.stale_bucket(0) == "")

print("\n— سیگنال هرگز پشت دروازه نمی‌ماند (دستور «بدون تأخیر»):")
tg = (PY / "telegram.py").read_text(encoding="utf-8")
sig_block = tg.split("def send_signals")[-1]
check("send_signals اصلاً alert_gate را صدا نمی‌زند",
      "alert_gate" not in sig_block)
check("و در مسیر ارسال سیگنال هیچ sleep/صف‌بندی نیست",
      "sleep" not in sig_block and "batch" not in sig_block.lower(),
      "هر مکثی این‌جا یعنی سیگنالِ دیرشده")

print()
if FAIL:
    print(f"شکست: {len(FAIL)} از {OK + len(FAIL)}")
    sys.exit(1)
print(f"پاسبان دروازهٔ آلارم: هر {OK} بررسی سبز")
