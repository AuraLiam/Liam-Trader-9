#!/usr/bin/env python3
"""بک‌تستِ کندلِ واقعیِ موتور شورت — همان چیزی که حکم را می‌دهد.

دفترِ پیپر گفت این چهار فیلتر ضررِ شورت را از −۰.۳۱R به ~صفر می‌آورند،
ولی دو چیز را **نمی‌توانست** بگوید:

۱. آن دفتر با قواعدِ دیگری ساخته شده بود؛ ردیف‌هایش فقط با فیلتر
   *برچسب‌گذاری* شدند، نه با این موتور *تولید*. یعنی شاهد است، نه آزمون.
۲. هر ۵۹۴ ردیفِ فیلترشده RR بین ۲.۰ و ۲.۵ داشتند — پس هندسهٔ تارگت
   اصلاً تنوع نداشت و از رویش نمی‌شد فهمید تارگتِ بزرگ‌تر جواب می‌دهد
   یا نه.

این ماژول موتور را روی کندلِ واقعی **بازپخش** می‌کند: بار به بار، فقط
با دادهٔ تا همان لحظه. شبکه لازم دارد، پس روی رانر می‌دود نه این‌جا.

## قاعدهٔ توقف — از پیش ثبت‌شده، نه بعد از دیدن نتیجه

| حکم | شرط |
|---|---|
| `PROMOTE` | CI95 **خالص از کارمزد** کاملاً بالای صفر روی n ≥ ۲۰۰ → فقط *پیشنهادِ* تولید؛ ورودش تأیید صریح حمید می‌خواهد (قانون ۱۲) |
| `REJECT` | CI95 خالص کاملاً زیر صفر روی n ≥ ۵۰۰ |
| `UNDECIDED` | بقیه، با برآوردِ «چند معاملهٔ دیگر تا تصمیم‌پذیری» |

حکم به **اثرانگشتِ پارامترها** گره خورده است (همان درسِ
`scalp_verdict`): عوض‌شدن هر پارامتر یعنی دفترِ حکم از صفر. پس REJECT
یعنی «این هندسه را اجرا نکن»، نه «شورت را رها کن».

## دو محافظه‌کاریِ عمدی

- **استاپ قبل از تارگت داخل یک کندل.** وقتی یک کندل هم استاپ و هم
  تارگت را لمس می‌کند، نمی‌دانیم کدام اول رسید؛ بدترین حالت فرض
  می‌شود. خوش‌بینیِ درون‌کندلی همان چیزی است که بک‌تست را دروغگو
  می‌کند.
- **کارمزد از `hamid/fees`**، نه عددِ محلی — و همیشه بازمحاسبه، نه
  خوانده از ردیف (سوگیریِ `fee_r` ذخیره‌شده، درس ۷ سپتامبر).
"""
import json
import math
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
ROOT = HERE.parents[2]
OUT = ROOT / "signals" / "short-backtest.json"

import liam9_short_strategy as S                     # noqa: E402
from hamid import trainer as TR                      # noqa: E402

MIN_N_PROMOTE = 200
MIN_N_REJECT = 500
TF_MS = {"5m": 300_000, "15m": 900_000, "1h": 3600_000, "4h": 14_400_000}


def fingerprint():
    """اثرانگشتِ هندسه — حکم فقط برای همین پارامترها معتبر است."""
    keys = ("min_stop_pct", "max_stop_pct", "rr_target", "min_net_rr",
            "min_chan_pos", "max_hold_bars")
    return "·".join(f"{k}={S.P[k]}" for k in keys)


def _htf_upto(htf, t_ms):
    """کندل‌های تایمِ بالا که **قبل از** این لحظه بسته شده‌اند.

    این تابع تنها جایی است که نگاه به آینده می‌تواند مخفی شود، پس
    شرطش سخت است: کندلی که هنوز باز است حذف می‌شود، نه اینکه «تقریباً
    بسته» حساب شود.
    """
    out = []
    for c in htf:
        t = S._ts(c)
        if t is None:
            continue
        out.append(c)
        if t >= t_ms:
            out.pop()
            break
    return out


NO_HISTORY = "UNKNOWN_NO_HISTORY"


def stance_fn(series=None, path=None):
    """→ callable(now_ms) → بسترِ استیبل در همان لحظه، یا None.

    سریِ دامیننس فقط از ۲۹ اوت ۲۰۲۶ جمع شده، پس برای بیشترِ بازهٔ یک
    بک‌تستِ عمیق **وجود ندارد**. آن‌جا `NO_HISTORY` برمی‌گردد — که نه
    وتو می‌کند نه تأیید؛ یعنی خطِ پایه دست‌نخورده می‌ماند و برشِ دروازه
    فقط روی بازه‌ای سنجیده می‌شود که واقعاً داده دارد. جعلِ بستر برای
    گذشته، همان «عددِ بی‌منبع» است (قانون ۰۱ بند ۱).

    کش بر سطلِ ۱۵دقیقه‌ای: بسترِ استیبل روی افق ۴ساعته سنجیده می‌شود و
    بین دو کندلِ ۱۵د عملاً تکان نمی‌خورد؛ بی‌کش، هر بار یک پیمایشِ کاملِ
    سری لازم بود و بازپخش عملاً نمی‌ایستاد.
    """
    if series is None:
        p = Path(path) if path else (ROOT / "brain" / "dominance-series.json")
        try:
            series = json.loads(p.read_text(encoding="utf-8")).get("points") or []
        except Exception:                            # noqa: BLE001
            series = []
    if not series:
        return None
    try:
        from hamid import stables as STB
    except Exception:                                # noqa: BLE001
        return None
    lo = min(p["t"] for p in series)
    hi = max(p["t"] for p in series)
    cache = {}

    def at(now_ms):
        if now_ms < lo or now_ms > hi:
            return NO_HISTORY
        k = int(now_ms // (15 * 60_000))
        if k not in cache:
            s = (STB.alt_stance(series, 240, now_ms=int(now_ms)) or {}).get("stance")
            cache[k] = s if s and s != "INSUFFICIENT" else NO_HISTORY
        return cache[k]
    return at


def replay(symbol, cd15, cd4h, btc1h=None, btc4h=None, tf="15m",
           warmup=200, stance_at=None):
    """بازپخشِ بار-به-بار. → فهرست معامله‌ها.

    هیچ کندلی بعد از اندیس جاری به موتور داده نمی‌شود؛ خروج هم فقط از
    کندل‌های **بعدی** خوانده می‌شود.

    `stance_at(now_ms)` بسترِ استیبل را در همان لحظه می‌دهد (دستور حمید
    ۸ سپتامبر: اولویتِ اول). بی‌آن، دروازهٔ دامیننس هر آلتی را وتو
    می‌کرد و بک‌تست صفر معامله می‌داد — پس این‌جا صریح تزریق می‌شود و
    روی هر معامله ثبت، تا مقایسهٔ «با دروازه / بی‌دروازه» **جفتی** باشد.
    """
    from hamid import fees
    tf_ms = TF_MS.get(tf, 900_000)
    trades = []
    i = warmup
    n = len(cd15)
    while i < n - 1:
        t = S._ts(cd15[i])
        if t is None:
            i += 1
            continue
        now = t + tf_ms                              # کندلِ i تازه بسته شد
        b4 = S.trend(_htf_upto(btc4h, now)) if btc4h else None
        b1 = S.trend(_htf_upto(btc1h, now)) if btc1h else None
        # بستر در **همان لحظه** محاسبه می‌شود؛ `dom_generated=now` یعنی
        # عکس‌فوری تازه است (نگاه به آینده نیست — تابع فقط نقاطِ ≤ now
        # را می‌بیند، چون `stables._at` پنجرهٔ گذشته را می‌گیرد).
        st_ = stance_at(now) if stance_at else NO_HISTORY
        d = S.decide(symbol, cd15[:i + 1], tf=tf,
                     cd_4h=_htf_upto(cd4h, now),
                     btc_4h=b4, btc_1h=b1, now_ms=now,
                     alt_stance=st_, dom_generated=now)
        if d.get("action") != "SHORT":
            i += 1
            continue
        entry, sl, tp1 = d["entry"], d["sl"], d["tp1"]
        # خروج از **همان** `trainer.resolve` که دفترِ سنجیده‌شده را ساخته
        # (استاپ قبل از تارگت داخل کندل · تریلِ ⅓ مسیر → +۰.۱۵R · سقف).
        # نسخهٔ قبل خروجِ خودش را داشت و تریل نداشت؛ ۱۰۳ از ۲۶۶ ردیفِ
        # واقعیِ دفتر با تریل بسته شده بودند — یعنی سومین جایی که اجرا از
        # اندازه‌گیری جدا افتاده بود.
        dcd = S._dicts(cd15)
        j, outcome, out_r, exc = TR.resolve(
            dcd, i, {"entry": entry, "sl": sl, "tp1": tp1, "dir": "SHORT"},
            max_hold=S.P["max_hold_bars"])
        bars = j - i
        if outcome == "timeout" and j >= n - 1 and bars < S.P["max_hold_bars"]:
            break                                    # ته‌داده: ثبت نمی‌شود (بریده)
        fee_r = fees.cost_in_r(entry, sl, symbol=symbol)
        trades.append({"sym": symbol, "t": t, "entry": entry, "sl": sl,
                       "tp1": tp1, "R": round(out_r, 4),
                       "outcome": outcome, "btc_4h": b4, "btc_1h": b1,
                       "fee_r": round(fee_r, 4),
                       "net": round(out_r - fee_r, 4),
                       "stop_pct": d["stop_pct"], "bars": bars,
                       "chan_pos": d["chan_pos"],
                       "alt_stance": d.get("alt_stance") or st_, **exc})
        i = j + 1                                    # یک پوزیشن در هر لحظه
    return trades


def _count(trades):
    out = {}
    for t in trades:
        k = t.get("outcome") or "?"
        out[k] = out.get(k, 0) + 1
    return out


def _ci(vals):
    if len(vals) < 2:
        return None
    m = sum(vals) / len(vals)
    sd = (sum((x - m) ** 2 for x in vals) / (len(vals) - 1)) ** 0.5
    se = sd / math.sqrt(len(vals))
    return {"n": len(vals), "mean": round(m, 4), "sd": round(sd, 4),
            "lo": round(m - 1.96 * se, 4), "hi": round(m + 1.96 * se, 4)}


def judge(trades):
    nets = [t["net"] for t in trades]
    ci = _ci(nets)
    if not ci:
        # قرارداد خروجی **یکی** است، چه نمونه باشد چه نباشد — وگرنه
        # مصرف‌کننده (merge/render) روی حالتِ کم‌نمونه می‌ترکد.
        return {"verdict": "UNDECIDED", "why": "نمونهٔ کم", "net": ci,
                "gross": None, "per_stance": {}, "dom_gate": None,
                "need": MIN_N_PROMOTE, "need_more": MIN_N_PROMOTE}
    n = ci["n"]
    if ci["lo"] > 0 and n >= MIN_N_PROMOTE:
        v, why = "PROMOTE", "CI خالص کاملاً بالای صفر"
    elif ci["hi"] < 0 and n >= MIN_N_REJECT:
        v, why = "REJECT", "CI خالص کاملاً زیر صفر"
    else:
        v, why = "UNDECIDED", "CI هنوز شاملِ صفر است یا نمونه کافی نیست"
    # چند نمونهٔ دیگر تا نصف‌شدنِ پهنای CI به اندازهٔ فاصله تا صفر
    need = 0
    if v == "UNDECIDED" and ci["sd"] > 0 and ci["mean"] != 0:
        want = (1.96 * ci["sd"] / abs(ci["mean"])) ** 2
        need = max(0, int(want) - n)
        need = max(need, MIN_N_PROMOTE - n if ci["mean"] > 0 else
                   MIN_N_REJECT - n)
    # برشِ بسترِ استیبل (دستور حمید ۸ سپتامبر). دروازه فقط **وتو** می‌کند،
    # پس «با دروازه» زیرمجموعهٔ «بی دروازه» است و مقایسه جفتی است: همان
    # کندل‌ها، همان ستاپ‌ها، فقط بخشی کنار گذاشته می‌شود.
    with_h = [t for t in trades if t.get("alt_stance") not in (None, NO_HISTORY)]
    per_stance = {}
    for st_ in sorted({t.get("alt_stance") or NO_HISTORY for t in trades}):
        per_stance[st_] = _ci([t["net"] for t in trades
                               if (t.get("alt_stance") or NO_HISTORY) == st_])
    gate = None
    if with_h:
        keep = [t for t in with_h if t["alt_stance"] in S.DOM_FAVORS_SHORT
                or t["alt_stance"] not in S.DOM_VETO_SHORT]
        drop = [t for t in with_h if t["alt_stance"] in S.DOM_VETO_SHORT]
        gate = {"window_only": True,
                "note": ("فقط بازه‌ای که سریِ دامیننس دارد؛ بقیهٔ بازپخش "
                         "بستر ندارد و در این برش نیست"),
                "ungated": _ci([t["net"] for t in with_h]),
                "gated": _ci([t["net"] for t in keep]),
                "vetoed": _ci([t["net"] for t in drop]),
                "favors_only": _ci([t["net"] for t in with_h
                                    if t["alt_stance"] in S.DOM_FAVORS_SHORT])}
    return {"verdict": v, "why": why, "net": ci,
            "gross": _ci([t["R"] for t in trades]),
            "per_stance": per_stance, "dom_gate": gate,
            "need_more": max(0, need)}


def trainer_shorts(symbol, cd15, tf="15m"):
    """همان کندل‌ها، از دیدِ خودِ `trainer.replay_symbol` — یعنی دقیقاً همان
    کدی که دفترِ سنجیده‌شده را ساخته. → (فیلترشده، همهٔ شورت‌ها).

    چرا: بعد از سه رفع (تعریف‌های قرضی، خروجِ trainer، بی‌بریده) موتور روی
    کندلِ واقعی هنوز −۰.۸۵R می‌داد و ردیف‌های واقعیِ دفتر −۰.۱۰R. این دو
    را فقط یک آزمون از هم جدا می‌کند: trainer را روی **همین** داده بدوان.
    اگر trainer هم این‌جا ~−۰.۸ بدهد، موتور وفادار است و اختلاف از رژیم/
    جهانِ نماد است؛ اگر ~−۰.۱ بدهد، هنوز جایی از موتور با اندازه‌گیری
    فرق دارد.
    """
    from hamid import fees
    d = S._dicts(cd15)
    trades, _ = TR.replay_symbol(symbol, d, after_ms=0, cap=10_000, tf=tf)
    allsh, filt = [], []
    for t in trades:
        if t.get("dir") != "SHORT" or TR.is_censored({**t, "tf": tf}):
            continue
        w = t.get("why") or {}
        fee_r = fees.cost_in_r(t["entry"], t["sl"], symbol=symbol)
        row = {"sym": symbol, "t": t["opened"], "R": t["R"],
               "net": round(t["R"] - fee_r, 4), "outcome": t["outcome"],
               "stop_pct": w.get("stop_pct"), "chan_pos": w.get("chan_pos"),
               "ob_align": w.get("ob_align"), "trend": w.get("trend_4h")}
        allsh.append(row)
        # همان چهار فیلتر، پس‌ازواقعه — همان‌طور که روی دفتر زده شد
        if (S.P["min_stop_pct"] <= (w.get("stop_pct") or 0) <= S.P["max_stop_pct"]
                and w.get("ob_align") == "with"
                and (w.get("chan_pos") or 0) > S.P["min_chan_pos"]
                and w.get("trend_4h") == "down"):
            filt.append(row)
    return filt, allsh


def _src_fetch(src):
    """لودرِ آرشیو سه‌سالهٔ درایو (aura-history) به‌جای صرافی — همان
    `history_ingest.load_klines` + `history_backtest.resample`، تا ۴س از
    خودِ ۱۵د با برچسبِ بی‌آینده ساخته شود (درایو تایم بالا ندارد)."""
    from hamid import history_ingest
    from hamid.history_backtest import resample
    inv_path = Path(src) / "inventory_short.json"
    inv = history_ingest.ingest(src, out_path=inv_path, quiet=True)
    cache = {}

    def fetch(sym, tf, n):
        if sym not in cache:
            cache[sym] = history_ingest.load_klines(sym, "15m", inv_path) or []
        c15 = cache[sym]
        if tf == "15m":
            return c15[-n:] if n else c15
        mins = {"1h": 60, "4h": 240}.get(tf)
        if not mins:
            return []
        r = resample(c15, mins)
        return r[-n:] if n else r

    syms = sorted(k.rsplit("_", 1)[0] for k, e in inv["klines"].items()
                  if e.get("status") == "OK" and k.endswith("_15m"))
    return fetch, syms


def htf_depth(bars, tf="15m"):
    """عمقِ تایمِ بالا متناسب با عمقِ ۱۵د، به‌اضافهٔ حاشیهٔ پنجره.

    عیبِ ۷ سپتامبر: بسترِ BTC و ۴سِ نماد همیشه ۵۰۰ کندل بود (≈۸۳ روزِ ۴س).
    در بازپخشِ ۷ماهه، آلت‌ها در ماه‌های اول بسترِ BTC نداشتند و بی‌صدا
    NO_SIGNAL می‌شدند — نمونه‌ای که فقط انتهای تاریخ را می‌دید و اسمش
    «عمیق» بود."""
    ms = TF_MS.get(tf, 900_000)
    span = bars * ms
    return {"1h": int(span / 3_600_000) + 300,
            "4h": int(span / 14_400_000) + 300}


def run(symbols, tf="15m", bars=1000, fetch=None, compare=True,
        shard=0, shards=1):
    """`shard/shards`: تکه‌بندیِ قطعی روی فهرستِ مرتبِ نمادها — همان الگوی
    `history_backtest` تا اجرای عمیق روی ماتریسِ رانر تقسیم شود.

    عمقِ بیش از ۱۰۰۰ کندل از `sources.klines_deep` می‌آید («تا N، دست‌کم
    کف») و تایمِ بالا هم به همان نسبت عمیق گرفته می‌شود."""
    symbols = sorted(symbols)[shard::shards] if shards > 1 else list(symbols)
    if fetch is None:
        import sources
        if bars and bars > 1000:
            fetch = lambda s, t, n: sources.klines_deep(s, t, n)   # noqa: E731
        else:
            fetch = lambda s, t, n: sources.klines(s, t, n)        # noqa: E731
    dep = htf_depth(bars or 1000, tf)
    n1h, n4h = max(500, dep["1h"]), max(500, dep["4h"])
    btc1h = btc4h = None
    try:
        btc1h, btc4h = fetch("BTCUSDT", "1h", n1h), fetch("BTCUSDT", "4h", n4h)
    except Exception as e:                           # noqa: BLE001
        print(f"بسترِ BTC گرفته نشد ({type(e).__name__}) — آلت‌ها رد می‌شوند")
    _stance = stance_fn()
    if _stance is None:
        print("سریِ دامیننس نیست — بسترِ استیبل روی هیچ معامله‌ای ثبت نمی‌شود")
    all_t, skipped, cmp_f, cmp_a = [], [], [], []
    for sym in symbols:
        try:
            cd = fetch(sym, tf, bars)
            cd4 = fetch(sym, "4h", n4h)
        except Exception as e:                       # noqa: BLE001
            skipped.append(f"{sym}: {type(e).__name__}")
            continue
        if not cd or len(cd) < 260:                 # bars=0 → کلِ سری از لودر
            skipped.append(f"{sym}: کندل کم ({len(cd or [])})")
            continue
        t = replay(sym, cd, cd4, btc1h=btc1h, btc4h=btc4h, tf=tf,
                   stance_at=_stance)
        all_t.extend(t)
        if compare:
            f_, a_ = trainer_shorts(sym, cd, tf=tf)
            cmp_f.extend(f_)
            cmp_a.extend(a_)
            print(f"  {sym}: موتور {len(t)} · trainer فیلترشده {len(f_)} · trainer همهٔ شورت‌ها {len(a_)}")
        else:
            print(f"  {sym}: {len(t)} معامله")
    v = judge(all_t)
    v["shard"], v["shards"] = shard, shards
    if compare:
        v["compare"] = {
            "trainer_filtered": _ci([x["net"] for x in cmp_f]),
            "trainer_all_shorts": _ci([x["net"] for x in cmp_a]),
            "engine_outcomes": _count(all_t),
            "trainer_filtered_outcomes": _count(cmp_f),
            "note": ("سه جمعیت روی **همان** کندل‌ها. اگر trainerِ فیلترشده هم "
                     "نزدیکِ موتور باشد، اختلاف با دفتر از رژیم/جهانِ نماد "
                     "است نه از کد؛ اگر نزدیکِ دفتر باشد، موتور هنوز جایی "
                     "فرق دارد."),
        }
    v.update({
        "generated": int(time.time() * 1000),
        "strategy": S.STRATEGY_ID, "version": S.STRATEGY_VERSION,
        "fingerprint": fingerprint(),
        "tf": tf, "symbols": len(symbols), "bars": bars,
        "skipped": skipped[:10],
        "stopping_rule": {"promote_min_n": MIN_N_PROMOTE,
                          "reject_min_n": MIN_N_REJECT,
                          "metric": "خالص از کارمزد (hamid/fees)"},
        "boundary": ("بازپخشِ کندلِ واقعی است، نه اجرای واقعی: فیلِ کامل و "
                     "بی‌لغزش فرض می‌شود، پس عددش سقفِ خوش‌بینانه است. "
                     "استاپ قبل از تارگت داخل یک کندل حساب می‌شود "
                     "(بدترین حالت). حکم فقط برای همین اثرانگشت معتبر است."),
        "panel": "لیام تریدر ۹",
    })
    return v, all_t


def _year(ms):
    return time.gmtime(ms / 1000).tm_year


def merge(shards_dir, out=None):
    """ادغام تکه‌ها → حکم با قاعدهٔ توقفِ از پیش ثبت‌شده + برشِ سال و رژیمِ
    BTC (قانون ۰۳: تغییرِ آستانه بدون out-of-sample و regime split ممنوع).

    تکه‌ها باید یک اثرانگشت داشته باشند؛ وگرنه ادغامشان دروغ است."""
    out = Path(out) if out else OUT
    trades, fps, files, nsym, skipped = [], set(), 0, 0, []
    for p in sorted(Path(shards_dir).rglob("*.json")):
        try:
            j = json.loads(p.read_text(encoding="utf-8"))
        except Exception:                            # noqa: BLE001
            continue
        if "trades" not in j or "fingerprint" not in j:
            continue
        files += 1
        trades += j["trades"]
        fps.add(j["fingerprint"])
        nsym += j.get("symbols", 0)
        skipped += j.get("skipped", [])
    if not files:
        raise SystemExit(f"هیچ تکه‌ای در {shards_dir} نیست")
    if len(fps) > 1:
        raise SystemExit("تکه‌ها اثرانگشتِ یکسان ندارند — ادغامشان دروغ است: "
                         + " | ".join(sorted(fps)))
    v = judge(trades)
    years = sorted({_year(t["t"]) for t in trades})
    v.update({
        "generated": int(time.time() * 1000),
        "strategy": S.STRATEGY_ID, "version": S.STRATEGY_VERSION,
        "fingerprint": sorted(fps)[0], "shards": files, "symbols": nsym,
        "skipped": skipped[:10], "n_skipped": len(skipped),
        "trade_span": ([time.strftime("%Y-%m-%d", time.gmtime(min(t["t"] for t in trades) / 1000)),
                        time.strftime("%Y-%m-%d", time.gmtime(max(t["t"] for t in trades) / 1000))]
                       if trades else None),
        "per_year": {str(y): _ci([t["net"] for t in trades if _year(t["t"]) == y])
                     for y in years},
        # رژیمِ بسترِ BTC در لحظهٔ ورود — برشی که برای شورت معنا دارد
        "per_btc_4h": {r: _ci([t["net"] for t in trades if t.get("btc_4h") == r])
                       for r in ("down", "range", "up", None)},
        "outcomes": _count(trades),
        "stopping_rule": {"promote_min_n": MIN_N_PROMOTE,
                          "reject_min_n": MIN_N_REJECT,
                          "metric": "خالص از کارمزد (hamid/fees)"},
        "boundary": ("بازپخشِ کندلِ واقعی با فیلِ کامل و بی‌لغزش (سقفِ خوش‌بینانه). "
                     "حکم فقط برای همین اثرانگشت. برشِ سال/رژیم برای قانون ۰۳ "
                     "است، نه برای گزینشِ پنجرهٔ خوش‌عکس."),
        "panel": "لیام تریدر ۹",
    })
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(v, ensure_ascii=False, indent=1), encoding="utf-8")
    print(render(v))
    for k in ("per_year", "per_btc_4h", "per_stance"):
        for lab, c in v[k].items():
            if c:
                print(f"    {k} {lab}: n={c['n']} {c['mean']:+.4f}R CI[{c['lo']:+.4f},{c['hi']:+.4f}]")
    print(f"نوشته شد: {out} ({len(trades)} معامله از {files} تکه)")
    return v


def render(v):
    net, g = v.get("net"), v.get("gross")
    L = [f"### بک‌تست شورت — {v['verdict']} ({v['why']})"]
    if g:
        L.append(f"  ناخالص: n={g['n']} · {g['mean']:+.4f}R "
                 f"CI[{g['lo']:+.4f},{g['hi']:+.4f}]")
    if net:
        L.append(f"  خالص  : n={net['n']} · {net['mean']:+.4f}R "
                 f"CI[{net['lo']:+.4f},{net['hi']:+.4f}]")
    c = v.get("compare")
    if c:
        for lab, key in (("trainer فیلترشده (همان چهار فیلتر)", "trainer_filtered"),
                         ("trainer همهٔ شورت‌ها", "trainer_all_shorts")):
            x = c.get(key)
            if x:
                L.append(f"  {lab:<36} n={x['n']} · {x['mean']:+.4f}R "
                         f"CI[{x['lo']:+.4f},{x['hi']:+.4f}]")
            else:
                L.append(f"  {lab:<36} نمونهٔ کم")
        L.append(f"  خروج‌ها — موتور: {c.get('engine_outcomes')} · "
                 f"trainer فیلترشده: {c.get('trainer_filtered_outcomes')}")
    if v.get("need_more"):
        L.append(f"  برای تصمیم‌پذیری ~{v['need_more']} معاملهٔ دیگر لازم است")
    L.append(f"  اثرانگشت: {v['fingerprint']}")
    L.append(f"  مرز: {v['boundary']}")
    return "\n".join(L)


# ═══════════════════ خودآزمایی (بدون شبکه) ═══════════════════

def _selftest():
    ok, fail = 0, []

    def chk(name, cond, extra=""):
        nonlocal ok
        if cond:
            ok += 1
        else:
            fail.append(name)
            print(f"  ✗ {name}" + (f"  ↳ {extra}" if extra else ""))

    now = 1788800000000
    # ── نگاه به آینده ممنوع: موتور نباید هیچ کندلی بعد از اندیس جاری
    # ببیند. جاسوس می‌گذاریم و طولِ ورودی را می‌شماریم.
    seen = []
    real = S.decide

    def spy(symbol, cd, **kw):
        seen.append(len(cd))
        return real(symbol, cd, **kw)

    S.decide = spy
    try:
        cd = S._zig(legs=14, down=12, up=6, end=now)
        cd4 = S._zig(legs=6, down=10, up=5, end=now, tf_ms=14_400_000)
        tr = replay("AAAUSDT", cd, cd4, tf="15m", warmup=200)
    finally:
        S.decide = real
    chk("موتور هرگز بیش از اندیسِ جاری کندل نمی‌بیند",
        all(x <= len(cd) for x in seen) and seen == sorted(seen),
        f"{seen[:5]}…")

    # ── کندلِ تایمِ بالا فقط تا لحظهٔ جاری ──
    htf = S._zig(legs=1, down=5, up=5, tf_ms=1000,
                 end=9000)
    chk("کندلِ HTF بازِ لحظهٔ جاری حذف می‌شود",
        len(_htf_upto(htf, 5000)) == 5, str(len(_htf_upto(htf, 5000))))
    chk("و پیش از اولین کندل، خالی برمی‌گردد",
        _htf_upto(htf, -1) == [])

    # ── سناریوی قطعی: ریزشِ ادامه‌دار باید به تارگت برسد ──
    # نماد عمداً BTCUSDT است: برای آلت، نبودِ بسترِ BTC یعنی NO_SIGNAL
    # (قانون ۰۱ بند ۳) و آن‌وقت این سناریو هیچ‌وقت به معامله نمی‌رسید —
    # آزمون سبز می‌ماند بی‌آنکه چیزی را سنجیده باشد.
    #
    # مسیر از **همان ستاپِ مرجع** ساخته می‌شود و بعد ریزش ادامه پیدا
    # می‌کند. در زیگزاگِ دوره‌ای کانال روی کلِ ریزش برازش می‌شود و
    # `chan_pos` وسطِ دامنه می‌ماند، پس دروازهٔ مکان هرگز باز نمی‌شد و
    # این آزمون **بی‌آنکه چیزی بسنجد سبز می‌ماند** — دقیقاً همان تلهٔ
    # «اسکریپتِ سبز ≠ محصولِ درست».
    ref = S._zig(end=now, **S.REF)
    px, t_last, tail = S._ohlc(ref[-1])[3], S._ts(ref[-1]), []
    for j in range(1, 41):
        o = px
        c = o * 0.994
        tail.append([t_last + j * 900_000, o, max(o, c) * 1.001,
                     min(o, c) * 0.999, c, 1000.0])
        px = c
    dn = list(ref) + tail
    t2 = replay("BTCUSDT", dn, cd4, btc4h=None, btc1h=None,
                warmup=len(ref) - 1)

    # ── بسترِ استیبل در بازپخش (دستور حمید ۸ سپتامبر) ──────────────────
    #
    # اثباتِ منفیِ جفتی: **همان** کندل‌ها با بسترِ وتوکننده باید صفر
    # معامله بدهند. بی‌این بررسی، دروازه ممکن است در بازپخش اصلاً وصل
    # نباشد و ما خیال کنیم سنجیده‌ایمش.
    # بسترِ BTC این‌جا **کندل** است نه رشتهٔ روند — `replay` خودش روند را
    # حساب می‌کند. (نسخهٔ اولِ همین بررسی رشته داد، `_htf_upto` روی رشته
    # پیمایش کرد و بستر None شد؛ آن‌وقت صفرِ خروجی به دروازه نسبت داده
    # می‌شد در حالی که عیبِ خودِ آزمون بود.)
    btc_dn4 = _zig_btc = S._zig(legs=6, down=10, up=5, end=now,
                                tf_ms=14_400_000)
    btc_dn1 = S._zig(legs=6, down=10, up=5, end=now, tf_ms=3_600_000)
    t_alt = replay("AAAUSDT", dn, cd4, btc4h=btc_dn4, btc1h=btc_dn1,
                   warmup=len(ref) - 1)
    t_veto = replay("AAAUSDT", dn, cd4, btc4h=btc_dn4, btc1h=btc_dn1,
                    warmup=len(ref) - 1,
                    stance_at=lambda _t: "LONG_ALT_STRONG")
    chk("بی‌بسترِ تاریخی، خطِ پایه دست‌نخورده می‌ماند (وتوی کور نمی‌کند)",
        len(t_alt) > 0, f"{len(t_alt)} معامله")
    chk("و با بسترِ وتوکننده، همان کندل‌ها صفر معامله می‌دهند",
        len(t_veto) == 0, f"{len(t_veto)} معامله")
    chk("بسترِ هر معامله روی خودش ثبت می‌شود",
        all(t.get("alt_stance") for t in t_alt), str(t_alt[:1]))
    chk("و بی‌تاریخچه صریح برچسب می‌خورد، نه «خنثی»",
        all(t["alt_stance"] == NO_HISTORY for t in t_alt))
    # `stance_fn` بیرون از بازهٔ سری باید NO_HISTORY بدهد، نه حدس
    _pts = [{"t": 1_788_000_000_000 + i * 180_000, "m": 3_000e9 + i,
             "u": 6.8, "c": 2.7, "b": 59.0} for i in range(200)]
    _fn = stance_fn(series=_pts)
    chk("stance_fn روی سریِ موجود کار می‌کند",
        _fn is not None and _fn(_pts[-1]["t"]) is not None)
    chk("و بیرون از بازهٔ سری، بستر جعل نمی‌کند",
        _fn(_pts[0]["t"] - 10 * 86_400_000) == NO_HISTORY)
    if t2:
        chk("در ریزشِ ادامه‌دار به تارگت می‌رسد",
            any(t["R"] > 0 for t in t2), str(t2[0]))
        chk("خالص = ناخالص منهای کارمزد",
            all(abs(t["net"] - (t["R"] - t["fee_r"])) < 1e-9 for t in t2))
        chk("یک پوزیشن در هر لحظه (زمان‌ها هم‌پوشان نیستند)",
            all(t2[k]["t"] < t2[k + 1]["t"] for k in range(len(t2) - 1)))
    else:
        fail.append("سناریوی ریزش هیچ معامله‌ای نساخت")
        print("  ✗ سناریوی ریزش هیچ معامله‌ای نساخت")

    # ── بدترین حالت داخل کندل: استاپ قبل از تارگت ──
    # کندلی که هر دو را لمس می‌کند باید −۱R بدهد، نه سود.
    up = S._zig(end=now, **S.REF)
    d = real("BTCUSDT", up, cd_4h=None, now_ms=now)
    if d["action"] == "SHORT":
        wide = list(up) + [[S._ts(up[-1]) + 900_000, d["entry"],
                            d["sl"] * 1.01, d["tp1"] * 0.99,
                            d["entry"], 1000.0]]
        t3 = replay("BTCUSDT", wide, cd4, warmup=len(up) - 1)
        chk("کندلی که هم استاپ هم تارگت را لمس کند = −۱R",
            t3 and t3[0]["R"] == -1.0, str(t3[:1]))
    else:
        fail.append("سناریوی مرجع SHORT نشد")

    # ── قاعدهٔ توقف از پیش ثبت است و با نمونهٔ کم حکم نمی‌دهد ──
    chk("با نمونهٔ کم حکم PROMOTE نمی‌دهد",
        judge([{"net": 1.0, "R": 1.0}] * 10)["verdict"] == "UNDECIDED")
    many_pos = [{"net": 0.5, "R": 0.6}] * MIN_N_PROMOTE
    chk("CI بالای صفر با n کافی = PROMOTE",
        judge(many_pos)["verdict"] == "PROMOTE")
    many_neg = [{"net": -0.5, "R": -0.4}] * MIN_N_REJECT
    chk("CI زیر صفر با n کافی = REJECT",
        judge(many_neg)["verdict"] == "REJECT")
    # حالتِ مقایسه: سه جمعیت روی یک داده، با ساختارِ ثابت — بی‌آن، اختلافِ
    # «کد» و «رژیم» از هم جدا نمی‌شود.
    ref_cd = S._zig(end=now, **S.REF)
    v_cmp, _ = run(["BTCUSDT"], compare=True,
                   fetch=lambda s_, t_, n_: ref_cd if t_ == "15m" else cd4)
    chk("حالتِ مقایسه هر سه جمعیت را برمی‌گرداند",
        set(v_cmp.get("compare", {})) >= {"trainer_filtered",
                                          "trainer_all_shorts",
                                          "engine_outcomes"})
    chk("مقایسه، trainer را روی همان کندل‌ها می‌دواند نه دفتر",
        "همان" in (v_cmp.get("compare") or {}).get("note", ""))
    # تکه‌بندی قطعی و ادغام: دو تکه روی یک فهرست ⇒ اجتماعِ بی‌هم‌پوشان؛
    # merge روی اثرانگشتِ متفاوت باید خطا بدهد (ادغامِ دروغ).
    import tempfile as _tmp
    d = Path(_tmp.mkdtemp(prefix="liam9-sb-"))
    fake = lambda s_, t_, n_: ref_cd if t_ == "15m" else cd4    # noqa: E731
    seen = []
    for k in (0, 1):
        vk, tk = run(["AAAUSDT", "BBBUSDT", "CCCUSDT"], fetch=fake,
                     compare=False, shard=k, shards=2)
        seen.append(vk["symbols"])
        (d / f"shard{k}.json").write_text(json.dumps({**vk, "trades": tk}))
    chk("تکه‌بندی بی‌هم‌پوشان است (۳ نماد → ۲+۱)", sorted(seen) == [1, 2], str(seen))
    vm = merge(d, out=d / "merged.json")
    chk("merge حکم و برشِ سال/رژیم می‌دهد",
        "per_year" in vm and "per_btc_4h" in vm and vm["shards"] == 2)
    bad = json.loads((d / "shard1.json").read_text()); bad["fingerprint"] = "x"
    (d / "shard1.json").write_text(json.dumps(bad))
    try:
        merge(d, out=d / "m2.json"); _raised = False
    except SystemExit:
        _raised = True
    chk("merge روی اثرانگشتِ متفاوت خطا می‌دهد", _raised)
    # عمقِ تایمِ بالا باید با عمقِ ۱۵د بزرگ شود — وگرنه «عمیق» فقط ته را می‌بیند
    chk("عمقِ HTF با عمقِ ۱۵د بزرگ می‌شود",
        htf_depth(20000)["4h"] > 1200 and htf_depth(1000)["4h"] < 500)
    calls = []
    def spy(s_, t_, n_):
        calls.append((t_, n_))
        return ref_cd if t_ == "15m" else cd4
    run(["BTCUSDT"], bars=20000, fetch=spy, compare=False)
    chk("در اجرای عمیق، ۴س هم عمیق خواسته می‌شود",
        any(t_ == "4h" and n_ > 1200 for t_, n_ in calls), str(calls[:4]))
    # klines_deep: سلامت روی کف، نه روی درخواست (ریشهٔ ردشدنِ ۷۷ نماد)
    import sources as _src
    short_ok = S._zig(legs=20, down=12, up=6, end=now)   # ۳۶۰ کندلِ سالم
    fake_venue = {"id": "fake-perp", "label": "Fake", "fetch": lambda s_, t_, n_: short_ok}
    _old = _src.PERP_VENUES
    _src.PERP_VENUES = [fake_venue]
    try:
        got = _src.klines_deep("AAAUSDT", "15m", 20000, floor=260)
        chk("klines_deep سریِ کوتاه‌ولی‌سالم را می‌پذیرد (۳۶۰ از ۲۰۰۰۰ خواسته)",
            len(got) == len(short_ok))
        _src.PERP_VENUES = [{"id": "fake-perp", "label": "Fake",
                             "fetch": lambda s_, t_, n_: short_ok[:50]}]
        try:
            _src.klines_deep("AAAUSDT", "15m", 20000, floor=260); _r = False
        except RuntimeError:
            _r = True
        chk("ولی زیرِ کف رد می‌کند", _r)
    finally:
        _src.PERP_VENUES = _old
    chk("اثرانگشت شامل هندسه است",
        "rr_target" in fingerprint() and "min_stop_pct" in fingerprint())
    # خاصیت، نه شکل: مرزِ صادقانه باید روی **خروجی** باشد (همان چیزی که
    # پنل و حمید می‌بینند)، نه در docstring — نسخهٔ قبل docstring را
    # می‌خواند و با تغییرِ متن افتاد بی‌آنکه چیزی خراب شده باشد.
    chk("مرزِ صادقانه روی خروجیِ اجرا و ادغام هست",
        "خوش‌بینانه" in (v_cmp.get("boundary") or "")
        and "خوش‌بینانه" in (vm.get("boundary") or ""))

    print(f"{ok} بررسی گذشت" + (f"، {len(fail)} افتاد: {fail}" if fail else ""))
    return not fail


DEFAULT_SYMS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
                "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT", "TONUSDT",
                "DOTUSDT", "TRXUSDT", "NEARUSDT", "APTUSDT", "OPUSDT",
                "ARBUSDT", "SUIUSDT", "INJUSDT", "LTCUSDT", "ATOMUSDT"]


def main(argv):
    if "--selftest" in argv:
        return 0 if _selftest() else 1
    syms = DEFAULT_SYMS
    if "--symbols" in argv:
        syms = argv[argv.index("--symbols") + 1].split(",")
    if "--universe" in argv:
        # همان جهانِ نمادی که دفترِ میز تمرین از آن ساخته شده (۱۰۰ برتر به
        # حجم) — تا مقایسه سیب با سیب باشد، نه ۲۰ نمادِ بزرگ با ۱۰۰ نمادِ داغ.
        n = int(argv[argv.index("--universe") + 1])
        syms = TR.top_symbols(n)
        print(f"جهان نماد: {len(syms)} نمادِ برتر به حجم")
    tf = argv[argv.index("--tf") + 1] if "--tf" in argv else "15m"
    bars = int(argv[argv.index("--bars") + 1]) if "--bars" in argv else 1000
    # `--no-compare`: بازپخشِ دومِ trainer را رد می‌کند. وفاداریِ موتور یک بار
    # با مقایسهٔ سیب‌باسیب اثبات شد (۷ سپتامبر: −۰.۵۸ در برابر −۰.۴۶، CI
    # هم‌پوشان)؛ در اجرای پهن فقط وقت می‌خورد. کرونِ روزانه مقایسه را نگه
    # می‌دارد تا واگراییِ تازه، اگر پیش آمد، دیده شود.
    if "--merge" in argv:
        merge(argv[argv.index("--merge") + 1],
              out=argv[argv.index("--out") + 1] if "--out" in argv else None)
        return 0
    fetch = None
    if "--src" in argv:                              # آرشیو سه‌سالهٔ درایو
        fetch, syms = _src_fetch(argv[argv.index("--src") + 1])
        bars = 0                                     # کلِ سری
    shard = int(argv[argv.index("--shard") + 1]) if "--shard" in argv else 0
    shards = int(argv[argv.index("--shards") + 1]) if "--shards" in argv else 1
    v, trades = run(syms, tf=tf, bars=bars, fetch=fetch,
                    compare="--no-compare" not in argv,
                    shard=shard, shards=shards)
    print(render(v))
    if "--out" in argv:                              # تکه: با معامله‌ها
        o = Path(argv[argv.index("--out") + 1])
        o.parent.mkdir(parents=True, exist_ok=True)
        o.write_text(json.dumps({**v, "trades": trades}, ensure_ascii=False),
                     encoding="utf-8")
        print(f"تکهٔ {shard}/{shards}: {o} ({len(trades)} معامله)")
    if "--write" in argv:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(v, ensure_ascii=False, indent=1),
                       encoding="utf-8")
        print(f"نوشته شد: {OUT} ({len(trades)} معامله)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
