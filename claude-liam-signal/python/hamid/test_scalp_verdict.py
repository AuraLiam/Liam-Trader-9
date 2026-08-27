"""پاسبان ماشینِ حکمِ میز ۱ دقیقه — همراه اجباری scalp_verdict.py. آفلاین.

خطرِ یک ماشینِ حکم این است که **حکمِ راحت** بدهد: با نمونهٔ کم PROMOTE
کند، یا یک دورهٔ بد را REJECT بخواند، یا حکمِ ساخته‌شده روی یک هندسه را
به هندسهٔ دیگر بچسباند. بیشترِ بررسی‌های این‌جا روی همین‌اند.
"""
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
sys.path.insert(0, str(PY))
from hamid import scalp_verdict as V                 # noqa: E402

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


def rows(net, n, gross=None, stage="scalp"):
    """n ردیف با R خالصِ داده‌شده. R ناخالص پیش‌فرض = خالص + کارمزد."""
    g = gross if gross is not None else net + 0.2
    return [{"sym": "X", "R": g, "R_net": net, "fee_r": g - net,
             "why": {"stage": stage}} for _ in range(n)]


print("— قاعدهٔ توقف، از پیش و بدون تخفیف:")
d = V.decide(rows(0.5, 100))
check("نمونهٔ زیر کف، حتی با اثر بزرگ، PROMOTE نمی‌گیرد",
      d["verdict"] == "UNDECIDED", d["verdict"])
check("و می‌گوید چند تا کم دارد", d["more_trades_needed"] == V.MIN_N - 100)

d = V.decide(rows(0.5, V.MIN_N + 10))
check("اثر بزرگ روی نمونهٔ کافی → PROMOTE", d["verdict"] == "PROMOTE", d["why"])
check("و PROMOTE صریح می‌گوید تأیید حمید لازم است",
      "تأیید صریح حمید" in d["why"])

d = V.decide(rows(-0.5, V.MIN_N + 10))
check("اثرِ منفی روی نمونهٔ کافی ولی زیر کفِ رد → هنوز REJECT نیست",
      d["verdict"] == "UNDECIDED", d["verdict"])
d = V.decide(rows(-0.5, V.REJECT_N + 10))
check("زیر کفِ رد فقط با نمونهٔ بزرگ‌تر → REJECT",
      d["verdict"] == "REJECT", d["verdict"])
check("REJECT صریح می‌گوید «این هندسه»، نه «ایدهٔ ۱ دقیقه»",
      "این هندسه" in d["why"], d["why"])
check("و راهِ بعد را می‌گوید (هندسه، نه صبر)",
      "صبر بیشتر" in d["why"] or "عوض‌کردن هندسه" in d["why"])

print("\n— معیار «خالص» است، نه ناخالص (همان جایی که این میز می‌بازد):")
d = V.decide(rows(-0.2, V.MIN_N + 10, gross=0.4))
check("ناخالصِ مثبتِ بزرگ، وقتی خالص منفی است، PROMOTE نمی‌گیرد",
      d["verdict"] != "PROMOTE", f"{d['verdict']} · ناخالص {d['mean_gross']}")
check("و تشخیص می‌گوید لبه هست ولی کارمزد می‌خوردش",
      "کارمزد آن را می‌خورد" in (d.get("diagnosis") or ""), str(d.get("diagnosis")))
check("تشخیص صریح می‌گوید اهرم/حجم جوابش نیست",
      "اهرم در این کسر نیست" in (d.get("diagnosis") or ""))
d2 = V.decide(rows(-0.4, V.MIN_N + 10, gross=-0.2))
check("وقتی ناخالص هم منفی است، تشخیصِ دیگری می‌دهد",
      "خودِ پیش‌بینی" in (d2.get("diagnosis") or ""), str(d2.get("diagnosis")))

print("\n— حکم به پیکربندی گره خورده است:")
cfg = V.config()
check("اثرانگشت از خودِ liam9_strategy می‌آید، نه کپیِ دستی",
      "hold_bars" in cfg and "rr_target" in cfg, str(cfg))
src = (PY / "hamid" / "scalp_verdict.py").read_text(encoding="utf-8")
check("و پارامترها در این فایل دوباره تعریف نشده‌اند",
      "hold_bars\": 45" not in src and "rr_target = " not in src)
check("سند صریح می‌گوید تغییر پارامتر = دفترِ حکم از صفر",
      "از صفر" in src and "هر تغییرِ پارامتر" in src)
# دستور صریح حمید (۲۷ اوت): «اصلاً قرار نبود هیچ پیامی از ترید در تایم
# یک دقیقه بیاد» — میز ۱د فقط پیپرمود است؛ حکمش در JSON/پنل می‌نشیند و
# هیچ آلارم تلگرامی ندارد. (بررسی قبلیِ «کلید آلارم اثرانگشت‌دار» با
# حذف کامل آلارم بی‌موضوع شد.)
check("میز ۱ دقیقه هیچ پیامی به تلگرام نمی‌فرستد (فقط پیپرمود)",
      "alert_gate.send(" not in src and "send_text(" not in src
      and "دستور صریح حمید" in src)

print("\n— برآوردِ «چقدر تا جواب»:")
n = V.needed_n([0.05, -0.05] * 200)          # میانگین ~صفر
check("اثرِ نزدیکِ صفر → یا None (عملاً بی‌نهایت) یا عددِ بزرگ",
      n is None or n > 1000, str(n))
check("نمونهٔ خیلی کوچک برآورد نمی‌گیرد", V.needed_n([1.0, -1.0]) is None)
big = V.needed_n([1.0] * 200)
check("اثرِ قاطع → صفرِ «همین حالا تصمیم‌پذیر»", big == 0, str(big))

print("\n— بازتولیدپذیری و ایزوله بودن:")
check("بوت‌استرپ با seed ثابت همان عدد را می‌دهد",
      V.boot_ci([0.3, -0.1, 0.5] * 40) == V.boot_ci([0.3, -0.1, 0.5] * 40))
with tempfile.TemporaryDirectory() as td:
    p = Path(td) / "c.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in
                 rows(0.5, 20) + rows(9.0, 500, stage="sig-ibs")
                 + rows(9.0, 500, stage="shock")) + "\n", encoding="utf-8")
    only = V.load(p)
check("فقط stage=scalp خوانده می‌شود — دفتر سیگنال و شوک دست‌نخورده",
      len(only) == 20, str(len(only)))
check("ردیف بی‌نمره (R=None) وارد نمی‌شود",
      V.decide([{"R": None, "why": {"stage": "scalp"}}])["n"] == 0)
check("R_net نبود، از fee_r بازسازی می‌شود",
      V.net_of({"R": 1.0, "fee_r": 0.2}) == 0.8)
check("نه R_net نه fee_r → None، نه حدس",
      V.net_of({"R": 1.0}) is None)
check("دفتر خالی حکمِ UNDECIDED می‌گیرد، نه خطا",
      V.decide([])["verdict"] == "UNDECIDED")

print("\n— مرز صادقانه روی خروجی:")
check("سند می‌گوید هیچ‌چیز خودکار به تولید نمی‌رود",
      "هیچ‌چیز را به تولید نمی‌برد" in src)
check("و می‌گوید روی دفتر سیگنال اثر ندارد (قانون ۹)",
      "قانون ۹" in src)

print()
if FAIL:
    print(f"شکست: {len(FAIL)} از {OK + len(FAIL)}")
    sys.exit(1)
print(f"پاسبان حکمِ میز ۱ دقیقه: هر {OK} بررسی سبز")
