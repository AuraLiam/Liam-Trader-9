"""پاسبان منبع کندل — بیت‌یونیکس پرپچوال + سوییچ ترجیح (۲ سپتامبر).

دستور مکرر حمید: صرافی اجرا بیت‌یونیکس است و چارت پرپچوال؛ و «گزینهٔ
جایگزین همیشه باید وجود داشته باشد». این آزمون بدون شبکه ثابت می‌کند:
۱. پارسر بیت‌یونیکس هر دو شکل (دیکشنری/لیست، ثانیه/میلی‌ثانیه) را می‌خواند.
۲. صفحه‌بندی ۲۰۰تایی تا n کندل، یکتا و مرتب.
۳. سوییچ LIAM9_CANDLES=perp اول پرپ می‌رود و در شکست به اسپات برمی‌گردد.
۴. پیش‌فرض همان اسپات تاریخی است (هیچ دفتری بی‌سنجش عوض نمی‌شود).
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
sys.path.insert(0, str(PY))

import sources as S                                   # noqa: E402

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


T0 = 1_756_800_000_000            # ms
STEP = 900_000                    # 15m


def _row(i, sec=False, as_list=False):
    t = T0 + i * STEP
    o = 100 + i * 0.1
    vals = (o, o + 0.5, o - 0.5, o + 0.2, 10 + i)
    if as_list:
        return [t // 1000 if sec else t, *vals]
    return {"time": t // 1000 if sec else t, "open": str(vals[0]), "high": str(vals[1]),
            "low": str(vals[2]), "close": str(vals[3]), "baseVol": str(vals[4]), "quoteVol": "1"}


# ── ۱. پارسر ──────────────────────────────────────────────────────────────
rows = S._bitunix_parse({"code": 0, "data": [_row(2), _row(0), _row(1)]})
check("دیکشنری‌های نامرتب → ۳ ردیف مرتب قدیمی→جدید", [r[0] for r in rows] == [T0, T0 + STEP, T0 + 2 * STEP])
check("قیمت‌های رشته‌ای به عدد تبدیل شدند", rows[0][1] == 100.0 and rows[0][4] == 100.2)
rows_s = S._bitunix_parse({"data": [_row(0, sec=True), _row(1, sec=True)]})
check("زمانِ ثانیه‌ای به میلی‌ثانیه یکنواخت می‌شود", rows_s[0][0] == T0 and rows_s[1][0] == T0 + STEP)
rows_l = S._bitunix_parse([_row(0, as_list=True), _row(1, as_list=True)])
check("شکل لیستی هم خوانده می‌شود", len(rows_l) == 2 and rows_l[1][2] == 100.6)
check("ردیف خراب حذف می‌شود، بقیه می‌مانند", len(S._bitunix_parse({"data": [_row(0), {"time": "x"}, _row(1)]})) == 2)
check("پاسخ خالی/نامعتبر = لیست خالی، نه استثنا", S._bitunix_parse({"code": 1}) == [] and S._bitunix_parse(None) == [])

# ── ۲. صفحه‌بندی ────────────────────────────────────────────────────────
calls = []
N_ALL = 500


def fake_json(url):
    calls.append(url)
    end = None
    if "endTime=" in url:
        end = int(url.split("endTime=")[1].split("&")[0])
    limit = int(url.split("limit=")[1].split("&")[0])
    # جدیدترین N_ALL کندل موجود
    last_i = N_ALL - 1 if end is None else min(N_ALL - 1, (end - T0) // STEP)
    first_i = max(0, last_i - limit + 1)
    return {"code": 0, "data": [_row(i) for i in range(first_i, last_i + 1)]}


got = S._bitunix_fetch("BTCUSDT", "15m", 420, _json_fn=fake_json)
check("۴۲۰ کندل از صفحه‌های ۲۰۰تایی جمع شد", len(got) == 420, str(len(got)))
check("سه درخواست (۲۰۰+۲۰۰+۲۰)", len(calls) == 3, str(len(calls)))
check("یکتا و مرتب، جدیدترین کندل آخر است", got[-1][0] == T0 + (N_ALL - 1) * STEP and all(got[i][0] < got[i + 1][0] for i in range(len(got) - 1)))
check("sane() این پنجره را می‌پذیرد", S.sane(got, 420))
check("درخواست اول limit=200 و type=LAST_PRICE دارد", "limit=200" in calls[0] and "LAST_PRICE" in calls[0] and "endTime" not in calls[0])
calls.clear()
short = S._bitunix_fetch("XUSDT", "15m", 420, _json_fn=lambda u: {"data": [_row(i) for i in range(50)]})
check("صرافی کمتر از خواسته داد → همان‌قدر برمی‌گردد (sane پایین‌دست رد می‌کند)", len(short) == 50 and not S.sane(short, 420))

# ── ۳. ترتیب و سوییچ ────────────────────────────────────────────────────
check("بیت‌یونیکس اولین صرافی پرپ است", S.PERP_VENUES[0]["id"] == "bitunix-perp" and S.PERP_VENUES[0].get("fetch"))
check("پیش‌فرضِ منبع اسپات است (سوییچ فقط با LIAM9_CANDLES=perp)", S.CANDLE_SOURCE in ("spot", "perp"))
_saved = (S.CANDLE_SOURCE, S.perp_klines, S.klines)
try:
    S.CANDLE_SOURCE = "perp"
    S.perp_klines = lambda sym, tf, n, quiet=True: [["perp"]]
    S.klines = lambda sym, tf, n, quiet=True: [["spot"]]
    check("perp ترجیح: اول پرپ", S.klines_pref("BTCUSDT", "15m", 10) == [["perp"]])

    def boom(*a, **k):
        raise RuntimeError("down")
    S.perp_klines = boom
    check("perp ترجیح، پرپ خراب → پشتیبان اسپات (هیچ مصرف‌کننده‌ای بی‌کندل نمی‌ماند)", S.klines_pref("BTCUSDT", "15m", 10) == [["spot"]])
    S.CANDLE_SOURCE = "spot"
    S.perp_klines = lambda *a, **k: [["perp"]]
    check("spot پیش‌فرض: اصلاً سراغ پرپ نمی‌رود", S.klines_pref("BTCUSDT", "15m", 10) == [["spot"]])
finally:
    S.CANDLE_SOURCE, S.perp_klines, S.klines = _saved

# ── ۴. اسکن هم همین سوییچ را دارد ────────────────────────────────────────
scan_src = (PY / "scan.py").read_text(encoding="utf-8")
check("scan.klines_now با LIAM9_CANDLES=perp اول پرپ را می‌خواند و اسپات پشتیبان می‌ماند",
      "sources.CANDLE_SOURCE" in scan_src and "sources.perp_klines(" in scan_src and "/api/v3/klines" in scan_src)

print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
sys.exit(1 if FAIL else 0)
