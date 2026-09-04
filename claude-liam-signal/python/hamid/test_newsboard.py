"""پاسبان بورد خبر (۴ سپتامبر) — آفلاین، بدون شبکه، قطعی.

قفل می‌کند دستور حمید: بورد مشترکِ همهٔ اتاق‌ها · بخش درسِ هر واحد ·
نظر افراد مهم دربارهٔ ارز **با تاریخ خبر** · رویداد آینده **از یک روز
قبل** · و مرز قانون ۱۵: خبر فقط دیدگاه است، نه دروازه.
"""
import json
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from hamid import newsboard as NB                    # noqa: E402

OK = 0
FAIL = []
NOW = 1_800_000_000_000
H = 3_600_000


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


# ── ۱. دسته‌بندی ─────────────────────────────────────────────────────────
for title, cat in [
    ("Major DeFi protocol hacked for $40M", "هک و سوءاستفاده"),
    ("SEC approves spot ETF application", "قانون‌گذاری"),
    ("Fed holds rates as CPI cools", "کلان و نرخ بهره"),
    ("Binance to list new perpetual futures", "لیستینگ و صرافی"),
    ("Massive token unlock scheduled", "آنلاک و عرضه"),
    ("Bank announces partnership with chain", "پذیرش و شراکت"),
    ("Weather is nice today", "عمومی"),
]:
    check(f"دستهٔ «{title[:34]}…» = {cat}", NB.category(title) == cat, NB.category(title))

# ── ۲. نام ارز حدس زده نمی‌شود ──────────────────────────────────────────
check("ارز از تیتر درست بیرون می‌آید", NB.coins("BTC and ETH rally") == ["BTC", "ETH"],
      str(NB.coins("BTC and ETH rally")))
check("نام کامل هم به نماد نگاشت می‌شود",
      "BTC" in NB.coins("Bitcoin hits new high") and "SOL" in NB.coins("Solana surges"))
check("کلمهٔ بزرگ‌نوشتهٔ غیرارز، ارز خوانده نمی‌شود",
      NB.coins("SEC CEO ETF news") == [], str(NB.coins("SEC CEO ETF news")))
noisy = NB.coins("Live updates: Bitcoin ETFs take $731 million, their biggest day")
check("تیترِ Title Case هر کلمه‌اش ارز نمی‌شود (عیبِ اجرای اول)",
      noisy == ["BTC"], str(noisy))
check("نمادِ خارج از تاکسونومی وارد بورد نمی‌شود",
      NB.coins("ZZQQ token launches") == [], str(NB.coins("ZZQQ token launches")))

# ── ۳. گویندهٔ مهم ──────────────────────────────────────────────────────
check("نظر شخصیت مهم با نامش شناخته می‌شود",
      NB.voice("Powell says rates stay high") == "جروم پاول (فدرال رزرو)")
check("و شخصیتِ نبوده حدس زده نمی‌شود", NB.voice("Analyst says BTC goes up") is None)
rows, _ = NB.board_now([{"title": "Saylor buys more Bitcoin", "t": NOW - H},
                        {"title": "Random market update", "t": NOW - H}], NOW)
v = NB.board_voices(rows)
check("بخش صداها فقط ردیفِ دارای گوینده را می‌گیرد",
      len(v) == 1 and v[0]["voice"].startswith("مایکل سیلر"), str(v))
check("و ارزِ مورد بحث را همراه دارد", v[0]["coins"] == ["BTC"], str(v[0]["coins"]))

# ── ۴. تاریخ جزو خبر است ────────────────────────────────────────────────
dated, undated = NB.board_now([
    {"title": "Fresh BTC story", "t": NOW - 2 * H},
    {"title": "Old ETH story", "t": NOW - 40 * H},
    {"title": "Story with no date"},
], NOW)
check("خبر بی‌تاریخ کنار خبر امروز چیده نمی‌شود",
      len(dated) == 2 and len(undated) == 1 and undated[0]["title"] == "Story with no date")
check("و دلیل بی‌تاریخی‌اش نوشته می‌شود، بی‌صدا حذف نمی‌شود",
      "تاریخ نداد" in undated[0]["why_undated"])
check("خبر تازه و کهنه از هم جدا برچسب می‌خورند",
      dated[0]["fresh"] is True and dated[1]["fresh"] is False, str([r["fresh"] for r in dated]))
check("سن خبر عدد دارد نه برچسبِ تنها", dated[1]["age_h"] == 40.0, str(dated[1]["age_h"]))
check("تاریخِ تهران روی هر خبر چاپ می‌شود", ":" in dated[0]["when"] and "-" in dated[0]["when"])
check("تازه‌ترین خبر اول می‌آید", dated[0]["age_h"] < dated[1]["age_h"])

# ── ۵. رویداد آینده: از یک روز قبل، نه زودتر ────────────────────────────
cal = [{"title": "CPI", "country": "USD", "in_hours": 3.0},
       {"title": "FOMC", "country": "USD", "in_hours": 20.0},
       {"title": "Far event", "country": "USD", "in_hours": 200.0},
       {"title": "Past event", "country": "USD", "in_hours": -5.0}]
up = NB.board_upcoming(cal, [], now_ms=NOW)
check("رویداد دورتر از ۲۴ ساعت روی بورد نمی‌آید (دستور: از یک روز قبل)",
      [r["title"] for r in up] == ["CPI", "FOMC"], str([r["title"] for r in up]))
check("رویداد گذشته هم نمی‌آید", all(r["in_hours"] >= 0 for r in up))
check("نزدیک‌ترین رویداد اول است", up[0]["in_hours"] < up[1]["in_hours"])
check("پنجرهٔ ۲۴ ساعت روی خودِ ماژول ثابت است", NB.POST_AHEAD_H == 24.0)
unl = [{"symbol": "ARB", "in_hours": 10.0},
       {"symbol": "OP", "in_hours": 100.0}]
up2 = NB.board_upcoming([], unl, now_ms=NOW)
check("آنلاکِ ارز هم با همان پنجره می‌آید و ارزش را نام می‌برد",
      len(up2) == 1 and up2[0]["coins"] == ["ARB"] and up2[0]["kind"] == "unlock", str(up2))
check("رویداد آینده ساعت تهران دارد", up[0]["when"] and ":" in up[0]["when"])

# ── ۶. درسِ واحدها: تکرار، ضریب می‌سازد نه ردیف تازه ────────────────────
les = NB.board_lessons([
    {"unit": "ایجنت روند", "lesson": "در پنجرهٔ خبر کلان، کانال ۱۵د نامعتبر است",
     "t": NOW - 5 * H, "coins": ["BTC"]},
    {"unit": "ایجنت روند", "lesson": "در پنجرهٔ خبر کلان، کانال ۱۵د نامعتبر است",
     "t": NOW - H, "coins": ["ETH"]},
    {"unit": "ایجنت حجم", "lesson": "حجمِ آنلاک با حجمِ تقاضا اشتباه نشود", "t": NOW - 2 * H},
], NOW)
check("درسِ تکراری ردیف دوم نمی‌سازد", len(les) == 2, str(len(les)))
top = les[0]
check("و تکرارش شمرده می‌شود", top["times"] == 2, str(top["times"]))
check("ضریب تجربه با تکرار بالا می‌رود (دستور حمید)", top["weight"] > 1.0, str(top["weight"]))
check("ضریب سقف دارد — تکرار بی‌نهایت وزن بی‌نهایت نمی‌سازد",
      NB.board_lessons([{"unit": "u", "lesson": "x", "t": NOW}] * 50, NOW)[0]["weight"] <= 3.0)
check("ارزهای هر دو رویداد زیر همان درس جمع می‌شوند",
      set(top["coins"]) == {"BTC", "ETH"}, str(top["coins"]))
check("درسِ پرتکرار بالای بورد می‌نشیند", les[0]["times"] >= les[1]["times"])
check("درس بی‌واحد یا بی‌متن اصلاً ثبت نمی‌شود",
      NB.board_lessons([{"unit": "", "lesson": "x"}, {"unit": "u", "lesson": ""}]) == [])

# دفترِ درس append-only است
with tempfile.TemporaryDirectory() as td:
    p = Path(td) / "lessons.jsonl"
    NB.post_lesson("ایجنت خط", "درس اول", event="ETF", coins_=["BTC"], path=p, now_ms=NOW)
    NB.post_lesson("ایجنت خط", "درس دوم", path=p, now_ms=NOW + H)
    body = p.read_text(encoding="utf-8").strip().splitlines()
    check("ثبت درس فقط اضافه می‌کند، بازنویسی نمی‌کند (قانون ضد-merge)", len(body) == 2)
    check("و هر ردیف واحد، متن، تاریخ و ارز را دارد",
          json.loads(body[0])["unit"] == "ایجنت خط" and json.loads(body[0])["coins"] == ["BTC"])

# ── ۷. بورد کامل ────────────────────────────────────────────────────────
b = NB.build(news=[{"title": "Powell speaks on BTC policy", "t": NOW - H},
                   {"title": "No date item"}],
             calendar=cal, unlocks=unl,
             lessons=[{"unit": "ایجنت حجم", "lesson": "درس", "t": NOW}],
             pump=[{"sym": "PEPEUSDT", "why": "حجم ۵×"}], now_ms=NOW)
for k in ("now", "undated", "voices", "upcoming", "lessons", "pump_notes", "counts",
          "by_cat", "boundary", "generated", "engine"):
    check(f"بورد بخش «{k}» را دارد", k in b)
check("شمارش بورد با محتوایش می‌خواند",
      b["counts"]["now"] == len(b["now"]) and b["counts"]["upcoming"] == len(b["upcoming"]))
check("مالک بورد E14 است (ردیف قرارداد)", b["engine"] == "E14")
check("مرز قانون ۱۵ روی خودِ بورد نوشته شده",
      "دروازه" in b["boundary"] and "قانون ۱۵" in b["boundary"])
check("پامپ‌های در دست بررسی هم روی بورد می‌آیند (دلیل و ارز)",
      b["pump_notes"] and b["pump_notes"][0]["sym"] == "PEPEUSDT")
check("شمارش دسته‌ای برای اتاق‌ها آماده است", isinstance(b["by_cat"], dict))

# ── ۸. مرز: بورد هیچ امتیاز یا دروازه‌ای نمی‌سازد ───────────────────────
src = (HERE / "newsboard.py").read_text(encoding="utf-8")
for bad in ("score", "gate", "veto", "confidence"):
    check(f"ماژول هیچ «{bad}»ی نمی‌سازد (خبر دروازه نیست — قانون ۱۵)",
          bad not in src.lower().replace("newsboard", ""))
flat = json.dumps(b, ensure_ascii=False)
check("خروجی بورد هیچ امتیاز عددیِ تصمیمی ندارد",
      '"score"' not in flat and '"weight_gate"' not in flat)

# ── ۹. سیم‌کشی ──────────────────────────────────────────────────────────
ROOT = HERE.parents[2]
reg = json.loads((ROOT / "config" / "state_registry.json").read_text(encoding="utf-8"))["files"]
check("newsboard.json ردیف قرارداد دارد (قانون ۱۳)",
      "newsboard.json" in reg and reg["newsboard.json"]["producer"] == "hamid/newsboard.py",
      str(reg.get("newsboard.json")))
wf = (ROOT / ".github" / "workflows" / "hamid-cycle.yml").read_text(encoding="utf-8")
check("چرخهٔ حمید بورد را می‌سازد", "hamid.newsboard --write" in wf)

print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
sys.exit(1 if FAIL else 0)
