#!/usr/bin/env python3
"""اتاق دامیننس — مهم‌ترین بخشِ پیش از ترید (دستور حمید، ۳ سپتامبر).

حمید: «دامیننس تتر مهم‌ترین بخشی است که باید درست تحلیل شود قبل از هر
تریدی؛ ریزش دامیننس یعنی بالا رفتن بازار و بالا رفتنش یعنی پایین آمدن
بازار… وقتی ارزی در تایم ۵ دقیقه تحلیل می‌شود، دامیننس هم باید در همان
تایم بررسی شود، **ولی روند کلی دامیننس از تایم‌های ریز مهم‌تر است**؛
۴ ساعته و ۱ ساعته را به روش خودم تحلیل کن و ببین کجای کانال است… و
**مورد جدیدی که باید خودت پیدا می‌کردی، در نظر گرفتن USDC است** —
استیبلی که مردم در اروپا و جاهای دیگر مجبور به استفاده از آن هستند و
تحلیلش خیلی مهم است.»

## پنج کاری که این اتاق می‌کند

| کار | بند |
|---|---|
| قاعدهٔ پایه با جهتِ صریح: USDT.D پایین = بازار بالا | H4.1 |
| هم‌ترازی تایم‌فریم با ارزِ در دستِ تحلیل، **با وزنِ کمتر** | H4.2 |
| نقشهٔ ۴س و ۱س به روش حمید + جای دامیننس در کانال | H4.3 |
| USDC.D به‌عنوان خطِ مستقل، نه فقط تفاضل با تتر | H4.4 |
| چرخهٔ پول: کجا می‌رود — استیبل، بیت‌کوین، یا آلت | H4.5 |

## چرا «روند کلی مهم‌تر از ریزتایم» عددی شد

حمید صریح گفت تایم بالا مهم‌تر است. اگر ۵د و ۴س هم‌وزن باشند، یک نوسانِ
پنج‌دقیقه‌ایِ دامیننس می‌تواند رأیِ چهارساعته را خنثی کند — و آن دقیقاً
همان چیزی است که او نمی‌خواهد. پس وزن‌ها ثابت و اعلام‌شده‌اند:
۴س = ۱.۰ · ۱س = ۰.۷ · ۱۵د = ۰.۴ · ۵د = **۰.۲**.

## چرا USDC.D جدا حساب می‌شود

تتر و یو‌اس‌دی‌سی همیشه یک کار نمی‌کنند. اگر USDT.D بالا برود و USDC.D
هم‌زمان پایین بیاید، پول از تتر به یواس‌دی‌سی رفته — این **چرخش بین دو
استیبل** است، نه فرارِ از بازار. تفاوتِ این دو حالت روی تصمیم اثر دارد
و بدون خطِ مستقلِ USDC.D اصلاً دیده نمی‌شود.

## مرز

این اتاق **بستر** می‌دهد، نه دستور. دروازهٔ تصمیم همان‌جایی است که بود
(`trend_gate` و قانون ۳)؛ هیچ عددی از این‌جا آستانه‌ای را جابه‌جا نمی‌کند
مگر از مسیر قانون ۰۳.

    python3 -m hamid.dominance_desk --write
"""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

ROOT = HERE.parents[2]
SERIES = ROOT / "brain" / "dominance-series.json"
OUT = ROOT / "signals" / "dominance-desk.json"

ENGINE = "E03"
PANEL = "لیام تریدر ۹"

# وزن تایم‌فریم — دستور صریح حمید: روند کلی از ریزتایم مهم‌تر است.
TF_WEIGHT = {"4h": 1.0, "1h": 0.7, "15m": 0.4, "5m": 0.2}
HTF = ("4h", "1h")             # «به روش خودم تحلیل کن» — همین دو
MIN_PTS = 60
STABLE_ROTATE = 0.02           # جابه‌جایی هم‌زمان و مخالفِ دو استیبل
CYCLE_MIN = 0.03               # کف تغییرِ معنادار برای اعلام چرخهٔ پول
TEHRAN_OFFSET_S = 3.5 * 3600


def _j(p, default):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:                                # noqa: BLE001
        return default


def load_points(path=None):
    d = _j(path or SERIES, {})
    return (d or {}).get("points") or []


def _chg(points, key, minutes):
    """تغییر یک سری در N دقیقهٔ اخیر. نبودِ نقطه = None، نه صفر."""
    pts = [p for p in points if isinstance(p.get(key), (int, float))]
    if len(pts) < 2:
        return None
    t0 = pts[-1]["t"] - minutes * 60_000
    past = min(pts, key=lambda p: abs(p["t"] - t0))
    if abs(past["t"] - t0) > minutes * 60_000 * 0.6:
        return None
    return round(pts[-1][key] - past[key], 4)


# ── H4.1 قاعدهٔ پایه ─────────────────────────────────────────────────────
def base_rule(delta_u):
    """جهتِ بازار از جهتِ USDT.D — همان جملهٔ خود حمید، عددی‌شده."""
    if delta_u is None:
        return {"market": "UNKNOWN", "why": "تغییر USDT.D در دست نیست — "
                                            "بستر اعلام نمی‌شود (قانون ۱)"}
    if delta_u < 0:
        return {"market": "UP", "why": f"USDT.D {delta_u:+g} — پول از حاشیه "
                                       "به بازار می‌آید: بازار رو به بالا"}
    if delta_u > 0:
        return {"market": "DOWN", "why": f"USDT.D {delta_u:+g} — پول به حاشیه "
                                         "می‌رود: بازار رو به پایین"}
    return {"market": "FLAT", "why": "USDT.D بی‌تغییر — بستر خنثی"}


# ── H4.2 و H4.3 خوانش چندتایمی با وزن ──────────────────────────────────
def read_tfs(points, tfs=("4h", "1h", "15m", "5m"), key="u"):
    from hamid import dom_tf
    out = {}
    for tf in tfs:
        try:
            out[tf] = dom_tf.read(points, tf, key=key)
        except Exception as e:                       # noqa: BLE001
            out[tf] = {"tf": tf, "regime": "ERROR", "note": f"{type(e).__name__}"}
    return out


def weighted_regime(reads):
    """رأی وزنی تایم‌فریم‌ها. تایمِ بی‌رزولوشن رأی ندارد، صفر هم نمی‌شود."""
    num = den = 0.0
    used, skipped = [], []
    for tf, r in reads.items():
        w = TF_WEIGHT.get(tf)
        if w is None:
            continue
        reg = r.get("regime")
        if reg not in ("BULLISH", "BEARISH", "RANGE"):
            skipped.append({"tf": tf, "why": r.get("note") or reg})
            continue
        v = 1.0 if reg == "BULLISH" else (-1.0 if reg == "BEARISH" else 0.0)
        num += w * v
        den += w
        used.append({"tf": tf, "regime": reg, "weight": w})
    if den <= 0:
        return {"score": None, "regime": "INSUFFICIENT", "used": used,
                "skipped": skipped,
                "why": "هیچ تایم‌فریمی رزولوشن یا کندل کافی نداشت"}
    s = round(num / den, 3)
    reg = "BULLISH" if s >= 0.25 else ("BEARISH" if s <= -0.25 else "RANGE")
    return {"score": s, "regime": reg, "used": used, "skipped": skipped,
            "why": (f"رأی وزنی {s} از {len(used)} تایم‌فریم — "
                    f"۴س وزن {TF_WEIGHT['4h']} و ۵د وزن {TF_WEIGHT['5m']}: "
                    "روند کلی از ریزتایم مهم‌تر است (دستور حمید)")}


def for_symbol_tf(reads, tf):
    """هم‌ترازیِ تایم‌فریم با ارزِ در دستِ تحلیل (بند H4.2).

    برمی‌گرداند هم خوانشِ همان تایم را و هم یادآوریِ این‌که وزنش کمتر از
    تایم بالاست — تا کسی رأیِ ۵دقیقه‌ای را جای بسترِ چهارساعته نگذارد.
    """
    r = reads.get(tf)
    if not r:
        return {"tf": tf, "regime": "UNKNOWN",
                "why": f"دامیننس در {tf} خوانده نشد"}
    return {**r, "weight": TF_WEIGHT.get(tf),
            "reminder": (f"وزن {tf} برابر {TF_WEIGHT.get(tf)} است در برابر "
                         f"{TF_WEIGHT['4h']} برای ۴س — ریزتایم بسترِ بالادست "
                         "را نقض نمی‌کند (قانون ۲)")}


def channel_place(points, key="u", tfs=HTF):
    """جای دامیننس در کانالِ ۴س و ۱س، به روش نقشهٔ پایهٔ حمید (قانون ۱۱)."""
    from hamid import base_map as BM
    from hamid import dom_tf
    frames = {}
    for tf in tfs:
        try:
            bs, _ = dom_tf.bars(points, key, tf)
        except Exception:                            # noqa: BLE001
            bs = []
        if len(bs) >= MIN_PTS:
            frames[tf] = bs
    if not frames:
        return {"ok": False, "why": "کندلِ کافیِ دامیننس برای نقشهٔ ۴س/۱س نیست"}
    m = BM.base_map(frames)
    out = {"ok": True, "frames": {}}
    for tf, cd in frames.items():
        info = m.get(tf) or {}
        ch = info.get("channel")
        px = cd[-1]["c"]
        row = {"px": round(px, 3), "levels": info.get("levels") or [],
               "channel": ch}
        if ch and ch.get("top") is not None and ch.get("bottom") is not None:
            span = ch["top"] - ch["bottom"]
            row["pos_pct"] = round((px - ch["bottom"]) / span * 100, 1) if span else None
            row["where"] = ("بالای میدلاین" if row["pos_pct"] is not None
                            and row["pos_pct"] > 55 else
                            "پایین میدلاین" if row["pos_pct"] is not None
                            and row["pos_pct"] < 45 else "حوالی میدلاین")
        else:
            row["where"] = "کانال معتبری روی این تایم نیست — جای زوری اعلام نمی‌شود"
        out["frames"][tf] = row
    out["confluence"] = m.get("confluence") or []
    return out


# ── H4.4 USDC.D خطِ مستقل ───────────────────────────────────────────────
def usdc_line(points, minutes=240):
    """USDC.D جدا — و مهم‌تر: نسبتش با USDT.D.

    اگر هر دو بالا بروند، پول واقعاً از بازار بیرون رفته. اگر یکی بالا و
    دیگری پایین برود، فقط بین دو استیبل چرخیده — و این دو حالت روی تصمیم
    یکی نیستند.
    """
    have = [p for p in points if isinstance(p.get("c"), (int, float))]
    if len(have) < 2:
        return {"ok": False,
                "why": "USDC.D در سری ذخیره نشده — تفکیک استیبل ممکن نیست "
                       "(عدد جعل نمی‌شود، قانون ۱)"}
    du = _chg(points, "u", minutes)
    dc = _chg(points, "c", minutes)
    if du is None or dc is None:
        return {"ok": False, "why": f"نقطهٔ {minutes} دقیقه قبل برای هر دو استیبل نیست"}
    now_u = [p for p in points if isinstance(p.get("u"), (int, float))][-1]["u"]
    now_c = have[-1]["c"]
    both_up = du > 0 and dc > 0
    both_dn = du < 0 and dc < 0
    rotate = (du > STABLE_ROTATE and dc < -STABLE_ROTATE) or \
             (du < -STABLE_ROTATE and dc > STABLE_ROTATE)
    if rotate:
        state, why = "STABLE_ROTATION", (
            f"USDT.D {du:+g} ولی USDC.D {dc:+g} — چرخش **بین دو استیبل**، "
            "نه فرار از بازار. جهتِ بازار را از این حرکت نتیجه نگیر")
    elif both_up:
        state, why = "TO_STABLE", (
            f"هر دو استیبل بالا ({du:+g} و {dc:+g}) — پول واقعاً از بازار "
            "بیرون می‌رود")
    elif both_dn:
        state, why = "TO_RISK", (
            f"هر دو استیبل پایین ({du:+g} و {dc:+g}) — پول واقعاً وارد بازار می‌شود")
    else:
        state, why = "MIXED", (
            f"USDT.D {du:+g} و USDC.D {dc:+g} — حرکت کوچک‌تر از آستانهٔ "
            f"{STABLE_ROTATE}، حکمِ قاطع اعلام نمی‌شود")
    return {"ok": True, "state": state, "why": why,
            "usdt_d": round(now_u, 3), "usdc_d": round(now_c, 3),
            "usdt_d_delta": du, "usdc_d_delta": dc,
            "stable_total": round(now_u + now_c, 3),
            "window_min": minutes,
            "note": "USDC استیبلِ اجباریِ اروپاست (دستور حمید) — سهمش جدا "
                    "شمرده می‌شود، نه داخل تتر"}


# ── H4.5 چرخهٔ پول ──────────────────────────────────────────────────────
def money_cycle(points, minutes=240):
    """پول کجا می‌رود: استیبل، بیت‌کوین، یا آلت — از سه سریِ موجود.

    منطق ساده و قابل بازشماری است: سهمِ استیبل‌ها، سهمِ بیت‌کوین، و
    باقی‌مانده (آلت‌ها). هر جزئی که در سری نباشد، از حکم کنار می‌رود و
    غیبتش نوشته می‌شود — نه این‌که صفر فرض شود.
    """
    du = _chg(points, "u", minutes)
    dc = _chg(points, "c", minutes)
    db = _chg(points, "b", minutes)
    missing = [k for k, v in (("USDT.D", du), ("USDC.D", dc), ("BTC.D", db))
               if v is None]
    if du is None or db is None:
        return {"ok": False, "missing": missing,
                "why": "بدون USDT.D و BTC.D، چرخهٔ پول قابل شمردن نیست"}
    stable = du + (dc or 0.0)
    alt = -(stable + db)                             # باقی‌مانده، نه اندازه‌گیری مستقل
    legs = sorted([("استیبل", stable), ("بیت‌کوین", db), ("آلت", alt)],
                  key=lambda x: -x[1])
    into, out_of = legs[0], legs[-1]
    if abs(into[1]) < CYCLE_MIN and abs(out_of[1]) < CYCLE_MIN:
        state, why = "QUIET", (f"هیچ سهمی بیش از {CYCLE_MIN} جابه‌جا نشده — "
                               "چرخهٔ پول در این پنجره خبری ندارد")
    else:
        state = f"{out_of[0]}→{into[0]}"
        why = (f"در {minutes} دقیقه: سهم {into[0]} {into[1]:+.3f} و سهم "
               f"{out_of[0]} {out_of[1]:+.3f} — پول از {out_of[0]} به "
               f"{into[0]} چرخیده")
    return {"ok": True, "state": state, "why": why, "window_min": minutes,
            "legs": {"stable": round(stable, 4), "btc": db,
                     "alt": round(alt, 4)},
            "missing": missing,
            "note": ("سهم آلت باقی‌ماندهٔ حسابی است نه اندازه‌گیری مستقل؛ "
                     "پس خطای دو سریِ دیگر رویش جمع می‌شود")}


# ── تابلو ────────────────────────────────────────────────────────────────
def build(points=None, tf=None, now_ms=None):
    points = load_points() if points is None else points
    now = int(now_ms if now_ms is not None else time.time() * 1000)
    if len(points) < 2:
        return {"generated": now, "engine": ENGINE, "ok": False,
                "why": f"سری دامیننس {len(points)} نقطه دارد — اتاق حرفی نمی‌زند"}
    reads = read_tfs(points)
    btc_reads = read_tfs(points, key="b")
    du1 = _chg(points, "u", 60)
    wr = weighted_regime(reads)
    return {
        "generated": now, "engine": ENGINE, "panel": PANEL, "ok": True,
        "points": len(points),
        "base_rule": base_rule(du1),
        "chg_1h": {"usdt_d": du1, "btc_d": _chg(points, "b", 60),
                   "usdc_d": _chg(points, "c", 60)},
        "by_tf": reads, "btc_d_by_tf": btc_reads,
        "weighted": wr,
        "tf_weights": TF_WEIGHT,
        "symbol_tf": for_symbol_tf(reads, tf) if tf else None,
        "channel": channel_place(points),
        "usdc": usdc_line(points),
        "money_cycle": money_cycle(points),
        "boundary": "این اتاق بستر می‌دهد نه دستور: دروازهٔ تصمیم همان "
                    "trend_gate و قانون ۳ است؛ هیچ عددی از این‌جا آستانه‌ای را "
                    "جابه‌جا نمی‌کند مگر از مسیر قانون ۰۳.",
    }


def main(argv=None):
    argv = list(argv if argv is not None else sys.argv[1:])
    tf = next((a.split("=", 1)[1] for a in argv if a.startswith("--tf=")), None)
    b = build(tf=tf)
    if "--write" in argv:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(b, ensure_ascii=False, indent=1) + "\n",
                       encoding="utf-8")
        print(f"اتاق دامیننس نوشته شد: {OUT.relative_to(ROOT)}")
    if not b.get("ok"):
        print(b.get("why"))
        return 0
    print(f"اتاق دامیننس — {b['points']} نقطه")
    print(f"  قاعدهٔ پایه: {b['base_rule']['why']}")
    w = b["weighted"]
    print(f"  رأی وزنی تایم‌فریم‌ها: {w['regime']} ({w['score']}) — {w['why']}")
    for tfk, r in (b["channel"].get("frames") or {}).items():
        print(f"  کانال {tfk}: {r['px']} · {r.get('where')}"
              + (f" ({r['pos_pct']}٪ ارتفاع)" if r.get("pos_pct") is not None else ""))
    u = b["usdc"]
    print(f"  استیبل‌ها: {u.get('state') or '—'} — {u.get('why')}")
    m = b["money_cycle"]
    print(f"  چرخهٔ پول: {m.get('state') or '—'} — {m.get('why')}")
    if b.get("symbol_tf"):
        s = b["symbol_tf"]
        print(f"  هم‌تراز با {s['tf']}: رژیم {s.get('regime')} · {s.get('reminder')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
