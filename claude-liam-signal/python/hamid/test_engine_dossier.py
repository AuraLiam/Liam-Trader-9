"""پاسبان پروندهٔ انجین‌ها — نقشهٔ ناقص بد است، نقشهٔ دروغ بدتر.

این پرونده چیزی است که حمید با آن **بررسی** می‌کند، پس دو خطر دارد:

۱. یالِ جعلی در گراف («می‌دهد به») — اگر الگوی جست‌وجو شل باشد، انجینی
   که فقط اسمِ شبیهی در سورسش دارد مصرف‌کننده شمرده می‌شود و حمید بر
   پایهٔ ارتباطی که وجود ندارد تصمیم می‌گیرد.
۲. شکافِ پنهان‌شده — اگر «بی‌محافظ» یا «بی‌کارنامه» از قلم بیفتد، پرونده
   خوش‌بین‌تر از واقعیت می‌شود، که دقیقاً خلافِ کاری است که برایش ساخته شد.

پس این آزمون هر دو را قفل می‌کند، و روی دادهٔ **ساختگی** می‌سنجد تا با
عوض‌شدن ریپو بی‌معنا نشود.

اجرا: `python3 -m hamid.test_engine_dossier`
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
sys.path.insert(0, str(PY))

from hamid import engine_dossier as D                          # noqa: E402
from hamid import engine_map as M                              # noqa: E402

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
    m = D.build()
    eng = m["engines"]
    by = {e["id"]: e for e in eng}

    # ── ۱) پوشش: هیچ انجینی از پرونده نمی‌افتد ─────────────────────────
    check("همان مجموعهٔ انجین‌های نقشه پوشش داده می‌شود",
          {e["id"] for e in eng} >= set(M.WATCHES),
          str(set(M.WATCHES) - {e["id"] for e in eng}))
    check("هر انجین جملهٔ «چه پایش می‌کند» دارد",
          all(e["watches"] and e["watches"] != "—" for e in eng),
          str([e["id"] for e in eng if not e["watches"] or e["watches"] == "—"]))

    # ── ۲) شکاف‌ها پنهان نمی‌شوند ──────────────────────────────────────
    for e in eng:
        pass
    tl = [e for e in eng if e["traceless"]]
    check("هر انجینِ بی‌ردپا، شکافش را روی پرونده دارد",
          all(any("بی‌ردپا" in g for g in e["gaps"]) for e in tl),
          str([e["id"] for e in tl if not any("بی‌ردپا" in g for g in e["gaps"])]))
    ng = [e for e in eng if not e["guards"] and not e["traceless"]]
    check("هر انجینِ بی‌محافظ، شکافش را روی پرونده دارد",
          all(any("بی‌محافظ" in g for g in e["gaps"]) for e in ng),
          str([e["id"] for e in ng if not any("بی‌محافظ" in g for g in e["gaps"])]))
    st = [e for e in eng if any(f["stale"] for f in e["files"])]
    check("فایلِ کهنه‌تر از سقفِ قرارداد صریح علامت می‌خورد",
          all(any("کهنه" in g for g in e["gaps"]) for e in st))
    # «بی‌کارنامه» از ۳۱ اوت یعنی مترِ سنجیده ندارد (`scorecard`)، نه
    # این‌که امتیاز جایزه ندارد — جایزه فقط برای انجینِ روی-معامله ساخته
    # می‌شود و بیشتر انجین‌ها ذاتاً از آن راه نمره نمی‌گیرند.
    check("انجینِ بی‌شکاف، فهرست شکاف خالی دارد",
          all(e["gaps"] or (e["guards"] and not e["traceless"]
                            and (e.get("grade") or {}).get("verdict")
                            not in (None, "NO_METRIC")
                            and e["research_findings"] > 0
                            and not any(f["stale"] for f in e["files"]))
              for e in eng))
    check("هر انجین کارنامهٔ سنجیده‌اش را روی پرونده دارد",
          all(e.get("grade") for e in eng),
          str([e["id"] for e in eng if not e.get("grade")]))

    # ── ۳) گراف: یالِ بی‌پشتوانه ساخته نمی‌شود ─────────────────────────
    # هر مصرف‌کننده باید از راهِ یک فایلِ واقعی آمده باشد، نه از هوا.
    owners = {}
    import json
    reg = json.loads((D.ROOT / "config" / "state_registry.json")
                     .read_text(encoding="utf-8"))
    fmap = reg.get("files", reg)
    for fn, v in fmap.items():
        owners.setdefault(v.get("owner"), set()).add(fn)
    bad = []
    for e in eng:
        for up in e["upstream"]:
            if not (owners.get(up) or set()) & set(e["eats_files"]):
                bad.append((e["id"], up))
    check("هر یالِ «تغذیه از» به فایلِ واقعیِ همان انجین وصل است",
          not bad, str(bad[:5]))
    check("گراف جهت‌دار است: انجین مصرف‌کنندهٔ خودش نیست",
          all(e["id"] not in e["upstream"] and e["id"] not in e["downstream"]
              for e in eng))

    # ── ۴) تقارن گراف: اگر A از B می‌خورد، B به A می‌دهد ────────────────
    asym = [(e["id"], up) for e in eng for up in e["upstream"]
            if up in by and e["id"] not in by[up]["downstream"]]
    check("گراف متقارن است (تغذیهٔ A از B ⇔ خروجیِ B به A)",
          not asym, str(asym[:5]))

    # ── ۵) الگوی جست‌وجو سخت‌گیر است، نه شل ────────────────────────────
    src = (PY / "hamid" / "engine_dossier.py").read_text(encoding="utf-8")
    check("نامِ فایل فقط داخل رشتهٔ نقل‌قولی تطبیق داده می‌شود",
          "[\"']\" + re.escape(fn) + r\"[\"']" in src
          or '[\\"\']" + re.escape(fn)' in src, "الگوی شل = یالِ جعلی")
    check("آزمون‌ها از گرافِ مصرف بیرون‌اند (test_ اسکن نمی‌شود)",
          'f.name.startswith("test_")' in src)

    # ── ۶) واسطهٔ منبع صریح است، نه چسبیده ─────────────────────────────
    viasrc = [e for e in eng
              if any("sources.py" in s for s in e["sources_external"])]
    check("منبعِ کندل از راه sources.py صریح علامت می‌خورد",
          viasrc, "هیچ انجینی واسطهٔ sources را اعلام نکرد")
    check("و اسپات از پرپچوال جدا اعلام می‌شود",
          any("اسپات" in s for e in viasrc for s in e["sources_external"]))

    # ── ۷) مرز: پرونده فقط می‌خواند ────────────────────────────────────
    check("پرونده هیچ فایلی نمی‌نویسد (قانون ۰۵: یک نویسنده per دامنه)",
          "write_text" not in src and "open(" not in src.replace("json.loads", ""),
          "ماژول تحلیلی نباید وضعیت بنویسد")

    print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(run())
