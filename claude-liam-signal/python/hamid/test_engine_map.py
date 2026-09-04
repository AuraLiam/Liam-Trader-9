"""پاسبان نقشهٔ انجین‌ها — نقشه باید از کد بیاید، نه از حافظه.

عیبی که می‌بندد: سندِ دست‌نویسِ معماری روزِ بعد کهنه می‌شود و کسی
نمی‌فهمد. این نقشه از `config/state_registry.json` + سورسِ تولیدکننده‌ها
ساخته می‌شود، پس با کد هم‌قدم می‌ماند.

و یک قید صداقت: انجینی که فایل وضعیت ندارد باید **در نقشه بماند** و
«بی‌ردپا» علامت بخورد — حذفش از نقشه یعنی پنهان‌کردنِ شکافِ اندازه‌گیری.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
sys.path.insert(0, str(PY))
from hamid import engine_map as M                             # noqa: E402

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
    m = M.build()
    ids = [e["id"] for e in m["engines"]]
    # شمار از خودِ نقشه می‌آید نه از عددِ دست‌نویس: عددِ ثابتِ ۲۷ وقتی E27
    # اضافه شد دروازهٔ زنجیرهٔ سیگنال را سرخ کرد و ساعت‌ها سیگنال نرفت.
    # حالا فقط پیوستگیِ شناسه‌ها سنجیده می‌شود: E00 تا E<n-1> بی‌حفره.
    check(f"شناسه‌های انجین بی‌حفره‌اند (E00..E{len(ids) - 1:02d})",
          ids == [f"E{i:02d}" for i in range(len(ids))], str(ids))
    check("و دست‌کم همان ۲۷ انجینِ پایه سر جایشان‌اند",
          len(ids) >= 27, str(len(ids)))
    check("ترتیب مرتب است (E00..E26)", ids == sorted(ids))
    check("هیچ شناسه‌ای تکراری نیست", len(set(ids)) == len(ids))
    check("همهٔ انجین‌ها جملهٔ «چه پایش می‌کند» دارند",
          all(e["watches"] and e["watches"] != "—" for e in m["engines"]),
          str([e["id"] for e in m["engines"] if e["watches"] == "—"]))
    check("انجینِ بی‌فایل از نقشه حذف نمی‌شود، برچسب می‌خورد",
          m["n_traceless"] > 0
          and all(e["files"] == [] for e in m["engines"] if e["traceless"]))
    tr = {e["id"] for e in m["engines"] if e["traceless"]}
    # ۲ سپتامبر: E15 با اتاق فومو (signals/fomo.json) ردپا گرفت — هفت شد شش.
    # این مجموعه فقط حق دارد کوچک شود؛ انجین تازه‌ای که بی‌ردپا شود سرخ می‌کند.
    check("همان شش انجینِ بی‌ردپای ممیزی (E15 از ۲ سپتامبر ردپا دارد)",
          tr == {"E04", "E05", "E07", "E09", "E13", "E24"}, str(tr))

    withf = [e for e in m["engines"] if not e["traceless"]]
    check("هر انجینِ فایل‌دار مصرف‌کننده دارد",
          all(e["consumers"] != ["—"] for e in withf))
    check("هر انجینِ فایل‌دار تولیدکننده دارد",
          all(e["producers"] for e in withf))
    check("منبع بیرونی از خودِ سورس استخراج می‌شود",
          any("binance" in s for e in m["engines"] for s in e["sources"]),
          "هیچ میزبانی پیدا نشد")
    e01 = next(e for e in m["engines"] if e["id"] == "E01")
    check("گشت چند-صرافی واقعاً چند میزبان دارد",
          len(e01["sources"]) >= 4, str(e01["sources"]))
    check("انجینِ بی‌منبعِ بیرونی صریح «داخلی» می‌گوید",
          any(s.startswith("داخلی") for e in m["engines"] for s in e["sources"]))
    check("شمار فایل‌ها با قرارداد می‌خواند",
          m["n_files"] == sum(len(e["files"]) for e in m["engines"]),
          f"{m['n_files']} در برابر {sum(len(e['files']) for e in m['engines'])}")

    print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(run())
