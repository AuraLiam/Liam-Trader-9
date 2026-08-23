"""پاسبان سنجهٔ اثر تجربه — همراه اجباری experience_effect.py. آفلاین.

خطر این ابزار خرابی نیست، **خوش‌بینی** است: نمونهٔ کوچک به‌راحتی
اختلافِ بزرگ نشان می‌دهد و اگر حکم بدون CI چاپ شود، همان می‌شود ادعای
«یادگیری جواب داد». پس بیشترِ این بررسی‌ها روی همین‌اند: بازه‌ای که صفر
را در بر می‌گیرد باید صریح «جدا از نویز نیست» بگوید، و نمونهٔ کوچک اصلاً
حکم نگیرد.
"""
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
sys.path.insert(0, str(PY))
from hamid import experience_effect as EE            # noqa: E402

OK = 0
FAIL = []


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


def rows(with_r, without_r):
    out = []
    for r in with_r:
        out.append({"R": r, "outcome": "target" if r > 0 else "stop",
                    "why": {"stage": "sig-ibs", "exp_used": True}})
    for r in without_r:
        out.append({"R": r, "outcome": "target" if r > 0 else "stop",
                    "why": {"stage": "sig-ibs", "exp_used": False}})
    return out


print("— حکم فقط با بازهٔ اطمینان:")
# اثر واقعی و بزرگ روی نمونهٔ کافی → باید معنادار اعلام شود
big = EE.measure(rows([2.0] * 40, [-1.0] * 40), "اثر بزرگ")
check("اثر بزرگ و نمونهٔ کافی → معنادار", "معنادار" in big["verdict"], big["verdict"])
check("و بازه کاملاً بالای صفر است", big["ci95"][0] > 0, str(big["ci95"]))

# دو گروه از یک توزیع → نباید معنادار شود
same = [0.5, -1.0, 1.2, -1.0, 0.3, 2.0, -1.0, 0.8, -1.0, 1.5] * 4
half = len(same) // 2
noise = EE.measure(rows(same[:half], same[half:]), "نویز")
check("دو گروهِ هم‌جنس → «جدا از نویز نیست»",
      "نویز" in noise["verdict"], noise["verdict"])

# نمونهٔ کوچک → اصلاً حکم ندهد
tiny = EE.measure(rows([3.0, 2.5, 3.0], [-1.0, -1.0]), "نمونهٔ کوچک")
check("نمونهٔ کوچک حکم نمی‌گیرد، حتی با اختلاف بزرگ",
      tiny["ci95"] is None and "نمونه کم" in tiny["verdict"], tiny["verdict"])
check("ولی خودِ اختلاف گزارش می‌شود (پنهان نمی‌شود)", tiny["diff"] > 0)

# اثر منفی هم باید دیده شود — نه فقط مثبت
neg = EE.measure(rows([-1.0] * 40, [2.0] * 40), "اثر منفی")
check("اثر منفیِ معنادار هم اعلام می‌شود (نه فقط خبر خوب)",
      "منفی" in neg["verdict"], neg["verdict"])

check("یک‌طرفِ خالی → مقایسه نمی‌شود",
      "قابل مقایسه نیست" in EE.measure(rows([1.0] * 10, []), "خالی")["verdict"])

print("\n— تعیین‌پذیری و انتخاب نمونه:")
a = EE.boot_diff([1.0] * 20, [0.0] * 20)
b = EE.boot_diff([1.0] * 20, [0.0] * 20)
check("بوت‌استرپ با seed ثابت بازتولیدپذیر است (عدد امروز فردا هم همان)",
      a == b, f"{a} vs {b}")

with tempfile.TemporaryDirectory() as td:
    p = Path(td) / "closed.jsonl"
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in [
        {"R": 1.0, "closed": 5000, "why": {"stage": "sig-ibs", "exp_used": True}},
        {"R": 1.0, "closed": 5000, "why": {"stage": "practice", "exp_used": True}},
        {"R": 1.0, "closed": 5000, "why": {"stage": "scalp"}},
        {"R": None, "closed": 5000, "why": {"stage": "sig-ibs"}},
        {"R": 1.0, "closed": 100, "why": {"stage": "sig-smc"}},
    ]) + "\n", encoding="utf-8")
    _old = EE.CLOSED
    EE.CLOSED = p
    try:
        only_sig = EE.load(sent_only=True)
        everything = EE.load(sent_only=False)
        windowed = EE.load(since_ms=1000, sent_only=True)
    finally:
        EE.CLOSED = _old

check("فقط دفتر سیگنالِ ارسال‌شده شمرده می‌شود، نه تمرین/اسکلپ",
      len(only_sig) == 2, str(len(only_sig)))
check("دفترهای دیگر با sent_only=False دیده می‌شوند", len(everything) == 4)
check("ردیف بی‌نمره (R=None) هرگز وارد آمار نمی‌شود",
      all(t["R"] is not None for t in everything))
check("پنجرهٔ زمانی واقعاً می‌بُرد", len(windowed) == 1, str(len(windowed)))

print("\n— مرز صادقانه روی خروجی:")
src = (PY / "hamid" / "experience_effect.py").read_text(encoding="utf-8")
check("فایل صریح می‌گوید exp_used علیت را ثابت نمی‌کند",
      "علیت را ثابت نمی‌کند" in src)
check("و هشدار وتو (دو گروه هم‌شکل نیستند) نوشته شده",
      "وتو" in src and "هم‌شکل" in src)

print()
if FAIL:
    print(f"شکست: {len(FAIL)} از {OK + len(FAIL)}")
    sys.exit(1)
print(f"پاسبان سنجهٔ اثر تجربه: هر {OK} بررسی سبز")
