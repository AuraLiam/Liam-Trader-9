"""پاسبان راستی‌آزمایی کتابخانه — همراه اجباری library_verify.py.

آنچه این‌جا قفل می‌شود همان دو خرابیِ متقابلی است که خودِ ساختن این فایل
لو داد: کلیدی که زیرعنوان را می‌برید دو کتابِ متفاوت را یکی می‌کرد، و
همان بریدن باعث می‌شد ده مدخل با هیچ تصمیمی نخورند. به‌علاوهٔ مهم‌ترین
قاعده: **سکوت هرگز تأیید نیست**.
"""
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from hamid import library_verify as LV                 # noqa: E402

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


# ── norm_key ────────────────────────────────────────────────────────────
check("زیرعنوان فارسی بعد از خط تیره حذف می‌شود",
      LV.norm_key("Advances in Financial ML — یادگیری ماشین")
      == "advances in financial ml")
check("شمارهٔ ویرایش کلید را عوض نمی‌کند",
      LV.norm_key("Empirical Market Microstructure, 2nd Edition")
      == LV.norm_key("Empirical Market Microstructure"))
check("قالب «book | نویسنده | سال» از عنوان پاک است",
      LV.norm_key("Limit Order Books | book | Gould") == "limit order books")
# همان خرابی که اولین اجرا لو داد
check("زیرعنوان بریده نمی‌شود — Trends و Reversals یکی نمی‌شوند",
      LV.norm_key("Trading Price Action: Trends")
      != LV.norm_key("Trading Price Action: Reversals"),
      LV.norm_key("Trading Price Action: Trends"))
check("کاما هم عنوان را قطع نمی‌کند",
      LV.norm_key("Thinking, Fast and Slow") == "thinking fast and slow",
      LV.norm_key("Thinking, Fast and Slow"))

# ── author_hint ─────────────────────────────────────────────────────────
check("نویسنده از قالب لوله‌ای خوانده می‌شود",
      LV.author_hint("book | Larry Harris | 2002 | https://x") == "harris")
check("نویسنده از قالب خط‌تیره‌ای خوانده می‌شود",
      LV.author_hint("David H. Weis — Trades About to Happen (Wiley)") == "weis")
check("از چند نویسنده، اولی گرفته می‌شود (نه آخری)",
      LV.author_hint("book | Jean-Philippe Bouchaud; Julius Bonart") == "bouchaud")
check("دو قالبِ یک کتاب به یک نویسنده می‌رسند",
      LV.author_hint("book | Álvaro Cartea; Sebastian Jaimungal")
      == LV.author_hint("Cartea, Jaimungal, Penalva — Algorithmic Trading"))
check("منبع خالی خطا نمی‌دهد", LV.author_hint("") == "")

# ── dupe_key ────────────────────────────────────────────────────────────
gould = {"title": "Limit Order Books", "source": "paper | Martin D. Gould"}
aberg = {"title": "Limit Order Books", "source": "book | Frédéric Abergel"}
check("دو اثرِ هم‌نام با نویسندهٔ متفاوت تکراری حساب نمی‌شوند",
      LV.dupe_key(gould) != LV.dupe_key(aberg))
check("یک اثر در دو قالبِ مختلف تکراری حساب می‌شود",
      LV.dupe_key({"title": "Trading and Exchanges: Market Microstructure "
                            "for Practitioners", "source": "book | Larry Harris"})
      .startswith(LV.norm_key("Trading and Exchanges")))

# ── پیش‌فرض امن ─────────────────────────────────────────────────────────
st, note = LV.decide({"title": "یک کتاب کاملاً ناشناخته", "source": "?"})
check("مدخلِ بی‌تصمیم QUEUED می‌ماند (سکوت ≠ تأیید)",
      st == "QUEUED" and note == "", f"{st} {note}")
st2, _ = LV.decide({"title": "Advances in Financial Machine Learning",
                    "source": "book | Marcos López de Prado"})
check("مدخلِ دارای تصمیم تأیید می‌شود", st2 == "VERIFIED")
check("تطبیق پیشوندیِ خیلی کوتاه اتفاق نمی‌افتد",
      LV.decide({"title": "The", "source": "x"})[0] == "QUEUED")

# ── نوشتن ───────────────────────────────────────────────────────────────
ROWS = [
    {"id": "a", "title": "Advances in Financial Machine Learning",
     "source": "book | Marcos López de Prado", "engine": "E18",
     "status": "QUEUED", "notes": "", "verified_by": "", "verified_at": 0},
    {"id": "b", "title": "Advances in Financial Machine Learning — تکراری",
     "source": "Marcos López de Prado — AFML", "engine": "E18",
     "status": "QUEUED", "notes": "", "verified_by": "", "verified_at": 0},
    {"id": "c", "title": "کتابِ ناشناخته", "source": "?", "engine": "E00",
     "status": "QUEUED", "notes": "", "verified_by": "", "verified_at": 0},
    {"id": "d", "title": "Mind Over Markets", "source": "James F. Dalton",
     "engine": "E08", "status": "REJECTED", "notes": "قبلاً رد شده",
     "verified_by": "lead", "verified_at": 1},
]

with tempfile.TemporaryDirectory() as td:
    q = Path(td) / "queue.jsonl"
    sh = Path(td) / "index.jsonl"
    q.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in ROWS))
    sh.write_text("")
    dry = LV.run(apply=False, quiet=True, queue_path=q, shelf_path=sh)
    check("اجرای خشک چیزی نمی‌نویسد", sh.read_text() == "" and
          len(q.read_text().splitlines()) == 4)
    res = LV.run(apply=True, quiet=True, queue_path=q, shelf_path=sh)
    newq = [json.loads(x) for x in q.read_text().splitlines() if x.strip()]
    newsh = [json.loads(x) for x in sh.read_text().splitlines() if x.strip()]

check("شمارش اجرای خشک و اجرای واقعی یکی است",
      (dry["verified"], dry["duplicates"], dry["still_queued"])
      == (res["verified"], res["duplicates"], res["still_queued"]),
      f"{dry} vs {res}")
check("یک تأیید، یک تکراری، یک باقی‌مانده",
      (res["verified"], res["duplicates"], res["still_queued"]) == (1, 1, 1),
      str(res))
check("هیچ مدخلی از صف حذف نمی‌شود (قانون ۲ README)", len(newq) == 4,
      str(len(newq)))
byid = {r["id"]: r for r in newq}
check("مدخل تأییدشده status و امضا می‌گیرد",
      byid["a"]["status"] == "VERIFIED" and byid["a"]["verified_by"] == "lead"
      and byid["a"]["verified_at"] > 0 and byid["a"]["notes"],
      str(byid["a"])[:120])
check("تکراری DUPLICATE می‌شود، نه VERIFIED دوم",
      byid["b"]["status"] == "DUPLICATE")
check("ناشناخته دست‌نخورده QUEUED می‌ماند", byid["c"]["status"] == "QUEUED")
check("مدخلِ غیرQUEUED دست نمی‌خورد",
      byid["d"]["status"] == "REJECTED" and byid["d"]["notes"] == "قبلاً رد شده")
check("فقط تأییدشده وارد قفسه می‌شود", len(newsh) == 1
      and newsh[0]["id"] == "a", str([r["id"] for r in newsh]))
check("مدخل قفسه یادداشت راستی‌آزمایی دارد (نه تأیید بی‌دلیل)",
      len(newsh[0]["notes"]) > 20, newsh[0].get("notes", ""))

# اجرای دوباره نباید همان را دوباره وارد قفسه کند
with tempfile.TemporaryDirectory() as td:
    q = Path(td) / "queue.jsonl"
    sh = Path(td) / "index.jsonl"
    q.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in ROWS))
    sh.write_text("")
    LV.run(apply=True, quiet=True, queue_path=q, shelf_path=sh)
    # صف را دوباره QUEUED می‌کنیم تا بدترین حالت آزموده شود
    q.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in ROWS))
    LV.run(apply=True, quiet=True, queue_path=q, shelf_path=sh)
    twice = [json.loads(x) for x in sh.read_text().splitlines() if x.strip()]
check("اجرای دوباره مدخل تکراری به قفسه اضافه نمی‌کند (idempotent)",
      len(twice) == 1, str(len(twice)))

# ── تعارض ثبت‌شده ───────────────────────────────────────────────────────
pro = LV.DECISIONS[LV.norm_key("The Predictive Power of Price Patterns")][1]
con = LV.DECISIONS[LV.norm_key(
    "Candlestick Technical Trading Strategies: Can They Create Value")][1]
check("هر دو طرفِ تعارضِ کندل‌شناسی در قفسه‌اند و تعارض در یادداشت آمده",
      "له" in pro and "علیه" in con, f"{pro[:40]} / {con[:40]}")
check("منبعی که با دادهٔ ما قابل‌استفادهٔ کامل نیست، مرزش نوشته شده",
      "قانون ۰۸" in LV.DECISIONS["detecting layering and spoofing in markets"][1])
check("منبع OFI صریح می‌گوید دادهٔ REST ما OFI واقعی نیست",
      "تقریب" in LV.DECISIONS["the price impact of order book events"][1])
# هیچ تأییدی بدون یادداشتِ معنادار نباشد — «VERIFIED» خالی یعنی هیچ.
check("هیچ مدخل تأییدشده‌ای یادداشت خالی یا کوتاه ندارد",
      all(len(n) >= 40 for _, n in LV.DECISIONS.values()),
      str([k for k, (_, n) in LV.DECISIONS.items() if len(n) < 40]))

# ── تکراریِ پیشوندی روی قفسه (عیب ۲۳ اوت) ─────────────────────────────
_h1 = {"title": "Trading and Exchanges: Market Microstructure for Practitioners",
       "source": "book | Larry Harris | 2002 | https://doi.org/x"}
_h2 = {"title": "Trading and Exchanges — ریزساختار بازار برای اهل عمل",
       "source": "Larry Harris — Trading and Exchanges (OUP)"}
check("عنوان کامل و عنوانِ کوتاه با زیرعنوان فارسی، یک اثر شناخته می‌شوند",
      LV.same_work(_h1, _h2), f"{LV.dupe_key(_h1)} vs {LV.dupe_key(_h2)}")
check("همان اثر با نویسندهٔ متفاوت، تکراری نیست",
      not LV.same_work(_h1, {"title": _h1["title"],
                             "source": "book | Someone Else | 2002 | x"}))
check("دو جلدِ متفاوتِ یک نویسنده به هم نمی‌چسبند (Trends/Reversals)",
      not LV.same_work(
          {"title": "Trading Price Action: Trends", "source": "Al Brooks — x"},
          {"title": "Trading Price Action: Reversals", "source": "Al Brooks — x"}))
check("ساقهٔ کوتاه پیشوندی نمی‌چسبد (ضد چسبِ بی‌جا)",
      not LV.same_work({"title": "Risk", "source": "book | A Jorion | 1 | x"},
                       {"title": "Risk Management Handbook",
                        "source": "book | A Jorion | 1 | x"}))
check("مدخل بی‌نویسنده هرگز تکراری اعلام نمی‌شود (پیش‌فرض امن)",
      not LV.same_work(_h1, {"title": _h1["title"], "source": ""}))
_g = LV.dupe_groups([_h1, _h2, {"title": "Other Book",
                                "source": "book | Zed | 1 | x"}])
check("گروه‌بندی، فقط گروهِ واقعی را برمی‌گرداند",
      len(_g) == 1 and len(_g[0]) == 2)

_shelf = LV.load(LV.SHELF)
_live = LV.dupe_groups([e for e in _shelf if e.get("status") == "VERIFIED"])
check("قفسهٔ واقعی هیچ تکراریِ VERIFIED ندارد", not _live,
      "; ".join(" + ".join(e["id"] for e in g) for g in _live))

print()
if FAIL:
    print(f"شکست: {len(FAIL)} از {OK + len(FAIL)}")
    sys.exit(1)
print(f"پاسبان راستی‌آزمایی کتابخانه: هر {OK} بررسی سبز")
