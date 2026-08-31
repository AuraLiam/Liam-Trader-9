"""پاسبان کارنامه — نمره‌ای که نمی‌تواند بد شود، نمره نیست.

این ماژول برای حمید ساخته شد تا انجین‌ها را **قضاوت** کند. پس دقیقاً دو
راهِ خراب‌شدن دارد، و هر دو این‌جا قفل می‌شوند:

۱. **نمرهٔ تعارفی** — متری که همیشه سبز است. اگر کارنامه‌ای `falsifier`
   نداشته باشد، یعنی هیچ‌کس نمی‌تواند بگوید کِی بد است؛ آن‌وقت عدد
   تزئین است نه سنجش.
۲. **نمرهٔ سخت‌گیرتر از قرارداد** — آلارمِ کاذب. نسخهٔ اولِ متر E25
   «هر تکرار در ۱۲ ساعت» را تخلف گرفت در حالی که قرارداد ۲۶ اوت سه
   کلید جدا دارد؛ سه ارسالِ کاملاً مجاز تخلف شمرده شدند. متری که با
   قرارداد نخواند، به همان اندازهٔ متری که شل باشد دروغ می‌گوید.

و یک قید سوم که از قانون ۰۱ می‌آید: **جای عددِ نبوده، حدس نمی‌نشیند** —
نبودِ دفتر باید `NO_METRIC` بدهد با دلیلِ مشخص، نه صفر یا میانگینِ چیزِ
دیگری.

اجرا: `python3 -m hamid.test_scorecard`
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
sys.path.insert(0, str(PY))

from hamid import scorecard as S                                # noqa: E402

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


H = 3_600_000


def run():
    m = S.build()
    cards = m["cards"]
    by = {c["id"]: c for c in cards}

    # ── ۱) پوشش ────────────────────────────────────────────────────────
    from hamid.engine_map import WATCHES
    check("هر انجینِ نقشه یک کارنامه دارد",
          set(by) >= set(WATCHES), str(set(WATCHES) - set(by)))
    check("هیچ انجینی دو کارنامه ندارد", len(cards) == len(by))

    # ── ۲) نمرهٔ تعارفی ممنوع ──────────────────────────────────────────
    scored = [c for c in cards if c["verdict"] != "NO_METRIC"]
    bad = [c["id"] for c in scored if not c["falsifier"] or c["falsifier"] == "—"]
    check("هر کارنامهٔ نمره‌دار جملهٔ «چه چیزی بدش می‌کند» دارد",
          not bad, str(bad))
    check("هر کارنامهٔ نمره‌دار منبعِ نام‌برده دارد",
          all(c["source"] for c in scored),
          str([c["id"] for c in scored if not c["source"]]))
    check("هر کارنامهٔ نمره‌دار عدد دارد (نه فقط برچسب)",
          all(c["value"] is not None for c in scored),
          str([c["id"] for c in scored if c["value"] is None]))

    # ── ۳) نبودِ دفتر = NO_METRIC با دلیل، نه صفر ──────────────────────
    nm = [c for c in cards if c["verdict"] == "NO_METRIC"]
    check("هر NO_METRIC می‌گوید چه دفتری لازم است",
          all("دفتر لازم ساخته نشده" in (c["note"] or "") for c in nm),
          str([c["id"] for c in nm if "دفتر لازم" not in (c["note"] or "")]))
    check("هیچ NO_METRIC عددِ ساختگی ندارد",
          all(c["value"] is None for c in nm))

    # ── ۴) پایه برای مترِ پیش‌بین اجباری است ───────────────────────────
    fc = [c for c in scored if c["family"] == "پیش‌بین"]
    check("هر مترِ پیش‌بین پایه (baseline) دارد",
          all(c["baseline"] is not None for c in fc),
          str([c["id"] for c in fc if c["baseline"] is None]))

    # ── ۵) مترِ دروازه‌بان باید گروه ضدواقع داشته باشد ─────────────────
    gk = [c for c in scored if c["family"] == "دروازه‌بان"]
    check("هر مترِ دروازه‌بان بازهٔ اطمینان دارد (اختلافِ دو گروه، نه یک گروه)",
          all(c["ci"] for c in gk),
          str([c["id"] for c in gk if not c["ci"]]))
    check("حکمِ دروازه‌بان از CI می‌آید نه از میانگین",
          all(c["verdict"] in ("SKILL", "NO_SKILL", "NEGATIVE") for c in gk),
          str([(c["id"], c["verdict"]) for c in gk]))

    # ── ۶) حکمِ CI درست خوانده می‌شود ──────────────────────────────────
    check("CI بالای صفر → SKILL", S.verdict_ci(0.1, 0.3) == "SKILL")
    check("CI زیر صفر → NEGATIVE", S.verdict_ci(-0.3, -0.1) == "NEGATIVE")
    check("CI شاملِ صفر → NO_SKILL", S.verdict_ci(-0.1, 0.3) == "NO_SKILL")

    # ── ۷) مترِ ضدتکرار دقیقاً قراردادِ ۲۶ اوت است، نه سخت‌گیرتر ────────
    #
    # سه ارسالِ **مجاز** ساخته می‌شود: استراتژیِ متفاوت با فاصلهٔ بیش از
    # ۳ ساعت. اگر متر این‌ها را تخلف بگیرد، آلارمِ کاذب می‌سازد.
    src = (PY / "hamid" / "scorecard.py").read_text(encoding="utf-8")
    check("متر هر سه کلیدِ قرارداد را دارد (۳س بی‌استراتژی · ۱۲س هم‌استراتژی · سقف ۲)",
          "3 * H" in src and "12 * H" in src and ">= 2" in src)
    check("متر از دفترِ واقعیِ ارسال می‌خواند، نه از حافظهٔ ضدتکرار",
          "telegram-log.json" in src)

    # ── ۸) مرز: کارنامه وزن نمی‌سازد و دروازه عوض نمی‌کند ──────────────
    check("خروجی مرز صادقانه دارد (قانون ۱۲)",
          "دروازه" in m["boundary"] and "قانون ۰۳" in m["boundary"])
    check("ماژول هیچ وزن/آستانه‌ای صادر نمی‌کند",
          "weight" not in src and "threshold" not in src)
    check("ماژول جز خروجی خودش چیزی نمی‌نویسد (قانون ۰۵)",
          src.count("write_text") == 1 and "OUT.write_text" in src)

    # ── ۹) شمارش‌ها با هم می‌خوانند ────────────────────────────────────
    check("شمارشِ نمره‌دار و بی‌متر با فهرست می‌خواند",
          m["n_scored"] == len(scored) and m["n_no_metric"] == len(nm)
          and m["n"] == len(cards))

    print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(run())
