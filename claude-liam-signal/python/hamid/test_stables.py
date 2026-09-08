"""محافظِ تحلیلِ تتر در کنارِ کلِ استیبل‌کوین‌ها (دستور حمید، ۸ سپتامبر).

    python3 -m hamid.test_stables

خطرِ کلاسی که این آزمون می‌بندد: خواندنِ «USDT.D بالا = بازار نزولی»
وقتی ریشهٔ حرکت چیزِ دیگری است (چرخشِ USDC→USDT یا ورودِ پولِ تازه).
هر چهار ریشه سناریوی ساختگیِ خودش را دارد و باید درست برچسب بخورد.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
sys.path.insert(0, str(PY))

from hamid import stables as S                       # noqa: E402

OK = 0
FAIL = []
T0 = 1_788_000_000_000
STEP = 3 * 60_000            # گامِ واقعیِ سری ~۳ دقیقه


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


def series(n, su0=180e9, sc0=60e9, other0=3_000e9,
           d_su=0.0, d_sc=0.0, d_other=0.0, b0=59.0, d_b=0.0):
    """سریِ ساختگی از **عرضه**‌ها ساخته می‌شود، نه از نسبت‌ها — چون در
    واقعیت هم نسبت از عرضه و مخرج می‌آید. هر سه جزء خطی حرکت می‌کنند."""
    pts = []
    for i in range(n):
        f = i / max(1, n - 1)
        su = su0 * (1 + d_su * f)
        sc = sc0 * (1 + d_sc * f)
        other = other0 * (1 + d_other * f)
        m = su + sc + other
        pts.append({"t": T0 + i * STEP, "m": m,
                    "u": round(su / m * 100, 3), "c": round(sc / m * 100, 3),
                    "b": round(b0 * (1 + d_b * f), 3)})
    return pts


# نمونهٔ ۴ ساعته = ۸۰ گامِ ۳دقیقه‌ای؛ دو برابرش می‌سازیم تا پنجره جا شود
N = 200

# ── ۱) چرخشِ استیبل: عرضهٔ تتر ↑ و یواس‌دی‌سی ↓، بازار ثابت ───────────
rot = series(N, d_su=+0.05, d_sc=-0.15)
c = S.classify(rot, 240)
check("چرخشِ USDC→USDT به‌عنوان ROTATION شناخته می‌شود",
      c["cause"] == "ROTATION", f"{c['cause']} · {c.get('why')}")
check("و صریح «گمراه‌کننده» علامت می‌خورد", c.get("misleading") is True)
check("در همین حالت USDT.D واقعاً بالا رفته (وگرنه آزمون بی‌معناست)",
      c["d_usdt_d"] > 0, str(c["d_usdt_d"]))
check("ولی STABLE.D تقریباً ثابت مانده — مصونیت از چرخش",
      abs(c["d_stable_d"]) < abs(c["d_usdt_d"]),
      f"Δتتر {c['d_usdt_d']} · Δاستیبل {c['d_stable_d']}")

# ── ۲) ریزشِ مخرج: عرضه‌ها ثابت، بازار می‌ریزد ───────────────────────
fall = series(N, d_other=-0.06)
c2 = S.classify(fall, 240)
check("ریزشِ بازار به‌عنوان MARKET_FALL شناخته می‌شود",
      c2["cause"] == "MARKET_FALL", f"{c2['cause']} · {c2.get('why')}")
check("و گمراه‌کننده نیست (ریسک‌آفِ واقعی)", c2.get("misleading") is False)
r2 = S.regime(fall, 240)
check("رژیمش SHORT_BIAS است", r2["bias"] == "SHORT_BIAS", r2.get("why"))

# ── ۳) پولِ تازه: هر دو عرضه بالا، بازار ثابت ────────────────────────
new = series(N, d_su=+0.06, d_sc=+0.06)
c3 = S.classify(new, 240)
check("ورودِ پولِ تازه به‌عنوان NEW_MONEY شناخته می‌شود",
      c3["cause"] == "NEW_MONEY", f"{c3['cause']} · {c3.get('why')}")
check("پولِ تازه هم «گمراه‌کننده» است (باروتِ خشک، نه ریزش)",
      c3.get("misleading") is True)

# ── ۴) بازارِ صعودی: عرضه ثابت، مخرج بزرگ ───────────────────────────
rise = series(N, d_other=+0.06)
c4 = S.classify(rise, 240)
check("رشدِ بازار به‌عنوان MARKET_RISE شناخته می‌شود",
      c4["cause"] == "MARKET_RISE", f"{c4['cause']} · {c4.get('why')}")
check("رژیمش LONG_BIAS است", S.regime(rise, 240)["bias"] == "LONG_BIAS")

# ── ۵) بی‌حرکت = FLAT، نه حکمِ ساختگی ────────────────────────────────
flat = series(N)
check("بازارِ بی‌حرکت حکمِ جهت نمی‌گیرد",
      S.regime(flat, 240)["bias"] == "NEUTRAL")

# ── ۶) دادهٔ ناقص = INSUFFICIENT، نه حدس (قانون ۰۱ بند ۱) ────────────
no_m = [{k: v for k, v in p.items() if k != "m"} for p in fall]
check("بدونِ کلِ بازار، حکم صادر نمی‌شود",
      S.classify(no_m, 240)["cause"] == "INSUFFICIENT")
check("سریِ خالی هم منفجر نمی‌شود",
      S.classify([], 240)["cause"] == "INSUFFICIENT"
      and S.regime([], 240)["bias"] == "INSUFFICIENT")
short_series = series(5)
check("سریِ کوتاه‌تر از پنجره = INSUFFICIENT",
      S.regime(short_series, 240)["bias"] == "INSUFFICIENT")

# ── ۷) هستهٔ استدلالِ حمید: چرخش، خواندنِ سادهٔ USDT.D را وارونه می‌کند ─
r_rot = S.regime(rot, 240)
check("در چرخش، خواندنِ سادهٔ «USDT.D تنها» با مبنای STABLE.D فرق می‌کند",
      r_rot["naive_usdt_only"] == "SHORT_BIAS" and r_rot["bias"] != "SHORT_BIAS",
      f"ساده={r_rot['naive_usdt_only']} · مبنا={r_rot['bias']}")
check("و این اختلاف صریح علامت می‌خورد",
      r_rot.get("disagrees_with_naive") is True)

# ── ۸) آستانه از توزیعِ خودِ سری می‌آید، نه از عددِ ثابت ─────────────
# پنجرهٔ کالیبراسیون ۶۰ دقیقه = ۲۰ گام؛ برای گذشتن از کفِ نمونه دست‌کم
# ۲۰ پنجره لازم است، یعنی ۴۲۰+ نقطه. (نسخهٔ اولِ همین بررسی ۴۰۰ نقطه
# داشت و هر دو سری به پشتیبان می‌افتادند — عیبِ آزمون بود، نه کد.)
NC = 900
noisy = []
for i in range(NC):
    wig = 0.02 if (i // 20) % 2 else -0.02          # نوسانِ بزرگِ دوره‌ای
    su = 180e9 * (1 + wig)
    m = su + 60e9 + 3_000e9
    noisy.append({"t": T0 + i * STEP, "m": m,
                  "u": round(su / m * 100, 3), "c": round(60e9 / m * 100, 3),
                  "b": 59.0})
thr_noisy = S.regime_threshold(noisy, 60)
thr_calm = S.regime_threshold(series(NC), 60)
check("کالیبراسیون واقعاً اجرا شد (نه سقوط به پشتیبان)",
      thr_noisy != S.REGIME_FALLBACK[60] or thr_calm != S.REGIME_FALLBACK[60],
      f"{thr_noisy} / {thr_calm}")
check("سریِ پرنوسان آستانهٔ بزرگ‌تری می‌گیرد از سریِ آرام",
      thr_noisy > thr_calm, f"پرنوسان {thr_noisy} · آرام {thr_calm}")
check("نمونهٔ کم → پشتیبانِ اعلام‌شده، نه عددِ ساختگی",
      S.regime_threshold(series(10), 240) == S.REGIME_FALLBACK[240])

# ── ۹) نقشهٔ دوبعدی با BTC.D (بند «و بقیهٔ دامیننس‌ها») ──────────────
fall_btc_up = series(N, d_other=-0.06, d_b=+0.02)
st_ = S.alt_stance(fall_btc_up, 240)
check("ریسک‌آف + BTC.D بالا = بدترین بسترِ آلت",
      st_["stance"] == "SHORT_ALT_STRONG", str(st_.get("stance")))
rise_btc_dn = series(N, d_other=+0.06, d_b=-0.02)
check("ریسک‌آن + BTC.D پایین = چرخش به آلت",
      S.alt_stance(rise_btc_dn, 240)["stance"] == "LONG_ALT_STRONG")
rise_btc_up = series(N, d_other=+0.06, d_b=+0.02)
check("ریسک‌آن + BTC.D بالا = پول به بیت‌کوین، نه آلت",
      S.alt_stance(rise_btc_up, 240)["stance"] == "LONG_BTC_ONLY")

# ── ۱۰) مرز و پوشش روی هر خروجی (قانون ۱۲) ──────────────────────────
v = S.build(fall)
check("بستهٔ خروجی مرزِ صادقانه دارد",
      "دروازه" in v.get("boundary", "") and "قانون ۰۳" in v.get("boundary", ""))
check("پوششِ ناقصِ استیبل‌ها اعلام می‌شود (DAI شمرده نمی‌شود)",
      "DAI" in v.get("coverage", ""))
check("روشِ سنجش روی خروجی نوشته شده (چرخش فقط روی عرضه دیده می‌شود)",
      "عرضه" in v.get("method", ""))
check("خطوطِ فارسی برای گزارش ساخته می‌شوند", len(S.fa_lines(v)) >= 2)

# ── ۱۱) فقط می‌خواند (قانون ۰۵) ─────────────────────────────────────
src = (HERE / "stables.py").read_text(encoding="utf-8")
check("این ماژول هیچ فایلی نمی‌نویسد",
      "write_text" not in src and "open(" not in src)

# ── ۱۲) سیم‌کشی: خروجی روی dominance.json و مصرفِ موتور شورت ─────────
dsrc = (HERE / "dominance.py").read_text(encoding="utf-8")
check("اتاق دامیننس بستهٔ استیبل را می‌نویسد",
      '"stables": stb' in dsrc and "stables.build" in dsrc.replace("_stb.build", "stables.build"))
ssrc = (PY / "liam9_short_strategy.py").read_text(encoding="utf-8")
check("موتور شورت همان کلید را می‌خواند",
      'get("stables")' in ssrc and "alt_stance" in ssrc)
# خاصیت، نه متن (درس ۶ سپتامبر): ترتیبِ **مسیرِ کد** سنجیده می‌شود، نه
# ترتیبِ جمله‌های فارسی. نسخهٔ اولِ همین بررسی به نثرِ کامنت چسبیده بود و
# با یک جملهٔ توضیحیِ بی‌ضرر می‌افتاد.
import inspect                                       # noqa: E402
from liam9_short_strategy import decide as _decide    # noqa: E402
_body = inspect.getsource(_decide)
check("و در مسیرِ کد، دروازهٔ دامیننس پیش از دروازهٔ BTC صدا زده می‌شود",
      _body.index("dominance_gate(") < _body.index('btc_4h == "up"'),
      "ترتیبِ اجرای دروازه‌ها عوض شده")
rsrc = (HERE / "dominance_report.py").read_text(encoding="utf-8")
check("گزارش ساعتی هم خطوطش را می‌برد", "stables" in rsrc)

# ── ۱۳) روی سریِ واقعی، بدونِ انفجار ────────────────────────────────
real = PY.parents[1] / "brain" / "dominance-series.json"
if real.exists():
    pts = json.loads(real.read_text(encoding="utf-8")).get("points") or []
    out = S.build(pts)
    check("روی سریِ واقعی خروجیِ معتبر می‌دهد",
          out.get("stable_d") is not None
          and (out.get("alt_stance") or {}).get("stance"),
          str(out.get("alt_stance"))[:120])
    check("STABLE.D برابر جمعِ اجزاست",
          abs(out["stable_d"] - sum(v for v in out["parts"].values() if v)) < 0.002)
else:
    check("(سریِ واقعی در دسترس نبود — بررسی رد شد، نه شکست)", True)

print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
sys.exit(1 if FAIL else 0)
