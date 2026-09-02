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
# یافتهٔ رانر (کاوش ۵): high یک تیک زیر open → رُندِ صرافی؛ تا ۰.۱٪ چسبانده می‌شود
quirk = S._bitunix_parse({"data": [{"time": T0, "open": "77864.5", "high": "77864.4", "low": "77777.7", "close": "77803.8", "baseVol": "1"},
                                     {"time": T0 + STEP, "open": "77803.8", "high": "77900", "low": "77803.9", "close": "77850", "baseVol": "1"}]})
check("سقفِ یک‌تیک‌زیرِ open (و کفِ یک‌تیک‌بالای بدنه) چسبانده می‌شود و سری معتبر می‌ماند",
      quirk[0][2] == 77864.5 and quirk[1][3] == 77803.8 and S.sane_why(quirk, 2) == "", S.sane_why(quirk, 2))
bad = S._bitunix_parse({"data": [{"time": T0, "open": "100", "high": "90", "low": "80", "close": "95", "baseVol": "1"}]})
check("انحراف بزرگ (۱۰٪) چسبانده نمی‌شود و sane ردش می‌کند", bad and bad[0][2] == 90.0 and S.sane_why(bad, 1) != "")

# ── ۲. صفحه‌بندی ────────────────────────────────────────────────────────
calls = []
N_ALL = 500


def _fake(semantics):
    """سه تفسیر ممکن endTime — کاوش ۶ روی رانر نشان داد بیت‌یونیکس «بسته≤» است."""
    def fake_json(url):
        calls.append(url)
        end = None
        if "endTime=" in url:
            end = int(url.split("endTime=")[1].split("&")[0])
        limit = int(url.split("limit=")[1].split("&")[0])
        if end is None:
            last_i = N_ALL - 1
        elif semantics == "open<=":      # open ≤ endTime
            last_i = (end - T0) // STEP
        elif semantics == "open<":       # open < endTime
            last_i = (end - 1 - T0) // STEP
        else:                            # close ≤ endTime  ⇔  open ≤ endTime − step
            last_i = (end - STEP - T0) // STEP
        last_i = min(N_ALL - 1, last_i)
        first_i = max(0, last_i - limit + 1)
        return {"code": 0, "data": [_row(i) for i in range(first_i, last_i + 1)]}
    return fake_json


for sem in ("close<=", "open<", "open<="):
    calls.clear()
    got = S._bitunix_fetch("BTCUSDT", "15m", 420, _json_fn=_fake(sem))
    check(f"[{sem}] ۴۲۰ کندل از صفحه‌های ۲۰۰تایی جمع شد", len(got) == 420, str(len(got)))
    check(f"[{sem}] یکتا و مرتب، جدیدترین کندل آخر است", got[-1][0] == T0 + (N_ALL - 1) * STEP and all(got[i][0] < got[i + 1][0] for i in range(len(got) - 1)))
    check(f"[{sem}] بی‌شکاف: هیچ کندلی در مرز صفحه‌ها جا نمی‌افتد (یافتهٔ کاوش ۵ و ۶)", all(got[i + 1][0] - got[i][0] == STEP for i in range(len(got) - 1)),
          str(sorted({got[i + 1][0] - got[i][0] for i in range(len(got) - 1)})))
    check(f"[{sem}] sane() این پنجره را می‌پذیرد", S.sane(got, 420))
    check(f"[{sem}] حداکثر ۴ درخواست", 3 <= len(calls) <= 4, str(len(calls)))
check("درخواست اول limit=200 و type=LAST_PRICE دارد", "limit=200" in calls[0] and "LAST_PRICE" in calls[0] and "endTime" not in calls[0])
check("صفحهٔ دوم endTime=قدیمی‌ترینِ صفحهٔ اول (نه −۱، نه −step)", f"endTime={T0 + (N_ALL - 200) * STEP}" in calls[1], calls[1])
calls.clear()
stuck = S._bitunix_fetch("YUSDT", "15m", 420, _json_fn=lambda u: (calls.append(u), {"data": [_row(i) for i in range(300, 500)]})[1])
check("صرافی همان صفحه را تکرار کند → حلقه می‌ایستد، بی‌پایان نمی‌شود", len(stuck) == 200 and len(calls) == 2, f"{len(stuck)} rows / {len(calls)} calls")
calls.clear()
short = S._bitunix_fetch("XUSDT", "15m", 420, _json_fn=lambda u: {"data": [_row(i) for i in range(50)]})
check("صرافی کمتر از خواسته داد → همان‌قدر برمی‌گردد (sane پایین‌دست رد می‌کند)", len(short) == 50 and not S.sane(short, 420))

# ── ۳. ترتیب و سوییچ ────────────────────────────────────────────────────
check("بیت‌یونیکس اولین صرافی پرپ است", S.PERP_VENUES[0]["id"] == "bitunix-perp" and S.PERP_VENUES[0].get("fetch"))
check("پیش‌فرضِ منبع اسپات است (سوییچ فقط با LIAM9_CANDLES=perp)", S.CANDLE_SOURCE in ("spot", "perp"))
_saved = (S.CANDLE_SOURCE, S.perp_klines, S.spot_klines)
try:
    S.CANDLE_SOURCE = "perp"
    S.perp_klines = lambda sym, tf, n, quiet=True: [["perp"]]
    S.spot_klines = lambda sym, tf, n, quiet=True: [["spot"]]
    check("perp ترجیح: sources.klines (نقطهٔ واحد ۴۰+ مصرف‌کننده) اول پرپ می‌رود", S.klines("BTCUSDT", "15m", 10) == [["perp"]])
    check("klines_pref همان klines است (نام قدیمی نمی‌شکند)", S.klines_pref is S.klines)

    def boom(*a, **k):
        raise RuntimeError("down")
    S.perp_klines = boom
    check("perp ترجیح، پرپ خراب → پشتیبان اسپات (هیچ مصرف‌کننده‌ای بی‌کندل نمی‌ماند)", S.klines("BTCUSDT", "15m", 10) == [["spot"]])
    S.CANDLE_SOURCE = "spot"
    S.perp_klines = lambda *a, **k: [["perp"]]
    check("spot پیش‌فرض: اصلاً سراغ پرپ نمی‌رود", S.klines("BTCUSDT", "15m", 10) == [["spot"]])
    S.CANDLE_SOURCE = "perp"
    check("spot_klines با سوییچ perp هم اسپات می‌ماند (perp_vs_spot به آن تکیه دارد)", S.spot_klines("BTCUSDT", "15m", 10) == [["spot"]])

    # ── هویت قرارداد (یافتهٔ کاوش ۹: PUMPUSDT پرپ ۱۷۱٪ دور از اسپات) ──
    S._perp_bad.clear(); S._perp_ok.clear()
    _row = lambda c: [0, c, c, c, c, 1]                                   # noqa: E731
    S.perp_klines = lambda sym, tf, n, quiet=True: [_row(2.7)] * 5        # پرپ ۲.۷ برابر
    S.spot_klines = lambda sym, tf, n, quiet=True: [_row(1.0)] * n
    out = S.klines("PUMPUSDT", "15m", 5)
    check("پرپِ همنام با قیمتِ بازارِ دیگر رد می‌شود و اسپات می‌نشیند", out and out[0][4] == 1.0 and "PUMPUSDT" in S._perp_bad, str(S._perp_bad))
    S.perp_klines = lambda sym, tf, n, quiet=True: [_row(1.004)] * 5      # basis عادی ۰.۴٪
    check("نماد ردشده در همین فرایند دیگر سراغ پرپ نمی‌رود", S.klines("PUMPUSDT", "15m", 5)[0][4] == 1.0)
    check("پرپ با basis عادی پذیرفته و هویتش یک‌بار ثبت می‌شود", S.klines("BTCUSDT", "15m", 5)[0][4] == 1.004 and "BTCUSDT" in S._perp_ok)
    S.spot_klines = lambda sym, tf, n, quiet=True: (_ for _ in ()).throw(RuntimeError("no spot"))
    check("بی‌اسپات = قابل‌راستی‌آزمایی نیست → پرپ پذیرفته (تنها منبع)", S.klines("NEWUSDT", "15m", 5)[0][4] == 1.004 and "NEWUSDT" in S._perp_ok)
    check("آستانهٔ هویت ۱۵٪ است (basis عادی ≤۱٪ هرگز رد نمی‌شود)", S.PERP_IDENTITY_TOL == 0.15)
    S._perp_bad.clear(); S._perp_ok.clear()
finally:
    S.CANDLE_SOURCE, S.perp_klines, S.spot_klines = _saved

# ── ۳ب. ردپا و اندازه‌گیری ─────────────────────────────────────────────────
pvs_src = (HERE / "perp_vs_spot.py").read_text(encoding="utf-8")
check("perp_vs_spot اسپات را صریح از spot_klines می‌گیرد", "sources.spot_klines" in pvs_src)
tg_src = (PY / "telegram.py").read_text(encoding="utf-8")
check("ردپای candle_src روی هر دو مسیر بازکردن پوزیشن می‌نشیند", tg_src.count("**_candle_trace()") >= 2 and '"candle_src"' in tg_src)
import hamid.paper as _paper                          # noqa: E402
_names = [c[0] for c in _paper.CONDITIONS]
check("ماشین بونفرونی شرط «کندل از پرپ بیت‌یونیکس» را دارد", "کندل از پرپ بیت‌یونیکس" in _names)
_cond = dict(_paper.CONDITIONS)["کندل از پرپ بیت‌یونیکس"]
check("شرط فقط روی bitunix-perp درست است، روی اسپات/None غلط",
      _cond({"candle_src": "bitunix-perp"}) and not _cond({"candle_src": "mexc"}) and not _cond({}))
import telegram as _tg                                # noqa: E402
_cap = _tg.caption({"dir": "LONG", "sym": "ETHUSDT", "tf": "15m", "entry": 100.0, "sl": 98.0,
                    "tp1": 104.0, "rr": 2.0, "candle_src": "bitunix-perp"})
check("کپشن نماد پرپ بیت‌یونیکس در تریدینگ‌ویو را دارد (BITUNIX:ETHUSDT.P)", "BITUNIX:ETHUSDT.P" in _cap, _cap[-300:])
check("کپشن منبع واقعی کندل را چاپ می‌کند", "bitunix-perp" in _cap)
_cap2 = _tg.caption({"dir": "SHORT", "sym": "XUSDT", "tf": "5m", "entry": 1.0, "sl": 1.02, "tp1": 0.96, "rr": 2.0})
check("بی‌ردپا: منبع «نامعلوم» یا منبعِ used()، هرگز ادعای بیت‌یونیکس", "BITUNIX:XUSDT.P" in _cap2 and "کندل تحلیل" in _cap2)
WF = PY.parent.parent / ".github" / "workflows"
for wf in ("pump-radar.yml", "live-scan.yml", "hamid-cycle.yml"):
    check(f"{wf}: سوییچ LIAM9_CANDLES=perp روشن است", "LIAM9_CANDLES: perp" in (WF / wf).read_text(encoding="utf-8"))

# ── ۳ج. برچسب منبع = شمارش، نه «آخرین صرافی» (اثبات سوییچ، ۲۱:۲۹) ─────────
S._used_counts.clear()
S._note_used("bitunix-perp"); S._note_used("bitunix-perp"); S._note_used("binance")
check("شمارش هر صرافی نگه داشته می‌شود", S.used_counts() == {"bitunix-perp": 2, "binance": 1})
check("used() همچنان آخرین صرافی را می‌گوید (سازگاری)", S.used()["klines"] == "binance")
check("برچسب پرپ از فهرست پرپ خوانده می‌شود، نه شناسهٔ خام", S.venue_label("bitunix-perp") == "Bitunix Perpetual" and S.venue_label("zzz") == "zzz")
import scan as _scan                                  # noqa: E402
_lbl = _scan._source_label()
check("برچسب اسکن، بیت‌یونیکس را با شمار بیشتر جلوتر از بایننس می‌آورد",
      _lbl.index("Bitunix Perpetual 2") < _lbl.index("Binance 1"), _lbl)
S._used_counts.clear()

# ── ۴. اسکن هم همین سوییچ را دارد ────────────────────────────────────────
scan_src = (PY / "scan.py").read_text(encoding="utf-8")
check("scan.klines_now با LIAM9_CANDLES=perp از sources.klines می‌خواند (پشتیبان + هویت) و اسپات پشتیبان می‌ماند",
      "sources.CANDLE_SOURCE" in scan_src and "sources.klines(" in scan_src
      and "sources.perp_klines(" not in scan_src and "/api/v3/klines" in scan_src)

print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
sys.exit(1 if FAIL else 0)
