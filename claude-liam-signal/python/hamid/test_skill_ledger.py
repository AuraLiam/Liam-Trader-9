"""پاسبان دفتر مهارت (۴ سپتامبر) — آفلاین، بدون شبکه، قطعی.

قفل می‌کند دستور حمید: «مهارت و تجربهٔ تکراری فقط ضریب آن تجربه را
بالا می‌برد» و «همهٔ اتفاقات با تاریخ و لحظهٔ وقوع ثبت شود» — و مرزها:
هیچ ردیفی حذف نمی‌شود، ضریب سقف دارد، و دفتر دروازه نیست.
"""
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from hamid import skill_ledger as SL                 # noqa: E402

OK = 0
FAIL = []
NOW = 1_800_000_000_000
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


# ── ۱. یکسان‌سازی متن ───────────────────────────────────────────────────
check("فاصلهٔ اضافه دو درس نمی‌سازد", SL.norm("درس  یک") == SL.norm("درس یک"))
check("نقطه‌گذاری دو درس نمی‌سازد", SL.norm("درس یک.") == SL.norm("درس یک"))
check("ی و ك عربی با فارسی یکی می‌شوند (وگرنه ضریب هرگز بالا نمی‌رود)",
      SL.norm("كیفیت داده") == SL.norm("کیفیت داده"))
check("نیم‌فاصله دو ردیف نمی‌سازد", SL.norm("می‌رود") == SL.norm("می رود"))
check("ولی دو درسِ واقعاً متفاوت یکی نمی‌شوند",
      SL.norm("کانال را بهتر بکش") != SL.norm("کانال را نکش"))
check("کلید، واحد و دامنه را هم در خود دارد",
      SL.key_of("روند", "x", "BTC") != SL.key_of("حجم", "x", "BTC")
      and SL.key_of("روند", "x", "BTC") != SL.key_of("روند", "x", "ETH"))

# ── ۲. ضریب: بازده نزولی با سقف ─────────────────────────────────────────
check("یک بار = ضریب ۱", SL.weight_of(1) == 1.0)
check("دو بار ضریب را بالا می‌برد", SL.weight_of(2) > SL.weight_of(1))
check("ولی چهار بار، دو برابرِ دو بار نیست (بازده نزولی)",
      SL.weight_of(4) < 2 * SL.weight_of(2), f"{SL.weight_of(4)} vs {SL.weight_of(2)}")
check("صد بار هم از سقف رد نمی‌شود", SL.weight_of(100) <= SL.MAX_WEIGHT)
check("هزار بار هم", SL.weight_of(1000) == SL.MAX_WEIGHT)
check("ضریب یک‌نواخت صعودی است", all(SL.weight_of(i) <= SL.weight_of(i + 1)
                                     for i in range(1, 40)))

# ── ۳. تکرار ردیف نمی‌سازد، ضریب می‌سازد ────────────────────────────────
with tempfile.TemporaryDirectory() as td:
    L, E = Path(td) / "l.json", Path(td) / "e.jsonl"
    kw = {"path": L, "events": E}
    r1 = SL.learn("ایجنت روند", "در پنجرهٔ خبر کلان کانال ۱۵د نامعتبر است",
                  scope="BTCUSDT", evidence="ستاپ ۱", now_ms=NOW, **kw)
    r2 = SL.learn("ایجنت روند", "در پنجرهٔ خبر کلان، کانال ۱۵د نامعتبر است.",
                  scope="BTCUSDT", evidence="ستاپ ۲", now_ms=NOW + DAY, **kw)
    check("درسِ همان، با نگارش کمی متفاوت، ردیف تازه نمی‌سازد",
          r2["times"] == 2 and len(SL._load(L)["skills"]) == 1)
    check("و ضریبش بالا می‌رود — دقیقاً دستور حمید",
          r2["weight"] > r1["weight"], f"{r1['weight']} → {r2['weight']}")
    check("متن نمایشیِ اولین ثبت می‌ماند (تغییر نگارشی تاریخ را عوض نمی‌کند)",
          r2["skill"] == r1["skill"])
    check("اولین و آخرین لحظه هر دو نگه داشته می‌شوند",
          r2["first_t"] == NOW and r2["last_t"] == NOW + DAY)

    SL.learn("ایجنت حجم", "حجم آنلاک با حجم تقاضا اشتباه نشود", now_ms=NOW, **kw)
    check("واحد دیگر ردیف خودش را دارد", len(SL._load(L)["skills"]) == 2)
    SL.learn("ایجنت روند", "همان درس", scope="ETHUSDT", now_ms=NOW, **kw)
    check("دامنهٔ دیگر هم ردیف خودش را دارد", len(SL._load(L)["skills"]) == 3)

    # ── ۴. دفتر رویداد append-only ─────────────────────────────────────
    ev = [json.loads(x) for x in E.read_text(encoding="utf-8").strip().splitlines()]
    check("هر بارِ دیده‌شدن یک ردیف رویداد می‌سازد (ادغام چیزی را نمی‌بلعد)",
          len(ev) == 4, str(len(ev)))
    check("هر رویداد لحظهٔ خودش را دارد (دستور: با تاریخ و لحظهٔ وقوع)",
          ev[0]["t"] == NOW and ev[1]["t"] == NOW + DAY)
    check("و شمار تکرار و ضریبِ همان لحظه را ثبت می‌کند",
          ev[1]["times"] == 2 and ev[1]["weight"] == r2["weight"])
    check("پس «ضریب بالا رفت» قابل بازشماری است",
          sum(1 for e in ev if e["key"] == ev[0]["key"]) == 2)
    check("شواهد روی ردیف خلاصه هم می‌ماند", len(r2["evidence"]) == 2)
    check("و تازه‌ترین شاهد اول است", r2["evidence"][0]["note"] == "ستاپ ۲")

    # ── ۵. بازخوانی برای تصمیم بعدی ────────────────────────────────────
    for _ in range(6):
        SL.learn("ایجنت روند", "پرتکرارترین درس", now_ms=NOW, **kw)
    top = SL.recall(now_ms=NOW + DAY, path=L)
    check("قوی‌ترین مهارت اول برگردانده می‌شود (تصمیم بعدی همان را می‌خواند)",
          top[0]["skill"] == "پرتکرارترین درس", str(top[0]["skill"]))
    check("بازخوانی به تفکیک واحد کار می‌کند",
          all(r["unit"] == "ایجنت حجم" for r in SL.recall(unit="ایجنت حجم", path=L)))
    eth = SL.recall(unit="ایجنت روند", scope="ETHUSDT", path=L)
    check("بازخوانی دامنه، مهارتِ دامنهٔ دیگر را نمی‌آورد",
          all(r["scope"] in (None, "ETHUSDT") for r in eth),
          str([r["scope"] for r in eth]))
    check("ولی مهارتِ بی‌دامنه را می‌آورد — درسِ عمومی همه‌جا معتبر است",
          any(r["scope"] is None for r in eth) and any(r["scope"] == "ETHUSDT" for r in eth),
          str([r["scope"] for r in eth]))
    check("کف ضریب فیلتر می‌کند",
          all(r["weight"] >= 1.4 for r in SL.recall(min_weight=1.4, path=L)))
    check("واحد ناموجود، ردیف جعلی نمی‌سازد", SL.recall(unit="واحد نبوده", path=L) == [])

    # ── ۶. کهنه، نه حذف ────────────────────────────────────────────────
    old = SL.recall(now_ms=NOW + int(SL.STALE_DAYS * DAY) + 10 * DAY, path=L)
    check("مهارت دیرندیده کهنه برچسب می‌خورد", any(r["stale"] for r in old))
    check("ولی حذف نمی‌شود (قانون ۶)", len(old) == len(SL._load(L)["skills"]))
    check("و سنش به روز گزارش می‌شود", all(r["age_days"] >= 0 for r in old))

    # ── ۷. ورودی خراب ──────────────────────────────────────────────────
    n_before = len(SL._load(L)["skills"])
    check("مهارت بی‌واحد ثبت نمی‌شود", SL.learn("", "x", **kw) is None)
    check("مهارت بی‌متن ثبت نمی‌شود", SL.learn("u", "   ", **kw) is None)
    check("و دفتر دست‌نخورده می‌ماند", len(SL._load(L)["skills"]) == n_before)

    # ── ۸. تابلو ───────────────────────────────────────────────────────
    s = SL.snapshot(now_ms=NOW + DAY, path=L)
    check("تابلو شمار مهارت، تکرارشده و کهنه را دارد",
          set(("skills", "repeated", "stale", "units")) <= set(s["counts"]))
    check("و به تفکیک واحد، قوی‌ترین مهارتش را",
          s["by_unit"]["ایجنت روند"]["top"]["skill"] == "پرتکرارترین درس")
    check("قاعدهٔ ضریب روی خود تابلو نوشته می‌شود", "بازده نزولی" in s["weight_rule"])
    check("مالک تابلو E21 (نگهبان حافظه) است", s["engine"] == "E21")
    check("مرز روی تابلو نوشته می‌شود",
          "دروازه" in s["boundary"] and "قانون ۰۳" in s["boundary"])

# ── ۸ب. خوراک از دفتر رویداد: یک‌بار، و بدون ردیفِ یک‌بارهٔ معامله ────
with tempfile.TemporaryDirectory() as td:
    L, E = Path(td) / "l.json", Path(td) / "e.jsonl"
    src_lessons = [
        {"at": NOW, "kind": "بررسی", "sym": "BTCUSDT", "text": "درس قابل تعمیم"},
        {"at": NOW + 1, "kind": "نتیجه", "sym": "BTCUSDT", "text": "✅ برد (+0.31R)"},
        {"at": NOW + 2, "kind": "تحلیل", "sym": None, "text": "درس دوم"},
    ]
    r = SL.ingest_memory(src_lessons, path=L, events=E, now_ms=NOW + 10)
    check("درس قابل‌تعمیم وارد دفتر مهارت می‌شود", r["ingested"] == 2, str(r))
    skills = SL._load(L)["skills"]
    check("ولی نتیجهٔ یک معاملهٔ مشخص نه — عددِ یکتا هرگز تکرار نمی‌سازد",
          len(skills) == 2 and not any("+0.31R" in v["skill"] for v in skills.values()),
          str([v["skill"] for v in skills.values()]))
    again = SL.ingest_memory(src_lessons, path=L, events=E, now_ms=NOW + 20)
    check("خوراکِ دوباره چیزی اضافه نمی‌کند (ضریب از تکرارِ خواندن بالا نمی‌رود)",
          again["ingested"] == 0 and len(SL._load(L)["skills"]) == 2)
    weights_before = {k: v["times"] for k, v in SL._load(L)["skills"].items()}
    SL.ingest_memory(src_lessons, path=L, events=E, now_ms=NOW + 30)
    check("و ضریب‌ها هم دست‌نخورده می‌مانند",
          {k: v["times"] for k, v in SL._load(L)["skills"].items()} == weights_before)
    newer = src_lessons + [{"at": NOW + 100, "kind": "بررسی", "sym": "BTCUSDT",
                            "text": "درس قابل تعمیم"}]
    r3 = SL.ingest_memory(newer, path=L, events=E, now_ms=NOW + 110)
    got = [v for v in SL._load(L)["skills"].values() if v["skill"] == "درس قابل تعمیم"][0]
    check("ولی همان درس در تاریخ تازه، ضریبش را بالا می‌برد",
          r3["ingested"] == 1 and got["times"] == 2 and got["weight"] > 1.0, str(got))
    check("نشانگر خوراک روی دفتر ذخیره می‌شود",
          (SL._load(L).get("cursors") or {}).get("memory") == NOW + 100)

# ── ۹. مرز در کد ────────────────────────────────────────────────────────
src = (HERE / "skill_ledger.py").read_text(encoding="utf-8")
for bad in ("veto", "threshold =", "gate(", "send_message"):
    check(f"دفتر مهارت «{bad}» ندارد — حافظه است نه دروازه", bad not in src)

# ── ۱۰. سیم‌کشی ─────────────────────────────────────────────────────────
ROOT = HERE.parents[2]
reg = json.loads((ROOT / "config" / "state_registry.json").read_text(encoding="utf-8"))["files"]
check("skills.json ردیف قرارداد دارد (قانون ۱۳)",
      "skills.json" in reg and reg["skills.json"]["producer"] == "hamid/skill_ledger.py",
      str(reg.get("skills.json")))
wf = (ROOT / ".github" / "workflows" / "hamid-cycle.yml").read_text(encoding="utf-8")
check("چرخهٔ حمید تابلوی مهارت را می‌سازد", "hamid.skill_ledger --write" in wf)

print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
sys.exit(1 if FAIL else 0)
