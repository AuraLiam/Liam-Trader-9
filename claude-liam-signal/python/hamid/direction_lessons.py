#!/usr/bin/env python3
"""درسِ جهتِ مخالف — هر لانگی که استاپ می‌خورد، درسی برای شورت است و برعکس.

دستور حمید (۷ سپتامبر): «باید تمام اطلاعات و نیازهای مربوط به شورت گرفتن
رو یاد بگیری. هر لانگی که استاپ میخوره میتونه یک درسی باشه برای شورت
گرفتن و بر عکس. پس وقتی میگم بلافاصله بعد از نتیجه به دست اومده علت یابی
کن، به این دلیله که بتونی تشخیص بدی مشکل از کجا بوده.»

## چرا این ماژول لازم شد

`memory.digest_closed` تا امروز فقط یک واقعیتِ آماری ثبت می‌کرد: «برد/باخت
با این شرایط». هیچ‌جا نمی‌گفت **این باخت چه چیزی دربارهٔ جهتِ مخالف یاد
می‌دهد** — که خواستهٔ صریح حمید است.

## چرا «هر استاپِ لانگ = فرصت شورت» غلط است

۶ سپتامبر همین فرضیه را روی ۷٬۱۷۱ استاپِ لانگ و ۲۰٬۳۱۰ شورت سنجیدم و
**رد شد**: اختلاف خالص +۰.۰۰۰۸R با CI شامل صفر، و ناخالص در هر ۶ پنجره
منفیِ معنادار. MFE و MAE هر دو کمتر می‌شدند — یعنی بعد از استاپِ لانگ
قیمت در **هر دو جهت** کمتر حرکت می‌کند: فشردگی، نه ریزش.

ولی آن سنجش یک عیب داشت که این ماژول رفعش می‌کند: **همهٔ استاپ‌ها را
یک‌کاسه کرد.** سه چیزِ کاملاً متفاوت زیر یک نام:

| کلاس | نشانه | چه یاد می‌دهد |
|---|---|---|
| `WRONG_SIDE` | هرگز در سود نرفت (MFE ناچیز) | جهت از اول غلط بود — قوی‌ترین شاهدِ جهتِ مخالف |
| `FAILED_CONT` | رفت در سود، بعد برگشت و استاپ خورد | در آن سطح عرضه/تقاضا ظاهر شد — شاهدِ سطح، نه شاهدِ جهت |
| `NOISE_STOP` | استاپِ تنگ، MAE کمی بالای ۱ | هندسه بد بود، نه تحلیل — **هیچ درسِ جهتی ندارد** |

قاطی‌کردن این سه، درس را مسموم می‌کند: `NOISE_STOP` اصلاً دربارهٔ جهت
حرف نمی‌زند و اگر با بقیه جمع شود، سیگنالِ واقعیِ `WRONG_SIDE` را رقیق
می‌کند. این ماژول هر کلاس را **جدا** ثبت و جدا نمره می‌دهد.

## مرزی که از آن رد نمی‌شود

هیچ درسی این‌جا به قاعده تبدیل نمی‌شود. هر ردیف یک **فرضیه** است با
باطل‌کنندهٔ خودش؛ ورودش به تصمیم فقط از مسیر قانون ۰۳ (CI بالای صفر و
تأیید حمید). ماژول فقط می‌خواند و دفتر خودش را می‌نویسد (قانون ۰۵).

    python3 -m hamid.direction_lessons            # گزارش + نمرهٔ کلاس‌ها
    python3 -m hamid.direction_lessons --write    # + دفتر و تابلو
"""
import json
import math
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
ROOT = PY.parents[1]
sys.path.insert(0, str(PY))

CLOSED = ROOT / "brain" / "paper" / "closed.jsonl"
BOOK = ROOT / "brain" / "lessons" / "direction.jsonl"     # append-only
OUT = ROOT / "signals" / "direction-lessons.json"

# آستانه‌ها — از پیش ثبت‌شده، نه بعد از دیدن نتیجه.
MFE_DEAD = 0.15        # زیر این، یعنی عملاً هرگز در سود نرفت
MFE_LIVE = 0.50        # بالای این، یعنی واقعاً کار کرد و بعد برگشت
TIGHT_STOP_PCT = 0.50  # استاپِ تنگ‌تر از این، مظنونِ نویز
MIN_N = 60             # کف نمونه برای نمره‌دادن به یک کلاس


def _f(v):
    return float(v) if isinstance(v, (int, float)) else None


def classify(row):
    """نوعِ شکست — و اینکه اصلاً درسِ جهتی دارد یا نه.

    برمی‌گرداند (کلاس، دلیلِ فارسی، آیا شاهدِ جهتِ مخالف هست؟).
    """
    w = row.get("why") or {}
    mfe = _f(row.get("mfe_r"))
    if mfe is None:
        mfe = _f(w.get("mfe"))
    mae = _f(row.get("mae_r"))
    if mae is None:
        m = _f(w.get("mae"))
        mae = abs(m) if m is not None else None
    stop_pct = _f(w.get("stop_pct"))
    if stop_pct is None:
        try:
            stop_pct = abs(row["entry"] - row["sl"]) / row["entry"] * 100
        except Exception:                            # noqa: BLE001
            stop_pct = None

    if mfe is None:
        return None, "MFE ثبت نشده — قابل طبقه‌بندی نیست", False
    # نویز اول سنجیده می‌شود: استاپِ تنگی که فقط کمی رد شده، دربارهٔ جهت
    # حرفی نمی‌زند. اگر این اول نیاید، همین ردیف‌ها به‌غلط WRONG_SIDE
    # می‌شوند و درسِ جهتی را رقیق می‌کنند.
    if (stop_pct is not None and stop_pct < TIGHT_STOP_PCT
            and mae is not None and mae < 1.35 and mfe < MFE_LIVE):
        return ("NOISE_STOP",
                f"استاپِ تنگ ({stop_pct:.2f}٪) و نفوذِ کم (MAE {mae:.2f}R) — "
                "هندسه، نه جهت", False)
    if mfe < MFE_DEAD:
        return ("WRONG_SIDE",
                f"هرگز در سود نرفت (MFE {mfe:.2f}R) — جهت از ابتدا غلط بود",
                True)
    if mfe >= MFE_LIVE:
        return ("FAILED_CONT",
                f"تا {mfe:.2f}R در سود رفت و برگشت — در آن سطح جهت عوض شد",
                True)
    return ("SHALLOW", f"حرکتِ کم‌عمق (MFE {mfe:.2f}R) — شاهدِ ضعیف", False)


def lesson_from(row, now_ms=None):
    """یک فرضیهٔ جهتِ مخالف از یک معاملهٔ بستهٔ بازنده — یا None."""
    if (row.get("R") or 0) >= 0 or row.get("outcome") in ("expired", "no_fill",
                                                          None):
        return None
    cls, why, directional = classify(row)
    if cls is None:
        return None
    d = (row.get("dir") or "").upper()
    opp = "SHORT" if d == "LONG" else "LONG" if d == "SHORT" else None
    if opp is None:
        return None
    w = row.get("why") or {}
    return {
        "at": int(now_ms or time.time() * 1000),
        "sym": row.get("sym"), "tf": row.get("tf"),
        "lost_dir": d, "opposite": opp,
        "class": cls, "why": why,
        "directional": directional,
        # سطحی که ازش درس می‌گیریم: قیمتِ استاپ. برای لانگِ استاپ‌خورده
        # این سقفِ عرضه است؛ برای شورت، کفِ تقاضا.
        "level": row.get("sl"), "entry": row.get("entry"),
        "R": row.get("R"), "mfe_r": row.get("mfe_r"),
        "mae_r": row.get("mae_r"), "held_h": row.get("held_h"),
        "stage": w.get("stage"), "trend_4h": w.get("trend_4h"),
        "trend_1h": w.get("trend_1h"), "closed": row.get("closed"),
        # فرضیه، نه قاعده — و باطل‌کننده‌اش همراهش می‌آید (قانون ۱۲).
        "hypothesis": (f"{opp} از نزدیکیِ {row.get('sl')} روی "
                       f"{row.get('sym')} لبه داشت" if directional else
                       "این شکست درسِ جهتی ندارد"),
        "falsifier": ("اگر نمرهٔ همین کلاس روی نمونهٔ کافی CI بالای صفر "
                      "نداد، فرضیه باطل است"),
    }


def _fee_r(row):
    try:
        from hamid import fees
        return fees.cost_in_r(row["entry"], row["sl"])
    except Exception:                                # noqa: BLE001
        try:
            sp = abs(row["entry"] - row["sl"]) / row["entry"] * 100
            return 0.15 / sp if sp > 0 else None
        except Exception:                            # noqa: BLE001
            return None


def _ci(vals):
    n = len(vals)
    if n < 2:
        return None
    m = statistics.mean(vals)
    h = 1.96 * statistics.stdev(vals) / math.sqrt(n)
    return {"n": n, "mean": round(m, 4), "lo": round(m - h, 4),
            "hi": round(m + h, 4),
            "verdict": ("بالای صفر" if m - h > 0 else
                        "زیر صفر" if m + h < 0 else "شامل صفر")}


def rows(path=None):
    """ردیف‌های بستهٔ یکتا (یکتایی پیش از هر CI — تصحیح ۲۴ اوت)."""
    p = Path(path or CLOSED)
    out, seen = [], set()
    if not p.exists():
        return out
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except Exception:                            # noqa: BLE001
            continue
        ident = (r.get("sym"), r.get("dir"), r.get("entry"), r.get("opened"))
        if ident in seen:
            continue
        seen.add(ident)
        out.append(r)
    return out


def score_classes(all_rows, now_ms=None):
    """آیا کلاسی که «شاهدِ جهتی» می‌داند، واقعاً جهت را درست می‌گوید؟

    روش: برای هر کلاس، معامله‌های **جهتِ مخالفِ** همان نماد که تا ۶ ساعت
    بعد از آن باخت باز شده‌اند جمع می‌شوند و خالصشان با CI سنجیده می‌شود؛
    در برابر خطِ پایهٔ همان جهت روی کلِ دفتر.

    این همان سنجهٔ ۶ سپتامبر است با **یک تفاوت**: آن‌جا همهٔ استاپ‌ها
    یک‌کاسه بودند و رد شد؛ این‌جا هر کلاس جدا داوری می‌شود.
    """
    import bisect
    import collections
    H = 6 * 3600e3
    # زمانِ باختِ هر کلاس، به تفکیک (نماد، جهتِ مخالف)
    marks = collections.defaultdict(list)
    for r in all_rows:
        les = lesson_from(r, now_ms)
        if not les or not les["directional"] or not r.get("closed"):
            continue
        marks[(les["sym"], les["opposite"], les["class"])].append(r["closed"])
    for v in marks.values():
        v.sort()

    def t_open(r):
        for k in ("filled", "opened"):
            if isinstance(r.get(k), (int, float)):
                return r[k]
        return None

    def net(r):
        f = _fee_r(r)
        R = _f(r.get("R"))
        return None if (f is None or R is None) else R - f

    classes = sorted({k[2] for k in marks})
    out = {}
    for cls in classes:
        treat, base = [], []
        for r in all_rows:
            d = (r.get("dir") or "").upper()
            t = t_open(r)
            nv = net(r)
            if t is None or nv is None:
                continue
            ts = marks.get((r.get("sym"), d, cls))
            hit = False
            if ts:
                i = bisect.bisect_right(ts, t) - 1
                hit = i >= 0 and 0 <= t - ts[i] <= H
            (treat if hit else base).append(nv)
        c_t, c_b = _ci(treat), _ci(base)
        diff = None
        if c_t and c_b and len(treat) >= 2 and len(base) >= 2:
            se = math.sqrt(statistics.pvariance(treat) / len(treat)
                           + statistics.pvariance(base) / len(base))
            d0 = c_t["mean"] - c_b["mean"]
            h = 1.96 * se
            diff = {"diff": round(d0, 4), "lo": round(d0 - h, 4),
                    "hi": round(d0 + h, 4),
                    "verdict": ("بالای صفر" if d0 - h > 0 else
                                "زیر صفر" if d0 + h < 0 else "شامل صفر"),
                    "t": round(abs(d0 / se), 2) if se else None}
        out[cls] = {"treated": c_t, "baseline": c_b, "diff": diff,
                    "enough": bool(c_t and c_t["n"] >= MIN_N)}
    return out


def build(path=None, now_ms=None):
    all_rows = rows(path)
    lessons = [x for x in (lesson_from(r, now_ms) for r in all_rows) if x]
    import collections
    by_cls = collections.Counter(x["class"] for x in lessons)
    by_dir = collections.Counter(f'{x["lost_dir"]}→{x["opposite"]}'
                                 for x in lessons)
    return {
        "generated": int(now_ms or time.time() * 1000),
        "panel": "لیام تریدر ۹",
        "n_lessons": len(lessons),
        "by_class": dict(by_cls), "by_direction": dict(by_dir),
        "directional": sum(1 for x in lessons if x["directional"]),
        "scores": score_classes(all_rows, now_ms),
        "min_n": MIN_N,
        "note": ("هر ردیف یک **فرضیه** است نه قاعده. ورود به تصمیم فقط با "
                 "CI بالای صفر و تأیید حمید (قانون ۰۳)."),
        "boundary": ("سنجهٔ ۶ سپتامبر روی همهٔ استاپ‌ها یک‌کاسه رد شد؛ این‌جا "
                     "هر کلاس جدا داوری می‌شود. کلاس NOISE_STOP عمداً "
                     "«بدون درسِ جهتی» علامت خورده — استاپِ نویزی دربارهٔ "
                     "جهت حرفی نمی‌زند."),
    }


def append_lessons(new_rows, now_ms=None):
    """درس‌های معاملات تازه‌بسته — append-only، بدون بازنویسی."""
    out = [x for x in (lesson_from(r, now_ms) for r in new_rows) if x]
    if not out:
        return 0
    BOOK.parent.mkdir(parents=True, exist_ok=True)
    with BOOK.open("a", encoding="utf-8") as f:
        for x in out:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")
    return len(out)


def render(v):
    L = [f"### درسِ جهتِ مخالف — {v['n_lessons']} درس "
         f"({v['directional']} شاهدِ جهتی)", ""]
    L.append("  کلاس‌ها: " + " · ".join(f"{k}={n}" for k, n in
                                        sorted(v["by_class"].items())))
    L.append("  جهت‌ها: " + " · ".join(f"{k}={n}" for k, n in
                                       sorted(v["by_direction"].items())))
    L.append("\n  — آیا کلاس واقعاً جهت را درست می‌گوید؟ "
             f"(کف نمونه {v['min_n']})")
    for cls, s in sorted(v["scores"].items()):
        t, d = s["treated"], s["diff"]
        if not t:
            L.append(f"    {cls:<12} نمونهٔ کافی نیست")
            continue
        line = f"    {cls:<12} n={t['n']:<5} خالص {t['mean']:+.4f}R"
        if d:
            line += (f" · اختلاف با پایه {d['diff']:+.4f} "
                     f"CI[{d['lo']:+.4f},{d['hi']:+.4f}] {d['verdict']}")
        if not s["enough"]:
            line += "  ← زیر کف، بی‌حکم"
        L.append(line)
    L.append(f"\n  ⚖️ {v['boundary']}")
    return "\n".join(L)


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    v = build()
    print(render(v))
    if "--write" in argv:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(v, ensure_ascii=False, indent=1),
                       encoding="utf-8")
        print(f"\n→ {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
