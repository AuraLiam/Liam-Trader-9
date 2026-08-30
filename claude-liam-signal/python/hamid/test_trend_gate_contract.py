"""پاسبان قرارداد شواهد بین ورکر و دروازهٔ روند — کلاسِ «فیکسچر خیالی».

## عیبی که این آزمون برای بستنش نوشته شد (۳۰ اوت شب)

`hamid/test_trend_gate.py` هفت آزمون سبز داشت و **هیچ‌کدام** عیب زیر را
نگرفت، چون شواهد را دستی و با نام‌های موردانتظارِ خودِ دروازه می‌ساخت:

- `scan_worker.js` برای smc کلیدِ `inside` می‌نویسد، نه `inOB`
- برای smc اصلاً `choch` تولید نمی‌شود
- برای ibs مقادیر `fvg` و `swept` **هاردکد** هستند (`false` و `null`)

نتیجه: مسیر «خلاف روند با تأیید کامل» — که سند ۱۷ اوت تعریفش کرده —
برای هر دو استراتژی **ساختاراً دست‌نیافتنی** بود. شاهدِ عددی: در تمام
آرشیو ارسال و دفتر بسته، صفر مورد `counter-confirmed`.

درسِ کلاس: **آزمونی که ورودی‌اش را خودش می‌سازد، فقط خودش را می‌سنجد.**
پس این آزمون ورودی را از **خودِ سورس ورکر** می‌گیرد و اگر قرارداد دو
طرف واگرا شود، چرخه را سرخ می‌کند.

## چیزی که این آزمون **نمی‌گوید**

نمی‌گوید مسیر خلاف روند باید باز شود. بازکردنش یعنی موتور واقعاً
fvg/swept/choch را حساب کند، و آن از مسیر قانون ۰۳ می‌گذرد. این آزمون
فقط تضمین می‌کند وضعیت **دیده شود** و بی‌صدا نماند.
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
sys.path.insert(0, str(PY))

from hamid import trend_gate as G                             # noqa: E402

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


def worker_blocks():
    """بلوکِ خروجیِ هر استراتژی را از سورس ورکر بیرون می‌کشد."""
    src = (PY / "scan_worker.js").read_text(encoding="utf-8")
    out = {}
    for strat in ("ibs", "smc"):
        i = src.find(f'strategy: "{strat}"')
        if i < 0:
            continue
        j = src.find("});", i)
        out[strat] = src[i:j if j > 0 else i + 2000]
    return out


def _wave(n, slope=0.30, amp=1.0, period=12):
    """کندلِ صعودی با سوینگِ واقعی.

    پله‌ای یکنواخت جواب نمی‌دهد: `structure.trend` سوینگ فراکتالی
    می‌خواهد و نردبانِ بی‌پولبک را «range» می‌خواند (خودِ داک‌استرینگش
    همین را می‌گوید). پس موجِ رونددارِ قطعی می‌سازیم."""
    import math
    out = []
    for i in range(n):
        o = 100.0 + slope * i + amp * math.sin(2 * math.pi * i / period)
        c = 100.0 + slope * (i + 1) + amp * math.sin(2 * math.pi * (i + 1) / period)
        out.append({"t": i * 60000, "o": o, "c": c,
                    "h": max(o, c) + amp * 0.15, "l": min(o, c) - amp * 0.15,
                    "v": 10.0})
    return out


def _flat(n):
    """رنجِ قطعی — بی‌جهت."""
    import math
    return [{"t": i * 60000, "o": 100 + math.sin(i / 6.0),
             "c": 100 + math.sin((i + 1) / 6.0),
             "h": 101.4, "l": 98.6, "v": 10.0} for i in range(n)]


def kget_counter(sym, tf, n):
    """۴س صعودی، ۱س رنج — یعنی SHORT «خلاف روند» است، نه وتوی مطلق.

    این تمایز مهم است: وتوی دو-تایم قبل از منطق تأییدیه‌ها برمی‌گردد،
    پس اگر هر دو تایم را صعودی بدهیم مسیرِ موردِ آزمون اصلاً اجرا
    نمی‌شود و آزمون به‌دروغ سبز/قرمز می‌شود."""
    return _wave(max(n, 240)) if tf == "4h" else _flat(max(n, 240))


def kget_both_up(sym, tf, n):
    """هر دو تایم بالا صعودی — وتوی مطلق برای SHORT."""
    return _wave(max(n, 240))


def run():
    blocks = worker_blocks()
    check("بلوک خروجی هر دو استراتژی در سورس ورکر پیدا شد",
          set(blocks) == {"ibs", "smc"}, str(list(blocks)))

    ibs, smc = blocks.get("ibs", ""), blocks.get("smc", "")

    # ── ۱) قرارداد واقعیِ ورکر، خوانده از خودِ سورس ────────────────────
    ibs_fvg_hard = re.search(r"\bfvg:\s*(false|true|null)\b", ibs) is not None
    ibs_swept_hard = re.search(r"\bswept:\s*(false|true|null)\b", ibs) is not None
    check("ibs مقدار fvg را هاردکد می‌گذارد (پس محاسبه نمی‌شود)",
          ibs_fvg_hard, ibs[:0] or "الگو پیدا نشد")
    check("ibs مقدار swept را هاردکد می‌گذارد", ibs_swept_hard)
    check("ibs کلید choch را واقعاً حساب می‌کند",
          re.search(r"\bchoch:\s*(?!false\b|true\b|null\b)", ibs) is not None)
    check("smc کلید inside دارد (نه inOB)",
          "inside:" in smc and not re.search(r"\binOB:", smc))
    check("smc کلید choch تولید نمی‌کند",
          not re.search(r"\bchoch:", smc))
    check("smc کلید fvg را واقعاً حساب می‌کند",
          re.search(r"\bfvg:\s*!!", smc) is not None)

    # ── ۲) جدول COMPUTED باید با همان سورس بخواند ─────────────────────
    check("جدول قرارداد، fvg را برای ibs محاسبه‌نشده می‌داند",
          ("fvg" in G.COMPUTED["ibs"]) is not ibs_fvg_hard,
          str(G.COMPUTED["ibs"]))
    check("جدول قرارداد، swept را برای ibs محاسبه‌نشده می‌داند",
          ("swept" in G.COMPUTED["ibs"]) is not ibs_swept_hard)
    check("جدول قرارداد، choch را برای smc محاسبه‌نشده می‌داند",
          "choch" not in G.COMPUTED["smc"])
    check("جدول قرارداد، inOB را برای smc محاسبه‌شده می‌داند "
          "(از راه نام هم‌معنای inside)",
          "inOB" in G.COMPUTED["smc"] and "inside" in G.ALIASES["inOB"])

    # ── ۳) مسیر خلاف روند: باز است یا بسته — صریح ─────────────────────
    for strat in ("ibs", "smc"):
        openp, gap = G.counter_path_open(strat)
        check(f"مسیر خلاف روند {strat} صریح اعلام می‌شود (باز={openp})",
              openp is False and gap, f"{openp} / {gap}")
    openp, gap = G.counter_path_open("unknown-strategy")
    check("استراتژی ناشناخته، مسیر را باز فرض می‌کند (سخت‌گیری کور نه)",
          openp is True and gap == [])

    # ── ۴) ردیفِ **واقعیِ** ورکر از دروازه رد شود ──────────────────────
    # شکل ردیف عیناً از scan_worker.js — نه دیکشنری آرزویی
    ibs_row = {"strategy": "ibs", "sym": "TESTUSDT", "tf": "15m",
               "stage": "SIGNAL", "dir": "SHORT", "entry": 100.0, "sl": 100.4,
               "tp1": 99.0, "quality": 88, "inside": True, "fvg": False,
               "swept": None, "choch": 1, "inOB": 1, "nearOB": 1}
    a = G.assess("TESTUSDT", "SHORT", kget_counter, evidence=ibs_row)
    check("ردیف واقعی ibs خلاف روند: عبور نمی‌کند",
          a["ok"] is False and a["mode"] in ("counter-blocked", "hard-veto"),
          str(a)[:160])
    check("و دلیلش «محاسبه‌نشده» را نام می‌برد، نه دروغِ «غایب»",
          "محاسبه‌نشده" in a["reason"] and set(a.get("uncomputed") or {})
          >= {"fvg", "swept"}, str(a.get("uncomputed")))

    smc_row = {"strategy": "smc", "sym": "TESTUSDT", "tf": "15m",
               "stage": "SIGNAL", "dir": "SHORT", "entry": 100.0, "sl": 102.0,
               "tp1": 96.0, "quality": 91, "inside": True, "fvg": True,
               "swept": {"n": 2}, "level": None, "channel": None}
    b = G.assess("TESTUSDT", "SHORT", kget_counter, evidence=smc_row)
    check("ردیف واقعی smc خلاف روند: عبور نمی‌کند",
          b["ok"] is False, str(b)[:160])
    check("و غیبتِ choch به‌عنوان محاسبه‌نشده گزارش می‌شود",
          "choch" in (b.get("uncomputed") or []), str(b.get("uncomputed")))
    check("inOB از راه inside خوانده شد (پس در غایب/محاسبه‌نشده نیست)",
          "inOB" not in (b.get("missing") or []), str(b.get("missing")))

    # ── ۵) رفع نباید هیچ چیزی را شل کرده باشد ─────────────────────────
    check("محاسبه‌نشده هم مثل غایب می‌بندد (قانون ۱)",
          G.confirm({"strategy": "ibs", "fvg": True}, "fvg") is None)
    check("شاهدِ حاضر همچنان حاضر خوانده می‌شود",
          G.confirm({"strategy": "smc", "inside": True}, "inOB") is True)
    check("شاهدِ صریحاً غایب، غایب می‌ماند",
          G.confirm({"strategy": "smc", "fvg": False}, "fvg") is False)
    check("کیفیت ناموجود، «محاسبه‌نشده» است نه صفر",
          G.confirm({"strategy": "ibs"}, "quality>=70") is None)
    check("کیفیت زیر آستانه، غایب است",
          G.confirm({"strategy": "ibs", "quality": 60}, "quality>=70") is False)
    # هر دو تایم مخالف: هیچ شاهدی نباید عبور بدهد
    full = dict(smc_row, quality=99, choch=1)
    c = G.assess("TESTUSDT", "SHORT", kget_both_up, evidence=full)
    check("وتوی مطلق دو-تایم دست‌نخورده است",
          c["ok"] is False, str(c)[:120])

    # ── ۶) قیف باید این نیمه را ببیند ─────────────────────────────────
    src_scan = (PY / "scan.py").read_text(encoding="utf-8")
    check("scan.py هم‌معنایی inOB/inside را از قبل می‌شناخت "
          "(دروازه عقب افتاده بود، نه اسکن)",
          's.get("inOB") == 1 or s.get("inside") is True' in src_scan)

    print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(run())
