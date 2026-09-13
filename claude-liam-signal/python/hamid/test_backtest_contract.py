"""پاسبان قرارداد بک‌تست — سه عیبی که ممیزی ۳۰ اوت در مرجعِ عملکرد یافت.

D1 — مرجع ادعای عملکرد (`backtest.py`) فقط `smcSetup` را ریپلی می‌کرد،
     در حالی که ۸۲٪ شورت‌های ارسالی از `ibsPullback` بود: استراتژیِ
     موضوعِ بحث اصلاً بک‌تست نمی‌شد.
D2 — ردیف معامله `stop_pct`/کارمزد/خالص نداشت: نه تفکیک هندسه ممکن بود
     نه ادعای خالص — و درس ۳۰ اوت این بود که «لبهٔ ناخالص» بدون خالص،
     دروغِ آبرومند است.
شرط شلیک — واریانت ibs باید **عین** شرط سیگنال زنده باشد
     (`quality>=55 && (inOB||nearOB)` — آینهٔ scan_worker.js)؛ وگرنه
     بک‌تست چیزی را می‌سنجد که هرگز ارسال نمی‌شود.

اثبات مکانیکی هم اجرا می‌شود: ورکر روی کندل مصنوعیِ قطعی، و صحتِ
حساب fee_r = 0.15/stop_pct و r_net = r − fee_r روی تک‌تک ردیف‌ها.
"""
import json
import math
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
sys.path.insert(0, str(PY))

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


def series(n=1200, seed=7):
    out, px = [], 100.0
    for i in range(n):
        drift = 0.0004 * math.sin(i / 90.0)
        wob = 0.006 * math.sin(i / 7.0) + 0.004 * math.sin(i / 13.0 + seed)
        o, c = px, px * (1 + drift + wob * 0.3)
        out.append({"t": i * 900_000, "o": o, "c": c,
                    "h": max(o, c) * (1 + abs(wob) * 0.4),
                    "l": min(o, c) * (1 - abs(wob) * 0.4),
                    "v": 10 + 500 * abs(wob)})
        px = c
    return out


def run():
    wsrc = (PY / "bt_worker.js").read_text(encoding="utf-8")
    bsrc = (PY / "backtest.py").read_text(encoding="utf-8")
    ssrc = (PY / "scan_worker.js").read_text(encoding="utf-8")

    # ── D1: واریانت ibs، با شرطِ شلیکِ آینه‌ای ─────────────────────────
    # خاصیت را بسنج نه شکل را (درس ۶ سپتامبر): این بررسی قبلاً دنبال
    # رشتهٔ دقیقِ `variant === "ibs"` می‌گشت، و وقتی ۱۳ سپتامبر بازوهای
    # `ibs_g2/g3/floor` اضافه شدند و شرط به `startsWith("ibs")` تبدیل شد،
    # بی‌آنکه چیزی خراب شده باشد قرمز شد. چیزی که واقعاً باید تضمین شود
    # این است که مسیرِ ibs وجود دارد و هر بازوی ibs از همان در رد می‌شود.
    check("ورکر مسیر واریانت ibs دارد",
          'variant === "ibs"' in wsrc or 'variant.startsWith("ibs")' in wsrc)
    check("و ibsPullback را ریپلی می‌کند", "E.ibsPullback(view)" in wsrc)
    m = re.search(r"quality\s*>=\s*(\d+)\s*&&\s*\(x\.inOB\s*\|\|\s*x\.nearOB\)",
                  wsrc.replace("x.quality", "quality"))
    live = re.search(r"quality\s*>=\s*(\d+)\s*&&\s*\(ibs\.inOB\s*\|\|\s*ibs\.nearOB\)",
                     ssrc.replace("ibs.quality", "quality"))
    check("شرط شلیک ibs در ورکرِ بک‌تست هست", m is not None)
    check("و عیناً همان آستانهٔ سیگنالِ زنده است (آینهٔ scan_worker)",
          m is not None and live is not None and m.group(1) == live.group(1),
          f"bt={m.group(1) if m else '?'} live={live.group(1) if live else '?'}")
    check("backtest.py واریانت ibs را در هر دو حلقه دارد",
          bsrc.count('"ibs"') >= 2, str(bsrc.count('"ibs"')))

    # ── D2: هندسه و خالص روی ردیف و گزارش ─────────────────────────────
    for fld in ("stop_pct:", "fee_r:", "r_net:"):
        check(f"ردیف معاملهٔ ورکر {fld[:-1]} دارد", fld in wsrc)
    check("کارمزد از همان مدل رسمی ۰.۱۵٪ است", "0.15 / open.stopPct" in wsrc)
    check("describe خالص و CI خالص می‌دهد",
          '"exp_net"' in bsrc and '"ci_net"' in bsrc)
    check("گزارش تفکیک جهت×باند استاپ دارد (by_geometry)",
          "def by_geometry" in bsrc and '"by_geometry": geo' in bsrc)
    check("باندهای استاپ همان چهار باندِ کالبدشکافی‌اند",
          "((0, 0.5), (0.5, 0.8), (0.8, 1.5), (1.5, 99" in bsrc)

    # ── اثبات مکانیکی روی کندل مصنوعی قطعی ────────────────────────────
    jobs = [{"sym": f"SYN{s}USDT", "tf": "15m", "candles": series(seed=s)}
            for s in range(4)]
    p = Path(tempfile.mkdtemp()) / "jobs.json"
    p.write_text(json.dumps(jobs), encoding="utf-8")
    try:
        r = subprocess.run(["node", str(PY / "bt_worker.js"), "ibs", str(p)],
                           capture_output=True, timeout=240)
        tr = json.loads(r.stdout) if r.returncode == 0 else None
    except Exception as e:                           # noqa: BLE001
        tr = None
        print(f"      ↳ اجرای node شکست خورد: {e}")
    check("واریانت ibs روی کندل مصنوعی معامله تولید می‌کند",
          bool(tr), f"n={len(tr) if tr else 0}")
    if tr:
        check("هر ردیف هندسه و خالص دارد",
              all(all(k in t for k in ("stop_pct", "fee_r", "r_net")) for t in tr))
        check("fee_r = 0.15 ÷ stop_pct روی تک‌تک ردیف‌ها",
              all(abs(t["fee_r"] - 0.15 / t["stop_pct"]) < 1e-3 for t in tr))
        check("r_net = r − fee_r روی تک‌تک ردیف‌ها",
              all(abs(t["r_net"] - (t["r"] - t["fee_r"])) < 1e-3 for t in tr))
        check("بی‌آیندگی: هیچ معامله‌ای قبل از گرم‌شدن باز نشده",
              all(t["openedAt"] >= 300 * 900_000 for t in tr))
        # قطعیت: اجرای دوم باید مو‌به‌مو همان باشد
        r2 = subprocess.run(["node", str(PY / "bt_worker.js"), "ibs", str(p)],
                            capture_output=True, timeout=240)
        check("ریپلی قطعی است (دو اجرا، یک خروجی)",
              r2.returncode == 0 and r2.stdout == r.stdout)

    # ── describe/by_geometry پایتونی روی همان خروجی ───────────────────
    if tr:
        import importlib.util
        spec = importlib.util.spec_from_file_location("bt", PY / "backtest.py")
        bt = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(bt)
            d = bt.describe("t", tr)
            check("describe خالص را واقعاً حساب می‌کند",
                  d.get("exp_net") is not None and d.get("fee_r_mean") is not None,
                  str({k: d.get(k) for k in ('exp_net', 'fee_r_mean')}))
            check("و خالص از ناخالص کمتر است (کارمزد جهت دارد)",
                  d["exp_net"] < d["exp"])
            geo = bt.by_geometry(tr)
            check("تفکیک هندسه سطل می‌سازد", len(geo) >= 1, str(list(geo)))
            # D4 (۱۳ سپتامبر) — `bt_worker.step()` به معامله‌ای که تی‌پی۱
            # را لمس کرده و به ورود برگشته، پاداش کاملِ R1 می‌دهد و
            # «breakeven» صدایش می‌زند. اجرای واقعی ⅓ را می‌بندد و بقیه
            # را روی سربه‌سر، پس برگشتِ کامل ≈ صفر است نه R1. اندازهٔ
            # اثر روی اجرای ۸۰نمادیِ ۱۳ سپتامبر: ibs از +۰.۳۸۴ به
            # +۰.۰۵۹ (۸۵٪ از برتری‌اش) و base از −۰.۱۱۴ به −۰.۲۵۱.
            check("describe نسخهٔ سختگیرانه را هم می‌دهد (سربه‌سر = ۰)",
                  d.get("exp_strict") is not None and d.get("ci_strict") is not None,
                  str({k: d.get(k) for k in ('exp_strict', 'ci_strict')}))
            check("و سختگیرانه از خالص بیشتر نیست",
                  d["exp_strict"] <= d["exp_net"] + 1e-9,
                  f"strict={d['exp_strict']} net={d['exp_net']}")
            check("و روی گزارش چاپ می‌شود — وگرنه کسی فقط خوش‌بین را نقل می‌کند",
                  "strict (breakeven paid 0)" in bsrc)
            # اثبات که بررسی توخالی نیست: ردیفی با سربه‌سر لازم است
            check("نمونهٔ آزمون واقعاً ردیفِ breakeven دارد",
                  any(t.get("why") == "breakeven" for t in tr))

        except Exception as e:                       # noqa: BLE001
            check("ماژول backtest بارگذاری شد", False, repr(e)[:150])

    # ── D5 (۱۳ سپتامبر): بازوهای هندسهٔ بزرگ‌تر ────────────────────────
    # فرضیه مکانیکی است (`fee_r = کارمزد٪ ÷ استاپ٪`)، پس آزمونش هم باید
    # مکانیکی باشد: جعبهٔ ×k باید استاپ را ×k و سهم کارمزد را ÷k کند و
    # RR را **دست‌نخورده** بگذارد. اگر RR هم عوض می‌شد، دو تغییر با هم
    # سنجیده می‌شد و هیچ‌کدام قابل‌انتساب نبود.
    check("بازوهای مقیاس تعریف شده‌اند", "GEO_SCALE" in wsrc and "ibs_g2" in wsrc)
    check("کفِ استاپ بازوی جداگانه دارد (انتخاب ≠ بزرگ‌کردن)",
          "STOP_FLOOR_PCT" in wsrc)
    check("سقفِ زمان هم با k بزرگ می‌شود — وگرنه آزمایش علیه فرضیه تنظیم است",
          "TIMEOUT_MS * k" in wsrc and "open.tmo" in wsrc)
    check("هر سه بازوی تازه در فهرست اجرای بک‌تست هستند",
          all(f'"{a}"' in bsrc for a in ("ibs_g2", "ibs_g3", "ibs_floor")))
    # مقیاس روی ریاضیِ خودش — همان فرمولی که در ورکر است
    for k in (2.0, 3.0):
        entry, sl, tp1 = 100.0, 99.0, 103.0
        sl2 = entry + (sl - entry) * k
        tp2_ = entry + (tp1 - entry) * k
        risk0, risk1 = abs(entry - sl), abs(entry - sl2)
        check(f"جعبهٔ ×{k:.0f}: استاپ {k:.0f} برابر می‌شود",
              abs(risk1 - k * risk0) < 1e-9)
        check(f"جعبهٔ ×{k:.0f}: RR دست‌نخورده می‌ماند",
              abs(abs(tp2_ - entry) / risk1 - abs(tp1 - entry) / risk0) < 1e-9)
        check(f"جعبهٔ ×{k:.0f}: سهم کارمزد {k:.0f} برابر کم می‌شود",
              abs((0.15 / ((risk1 / entry) * 100))
                  - (0.15 / ((risk0 / entry) * 100)) / k) < 1e-9)

    print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(run())
