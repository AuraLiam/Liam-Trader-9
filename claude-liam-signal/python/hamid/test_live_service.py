"""آزمون آفلاین چرخهٔ کامل محلی در حلقهٔ زنده (CycleRunner).

چیزهایی که باید نگه داشته شوند تا «بی‌نیازی از ابر» واقعی باشد و ضربان
۳۰ ثانیه‌ای هم سالم بماند:
  ۱. موعد رسید و گزارش تازه‌ای از Actions نبود → چرخهٔ محلی شروع می‌شود.
  ۲. تا چرخهٔ قبلی تمام نشده، چرخهٔ دوم شروع نمی‌شود (بدون هم‌پوشانی).
  ۳. پایان موفق چرخه → رادار اردر بلاک، مثل ورک‌فلوی Actions.
  ۴. گزارش تازهٔ Actions (از همگام‌سازی گیت) → اجرای محلی تکرار نمی‌شود
     و همان پنجره سوخته حساب می‌شود، نه اینکه هر تیک دوباره بپرسد.
  ۵. قبل از موعد بعدی هیچ چرخه‌ای شروع نمی‌شود.
  ۶. poll هرگز مسدود نمی‌کند — هیچ wait ای صدا زده نمی‌شود.

    python3 -m hamid.test_live_service
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hamid import live_service as ls                 # noqa: E402

FAIL = 0


def check(n, ok, txt):
    global FAIL
    print(f"{n} {'✅' if ok else '❌'} {txt}")
    if not ok:
        FAIL += 1


class FakeProc:
    """پردازهٔ قلابی — poll قابل‌برنامه‌ریزی، بدون هیچ اجرای واقعی."""

    def __init__(self, argv):
        self.argv = argv
        self.rc = None                               # None = هنوز مشغول

    def poll(self):
        return self.rc


spawned = []


def fake_popen(argv, cwd=None):
    p = FakeProc(argv)
    spawned.append(p)
    return p


ls.subprocess.Popen = fake_popen                     # هیچ پردازهٔ واقعی‌ای
_TMP = Path(tempfile.mkdtemp(prefix="live-service-"))
ls.LATEST = _TMP / "hamid-latest.json"               # دور از signals/ تولید

NOW = 1_000_000.0

# ۱) موعد اول، بدون گزارش تازه → چرخه شروع می‌شود
r = ls.CycleRunner()
note = r.poll(NOW)
started = [p for p in spawned if "hamid.cycle" in p.argv]
check("۱", len(started) == 1 and note and "شروع" in note
      and "--symbols" in started[0].argv,
      "موعد بدون گزارش تازه → چرخهٔ محلی شروع شد")

# ۲) تا تمام نشده، دومی شروع نمی‌شود — حتی بعد از گذشتن یک موعد کامل
n2 = r.poll(NOW + ls.CYCLE_EVERY_S + 1)
check("۲", n2 is None and len(spawned) == 1,
      "چرخهٔ در حال اجرا → شروع دوباره ممنوع")

# ۳) پایان موفق → درو + رادار اردر بلاک (مثل ورک‌فلو)
started[0].rc = 0
n3 = r.poll(NOW + ls.CYCLE_EVERY_S + 2)
obs = [p for p in spawned if "hamid.ob_intel" in p.argv]
check("۳", r.proc is None and len(obs) == 1 and n3 and "اردر بلاک" in n3,
      "پایان موفق چرخه → رادار اردر بلاک")

# ۴) گزارش تازه از Actions → اجرای محلی لازم نیست و پنجره می‌سوزد
t4 = NOW + 2 * ls.CYCLE_EVERY_S + 10
ls.LATEST.write_text(json.dumps({"generated": int((t4 - 60) * 1000)}))
before = len(spawned)
n4 = r.poll(t4)
n4b = r.poll(t4 + 1)                                 # تیک بعدی، هنوز قبل از موعد
check("۴", len(spawned) == before and n4 and "لازم نشد" in n4 and n4b is None,
      "گزارش تازهٔ Actions → بدون چرخهٔ محلی، پنجره سوخت")

# ۵) قبل از موعد بعدی هیچ شروعی نیست؛ بعد از موعد و با گزارش کهنه، هست
n5a = r.poll(t4 + ls.CYCLE_EVERY_S - 5)
ls.LATEST.write_text(json.dumps(
    {"generated": int((t4 - 2 * ls.CYCLE_FRESH_S) * 1000)}))
n5b = r.poll(t4 + ls.CYCLE_EVERY_S + 1)
check("۵", n5a is None and n5b and "شروع" in n5b
      and len([p for p in spawned if "hamid.cycle" in p.argv]) == 2,
      "موعد بعدی با گزارش کهنه → چرخهٔ تازه")

# ۶) poll مسدود نمی‌کند — FakeProc اصلاً wait ندارد؛ اگر CycleRunner
#    چیزی جز poll صدا می‌زد همین‌جا AttributeError می‌گرفت. شکست چرخه هم
#    فقط لاگ است، نه استثنا.
[p for p in spawned if "hamid.cycle" in p.argv][-1].rc = 3
n6 = r.poll(t4 + ls.CYCLE_EVERY_S + 2)
check("۶", n6 and "کد 3" in n6 and r.proc is None,
      "شکست چرخه → لاگ و ادامهٔ حلقه، بدون استثنا")

print()
if FAIL:
    print(f"{FAIL} آزمون شکست")
    sys.exit(1)
print("همهٔ ۶ آزمون چرخهٔ محلی گذشت")
