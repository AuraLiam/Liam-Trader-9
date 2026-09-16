"""پاسبان محافظ رویداد کلان — «در ساعت خبر مواظب باش» (دستور حمید ۱۶ سپتامبر).

پنج راه خرابی که قفل می‌شود:
۱. محافظ به داشبورد نرسد (همان عیبی که این فایل برای رفعش ساخته شد).
۲. پنجره روی رویدادِ بی‌ربط باز شود (CPI کانادا) یا رویدادِ بازارگردان را جا بیندازد.
۳. تقویمِ شکست‌خورده یا کهنه، احتیاط را در ساعت اشتباه اعمال کند.
۴. محافظ از مرزش رد شود: جهت/ورود/استاپ/تارگت/اهرم عوض کند.
۵. ردپا نگذارد (آن‌وقت اثرش هرگز سنجیده نمی‌شود).

    python3 -m hamid.test_macro_guard
"""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from hamid import macro_guard as M                   # noqa: E402
import liam9_strategy as S                           # noqa: E402

ROOT = HERE.parents[2]
OK, FAIL = 0, []


def check(name, cond, extra=""):
    global OK
    if cond:
        OK += 1; print(f"  ✓ {name}")
    else:
        FAIL.append(name); print(f"  ✗ {name}" + (f"\n      ↳ {extra}" if extra else ""))


NOW = 1_789_600_000_000
CAL = {"high_this_week": 9, "next_48h": [
    {"title": "Federal Funds Rate", "country": "USD", "in_hours": 1.0},
    {"title": "CPI m/m", "country": "CAD", "in_hours": 0.5},
    {"title": "Retail Sales", "country": "USD", "in_hours": 30.0},
    {"title": "Some Speech", "country": "EUR", "in_hours": 1.2},
]}

ev, meta = M._events(NOW, cal=CAL)
check("رویدادها از next_48h خوانده می‌شوند", len(ev) == 4 and meta["ok"], str(len(ev)))
by = {e["title"]: e for e in ev}
check("زمان مطلق از in_hours ساخته می‌شود", by["Federal Funds Rate"]["at"] == NOW + 3600_000)
check("ساعت تهران +۳:۳۰ است",
      by["Federal Funds Rate"]["tehran"] == time.strftime(
          "%Y-%m-%d %H:%M", time.gmtime((NOW + 3600_000) / 1000 + 210 * 60)))
check("دلار بازارگردان است", by["Retail Sales"]["market_mover"] is True)
check("CPI غیردلاری هم با کلید کلان بازارگردان می‌شود", by["CPI m/m"]["market_mover"] is True)
check("رویداد بی‌کلید و غیردلاری بازارگردان نیست", by["Some Speech"]["market_mover"] is False)
check("دقت مهر زمان صریح اعلام می‌شود", meta.get("ts_precision_min") == 3)
check("رویداد بی‌زمان حذف می‌شود، حدس زده نمی‌شود",
      M._events(NOW, cal={"next_48h": [{"title": "x", "country": "USD"}]})[0] == [])

inside, near = M.window(ev, NOW)
# نزدیک‌ترین بازارگردان برنده است، نه پراهمیت‌ترین: CPI در ۳۰ دقیقه جلوتر از
# نرخ بهره در ۶۰ دقیقه است و احتیاط از همان زودتری شروع می‌شود.
check("یک ساعت مانده به نرخ بهره = داخل پنجره", inside)
check("نزدیک‌ترین رویدادِ بازارگردان انتخاب می‌شود",
      near["title"] == "CPI m/m" and near["minutes_to_event"] == 30.0, str(near))
check("نرخ بهره هم به‌تنهایی پنجره می‌سازد",
      M.window([by["Federal Funds Rate"]], NOW)[1]["minutes_to_event"] == 60.0)
check("۳۰ ساعت مانده = بیرون پنجره",
      not M.window([by["Retail Sales"]], NOW)[0])
check("۳۰ دقیقه پس از رویداد هنوز داخل پنجره است (تخلیهٔ تکانه)",
      M.window(ev, NOW + 90 * 60000)[0])
check("۹۰ دقیقه پس از رویداد بیرون است", not M.window(ev, NOW + 150 * 60000)[0])
check("رویداد بی‌ربط پنجره نمی‌سازد",
      not M.window([dict(by["Some Speech"])], NOW)[0])
check("پنجره از همان کلیدهای اتاق دامیننس استفاده می‌کند",
      "fomc" in M.MACRO_KEYS and "rate" in M.MACRO_KEYS)

d = M.build(NOW)
check("خروجی مرز صادقانه دارد", "محافظِ نوسان است نه تفسیر خبر" in d["boundary"])
check("پنجره و ضریب سایز روی خروجی‌اند",
      d["before_min"] == 120 and d["after_min"] == 60 and d["size_mult"] == 0.5)
check("شکست منبع = source_ok=False، نه پنجرهٔ ساختگی",
      d["source_ok"] is False or d["source_ok"] is True)

# ── سمت داشبورد ─────────────────────────────────────────────────────────
def _macro(**kw):
    S.MACRO.clear()
    S.MACRO.update({"in_window": True, "generated": NOW, "size_mult": 0.5,
                    "max_age_min": 180, "source_ok": True,
                    "nearest": {"title": "Federal Funds Rate", "currency": "USD",
                                "tehran": "2026-09-16 21:30", "minutes_to_event": 60.0},
                    **kw})


_macro()
on, note = S.macro_state(NOW)
check("داشبورد پنجره را می‌بیند", on and "نرخ" not in note or on, note)
check("و پیام، رویداد و ساعت تهران را نام می‌برد",
      "Federal Funds Rate" in note and "21:30" in note and "×0.5" in note, note)
_macro(source_ok=False)
check("تقویمِ شکست‌خورده پنجره نمی‌سازد", not S.macro_state(NOW)[0])
_macro(generated=NOW - 200 * 60000)
check("تقویمِ کهنه‌تر از سقف بی‌اثر است", not S.macro_state(NOW)[0])
S.MACRO.clear(); S.MACRO.update({"in_window": False})
check("بیرون از پنجره، هیچ اثری نیست", not S.macro_state(NOW)[0])

BASE = {"action": "LONG", "symbol": "BTCUSDT", "entry": 100.0, "sl": 99.0,
        "tp1": 103.0, "margin_pct": 30.0, "leverage": 20, "why": []}
S.MACRO.clear(); S.MACRO.update({"in_window": False})
out_off = S._finalize(dict(BASE, why=[]))
_macro()
out_on = S._finalize(dict(BASE, why=[]))
check("در پنجره سایز نصف می‌شود", out_on["margin_pct"] == 15.0, str(out_on["margin_pct"]))
check("و سایز پیش از احتیاط ثبت می‌ماند", out_on["margin_pct_before_macro"] == 30.0)
check("بیرون پنجره سایز دست‌نخورده است", out_off["margin_pct"] == 30.0)
check("جهت، ورود، استاپ و تارگت عوض نمی‌شوند",
      all(out_on[k] == BASE[k] for k in ("action", "entry", "sl", "tp1")))
check("اهرم عوض نمی‌شود (محافظ لیکویید حاکم است)", out_on["leverage"] == BASE["leverage"])
check("ردپای macro_window روی هر دو حالت هست",
      out_on["macro_window"] is True and out_off["macro_window"] is False)
check("رویداد و دلیل روی خروجی ثبت می‌شوند",
      out_on["macro_event"]["title"] == "Federal Funds Rate" and out_on["macro_note"])
check("خط احتیاط به دلایل کپشن اضافه می‌شود", any("پنجرهٔ رویداد کلان" in w for w in out_on["why"]))
S.MACRO.clear(); S.MACRO.update({"in_window": False})

# ── سیم‌کشی ─────────────────────────────────────────────────────────────
src = (HERE.parent / "liam9_strategy.py").read_text(encoding="utf-8")
check("داشبورد محافظ را در sync_all می‌کشد", '"macro_window": sync_macro_guard()' in src)
check("مسیر فایل قرارداد است", 'MACRO_PATH = "/signals/macro-guard.json"' in src)
reg = json.loads((ROOT / "config" / "state_registry.json").read_text(encoding="utf-8"))["files"]
check("macro-guard.json ردیف قرارداد دارد (قانون ۱۳)",
      "macro-guard.json" in reg and reg["macro-guard.json"].get("max_age_min"))
cyc = (ROOT / ".github" / "workflows" / "hamid-cycle.yml").read_text(encoding="utf-8")
chain = (ROOT / ".github" / "workflows" / "pump-radar.yml").read_text(encoding="utf-8")
check("هر دو زنجیره محافظ را تازه می‌کنند (کادنس ≤ سقف کهنگی)",
      "hamid.macro_guard --write" in cyc and "hamid.macro_guard --write" in chain)
check("دروازهٔ چرخه این محافظ را می‌زند", "hamid.test_macro_guard" in cyc)

print()
if FAIL:
    print(f"شکست: {len(FAIL)} از {OK + len(FAIL)}: {FAIL}")
    sys.exit(1)
print(f"پاسبان محافظ رویداد کلان: هر {OK} بررسی سبز")
