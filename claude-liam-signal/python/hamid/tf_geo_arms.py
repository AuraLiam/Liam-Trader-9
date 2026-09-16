"""دو بازوی آزمایش — «فقط ۱۵ دقیقه» و «هندسهٔ بزرگ‌تر روی ۵ دقیقه» (دستور حمید، ۱۶ سپتامبر).

## چرا

ممیزی تلگرام ۱۵ سپتامبر روی ۱۶۲ سیگنالِ ارسالیِ تطبیق‌خورده: برد ۶۰.۵٪ ولی
خالص **−۰.۱۵۵R** (ibs −۰.۲۶۲R n=۷۷ · smc −۰.۰۶۱R n=۸۴)، ۱۶۰ از ۱۶۴ روی
۵ دقیقه، خروج‌ها: تریل ۹۴ · منقضی ۳۳ · استاپ ۳۱ · تارگت ۴. برد بالا با خالص
منفی یعنی کارمزد روی استاپ تنگِ ۵ دقیقه سنگین است — همان بیماری اسکلپ ۱د
(قانون ۱۰). حمید: «دو بازوی آزمایش رو بذار تا CI بده.»

## دو بازو — هر دو فقط پیپر، هیچ دروازه‌ای عوض نمی‌شود (قانون ۰۳/۱۲)

| بازو | برچسب | طرح | پایهٔ مقایسه |
|---|---|---|---|
| فقط ۱۵ دقیقه | `exp-tf15` | هر ستاپِ SIGNALِ ۱۵د که از دروازه‌های انتشار گذشته، در دفتر جدا باز می‌شود (سقف ۱۲ در هر اسکن، ضدتکرار نماد+جهت) | سیگنال‌های ارسالیِ ۵د (`sig-*`، tf=5m) — **ناجفت**، آزمون ولش |
| هندسهٔ ×۲ روی ۵د | `exp-geo-x2` | آینهٔ هر سیگنالِ ارسالیِ ۵د با استاپ و تارگت ×۲ (RR ثابت) — `paper.mirror_geo_arm` | همان ردیفِ پایه — **جفتی** روی نماد+ورود+لحظه |

## قاعدهٔ توقف — ثبت‌شده پیش از دیدن داده

| حکم | شرط |
|---|---|
| PROMOTE | CI **خالص از کارمزد** کاملاً بالای صفر (Šidák برای ۲ بازو، z=۲.۲۴) روی n ≥ ۲۰۰ (جفت، یا هر دو گروه) → فقط پیشنهاد؛ ورود به تولید تأیید صریح حمید |
| REJECT | CI کاملاً زیر صفر روی n ≥ ۴۰۰ |
| UNDECIDED | بقیه، با برآورد «چند نمونهٔ دیگر تا نیم‌پهنای ۰.۰۵R» |

اثرانگشت (ضریب هندسه، تایم، کارمزد) روی حکم ثبت می‌شود؛ تغییر هرکدام =
دفترِ حکم از صفر. خالص همیشه از `fee_r` خودِ ردیف (که در تسویه از استاپِ
همان ردیف بازمحاسبه می‌شود) — پس بازوی ×۲ نصفِ کارمزد را «به‌دست» نمی‌آورد
مگر واقعاً به تارگت برسد.

اجرا:  python3 -m hamid.tf_geo_arms [--json] [--write]
       (نمونه‌گیر ۱۵د از scan.py صدا زده می‌شود؛ آینهٔ ×۲ از hamid.cycle)
"""
import json
import math
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
ROOT = HERE.parent.parent.parent
OUT = ROOT / "signals" / "tf-geo-arms.json"

TF15_TAG = "exp-tf15"
GEO_TAG = "exp-geo-x2"
TF15X2_TAG = "exp-tf15-x2"      # هندسهٔ ×۲ روی همان ستاپ ۱۵د (۱۶ سپتامبر شب)
TF15_CAP = 12                # سقف ردیف تازه در هر اسکن — مهار سیل (درس stage-vetoed)
Z = 2.3877                   # Šidák برای ۳ آزمون، دوطرفه، آلفا ۰.۰۵
N_PROMOTE = 200
N_REJECT = 400
HALF_WIDTH_TARGET = 0.05
ARM_START_MS = 1_789_550_000_000   # ~۱۶ سپتامبر ۲۰۲۶ ۰۹:۱۳ UTC — پایهٔ ناجفت فقط از این‌جا به بعد


def fingerprint():
    from hamid import paper
    try:
        import liam9_strategy as S
        fee = S.PARAMS.get("fee_round_trip_pct")
    except Exception:                                # noqa: BLE001
        fee = None
    return {"geo_mult": paper.GEO_ARMS.get(GEO_TAG, (None, None))[1],
            "geo_mult_tf15": paper.GEO_ARMS.get(TF15X2_TAG, (None, None))[1],
            "tf15": "15m", "base_tf": "5m", "fee_round_trip_pct": fee,
            "tf15_cap_per_scan": TF15_CAP, "z": Z}


# ── نمونه‌گیر ۱۵ دقیقه (از scan.py، بعد از دروازه‌ها) ──────────────────────
def _open_keys(tag):
    from hamid import paper
    out = set()
    for r in paper._read(paper.OPEN):
        st = (r.get("why") or {}).get("stage") or r.get("stage_tag")
        if st == tag:
            out.add((r.get("sym"), (r.get("dir") or "").upper()))
    return out


def sample_tf15(setups, cap=TF15_CAP):
    """هر ستاپِ SIGNALِ ۱۵د که از دروازه‌ها گذشته → ردیف `exp-tf15`.

    فقط SIGNAL (نه ARMED/PULLBACK)، فقط tf=15m، ضدتکرار (نماد،جهت) روی دفتر
    باز، سقف در هر اسکن. ستاپ را دست نمی‌زند و به تلگرام چیزی نمی‌دهد."""
    from hamid import paper
    have = _open_keys(TF15_TAG)
    opened, seen = 0, 0
    for s in setups or []:
        if str(s.get("stage", "")).upper() != "SIGNAL" or s.get("tf") != "15m":
            continue
        seen += 1
        if opened >= cap:
            break
        key = (s.get("sym"), (s.get("dir") or "").upper())
        if key in have or not (s.get("entry") and s.get("sl")):
            continue
        try:
            n = paper.open_from(
                [{"symbol": s["sym"], "dir": s["dir"], "entry": s["entry"],
                  "sl": s["sl"], "tp1": s.get("tp1") or s["entry"],
                  "tp2": s.get("tp2"), "stage_tag": TF15_TAG, "tf": "15m"}],
                {"arm": TF15_TAG, "strategy": s.get("strategy"),
                 "quality": s.get("quality"), "trend_4h": s.get("trend4"),
                 "trend_1h": s.get("trend1")})
        except Exception:                            # noqa: BLE001
            n = 0
        if n:
            opened += n
            have.add(key)
    # آینهٔ هندسهٔ ×۲ **همین لحظه** ساخته می‌شود، نه در اجرای بعد. اگر منتظر
    # چرخه بمانیم، ستاپی که زود بسته شود هرگز جفت نمی‌گیرد و نمونه به‌سمت
    # معامله‌های کُند سوگیری می‌کند — همان اشتباهی که اختلاف را به هندسه
    # نسبت می‌دهد در حالی که از سوگیریِ انتخاب آمده.
    mirrored = 0
    if opened:
        try:
            mirrored = paper.mirror_geo_arm()
        except Exception:                            # noqa: BLE001
            mirrored = 0
    return {"opened": opened, "seen": seen, "cap": cap, "mirrored": mirrored}


# ── داور ────────────────────────────────────────────────────────────────
def _net(r):
    if r.get("R") is None:
        return None
    fee = r.get("fee_r")
    return r["R"] - (fee if fee is not None else 0.0)


def _ci(xs, z=Z):
    n = len(xs)
    if n < 2:
        return None, None
    m = statistics.fmean(xs)
    sd = statistics.pstdev(xs)
    h = z * sd / math.sqrt(n)
    return round(m - h, 4), round(m + h, 4)


def _need(xs, z=Z):
    n = len(xs)
    if n < 20:
        return None
    sd = statistics.pstdev(xs)
    want = int(math.ceil((z * sd / HALF_WIDTH_TARGET) ** 2))
    return max(0, want - n)


def _welch(a, b, z=Z):
    """اختلاف میانگین دو گروه مستقل (بازو − پایه) با CI ولش."""
    if len(a) < 2 or len(b) < 2:
        return None, (None, None)
    ma, mb = statistics.fmean(a), statistics.fmean(b)
    va, vb = statistics.pvariance(a), statistics.pvariance(b)
    se = math.sqrt(va / len(a) + vb / len(b))
    d = ma - mb
    return round(d, 4), (round(d - z * se, 4), round(d + z * se, 4))


def _verdict(lo, hi, n, need):
    if lo is not None and lo > 0 and n >= N_PROMOTE:
        return "PROMOTE", f"CI خالص بالای صفر روی n={n} ≥ {N_PROMOTE} — فقط پیشنهاد، تأیید حمید لازم"
    if hi is not None and hi < 0 and n >= N_REJECT:
        return "REJECT", f"CI خالص زیر صفر روی n={n} ≥ {N_REJECT}"
    if need is not None:
        return "UNDECIDED", f"n={n}؛ برآورد ~{need} نمونهٔ دیگر تا نیم‌پهنای {HALF_WIDTH_TARGET}R"
    return "UNDECIDED", f"n={n} — هنوز برای برآورد هم کم است"


def _paired(base, arm_rows):
    """اختلاف جفتیِ خالص روی کلید (نماد، ورود، لحظهٔ باز شدن)."""
    diffs = []
    for k, arm in arm_rows.items():
        b = base.get(k)
        if not b or b.get("outcome") == "expired" or arm.get("outcome") == "expired":
            continue
        nb, na = _net(b), _net(arm)
        if nb is None or na is None:
            continue
        diffs.append(na - nb)
    return diffs


def study(rows=None):
    from hamid import paper
    rows = paper._read(paper.CLOSED) if rows is None else rows
    base5, tf15, geo, tf15x2 = {}, [], {}, {}
    tf15_by_key = {}
    for r in rows:
        st = (r.get("why") or {}).get("stage") or ""
        k = (r.get("sym"), r.get("entry"), r.get("opened"))
        if st.startswith("sig-") and r.get("tf") == "5m" and r.get("outcome") != "expired":
            base5[k] = r
        elif st == TF15_TAG and r.get("outcome") != "expired":
            tf15.append(r)
            tf15_by_key[k] = r
        elif st == GEO_TAG:
            geo[k] = r
        elif st == TF15X2_TAG:
            tf15x2[k] = r
    # بازوی ۱ — ناجفت: بازوی ۱۵د در برابر پایهٔ ۵د از همان بازهٔ زمانی
    a = [x for x in (_net(r) for r in tf15) if x is not None]
    b = [x for x in (_net(r) for r in base5.values()
                     if (r.get("opened") or 0) >= ARM_START_MS) if x is not None]
    d, (lo, hi) = _welch(a, b)
    n1 = min(len(a), len(b))
    v1, why1 = _verdict(lo, hi, n1, _need(a) if a else None)
    arm1 = {"tag": TF15_TAG, "design": "unpaired-welch", "n_arm": len(a), "n_base": len(b),
            "mean_arm": round(statistics.fmean(a), 4) if a else None,
            "mean_base": round(statistics.fmean(b), 4) if b else None,
            "diff": d, "ci": [lo, hi], "verdict": v1, "why": why1,
            "win_arm": round(sum(x > 0 for x in a) / len(a), 3) if a else None}
    # بازوی ۲ و ۳ — جفتی: هندسهٔ ×۲ در برابر همان ستاپ، روی دو تایم‌فریم
    out = {TF15_TAG: arm1}
    for tag, base, label in ((GEO_TAG, base5, "۵د"), (TF15X2_TAG, tf15_by_key, "۱۵د")):
        arm_rows = geo if tag == GEO_TAG else tf15x2
        diffs = _paired(base, arm_rows)
        n = len(diffs)
        lo2, hi2 = _ci(diffs)
        v2, why2 = _verdict(lo2, hi2, n, _need(diffs) if diffs else None)
        out[tag] = {"tag": tag, "design": "paired", "base_tf": label, "n_pairs": n,
                    "mean_diff": round(statistics.fmean(diffs), 4) if diffs else None,
                    "ci": [lo2, hi2], "verdict": v2, "why": why2,
                    "open_mirrors": sum(1 for r in paper._read(paper.OPEN)
                                        if (r.get("why") or {}).get("stage") == tag)}
    return {"generated": int(time.time() * 1000), "panel": "لیام تریدر ۹",
            "fingerprint": fingerprint(), "arms": out,
            "stopping_rule": (f"PROMOTE = CI خالص کاملاً بالای صفر روی n≥{N_PROMOTE} (فقط پیشنهاد) · "
                              f"REJECT = CI زیر صفر روی n≥{N_REJECT} · بقیه UNDECIDED. "
                              f"Šidák برای ۳ بازو (z={Z})."),
            "boundary": ("هر سه بازو فقط پیپرند؛ هیچ دروازه، سایز یا پیامی عوض نمی‌شود. "
                         "بازوی ۱۵د ناجفت است (جمعیت ستاپ فرق دارد) و شاهد ضعیف‌تری از "
                         "دو بازوی جفتیِ هندسه است. دو بازوی هندسه یک فرضیه را روی دو "
                         "تایم‌فریم می‌سنجند: هم‌جهت بودنشان شاهد قوی‌تر است، ناهم‌جهتی "
                         "یعنی اثر به تایم‌فریم وابسته است. "
                         "پیپر سقف خوش‌بینانه است (فیل کامل، بی‌لغزش).")}


def render(s):
    L = [f"بازوهای ۱۵د / هندسه — {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime(s['generated'] / 1000))}"]
    for tag, a in s["arms"].items():
        n = a.get("n_pairs", a.get("n_arm"))
        L.append(f"  {tag}: {a['verdict']} · n={n} · اختلاف {a.get('mean_diff', a.get('diff'))} · "
                 f"CI {a['ci']} — {a['why']}")
    return "\n".join(L)


def main(argv=()):
    s = study()
    if "--json" in argv:
        print(json.dumps(s, ensure_ascii=False, indent=1))
    else:
        print(render(s))
    if "--write" in argv:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
