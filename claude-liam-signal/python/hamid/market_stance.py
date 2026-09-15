"""موضع بازار — هم‌جهت با حرکت پول، هفتگی و در هر تغییر ساختار (دستور حمید، ۱۴ سپتامبر).

حمید: «هر هفته یا بعد از هر تغییر روند یا ساختاری یا بررسی پالی‌مارکت
باید تغییر موقعیت بدی و همراه با روند حرکت پول حرکت کنی؛ روند نزولی شد
شورت، صعودی شد لانگ؛ ما هیچ تعصبی روی تحلیل نداریم.»

قطعی، بی‌LLM (قانون ۰۶). فقط از داده‌ای که همین حالا داریم می‌خواند و
هرچه نیست را «ممتنع» اعلام می‌کند (قانون ۱). خروجی **دیدگاه** است
(قانون ۱۵) — هیچ دروازه، امتیاز یا سایزی از این‌جا عوض نمی‌شود تا ماشین
شبانه CI بالای صفر بدهد و حمید تأیید کند (قانون ۰۳/۱۲).

## ورودی‌ها، وزن و شرط اعتبار (همه صریح — قانون «شرط و کف/سقف»)

| ورودی | منبع | وزن | ممتنع وقتی |
|---|---|---|---|
| روند BTC ۴س | structure.trend روی ۲۲۰ کندل | ۰.۴۰ | کندل نرسد → کل موضع NO_STANCE |
| روند BTC ۱س | همان | ۰.۱۵ | همان |
| USDT.D ۴س (معکوس) | dominance.json → structure.usdt.trend_4h | ۰.۲۰ | کهنه‌تر از ۹۰د (۲× سقف قرارداد ۴۵د) |
| USDT.D ۱س (معکوس) | همان، trend_1h | ۰.۱۰ | همان |
| پالی‌مارکت (شاهد پول) | polymarket.json، بازارهای BTC وزنی با حجم | ۰.۰۵ (سقف لایهٔ شاهد، قانون ۱۱) | کهنه‌تر از ۱۲س یا بی‌بازار |

BTC.D عمداً در امتیاز نیست: جهتِ «آلت در برابر بیت» را می‌گوید نه «بالا
در برابر پایین»؛ فقط به‌عنوان یادداشت ثبت می‌شود.

امتیاز = میانگین وزنیِ رأی‌های {+۱، ۰، −۱} روی ورودی‌های حاضر (وزن‌ها
بازنرمال می‌شوند). برچسب: ≥ +۰.۲۵ LONG_BIAS · ≤ −۰.۲۵ SHORT_BIAS · بین
این دو NEUTRAL. چرا ۰.۲۵: روند ۴س به‌تنهایی (۰.۴۰/۰.۹۰ = ۰.۴۴) برچسب
را می‌سازد ولی ۱س به‌تنهایی (۰.۱۷) نمی‌تواند — همان قانون ۲ (تایم پایین
حق نقض ساختار بالا را ندارد).

## کِی موضع عوض می‌شود (ضدلرزش)

۱. **بازبینی هفتگی** (دوشنبه‌ها): همیشه بازمحاسبه و ثبت.
۲. **تغییر ساختار**: برچسب روند ۴س BTC نسبت به آخرین ثبت عوض شود → همان
   لحظه.
۳. **عبور امتیاز** از آستانه با علامت مخالف → فقط اگر ≥ ۲۴ ساعت از آخرین
   تغییر گذشته باشد (کف نگهداری).
۴. **پنجرهٔ رویداد کلان ≤ ۲ ساعت** (همان قرارداد UNSAFE دامیننس) →
   هیچ تغییری؛ موضع قبلی نگه داشته و «یخ‌زده» علامت می‌خورد.

## کارنامه (بدون آن، وزن هیچ‌وقت داده نمی‌شود)

هر ثبت در `brain/stance/history.jsonl` (append-only) با قیمت BTC همان
لحظه می‌ماند؛ ۷ روز بعد با قیمت روز داوری می‌شود: LONG درست اگر بازده
> +۰.۴٪، SHORT درست اگر < −۰.۴٪ (باند نویز BTC همان قانون ۱۵)، NEUTRAL
داوری نمی‌شود. اصابت با CI ویلسون؛ زیر n=۲۰ عدد گزارش نمی‌شود.

اجرا:  python3 -m hamid.market_stance --write     (هر چرخهٔ حمید)
"""
import argparse
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
DOM = ROOT / "signals" / "dominance.json"
POLY = ROOT / "signals" / "polymarket.json"
OUT = ROOT / "signals" / "market-stance.json"
LEDGER = ROOT / "brain" / "stance" / "history.jsonl"

W = {"btc_4h": 0.40, "btc_1h": 0.15, "usdt_4h": 0.20, "usdt_1h": 0.10,
     "polymarket": 0.05}
BAND = 0.25                     # آستانهٔ برچسب
MIN_HOLD_H = 24                 # کف نگهداری بین دو تغییرِ امتیازی
EVENT_FREEZE_H = 2.0            # پنجرهٔ رویداد کلان
DOM_MAX_AGE_MIN = 90            # ۲× سقف قرارداد dominance.json
POLY_MAX_AGE_MIN = 720
NOISE_BAND = 0.004              # داوری ۷روزه: باند نویز BTC
JUDGE_DAYS = 7
MIN_N_TRACK = 20
KL_N = 220


def _load(p):
    try:
        return json.loads(p.read_text())
    except Exception:                                # noqa: BLE001
        return None


def _vote(trend, inverse=False):
    v = {"up": 1, "down": -1}.get(trend, 0)
    return -v if inverse else v


def _kget_default(sym, tf, n):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    import sources
    return [{"t": k[0], "o": k[1], "h": k[2], "l": k[3], "c": k[4], "v": k[5]}
            for k in sources.klines(sym, tf, n)]


def _poly_view(poly, now_ms):
    """رأی پالی‌مارکت روی BTC در [−۱,+۱]، وزنی با حجم؛ None = ممتنع."""
    if not poly or not poly.get("ok"):
        return None, "پالی‌مارکت ناموجود"
    try:
        at = datetime.strptime(poly["at"], "%Y-%m-%d %H:%M UTC")
        age = (now_ms / 1000 - at.replace(tzinfo=timezone.utc).timestamp()) / 60
    except Exception:                                # noqa: BLE001
        age = None
    if age is None or age > POLY_MAX_AGE_MIN:
        return None, f"پالی‌مارکت کهنه ({None if age is None else int(age)}د)"
    num = den = 0.0
    for m in poly.get("markets") or []:
        if m.get("asset") != "BTC" or m.get("implied_yes") is None:
            continue
        p_up = m["implied_yes"] if m.get("direction") == "up" else 1 - m["implied_yes"]
        w = max(1.0, float(m.get("volume24h") or 1.0))
        num += w * (2 * p_up - 1)
        den += w
    if not den:
        return None, "بازار BTC در پالی‌مارکت نیست"
    return max(-1.0, min(1.0, num / den)), None


def compute(kget=_kget_default, dom=None, poly=None, now_ms=None):
    """رأی‌ها و امتیاز خام — بدون ضدلرزش و بدون ثبت."""
    now_ms = now_ms or int(time.time() * 1000)
    dom = dom if dom is not None else _load(DOM)
    poly = poly if poly is not None else _load(POLY)
    votes, abstain = {}, {}
    try:
        c4 = kget("BTCUSDT", "4h", KL_N)
        c1 = kget("BTCUSDT", "1h", KL_N)
        if len(c4) < 60 or len(c1) < 60:
            raise ValueError("کندل کافی نیست")
    except Exception as e:                           # noqa: BLE001
        return {"stance": "NO_STANCE", "score": None, "votes": {},
                "abstain": {"btc": f"کندل BTC خواندنی نیست ({type(e).__name__}: {e})"},
                "btc_px": None, "t4": None, "t1": None,
                "why": "دادهٔ ناقص = بدون موضع (قانون ۱)"}
    from hamid.structure import trend
    t4, t1 = trend(c4), trend(c1)
    votes["btc_4h"], votes["btc_1h"] = _vote(t4), _vote(t1)
    btc_px = c1[-1]["c"]

    dom_age = None
    if dom and dom.get("generated"):
        dom_age = (now_ms - dom["generated"]) / 60000
    st = ((dom or {}).get("structure") or {}).get("usdt") or {}
    if dom_age is not None and dom_age <= DOM_MAX_AGE_MIN and st:
        votes["usdt_4h"] = _vote(st.get("trend_4h"), inverse=True)
        votes["usdt_1h"] = _vote(st.get("trend_1h"), inverse=True)
    else:
        abstain["usdt"] = ("دامیننس ناموجود" if dom_age is None
                           else f"دامیننس کهنه ({int(dom_age)}د > {DOM_MAX_AGE_MIN})")

    pv, why = _poly_view(poly, now_ms)
    if pv is None:
        abstain["polymarket"] = why
    else:
        votes["polymarket"] = pv

    wsum = sum(W[k] for k in votes)
    score = round(sum(W[k] * votes[k] for k in votes) / wsum, 3) if wsum else 0.0
    stance = ("LONG_BIAS" if score >= BAND else
              "SHORT_BIAS" if score <= -BAND else "NEUTRAL")
    events = [e for e in ((dom or {}).get("macro") or [])
              if e.get("country") == "USD" and 0 <= float(e.get("in_hours") or 99) <= EVENT_FREEZE_H]
    return {"stance": stance, "score": score, "votes": votes, "abstain": abstain,
            "btc_px": btc_px, "t4": t4, "t1": t1,
            "btc_d_note": ((dom or {}).get("structure") or {}).get("btc_d"),
            "event_freeze": [e.get("title") for e in events],
            "why": f"BTC ۴س={t4} · ۱س={t1} · USDT.D "
                   f"{'۴س='+str(st.get('trend_4h'))+' ۱س='+str(st.get('trend_1h')) if 'usdt_4h' in votes else 'ممتنع'}"
                   f" · پالی‌مارکت {'%+.2f' % pv if pv is not None else 'ممتنع'}"}


def _ledger_rows():
    if not LEDGER.exists():
        return []
    rows = []
    for ln in LEDGER.read_text().splitlines():
        try:
            rows.append(json.loads(ln))
        except Exception:                            # noqa: BLE001
            continue
    return rows


def decide(cur, last, now_ms):
    """ضدلرزش: (موضع نهایی، محرک، نگه‌داشته؟)."""
    weekly = datetime.fromtimestamp(now_ms / 1000, tz=timezone.utc).weekday() == 0
    if cur["stance"] == "NO_STANCE":
        return cur["stance"], "no-data", False
    if last is None:
        return cur["stance"], "first", False
    if cur.get("event_freeze"):
        return last["stance"], "event-freeze", True
    if cur["t4"] != last.get("t4"):
        return cur["stance"], "structure-change", False
    if weekly and (now_ms - last["ts"]) > 6 * 86_400_000:
        return cur["stance"], "weekly", False
    if cur["stance"] != last["stance"]:
        if (now_ms - last["ts"]) >= MIN_HOLD_H * 3_600_000:
            return cur["stance"], "score-cross", False
        return last["stance"], "min-hold", True
    return cur["stance"], "unchanged", False


def _wilson(k, n, z=1.96):
    if not n:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(c - h, 3), round(c + h, 3)]


def track_record(rows, btc_px_now, now_ms):
    """داوری ۷روزهٔ ثبت‌های قدیمی با قیمت امروز؛ زیر n=۲۰ عدد ندارد."""
    hits = n = 0
    for r in rows:
        if r.get("stance") not in ("LONG_BIAS", "SHORT_BIAS") or not r.get("btc_px"):
            continue
        if now_ms - r["ts"] < JUDGE_DAYS * 86_400_000:
            continue
        ret = btc_px_now / r["btc_px"] - 1
        n += 1
        if (r["stance"] == "LONG_BIAS" and ret > NOISE_BAND) or \
           (r["stance"] == "SHORT_BIAS" and ret < -NOISE_BAND):
            hits += 1
    if n < MIN_N_TRACK:
        return {"n": n, "hit": None, "ci": None,
                "why": f"n={n} < {MIN_N_TRACK} — کارنامه هنوز عدد ندارد"}
    return {"n": n, "hit": round(hits / n, 3), "ci": _wilson(hits, n), "why": None}


def build(kget=_kget_default, dom=None, poly=None, now_ms=None, rows=None):
    now_ms = now_ms or int(time.time() * 1000)
    cur = compute(kget, dom, poly, now_ms)
    rows = _ledger_rows() if rows is None else rows
    last = rows[-1] if rows else None
    stance, trigger, held = decide(cur, last, now_ms)
    changed = last is None or stance != last.get("stance")
    tr = track_record(rows, cur["btc_px"], now_ms) if cur["btc_px"] else \
        {"n": 0, "hit": None, "ci": None, "why": "قیمت BTC ندارد"}
    up = "عبور ۴س از سقف قبلی با حجم → موضع لانگ محکم‌تر؛ USDT.D زیر سطح پایینی"
    down = "شکست کف ۴س + USDT.D بالای سطح بالایی → موضع شورت؛ لانگ فقط با تأیید کامل"
    return {
        "generated": now_ms, "panel": "لیام تریدر ۹",
        "stance": stance, "score": cur["score"], "raw_stance": cur["stance"],
        "trigger": trigger, "held": held, "changed": changed,
        "votes": cur["votes"], "weights": W, "abstain": cur["abstain"],
        "btc": {"px": cur["btc_px"], "t4": cur["t4"], "t1": cur["t1"]},
        "btc_d_note": cur.get("btc_d_note"),
        "event_freeze": cur.get("event_freeze") or [],
        "rules": {"band": BAND, "min_hold_h": MIN_HOLD_H,
                  "event_freeze_h": EVENT_FREEZE_H, "dom_max_age_min": DOM_MAX_AGE_MIN},
        # بستهٔ شواهد (قانون ۱۲)
        "claim": f"موضع بازار: {stance}",
        "numbers": cur["why"],
        "track_record": tr,
        "scenario_up": up, "scenario_down": down,
        "invalidator": "تغییر برچسب روند ۴س BTC یا عبور USDT.D از سطح مخالف",
        "sources": ["sources.klines BTCUSDT 4h/1h", "signals/dominance.json",
                    "signals/polymarket.json"],
        "boundary": "دیدگاه است، نه دروازه؛ هیچ امتیاز/سایز/اهرمی عوض نمی‌شود "
                    "تا CI بالای صفر + تأیید حمید (قانون ۰۳/۱۲/۱۵)",
    }


def write(res):
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    # ردیف دفتر: هر تغییر موضع + هر بازبینی هفتگی/ساختاری (تا کارنامه کادنس داشته باشد)
    if res["stance"] != "NO_STANCE" and (
            res["changed"] or res["trigger"] in ("weekly", "structure-change")):
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with LEDGER.open("a") as f:
            f.write(json.dumps({"ts": res["generated"], "stance": res["stance"],
                                "score": res["score"], "trigger": res["trigger"],
                                "t4": res["btc"]["t4"], "btc_px": res["btc"]["px"]},
                               ensure_ascii=False) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    res = build()
    if a.write:
        write(res)
    print(f"موضع بازار: {res['stance']} (امتیاز {res['score']}) — {res['trigger']}"
          f"{' · نگه‌داشته' if res['held'] else ''} · {res['numbers']}")


if __name__ == "__main__":
    main()
