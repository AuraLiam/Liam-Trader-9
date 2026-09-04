"""پاسبان میز پامپ (۴ سپتامبر) — آفلاین، بدون شبکه، قطعی.

قفل می‌کند دستور حمید: تاریخچهٔ ارز از روز اول · همراهان و پیش‌روها ·
پایش تاپ گینرز · و مهم‌ترینش: «تا وقتی آن ارز در صدر تاپ گینرز است
نیازی نیست هر لحظه گزارش پامپ بفرستد».
"""
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from hamid import pump_desk as PD                    # noqa: E402

OK = 0
FAIL = []
NOW = 1_800_000_000_000
H = 3_600_000
DAY = 86_400_000


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


HIST = {"symbols": {
    "AAAUSDT": {"events": [
        {"t": NOW - 30 * DAY, "ret_4h_pct": 12.0, "vol_z": 6.0},
        {"t": NOW - 20 * DAY, "ret_4h_pct": 31.0, "vol_z": 9.0},
        {"t": NOW - 5 * DAY, "ret_4h_pct": 18.0, "vol_z": 7.0}]},
    "BBBUSDT": {"events": [
        {"t": NOW - 30 * DAY + 2 * H, "ret_4h_pct": 9.0},     # همراه
        {"t": NOW - 20 * DAY + 3 * H, "ret_4h_pct": 11.0}]},  # همراه
    "CCCUSDT": {"events": [
        {"t": NOW - 30 * DAY - 4 * H, "ret_4h_pct": 7.0},     # پیش‌رو
        {"t": NOW - 5 * DAY - 6 * H, "ret_4h_pct": 8.0}]},    # پیش‌رو
    "ZZZUSDT": {"events": [{"t": NOW - 300 * DAY, "ret_4h_pct": 5.0}]},
}}

# ── ۱. تاریخچه از اولین رویدادِ دفتر ────────────────────────────────────
h = PD.history("AAAUSDT", HIST, NOW)
check("همهٔ پامپ‌های ثبت‌شده شمرده می‌شوند، نه پنجرهٔ چندهفته‌ای", h["n"] == 3, str(h["n"]))
check("اولین و آخرین پامپ با تاریخ تهران گزارش می‌شوند",
      h["first_when"] and h["last_when"] and ":" in h["first_when"])
check("بازهٔ کل تاریخچه عدد دارد", h["span_days"] == 25.0, str(h["span_days"]))
check("بزرگ‌ترین پامپ و تاریخش نام برده می‌شود",
      h["ret_max_pct"] == 31.0 and h["biggest_when"], str(h["ret_max_pct"]))
check("میانهٔ بازده و حجم از عدد واقعی می‌آید",
      h["ret_median_pct"] == 18.0 and h["vol_z_median"] == 7.0, str(h))
check("فاصلهٔ معمول بین پامپ‌ها شمرده می‌شود", h["gap_median_days"] == 12.5,
      str(h["gap_median_days"]))
check("ساعت معمولِ پامپ به وقت تهران گزارش می‌شود",
      isinstance(h["typical_hour_tehran"], int) and 0 <= h["typical_hour_tehran"] <= 23)
check("زمان از آخرین پامپ عدد دارد", h["since_last_h"] == 120.0, str(h["since_last_h"]))
h0 = PD.history("NOSUCHUSDT", HIST, NOW)
check("ارز بی‌سابقه، تاریخچهٔ جعلی نمی‌گیرد", h0["n"] == 0 and h0.get("why"))
check("و مرزش صریح گفته می‌شود (دفتر ندیده ≠ رخ نداده)",
      "دفتر ندیده" in h0["why"], h0["why"])
check("«از روز اول» صادقانه تعریف شده", "پیدایش ارز" in h["boundary"])

# ── ۲. همراهان و پیش‌روها ───────────────────────────────────────────────
c = PD.cohort("AAAUSDT", HIST)
withs = {x["symbol"]: x["times"] for x in c["with"]}
befores = {x["symbol"]: x["times"] for x in c["before"]}
check("ارزی که در پنجرهٔ ۲۴ ساعته با آن پامپ شد، همراه شمرده می‌شود",
      withs.get("BBBUSDT") == 2, str(withs))
check("ارزی که قبلش حرکت کرد، پیش‌رو شمرده می‌شود",
      befores.get("CCCUSDT") == 2, str(befores))
check("ارزِ بی‌ربطِ ۳۰۰ روز پیش نه همراه است نه پیش‌رو",
      "ZZZUSDT" not in withs and "ZZZUSDT" not in befores)
check("سهم درصدی از تعداد رویدادها حساب می‌شود",
      c["with"][0]["share_pct"] == round(100 * 2 / 3, 1), str(c["with"][0]))
check("مرز صریح است: هم‌زمانی، نه علیت", "علیت" in c["boundary"])
check("ارز بی‌رویداد، همراه جعلی نمی‌سازد",
      PD.cohort("NOSUCHUSDT", HIST)["with"] == [])

# ── ۳. پایش تاپ گینرز ───────────────────────────────────────────────────
g = PD.gainers_watch([{"symbol": f"S{i}USDT", "change_pct": 50 - i,
                       "top_age_h": i * 1.0} for i in range(8)])
check("رتبه از یک شروع می‌شود", g[0]["rank"] == 1)
check("فقط پنج ردیف اول «در صدر» حساب می‌شوند",
      sum(1 for x in g if x["in_top"]) == PD.TOP_N, str(sum(1 for x in g if x["in_top"])))
check("سن حضور در صدر همراه هر ردیف می‌آید", g[3]["top_age_h"] == 3.0)
check("ردیف بی‌نماد کنار گذاشته می‌شود",
      PD.gainers_watch([{"change_pct": 10}, {"symbol": "XUSDT"}])[0]["symbol"] == "XUSDT")

# ── ۴. ضدتکرار — قلبِ دستور ─────────────────────────────────────────────
ok, why = PD.should_report("AAAUSDT", 50.0, True, 3, {}, NOW)
check("اولین گزارش می‌رود", ok is True and "اولین" in why)

st = PD.mark_reported("AAAUSDT", 50.0, True, 3, {}, NOW, save=False)
ok, why = PD.should_report("AAAUSDT", 52.0, True, 3, st, NOW + 2 * H)
check("همان ارز، همان داستان، هنوز در صدر → گزارش تکراری نمی‌رود",
      ok is False, f"{ok} — {why}")
check("و دلیل سکوت صریح نوشته می‌شود (نه سکوتِ بی‌توضیح)",
      "هنوز در صدر" in why and "تکراری" in why, why)

ok, why = PD.should_report("AAAUSDT", 70.0, True, 3, st, NOW + 2 * H)
check("ولی جهشِ معنادار رشد، خبر تازه است",
      ok is True and "داستان عوض شد" in why, why)
ok, why = PD.should_report("AAAUSDT", 52.0, True, 4, st, NOW + 2 * H)
check("ایمپالس تازه هم خبر تازه است", ok is True and "ایمپالس تازه" in why, why)

st_out = PD.mark_reported("AAAUSDT", 50.0, False, 3, {}, NOW, save=False)
ok, why = PD.should_report("AAAUSDT", 50.0, True, 3, st_out, NOW + 2 * H)
check("بیرون رفتن از صدر و برگشتن، خبر تازه است",
      ok is True and "برگشت" in why, why)

ok, why = PD.should_report("AAAUSDT", 52.0, True, 3, st, NOW + 13 * H)
check("سکوتِ بی‌پایان هم درست نیست — بعد از سقف، یادآوری می‌رود",
      ok is True and "یادآوری" in why, why)
ok, why = PD.should_report("AAAUSDT", 52.0, True, 3, st, NOW + 11 * H)
check("ولی درست قبل از سقف هنوز ساکت است", ok is False, why)
ok, why = PD.should_report("AAAUSDT", 50.0, False, 3, st, NOW + 2 * H)
check("ارزی که از صدر بیرون است هم بی‌خبر تازه گزارش نمی‌گیرد", ok is False, why)
check("آستانه‌ها روی خودِ ماژول‌اند، نه پراکنده",
      PD.TOP_N == 5 and PD.MOVE_PCT == 15.0 and PD.MAX_SILENCE_H == 12.0)

# ثبت روی دیسک
with tempfile.TemporaryDirectory() as td:
    p = Path(td) / "reported.json"
    PD.mark_reported("AAAUSDT", 50.0, True, 3, {}, NOW, path=p)
    on_disk = json.loads(p.read_text(encoding="utf-8"))
    check("وضعیت گزارش روی دیسک می‌ماند (بین دو اجرا فراموش نمی‌شود)",
          on_disk["AAAUSDT"]["change_pct"] == 50.0 and on_disk["AAAUSDT"]["t"] == NOW)
    check("و لحظهٔ گزارش به وقت تهران هم ثبت می‌شود", ":" in on_disk["AAAUSDT"]["when"])
    st2 = PD.mark_reported("BBBUSDT", 20.0, True, 1, on_disk, NOW + H, path=p)
    check("ارز دوم ردیف خودش را می‌گیرد و اولی پاک نمی‌شود",
          set(json.loads(p.read_text(encoding="utf-8"))) == {"AAAUSDT", "BBBUSDT"})

# ── ۵. تابلو ────────────────────────────────────────────────────────────
radar = {"gainers": [{"symbol": "AAAUSDT", "change_pct": 60.0, "top_age_h": 3.0},
                     {"symbol": "BBBUSDT", "change_pct": 30.0, "top_age_h": 1.0}]}
b = PD.build(radar, HIST, {}, NOW)
check("تابلو برای هر صدرنشین کارت می‌سازد", len(b["cards"]) == 2)
check("هر کارت تاریخچه و همراهان دارد",
      all("history" in c and "cohort" in c for c in b["cards"]))
check("و تصمیم ارسال با دلیلش",
      all(isinstance(c["report_now"], bool) and c["report_why"] for c in b["cards"]))
check("شمارِ لازم و ساکت با کارت‌ها می‌خواند",
      b["counts"]["due"] + b["counts"]["silenced"] == len(b["cards"]))
st3 = {c["symbol"]: {"t": NOW, "in_top": True, "change_pct": c["change_pct"],
                     "pump_n": c["history"]["n"]} for c in b["cards"]}
b2 = PD.build(radar, HIST, st3, NOW + H)
check("بار دوم، بی‌خبر تازه، همه ساکت‌اند — دقیقاً دستور حمید",
      b2["counts"]["due"] == 0 and b2["counts"]["silenced"] == 2, str(b2["counts"]))
check("و دلیلِ سکوت با وضعیتِ واقعی می‌خواند (صدرنشین باید بگوید «در صدر»)",
      all("در صدر" in c["report_why"] for c in b2["cards"] if c["in_top"]),
      str([c["report_why"] for c in b2["cards"]]))
check("مالک تابلو E12 است", b["engine"] == "E12")
check("قواعد ضدتکرار روی تابلو اعلام می‌شوند", b["rules"]["top_n"] == PD.TOP_N)
check("مرز روی تابلو نوشته می‌شود",
      "نمی‌فرستد" in b["boundary"] and "قانون ۰۷" in b["boundary"])

# ── ۶. مرز در کد ────────────────────────────────────────────────────────
src = (HERE / "pump_desk.py").read_text(encoding="utf-8")
for bad in ("sendMessage", "requests.post", "urlopen", "TELEGRAM"):
    check(f"میز پامپ «{bad}» ندارد — خودش چیزی نمی‌فرستد", bad not in src)

# ── ۷. سیم‌کشی ──────────────────────────────────────────────────────────
ROOT = HERE.parents[2]
reg = json.loads((ROOT / "config" / "state_registry.json").read_text(encoding="utf-8"))["files"]
check("pump-desk.json ردیف قرارداد دارد (قانون ۱۳)",
      "pump-desk.json" in reg and reg["pump-desk.json"]["producer"] == "hamid/pump_desk.py",
      str(reg.get("pump-desk.json")))
wf = (ROOT / ".github" / "workflows" / "pump-review.yml").read_text(encoding="utf-8")
check("نوبت پامپ میز را می‌سازد", "hamid.pump_desk --write" in wf)

print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
sys.exit(1 if FAIL else 0)
