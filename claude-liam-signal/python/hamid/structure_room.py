#!/usr/bin/env python3
"""اتاق ساختار — گزارش یکپارچهٔ ۴س/۱س/۱۵د به مدیر انجین (دستور حمید، ۳ سپتامبر).

حمید: «در آخر به ایجنت اصلی که این انجین را مدیریت می‌کند گزارش بدهد؛
مثلاً این ارز در تایم ۴ ساعته نزولی است زیر مقاومت فلان، در ۱ ساعته
روند فلان است، در ۱۵ دقیقه طبق استراتژی و ستاپ این شرایط را دارد… و
ایجنتِ این انجین باید این ستاپ را بارها تمرین کرده باشد که با دیدن
گزارش، نقص را به واحد مربوطه برگرداند — مثلاً به ایجنت روند بگوید
این‌جا باید کانال را بهتر بکشی — یا همه چیز اوکی است و می‌رود جلو.»

## چهار واحد و مالکِ هر نقص

| واحد | چه می‌آورد | کدِ نقص |
|---|---|---|
| روند و خط | جهت هر تایم + خط‌کشی رو-به-جلو + هندسه + ری‌های افقی | `trend` / `lines` |
| اردر بلاک | باکس‌های ۱س و ۱۵د به روش خود حمید | `ob` |
| کندل و ستاپ | مکان قیمت داخل نقشه، آمادگی ستاپ | `setup` |
| حجم | تأیید حجمی — مهم‌ترین تأیید حمید (قانون ۰۰) | `volume` |

## چرا «نقص» و نه «خطا»

نقص یعنی گزارشِ واحد **قابل استفاده نیست**، نه این‌که واحد خراب است.
نبودِ ستاپ عیب نیست؛ نبودِ *جواب* عیب است. پس «۱۵د ستاپ ندارد» نقص
نیست و در `notes` می‌نشیند؛ ولی «۴س هیچ خط معتبری نداد» نقص است، چون
بدون نقشهٔ ۴س هیچ تصمیمی نباید گرفته شود (قانون ۲).

## مرز صادقانه

این اتاق **گزارش می‌دهد و نقص برمی‌گرداند**؛ سیگنال صادر نمی‌کند و هیچ
دروازه‌ای را شل یا سفت نمی‌کند. `ready` فقط یعنی «نقشه کامل است، حالا
می‌شود تصمیم گرفت» — نه «برو».

    python3 -m hamid.structure_room --demo
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from hamid import lines_wf as LW                     # noqa: E402
from hamid import orderblocks as OB                  # noqa: E402
from hamid import structure as ST                    # noqa: E402

# ترتیب اجباری تحلیل (قانون ۰۰): بالا به پایین، هرگز برعکس.
ORDER = ("4h", "1h", "15m")
ANCHOR_DAYS = {"4h": 30.0, "1h": 7.0, "15m": 2.0}    # «یک هفته» روی ۱س؛ بالاتر بلندتر
OB_TFS = ("1h", "15m")                               # دستور حمید: OB در ۱س و ۱۵د
MIN_BARS = 60                                        # کمتر از این، تایم گزارش ندارد
VOL_HOT = 1.30                                       # حجم اخیر نسبت به میانهٔ ۵۰ کندل
VOL_COLD = 0.70

FA_TREND = {"up": "صعودی", "down": "نزولی", "range": "رنج"}
FA_SHAPE = {"channel_up": "کانال صعودی", "channel_down": "کانال نزولی",
            "ascending_triangle": "مثلث صعودی", "descending_triangle": "مثلث نزولی",
            "symmetric_triangle": "مثلث متقارن", "rising_wedge": "گُوهٔ صعودی",
            "falling_wedge": "گُوهٔ نزولی", "broadening": "الگوی پهن‌شونده",
            "range": "رنج افقی", "none": "بدون هندسهٔ شناخته‌شده"}
UNIT_FA = {"trend": "ایجنت روند", "lines": "ایجنت خط‌کشی",
           "ob": "ایجنت اردر بلاک", "setup": "ایجنت ستاپ", "volume": "ایجنت حجم"}


# ── حجم: تأیید، نه ماشه ──────────────────────────────────────────────────
def volume_state(cd, n=50, recent=3):
    """حجمِ کندل‌های اخیر در برابر میانهٔ پنجره. بی‌حجم = unknown، نه «عادی»."""
    vols = [c.get("v") for c in cd[-(n + recent):]]
    vols = [v for v in vols if isinstance(v, (int, float)) and v > 0]
    if len(vols) < 20:
        return {"state": "unknown", "ratio": None,
                "why": "حجم روی این سری نیست یا کم است — عدد ساخته نمی‌شود (قانون ۱)"}
    base = sorted(vols[:-recent] or vols)
    med = base[len(base) // 2]
    cur = sum(vols[-recent:]) / recent
    r = round(cur / med, 3) if med else None
    if r is None:
        return {"state": "unknown", "ratio": None, "why": "میانهٔ حجم صفر است"}
    st = "hot" if r >= VOL_HOT else "cold" if r <= VOL_COLD else "normal"
    fa = {"hot": "حجم بالای میانه", "cold": "حجم زیر میانه", "normal": "حجم عادی"}[st]
    return {"state": st, "ratio": r, "why": f"{fa} (نسبت {r}× به میانهٔ {len(base)} کندل)"}


# ── مکان قیمت داخل نقشه ─────────────────────────────────────────────────
def location(cd, m):
    """قیمت کجای هندسه و نزدیک‌ترین ری افقی کجاست — «مکان قبل از سیگنال»."""
    px = cd[-1]["c"]
    geo = m.get("geometry") or {}
    out = {"price": px, "in_pattern": None, "pos_pct": None,
           "nearest_ray": None, "ray_dist_pct": None}
    top, bot = geo.get("top"), geo.get("bottom")
    if isinstance(top, (int, float)) and isinstance(bot, (int, float)) and top > bot:
        out["in_pattern"] = bot <= px <= top
        out["pos_pct"] = round((px - bot) / (top - bot) * 100, 1)
    best = None
    for r in m.get("rays") or []:
        d = abs(px - r["price"])
        if best is None or d < best[0]:
            best = (d, r)
    if best and px:
        out["nearest_ray"] = {"kind": best[1]["kind"], "price": best[1]["price"]}
        out["ray_dist_pct"] = round(best[0] / px * 100, 3)
    return out


# ── یک تایم‌فریم ─────────────────────────────────────────────────────────
def read_tf(cd, tf):
    """گزارش یک تایم‌فریم از چهار واحد. هر غیبتی دلیلش را می‌نویسد."""
    if not cd or len(cd) < MIN_BARS:
        return {"tf": tf, "ok": False,
                "why": f"کندل کم است ({len(cd or [])} < {MIN_BARS}) — این تایم گزارش ندارد"}
    m = LW.build(cd, tf, days=ANCHOR_DAYS.get(tf, LW.ANCHOR_DAYS))
    r = {"tf": tf, "ok": True, "bars": len(cd), "price": cd[-1]["c"],
         "trend": ST.trend(cd), "map": {"candidates": m.get("candidates"),
                                        "kept_n": m.get("kept_n"),
                                        "dropped_n": m.get("dropped_n"),
                                        "geometry": m.get("geometry"),
                                        "rays": m.get("rays") or []},
         "location": location(cd, m), "volume": volume_state(cd)}
    if tf in OB_TFS:
        inside, nearby = OB.near(cd, tf=tf)
        blocks = OB.find(cd, tf=tf)
        r["ob"] = {"n": len(blocks), "fresh": sum(1 for b in blocks if b["fresh"]),
                   "inside": inside, "near": nearby}
    return r


# ── نقص‌ها: هر کدام با مالک و کارِ خواسته‌شده ───────────────────────────
def defects(reads):
    """نقصِ قابل‌برگرداندن به واحد. «ستاپ نیست» نقص نیست؛ «جواب نیست» هست."""
    out = []

    def add(unit, tf, what, ask):
        out.append({"unit": unit, "unit_fa": UNIT_FA[unit], "tf": tf,
                    "what": what, "ask": ask})

    for tf in ORDER:
        r = reads.get(tf)
        if not r:
            add("trend", tf, f"گزارش {tf} اصلاً نیامد", "کندل این تایم را برسان")
            continue
        if not r.get("ok"):
            add("trend", tf, r.get("why", "گزارش ناقص"), "کندل کافی برسان یا این تایم را صریح کنار بگذار")
            continue
        mp = r["map"]
        if mp["kept_n"] == 0:
            add("lines", tf, "هیچ خط معتبری نماند",
                "خط را بهتر بکش: لنگر عقب‌تر یا پیوت با تأیید کمتر — "
                "بدون نقشهٔ خط، تصمیم این تایم بی‌پایه است")
        elif mp["geometry"].get("shape") == "none" and tf in ("4h", "1h"):
            add("lines", tf, "خط هست ولی هندسه‌ای نساخت",
                "کانال/مثلث را بهتر بکش — یا اگر واقعاً هندسه‌ای نیست، همین را صریح بگو")
        if tf == "4h" and not mp["rays"]:
            add("lines", "4h", "هیچ سقف/کفِ افقیِ معتبری علامت نخورد",
                "سطوحی که واقعاً نقش حمایت/مقاومت گرفتند را با ری افقی بزن (دستور ۴س)")
        if r["volume"]["state"] == "unknown":
            add("volume", tf, r["volume"]["why"], "منبع حجم این تایم را وصل کن")
        if tf in OB_TFS:
            ob = r.get("ob") or {}
            if ob.get("n", 0) == 0:
                add("ob", tf, "هیچ اردر بلاک معتبری پیدا نشد",
                    "پنجرهٔ ۳۰۰ کندل و آستانهٔ ایمپالس را دوباره ببین — "
                    "روش حمید در این تایم باید باکس بدهد")

    ok = [tf for tf in ORDER if (reads.get(tf) or {}).get("ok")]
    if len(ok) < len(ORDER):
        add("trend", "-", f"فقط {len(ok)} تایم از {len(ORDER)} گزارش داد",
            "سلسله‌مراتب ۴س→۱س→۱۵د ناقص است (قانون ۲)")
    return out


# ── جهت‌گیری: خوانشِ سلسله‌مراتبی ───────────────────────────────────────
def stance(reads):
    """حکمِ اتاق: هم‌جهت یا متعارض. تایم پایین بالادست را نقض نمی‌کند."""
    t = {tf: (reads.get(tf) or {}).get("trend") for tf in ORDER}
    have = [v for v in t.values() if v]
    if len(have) < 2:
        return {"bias": "UNKNOWN", "why": "کمتر از دو تایم گزارش داد — جهتی اعلام نمی‌شود"}
    up = sum(1 for v in have if v == "up")
    dn = sum(1 for v in have if v == "down")
    hi = t.get("4h")
    if hi in ("up", "down") and t.get("1h") in ("up", "down") and t["1h"] != hi:
        return {"bias": "CONFLICT",
                "why": f"۴س {FA_TREND[hi]} ولی ۱س {FA_TREND[t['1h']]} — تایم بالا حاکم است (قانون ۲)"}
    if up and not dn:
        return {"bias": "LONG", "why": "همهٔ تایم‌های دارای جهت صعودی‌اند"}
    if dn and not up:
        return {"bias": "SHORT", "why": "همهٔ تایم‌های دارای جهت نزولی‌اند"}
    if up and dn:
        return {"bias": "CONFLICT", "why": "تایم‌ها هم‌جهت نیستند"}
    return {"bias": "RANGE", "why": "هیچ تایمی جهت قاطع نداد — رنج"}


# ── گزارش فارسی به مدیر انجین ───────────────────────────────────────────
def lines_fa(sym, reads, st, dfs):
    out = [f"🏛 اتاق ساختار — {sym}"]
    for tf in ORDER:
        r = reads.get(tf)
        if not r:
            out.append(f"• {tf}: گزارشی نیامد")
            continue
        if not r.get("ok"):
            out.append(f"• {tf}: {r.get('why')}")
            continue
        mp = r["map"]
        seg = [f"روند {FA_TREND.get(r['trend'], r['trend'])}",
               FA_SHAPE.get(mp["geometry"].get("shape"), mp["geometry"].get("shape"))]
        loc = r["location"]
        if loc.get("pos_pct") is not None:
            seg.append(f"قیمت در {loc['pos_pct']}٪ ارتفاع الگو")
        nr = loc.get("nearest_ray")
        if nr:
            side = "مقاومت" if nr["kind"] == "res" else "حمایت"
            seg.append(f"نزدیک‌ترین {side} افقی {nr['price']} ({loc['ray_dist_pct']}٪ فاصله)")
        seg.append(r["volume"]["why"])
        if tf in OB_TFS:
            ob = r.get("ob") or {}
            if ob.get("inside"):
                seg.append("قیمت داخل یک اردر بلاک معتبر")
            elif ob.get("near"):
                seg.append("اردر بلاک معتبر نزدیک قیمت")
            seg.append(f"{ob.get('n', 0)} اردر بلاک ({ob.get('fresh', 0)} تازه)")
        out.append(f"• {tf}: " + " · ".join(str(x) for x in seg))
    out.append(f"⚖️ جهت‌گیری: {st['bias']} — {st['why']}")
    if dfs:
        out.append(f"🔧 {len(dfs)} نقص برگشت به واحدها:")
        for d in dfs[:6]:
            out.append(f"   ↩ {d['unit_fa']} ({d['tf']}): {d['what']} → {d['ask']}")
    else:
        out.append("✅ همه چیز اوکی است — نقشه کامل، می‌شود جلو رفت")
    return out


def report(sym, candles):
    """`candles` = {"4h": [...], "1h": [...], "15m": [...]} — تزریقی، نه شبکه‌ای."""
    reads = {}
    for tf in ORDER:
        reads[tf] = read_tf(candles.get(tf) or [], tf)
    st = stance(reads)
    dfs = defects(reads)
    return {"symbol": sym, "order": list(ORDER), "timeframes": reads,
            "stance": st, "defects": dfs,
            "ready": not dfs and st["bias"] != "UNKNOWN",
            "text": "\n".join(lines_fa(sym, reads, st, dfs)),
            "boundary": "این اتاق گزارش می‌دهد و نقص برمی‌گرداند؛ سیگنال صادر نمی‌کند "
                        "و هیچ دروازه‌ای را عوض نمی‌کند (قانون ۰۳/۱۲)"}


def main(argv=None):
    argv = list(argv if argv is not None else sys.argv[1:])
    if "--demo" in argv or not argv:
        cds = {"4h": LW.synth("channel_up", n=300),
               "1h": LW.synth("ascending_triangle", n=300),
               "15m": LW.synth("range", n=300)}
        r = report("DEMOUSDT", cds)
        print(r["text"])
        print(f"\nآماده: {r['ready']}")
        return 0
    print("استفاده: python3 -m hamid.structure_room --demo")
    return 0


if __name__ == "__main__":
    sys.exit(main())
