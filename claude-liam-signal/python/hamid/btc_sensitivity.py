#!/usr/bin/env python3
"""حساسیت هر ارز به بیت‌کوین — لگ-کورولیشن تاریخی چندتایمه (دستور حمید، ۲۹ اوت).

حمید: «ارزها حتماً با گذشتهٔ بیت‌کوین لگ-کورولیشن شوند — بررسی در
تایم‌فریم‌های مختلف در گذشته که آیا با رفتار بیت‌کوین واکنشی داشته یا
خیر. اگر نسبت به رفتار بیت‌کوین بی‌تفاوت بوده، در امتیازی که برای
سیگنال‌شدنش می‌دهی تجدید نظر کن. تعداد خیلی کمی از ارزها مثل ارز ترامپ
خیلی با رفتار بیت‌کوین همسو نیستند، پس سیگنال‌شدنش باید از روی تحلیل
باشد. تاریخچه باید یکی از چندین پارامتری باشد که تحلیل را تأیید یا رد
می‌کند.»

سه کلاس، از روی همان دادهٔ کندل و همان `lagcorr` که از قبل داریم:

| کلاس | معنی | اثر روی امتیاز |
|---|---|---|
| `COUPLED` | تاریخاً به BTC واکنش نشان داده (|r| کافی در چند تایم) | بسترِ BTC وزن کامل دارد |
| `INDEPENDENT` | تاریخاً بی‌تفاوت بوده (مثل TRUMP) | بسترِ BTC وزنش کم می‌شود؛ حکم باید از ساختار خودِ نماد بیاید |
| `UNKNOWN` | نمونه کافی نیست | هیچ اثری — نه مثبت نه منفی (قانون ۱) |

سه قید که این ماژول را از «عدد قشنگ‌سازی» جدا می‌کند:

۱. **چند تایم‌فریم، نه یکی.** ۱۵د/۱س/۴س جدا سنجیده می‌شوند و کلاس از
   اجماعشان می‌آید. یک تایمِ خوش‌شانس کافی نیست.
۲. **هم‌زمان و باتأخیر، هر دو.** واکنش به BTC می‌تواند هم‌لحظه باشد
   (r در لگ صفر) یا با تأخیر. بیشینهٔ |r| روی هر دو گرفته می‌شود.
۳. **زیر کف نمونه، حکم صادر نمی‌شود.** `UNKNOWN` یعنی نمی‌دانیم — و
   «نمی‌دانم» هرگز به‌عنوان «مستقل» جا زده نمی‌شود.

مرزِ صادقانه: این ماژول **رتبه را کم یا زیاد نمی‌کند**؛ فقط اعلام
می‌کند بسترِ BTC برای این نماد چقدر شاهدِ معتبری است. اثر عددی‌اش روی
تصمیم از مسیر قانون ۰۳ می‌آید — تا CI از صفر رد نکرده، فقط برچسب و
شفافیت است، نه دروازه.

    python3 -m hamid.btc_sensitivity              # چند نماد نمونه
    python3 -m hamid.btc_sensitivity --write      # کل واچ‌لیست → signals/
"""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
ROOT = PY.parents[1]
sys.path.insert(0, str(PY))

OUT = ROOT / "signals" / "btc-sensitivity.json"

TFS = ("15m", "1h", "4h")
MAX_LAG = {"15m": 8, "1h": 6, "4h": 4}     # تا ۲ ساعت / ۶ ساعت / ۱۶ ساعت
MIN_N = {"15m": 200, "1h": 200, "4h": 80}
R_COUPLED = 0.20        # همان آستانهٔ سختِ lagcorr — کمتر از این، نویز است
R_INDIFFERENT = 0.10    # زیر این، در آن تایم بی‌تفاوت شمرده می‌شود
STALE_H = 24            # کلاس کهنه‌تر از این، خنثی خوانده می‌شود


def profile(btc_cd, sym_cd, tf):
    """بیشینهٔ |r| روی همهٔ تأخیرها (شامل لگ صفر) در یک تایم‌فریم."""
    from hamid.lagcorr import lag_profile, MS
    prof = lag_profile(btc_cd, sym_cd, MS[tf], MAX_LAG[tf], min_n=MIN_N[tf])
    if not prof:
        return None
    best_k, best = None, 0.0
    for k, v in prof.items():
        if abs(v["r"]) > abs(best):
            best, best_k = v["r"], k
    return {"tf": tf, "r": round(best, 3), "abs_r": round(abs(best), 3),
            "lag_bars": best_k, "n": prof[best_k]["n"]}


def classify(per_tf):
    """کلاس از اجماع تایم‌فریم‌ها — یک تایمِ تنها حکم نمی‌دهد."""
    seen = [p for p in per_tf if p]
    if len(seen) < 2:
        return {"klass": "UNKNOWN", "why": "کمتر از دو تایم‌فریم نمونهٔ کافی داشت"}
    strong = [p for p in seen if p["abs_r"] >= R_COUPLED]
    weak = [p for p in seen if p["abs_r"] < R_INDIFFERENT]
    top = max(seen, key=lambda p: p["abs_r"])
    if len(strong) >= 2:
        return {"klass": "COUPLED",
                "why": (f"در {len(strong)} تایم |r| ≥ {R_COUPLED} "
                        f"(بیشینه {top['abs_r']} در {top['tf']})")}
    if len(weak) == len(seen):
        return {"klass": "INDEPENDENT",
                "why": (f"در هر {len(seen)} تایم |r| < {R_INDIFFERENT} "
                        f"(بیشینه فقط {top['abs_r']} در {top['tf']})")}
    return {"klass": "UNKNOWN",
            "why": (f"شواهد ناهمخوان — بیشینه {top['abs_r']} در {top['tf']}، "
                    f"{len(strong)} تایم قوی از {len(seen)}")}


def measure(kc, sym, btc="BTCUSDT"):
    """kc: dict[(sym, tf)] -> candles. خروجی: کلاس + پروفایل هر تایم."""
    per = []
    for tf in TFS:
        b, s = kc.get((btc, tf)), kc.get((sym, tf))
        if not b or not s:
            continue
        try:
            p = profile(b, s, tf)
        except Exception:                            # noqa: BLE001
            p = None
        if p:
            per.append(p)
    c = classify(per)
    return {"sym": sym, "at": int(time.time() * 1000),
            "per_tf": per, **c}


def load():
    try:
        return json.loads(OUT.read_text(encoding="utf-8"))
    except Exception:                                # noqa: BLE001
        return {"generated": 0, "coins": {}}


def klass_of(sym, book=None):
    """کلاسِ ذخیره‌شدهٔ یک نماد — کهنه‌تر از STALE_H ساعت = UNKNOWN.

    مصرف‌کننده (امتیازدهی) از همین می‌خواند؛ نبودِ داده هرگز «مستقل»
    تفسیر نمی‌شود."""
    b = book or load()
    row = (b.get("coins") or {}).get(sym)
    if not row:
        return "UNKNOWN"
    age_h = (time.time() * 1000 - (row.get("at") or 0)) / 3600e3
    if age_h > STALE_H:
        return "UNKNOWN"
    return row.get("klass", "UNKNOWN")


def packet(book):
    from hamid import evidence_packet as EP
    coins = book.get("coins") or {}
    n = len(coins)
    cnt = {}
    for r in coins.values():
        cnt[r.get("klass")] = cnt.get(r.get("klass"), 0) + 1
    indep = [s for s, r in coins.items() if r.get("klass") == "INDEPENDENT"][:6]
    return EP.build(
        claim=(f"{cnt.get('COUPLED', 0)} نماد تاریخاً به BTC واکنش دارند، "
               f"{cnt.get('INDEPENDENT', 0)} بی‌تفاوت‌اند، "
               f"{cnt.get('UNKNOWN', 0)} نمونهٔ کافی ندارند"),
        numbers={"نماد": n, "آستانهٔ همبسته": R_COUPLED,
                 "آستانهٔ بی‌تفاوت": R_INDIFFERENT,
                 "تایم‌فریم": "/".join(TFS)},
        track_record=("کلاس از اجماع ≥۲ تایم‌فریم می‌آید؛ تک‌تایم حکم نمی‌دهد"),
        scenario_up=("نماد COUPLED: بسترِ BTC شاهد معتبر است و وزن کامل دارد"),
        scenario_down=("نماد INDEPENDENT (مثل TRUMP): بسترِ BTC شاهد ضعیفی "
                       "است؛ حکم باید از ساختار خودِ نماد بیاید"),
        invalidator=("رژیم بازار عوض شود — کلاس هر ۲۴ ساعت بازسنجی می‌شود و "
                     "کهنه‌ترش خنثی خوانده می‌شود"),
        sources=["کندل واقعی صرافی", "hamid/lagcorr.lag_profile"],
        limit=("همبستگی علیت نیست و این ماژول رتبه را جابه‌جا نمی‌کند؛ فقط "
               "اعلام می‌کند بسترِ BTC برای این نماد چقدر معتبر است. اثر "
               "عددی فقط از مسیر قانون ۰۳ (CI بالای صفر) وارد می‌شود." +
               (f" نمونهٔ مستقل‌ها: {'، '.join(indep)}" if indep else "")))


def _candles(sym, tf, n):
    """کندل واقعی از همان منبعِ مشترک بقیهٔ انجین‌ها (بدون منبع تازه)."""
    import sources
    rows = sources.klines(sym, tf, n)
    return [{"t": k[0], "o": k[1], "h": k[2], "l": k[3], "c": k[4], "v": k[5]}
            for k in rows]


def collect(syms, btc="BTCUSDT"):
    """کندل هر نماد در سه تایم + BTC — نمادِ بی‌داده بی‌صدا رد می‌شود."""
    N = {"15m": 800, "1h": 1000, "4h": 400}
    kc = {}
    for s in [btc] + list(syms):
        for tf in TFS:
            try:
                c = _candles(s, tf, N[tf])
                if c:
                    kc[(s, tf)] = c
            except Exception:                        # noqa: BLE001
                continue
    return kc


def main(argv):
    syms = [a for a in argv if not a.startswith("--")]
    if not syms:
        try:
            wl = json.loads((ROOT / "signals" / "watchlist.json").read_text())
            syms = [r["symbol"] for r in (wl.get("rows") or wl.get("coins") or [])][:60]
        except Exception:                            # noqa: BLE001
            syms = []
    if not syms:
        syms = ["ETHUSDT", "SOLUSDT", "TRUMPUSDT", "DOGEUSDT"]
    kc = collect(syms)
    book = load()
    coins = book.get("coins") or {}
    for s in syms:
        r = measure(kc, s)
        if r["klass"] != "UNKNOWN" or s not in coins:
            coins[s] = r
        print(f"  {s:14s} {r['klass']:12s} {r.get('why', '')}")
    out = {"generated": int(time.time() * 1000), "coins": coins}
    if "--write" in argv:
        OUT.parent.mkdir(exist_ok=True)
        OUT.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
        print(f"نوشته شد: {OUT.relative_to(ROOT)} ({len(coins)} نماد)")
    from hamid import evidence_packet as EP
    print("\n" + EP.render(packet(out)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
