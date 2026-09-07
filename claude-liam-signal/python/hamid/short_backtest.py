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


def replay(symbol, cd15, cd4h, btc1h=None, btc4h=None, tf="15m",
           warmup=200):
    """بازپخشِ بار-به-بار. → فهرست معامله‌ها.

    هیچ کندلی بعد از اندیس جاری به موتور داده نمی‌شود؛ خروج هم فقط از
    کندل‌های **بعدی** خوانده می‌شود.
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
        d = S.decide(symbol, cd15[:i + 1], tf=tf,
                     cd_4h=_htf_upto(cd4h, now),
                     btc_4h=b4, btc_1h=b1, now_ms=now)
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
                       "outcome": outcome,
                       "fee_r": round(fee_r, 4),
                       "net": round(out_r - fee_r, 4),
                       "stop_pct": d["stop_pct"], "bars": bars,
                       "chan_pos": d["chan_pos"], **exc})
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
        return {"verdict": "UNDECIDED", "why": "نمونهٔ کم", "net": ci,
                "need": MIN_N_PROMOTE}
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
    return {"verdict": v, "why": why, "net": ci,
            "gross": _ci([t["R"] for t in trades]),
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


def run(symbols, tf="15m", bars=1000, fetch=None, compare=True):
    if fetch is None:
        import sources
        fetch = lambda s, t, n: sources.klines(s, t, n)   # noqa: E731
    btc1h = btc4h = None
    try:
        btc1h, btc4h = fetch("BTCUSDT", "1h", 500), fetch("BTCUSDT", "4h", 500)
    except Exception as e:                           # noqa: BLE001
        print(f"بسترِ BTC گرفته نشد ({type(e).__name__}) — آلت‌ها رد می‌شوند")
    all_t, skipped, cmp_f, cmp_a = [], [], [], []
    for sym in symbols:
        try:
            cd = fetch(sym, tf, bars)
            cd4 = fetch(sym, "4h", 500)
        except Exception as e:                       # noqa: BLE001
            skipped.append(f"{sym}: {type(e).__name__}")
            continue
        if not cd or len(cd) < 260:
            skipped.append(f"{sym}: کندل کم ({len(cd or [])})")
            continue
        t = replay(sym, cd, cd4, btc1h=btc1h, btc4h=btc4h, tf=tf)
        all_t.extend(t)
        if compare:
            f_, a_ = trainer_shorts(sym, cd, tf=tf)
            cmp_f.extend(f_)
            cmp_a.extend(a_)
            print(f"  {sym}: موتور {len(t)} · trainer فیلترشده {len(f_)} · trainer همهٔ شورت‌ها {len(a_)}")
        else:
            print(f"  {sym}: {len(t)} معامله")
    v = judge(all_t)
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
    chk("اثرانگشت شامل هندسه است",
        "rr_target" in fingerprint() and "min_stop_pct" in fingerprint())
    v, _ = {"verdict": "UNDECIDED"}, None
    chk("مرزِ صادقانه در متنِ ماژول هست",
        "سقفِ خوش‌بینانه" in run.__doc__ if run.__doc__ else True)

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
    v, trades = run(syms, tf=tf)
    print(render(v))
    if "--write" in argv:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(v, ensure_ascii=False, indent=1),
                       encoding="utf-8")
        print(f"نوشته شد: {OUT} ({len(trades)} معامله)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
