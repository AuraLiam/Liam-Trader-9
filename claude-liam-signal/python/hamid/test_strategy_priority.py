"""پاسبان ترجیح استراتژی — دستور حمید ۳۰ اوت شب: «تا فردا همون مدل ترید کنه».

ارز یونی با `smc|UNIUSDT|5m|LONG` صادر شده بود و حمید خواست همان مدل
اولویت بگیرد، **بدون بستن ibs**.

چهار خطری که این آزمون می‌بندد — هر چهار، کلاسِ عیب‌اند نه یک مورد:

۱. **ترجیح به دروازه تبدیل شود.** اگر روزی کسی از این کلید برای خاموش
   کردن یک استراتژی یا جابه‌جا کردن آستانه استفاده کند، دیگر «ترتیب»
   نیست — شل‌کردن دروازه است.
۲. **ترجیحِ بی‌سنجش، سنجهٔ اثبات‌شده را کنار بزند.** رتبهٔ تایم‌فریم از
   بک‌تست کندل واقعی آمده (۵د CI بالای صفر، ۱۵د نه). ترجیحی که پشتش CI
   نیست حق ندارد جلوترش بنشیند.
۳. **ترجیح ابدی شود.** بدون سررسید، یک دستورِ «تا فردا» می‌تواند ماه‌ها
   بماند و هیچ‌کس نفهمد — همان کلاسِ «تورِ ایمنیِ همیشه‌روشن» که ۳۰ اوت
   صبح پیدا شد.
۴. **بی‌صدا کار کند.** ترجیحی که روی خروجی دیده نشود، در ممیزی بعدی
   غافلگیری است.
"""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
ROOT = PY.parents[1]
sys.path.insert(0, str(PY))

import scan                                                   # noqa: E402

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


def sort_key(setups, pref):
    """همان کلیدِ مرتب‌سازی scan.py — این‌جا اجرایی، تا رفتارش سنجیده شود."""
    setups = list(setups)
    setups.sort(key=lambda s: (scan.STAGE_RANK.get(s["stage"], 0),
                               scan.TF_RANK.get(s["tf"], 0),
                               1 if (pref and s.get("strategy") == pref) else 0,
                               (s.get("learned") or {}).get("boost", 0.0),
                               s["conf"] or 0, s["ev"] or 0), reverse=True)
    return setups


def s(strategy, stage="SIGNAL", tf="5m", conf=50, ev=0.1):
    return {"strategy": strategy, "stage": stage, "tf": tf,
            "conf": conf, "ev": ev, "sym": f"{strategy}-{stage}-{tf}"}


def run():
    now = int(time.time() * 1000)

    # ── ۱) پیکربندی: هست، معتبر، و سررسید دارد ───────────────────────────
    cfg_path = ROOT / "config" / "strategy_priority.json"
    check("فایل ترجیح وجود دارد", cfg_path.exists())
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    check("استراتژی مرجَح یکی از استراتژی‌های شناخته‌شده است",
          cfg.get("prefer") in scan.STRATS, str(cfg.get("prefer")))
    check("ترجیح سررسید عددی دارد (ابدی نیست)",
          isinstance(cfg.get("until"), (int, float)), str(cfg.get("until")))
    # ⚠️ کلاسِ عیبِ ۱ سپتامبر — این بررسی، خودش زنجیرهٔ سیگنال را کشت.
    #
    # نسخهٔ قبلی شرط می‌گذاشت سررسید **در آینده** باشد. ترجیحِ smc دقیقاً
    # طبق طراحی ساعت ۲۰:۲۹ UTC سررسید شد، محافظ قرمز شد، و چون در دروازهٔ
    # سختِ زنجیره بود، حلقهٔ ۵دقیقه‌ای skip شد و latest/funnel/system-state
    # و بقیه کهنه ماندند. یعنی یک محافظ، به‌خاطر اینکه **وضعیتِ گذرا** را
    # ثابت فرض کرده بود، تولید را خواباند.
    #
    # قاعدهٔ کلاس: محافظ باید **ناوردا** را بسنجد نه مقدارِ لحظه‌ای یک
    # وضعیتِ منقضی‌شونده. ناوردای درست این است: سررسید یا در آینده است
    # (حداکثر ۷ روز — ابدی نیست)، یا گذشته و آن‌وقت موتور خودبه‌خود
    # خنثی شده. هر دو حالت سالم‌اند؛ آنچه سالم نیست ترجیحِ بی‌سررسید است.
    left_h = round((cfg["until"] - now) / 3600000, 1)
    expired_now = cfg["until"] <= now
    check("سررسید یا در آیندهٔ معقول است یا گذشته و خنثی شده",
          expired_now or 0 < (cfg["until"] - now) <= 7 * 86400000,
          f"{left_h} ساعت مانده")
    check("کارنامهٔ عددی دو استراتژی روی خودِ پیکربندی ثبت است",
          isinstance(cfg.get("evidence"), dict)
          and "smc_ci" in cfg["evidence"] and "ibs_ci" in cfg["evidence"])
    check("مرزِ ترجیح صریح نوشته شده (فقط ترتیب)",
          "ترتیب" in str(cfg.get("scope", "")), str(cfg.get("scope"))[:80])

    # ── ۲) بارگذاری و سررسید ─────────────────────────────────────────────
    pref, note = scan.strategy_priority(now)
    # همان کلاس: «فعال بودن» وضعیتِ گذراست. ناوردا این است که موتور و
    # فایل **یک چیز بگویند** — فعال با همان استراتژی، یا خنثی با دلیل.
    if expired_now:
        check("ترجیح سررسیده، خنثی و بادلیل گزارش می‌شود",
              pref is None and note.get("expired") is True and "why" in note,
              str(note))
    else:
        check("ترجیح فعال با همان استراتژیِ فایل گزارش می‌شود",
              pref == cfg["prefer"] and note["active"], str(note))
    p2, n2 = scan.strategy_priority(cfg["until"] + 1)
    check("بعد از سررسید خودبه‌خود خنثی می‌شود (ابدی نمی‌ماند)",
          p2 is None and n2.get("expired") is True, str(n2))
    check("و دلیلِ خنثی‌شدن نوشته می‌شود، نه سکوت", "why" in n2)

    # ── ۳) رفتار رتبه‌بندی — قلبِ ماجرا ──────────────────────────────────
    both = [s("ibs"), s("smc")]
    check("در شرایط برابر، smc اول می‌آید",
          sort_key(both, "smc")[0]["strategy"] == "smc")
    check("بدون ترجیح، ترتیبِ قبلی برمی‌گردد (ibs جلو نمی‌افتد بی‌دلیل)",
          [x["strategy"] for x in sort_key(both, None)]
          == [x["strategy"] for x in sort_key(both, None)])

    # مرحله بر ترجیح مقدم است — WATCH smc نباید از SIGNAL ibs جلو بزند
    mix = [s("smc", stage="WATCH"), s("ibs", stage="SIGNAL")]
    check("مرحله بر ترجیح مقدم است (WATCH smc از SIGNAL ibs جلو نمی‌زند)",
          sort_key(mix, "smc")[0]["stage"] == "SIGNAL",
          str([(x["strategy"], x["stage"]) for x in sort_key(mix, "smc")]))

    # تایم‌فریمِ سنجیده‌شده بر ترجیحِ بی‌سنجش مقدم است
    tfmix = [s("smc", tf="15m"), s("ibs", tf="5m")]
    check("تایم‌فریمِ CI-دار بر ترجیحِ بی‌CI مقدم است (۵د ibs جلوتر از ۱۵د smc)",
          sort_key(tfmix, "smc")[0]["tf"] == "5m",
          str([(x["strategy"], x["tf"]) for x in sort_key(tfmix, "smc")]))

    # ── ۴) ibs بسته نمی‌شود — نه در کد، نه در پیکربندی ───────────────────
    src = (PY / "scan.py").read_text(encoding="utf-8")
    check("هر دو استراتژی هنوز در فهرست فعال‌اند",
          set(scan.STRATS) == {"smc", "ibs"}, str(set(scan.STRATS)))
    for bad in ("disable", "only_strategy", "exclude_strategy"):
        check(f"ترجیح به دروازه تبدیل نشده (بدون «{bad}»)",
              bad not in json.dumps(cfg, ensure_ascii=False))
    check("ترجیح هیچ آستانه‌ای را دست نمی‌زند (فقط داخل کلید مرتب‌سازی)",
          src.count("s.get(\"strategy\") == pref") == 1,
          "ترجیح جای دیگری هم اثر گذاشته — باید فقط رتبه‌بندی باشد")

    # ── ۵) ترتیبِ کلید در **خودِ کد**، نه در بازنویسیِ آزمون ──────────────
    # اثبات منفی اولِ همین آزمون این ضعف را نشان داد: بالا کلیدِ مرتب‌سازی
    # بازنویسی شده بود، پس جابه‌جا کردنِ ترتیب در scan.py را نمی‌گرفت.
    # حالا ترتیبِ واقعیِ سه جمله از خودِ منبع خوانده می‌شود.
    key_src = src.split("setups.sort(key=lambda s:", 1)[1].split("reverse=True")[0]
    i_stage = key_src.find("STAGE_RANK")
    i_tf = key_src.find("TF_RANK")
    i_pref = key_src.find('s.get("strategy") == pref')
    check("هر سه جملهٔ رتبه در کلیدِ واقعی هستند",
          min(i_stage, i_tf, i_pref) >= 0, f"stage={i_stage} tf={i_tf} pref={i_pref}")
    check("در کدِ واقعی: مرحله قبل از ترجیح است",
          0 <= i_stage < i_pref, f"stage={i_stage} pref={i_pref}")
    check("در کدِ واقعی: تایم‌فریمِ CI-دار قبل از ترجیحِ بی‌CI است",
          0 <= i_tf < i_pref, f"tf={i_tf} pref={i_pref}")

    # ── ۶) دیده می‌شود ───────────────────────────────────────────────────
    check("ترجیح فعال روی خروجی اسکن چاپ می‌شود",
          '"strategy_priority": pref_note' in src)

    print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(run())
