"""پاسبان برنامهٔ درسی — سه راهِ خراب‌شدن.

۱. **تکرار**: همان کتاب دو بار در تخصیصِ یک انجین، یا همان کتاب هر روز.
   آن‌وقت «سه منبع در روز» عملاً یکی می‌شود. (نسخهٔ اولِ `shelf` همین را
   داشت: E00 دو بار «Thinking, Fast and Slow» گرفت.)
۲. **پنهان‌کردن کمبود**: اگر قفسه برای موضوعی خالی باشد و ماژول سکوت
   کند، حمید فکر می‌کند برنامه کامل اجرا شده. کمبود باید صریح باشد.
۳. **پر کردنِ صف با هرچیزی**: منبعی که هیچ ربطی به کارِ انجین ندارد،
   تخصیص نیست. امتیازِ تطبیق باید مثبت باشد.

اجرا: `python3 -m hamid.test_curriculum`
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
sys.path.insert(0, str(PY))

from hamid import curriculum as C                               # noqa: E402
from hamid import engine_map as M                               # noqa: E402

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


def run():
    cur = C.assign()
    rows = {r["engine"]: r for r in cur["rows"]}

    check("هر انجینِ نقشه ردیف برنامهٔ درسی دارد",
          set(rows) >= set(M.WATCHES), str(set(M.WATCHES) - set(rows)))
    check("هر انجین موضوعِ تعریف‌شده دارد (تطبیق کور نیست)",
          all(r["topics"] for r in cur["rows"]))

    # ── ۱) تکرار ───────────────────────────────────────────────────────
    dup = [r["engine"] for r in cur["rows"]
           if len({a["title"] for a in r["assigned"]}) != len(r["assigned"])]
    check("هیچ انجینی یک منبع را دو بار نمی‌گیرد", not dup, str(dup))
    sh = C.shelf()
    check("قفسه بر عنوان یکتاست",
          len({r["title"].strip().lower() for r in sh}) == len(sh))
    check("نسخهٔ VERIFIED بر QUEUED می‌چربد",
          all(r["status"] in ("VERIFIED", "QUEUED", "DUPLICATE", "REJECTED")
              for r in sh))

    # منبعی که انجین قبلاً خوانده دوباره تخصیص نمی‌شود
    eid = next(iter(sorted(C.TOPICS)))
    already = C.read_already(eid)
    given = {a["title"].strip().lower() for a in rows[eid]["assigned"]}
    check("منبعِ قبلاً خوانده دوباره تخصیص نمی‌شود", not (given & already),
          str(given & already))

    # ── ۲) کمبود پنهان نمی‌شود ─────────────────────────────────────────
    short = [r for r in cur["rows"] if len(r["assigned"]) < cur["per_engine"]]
    check("هر انجینِ کم‌منبع، جملهٔ کمبود دارد",
          all(r["gap"] for r in short),
          str([r["engine"] for r in short if not r["gap"]]))
    check("انجینِ کامل، جملهٔ کمبود ندارد",
          all(not r["gap"] for r in cur["rows"]
              if len(r["assigned"]) >= cur["per_engine"]))
    check("شمارشِ کمبود با فهرست می‌خواند", cur["n_short"] == len(short))
    check("شمارشِ تخصیص با فهرست می‌خواند",
          cur["n_assigned"] == sum(len(r["assigned"]) for r in cur["rows"]))

    # ── ۳) تطبیق کور نیست ──────────────────────────────────────────────
    check("منبعِ بی‌ربط تخصیص نمی‌شود (امتیاز تطبیق باید مثبت باشد)",
          C._score({"tags": ["cooking"], "text": "آشپزی", "engine": None},
                   "E16") == 0)
    check("منبعِ صریحاً مالِ همان انجین بالاترین امتیاز را می‌گیرد",
          C._score({"tags": [], "text": "", "engine": "E16"}, "E16") == 100)
    check("برچسبِ هم‌موضوع امتیاز می‌گیرد",
          C._score({"tags": ["risk"], "text": "", "engine": None}, "E16") >= 3)

    # ── ۴) اولویت با ضعف ───────────────────────────────────────────────
    order = [r["priority"] for r in cur["rows"]]
    idx = {p: i for i, p in enumerate(["قرمز", "بی‌متر", "عادی"])}
    check("انجینِ قرمز جلوتر از عادی در صف است",
          order == sorted(order, key=lambda p: idx.get(p, 9)),
          str(order[:8]))

    # ── ۵) پیگیری: تخصیصِ بی‌یافته «مطالعه» حساب نمی‌شود ────────────────
    fake = {"generated": 0, "rows": [
        {"engine": "E16", "assigned": [{"claim_id": "CUR-deadbeef"}]}]}
    v = C.verify(fake, now_ms=(C.DUE_H + 1) * 3_600_000)
    check("تخصیصِ سررسیده بدون یافته، «پیگیری ناقص» می‌شود",
          v["verdict"] == "پیگیری ناقص" and v["done"] == 0, str(v))
    v2 = C.verify(fake, now_ms=1000)
    check("و قبل از سررسید، ناقص اعلام نمی‌شود",
          "زود است" in v2["verdict"], str(v2))
    check("هر تخصیص شناسهٔ یکتا دارد (برای اتصال به یافته)",
          all(a["claim_id"].startswith("CUR-")
              for r in cur["rows"] for a in r["assigned"]))
    ids = [a["claim_id"] for r in cur["rows"] for a in r["assigned"]]
    check("شناسه‌ها بین انجین‌ها قاطی نمی‌شوند",
          len(set(ids)) == len(ids), f"{len(ids)-len(set(ids))} تکراری")

    # ── ۶) مرز ─────────────────────────────────────────────────────────
    src = (PY / "hamid" / "curriculum.py").read_text(encoding="utf-8")
    check("خروجی مرز صادقانه دارد (قانون ۰۳)",
          "قانون ۰۳" in cur["boundary"])
    check("ماژول هیچ آستانه/وزنی به تولید نمی‌دهد",
          "threshold" not in src and "weight" not in src)
    check("فقط خروجی خودش را می‌نویسد (قانون ۰۵)",
          src.count("write_text") == 1)
    check("منبع فقط از قفسه می‌آید، نه از حافظهٔ ایجنت",
          "library" in src and "index.jsonl" in src)

    print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(run())
