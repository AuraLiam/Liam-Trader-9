#!/usr/bin/env python3
"""دفترِ ضدواقعیتِ دروازهٔ روند — «وتو پول نجات داد یا سوزاند؟»

دستور حمید (۶ سپتامبر): «همون دفتر ضدواقعیت دروازه روند رو بساز.»

## چرا لازم شد

شکایت حمید این بود که سیگنال شورت پیدا نمی‌شود. سه ممیزی مستقل مکانیزم را
پیدا کردند و همه به یک جای خالی رسیدند: **دروازهٔ روند خودش را نمره
نمی‌داد.** دفتر `vetoed` فقط بازجویی (`premortem`) را ثبت می‌کرد —
۲٬۹۸۵ ردیف در برابر **صفر** ردیف از دروازهٔ روند. یعنی قاعده‌ای که
بیشترین شورت را می‌کشد، تنها قاعده‌ای بود که هیچ کارنامه‌ای نداشت.

اصلِ نقض‌شده در قانون ۰۳/۱۲ نوشته است: هیچ دروازه‌ای بی‌سنجش تنظیم
نمی‌شود. بدون این دفتر، هر بحثی دربارهٔ «دروازه سخت‌گیر است» یا «درست
عمل می‌کند» حدس بود، نه اندازه‌گیری.

## چه چیزی می‌سنجد

`telegram.send_signals` هنگام وتوی روند همان ستاپ را با
`stage_tag="gate-vetoed"` در دفتر کاغذی باز می‌کند — بدون هیچ تغییری در
رفتار: سیگنال همچنان نمی‌رود. `paper.mark` آن را با کندل واقعی می‌بندد.
این‌جا آن ردیف‌ها خوانده و داوری می‌شوند:

- **R ناخالص** — آیا ستاپِ وتوشده اصلاً حرکت درست را می‌کرد؟
- **R خالص** — با کارمزدِ منبع واحد (`hamid/fees.py`)، چون تصمیمِ واقعی
  خالص است نه ناخالص.
- **برش بر جهت** — سؤال اصلی حمید: آیا وتو روی شورت‌ها بیشتر خرج دارد؟
- **برش بر نوع وتو** — «وتوی مطلقِ دو-تایم» در برابر «تأییدِ ناقصِ
  یک-تایم». این دو قاعدهٔ متفاوت‌اند و باید جدا نمره بگیرند.

## مرزی که این ماژول از آن رد نمی‌شود

فقط می‌خواند و داوری می‌کند. هیچ آستانه‌ای را عوض نمی‌کند و هیچ دروازه‌ای
را شل نمی‌کند. حکم `LOOSEN_CANDIDATE` یعنی «شواهد جمع شد، حمید تصمیم
بگیرد» — نه اجرا. ورود هر تغییری به تولید فقط از مسیر قانون ۰۳.

**حکم‌ها**

| حکم | شرط |
|---|---|
| `GATE_PAYS` | CI95 خالصِ وتوشده‌ها کاملاً **زیر** صفر با n≥۱۵۰ — یعنی وتو ضرر را جلو گرفت |
| `LOOSEN_CANDIDATE` | CI95 خالص کاملاً **بالای** صفر با n≥۱۵۰ — وتو پولِ روی میز را رد کرد |
| `UNDECIDED` | بقیه — با برآوردِ «چند نمونهٔ دیگر لازم است» |

آستانهٔ n=۱۵۰ از پیش ثبت شده تا بعداً به دلخواه جابه‌جا نشود (همان قاعدهٔ
`scalp_verdict`: قاعدهٔ توقف قبل از دیدنِ نتیجه نوشته می‌شود).

    python3 -m hamid.gate_verdict            # گزارش
    python3 -m hamid.gate_verdict --write    # + signals/gate-verdict.json
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
OUT = ROOT / "signals" / "gate-verdict.json"

# دو جمعیتِ **جدا** — هرگز جمع نمی‌شوند (دستور حمید، ۶ سپتامبر).
#   delivery — ستاپی که تا گلوگاه ارسال رفت و فقط دروازهٔ روند نگذاشت.
#              ضدواقعِ تمیز: «سیگنالی که می‌رفت».
#   stage    — ستاپی که در مرحلهٔ انتشار تنزل خورد. پرحجم‌تر و سریع‌تر پر
#              می‌شود، ولی از دروازه‌های پایین‌دست رد نشده؛ پس حکمش
#              دربارهٔ «انتشار» است نه «ارسال».
# پول‌کردنشان حکمی می‌سازد که معلوم نیست دربارهٔ چیست — به‌عمد جدا ماندند.
STAGES = {"delivery": "gate-vetoed", "stage": "stage-vetoed"}
STAGE = STAGES["delivery"]
MIN_N = 150                    # قاعدهٔ توقف، از پیش ثبت‌شده
HALF_WIDTH_TARGET = 0.10       # برای برآوردِ «چند نمونهٔ دیگر»


def _fee_r(row):
    """کارمزد بر حسب R از منبع واحد — نه عددِ ذخیره‌شده.

    عددِ `fee_r` روی دفتر فقط ~۴۹٪ ردیف‌ها هست و زیرنمونه‌اش سوگیری دارد؛
    سنجه‌ای که از آن بخواند می‌تواند علامتِ نتیجه را برگرداند (درسِ
    ۶ سپتامبر — همان چیزی که یک بار «اثر مثبت» کاذب ساخت).
    """
    try:
        from hamid import fees
        return fees.cost_in_r(row["entry"], row["sl"])
    except Exception:                                # noqa: BLE001
        try:
            stop = abs(row["entry"] - row["sl"]) / row["entry"] * 100
            return 0.15 / stop if stop > 0 else None
        except Exception:                            # noqa: BLE001
            return None


def rows(path=None, stage=None):
    """ردیف‌های بستهٔ ضدواقعِ یک جمعیت، یکتا بر هویت معامله."""
    want = stage or STAGE
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
        w = r.get("why") or {}
        if (w.get("stage") or r.get("stage_tag")) != want:
            continue
        if r.get("outcome") in ("expired", "no_fill", None):
            continue
        R = r.get("R")
        if not isinstance(R, (int, float)):
            continue
        # یکتایی پیش از هر CI (تصحیح ۲۴ اوت): بازهٔ اطمینان فرض می‌کند هر
        # ردیف یک مشاهدهٔ مستقل است؛ تکرار، CI را ساختگی تنگ می‌کند.
        ident = (r.get("sym"), r.get("dir"), r.get("entry"), r.get("opened"))
        if ident in seen:
            continue
        seen.add(ident)
        fee = _fee_r(r)
        out.append({**r, "_gross": float(R),
                    "_fee": fee,
                    "_net": (float(R) - fee) if fee is not None else None,
                    "_why": w})
    return out


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


def _need(vals):
    """چند نمونهٔ دیگر تا **هم** کف نمونه **هم** نیم‌پهنای هدف.

    کف نمونه جدا از پهنای CI است و هر دو باید برآورده شوند: نمونه‌ای که
    اتفاقاً پراکندگی کمی دارد می‌تواند CI تنگ بدهد در حالی که هنوز
    زیر قاعدهٔ توقف است. (این را خودِ آزمون گرفت: با ۲۰ ردیفِ هم‌مقدار،
    انحراف معیار صفر شد و برآورد گفت «چیزی لازم نیست» — در حالی که
    ۱۳۰ نمونه تا کف باقی بود.)
    """
    n = len(vals)
    if n < 2:
        return None
    sd = statistics.stdev(vals)
    by_width = math.ceil((1.96 * sd / HALF_WIDTH_TARGET) ** 2)
    return max(0, MIN_N - n, by_width - n)


def judge(path=None, now_ms=None, stage=None):
    rs = rows(path, stage=stage or STAGE)
    net = [r["_net"] for r in rs if r["_net"] is not None]
    gross = [r["_gross"] for r in rs]
    c_net, c_gross = _ci(net), _ci(gross)

    if c_net and c_net["n"] >= MIN_N and c_net["hi"] < 0:
        verdict, why = "GATE_PAYS", "ستاپ‌های وتوشده خالصاً ضرر بودند — وتو پول نجات داد"
    elif c_net and c_net["n"] >= MIN_N and c_net["lo"] > 0:
        verdict, why = ("LOOSEN_CANDIDATE",
                        "ستاپ‌های وتوشده خالصاً سودده بودند — دروازه پولِ روی میز را رد کرد")
    else:
        left = _need(net) if net else None
        verdict = "UNDECIDED"
        why = (f"هنوز تصمیم‌پذیر نیست — n={len(net)} از {MIN_N}"
               + (f"، حدود {left} نمونهٔ دیگر تا نیم‌پهنای ±{HALF_WIDTH_TARGET}R"
                  if left else ""))

    def slice_by(keyfn):
        buckets = {}
        for r in rs:
            k = keyfn(r)
            if k is None:
                continue
            buckets.setdefault(str(k), []).append(r)
        out = {}
        for k, v in sorted(buckets.items()):
            nv = [x["_net"] for x in v if x["_net"] is not None]
            out[k] = {"gross": _ci([x["_gross"] for x in v]), "net": _ci(nv)}
        return out

    def _mode(r):
        # «هر دو تایم مخالف» در برابر «یک تایم مخالف، تأیید ناقص» — دو
        # قاعدهٔ متفاوت‌اند و یک‌کاسه‌کردنشان جوابِ بی‌معنا می‌دهد.
        g = str((r["_why"]).get("gate_reason") or "")
        if "هر دو تایم" in g:
            return "وتوی مطلق (هر دو تایم)"
        if "خلاف روند" in g:
            return "تأیید ناقص (یک تایم)"
        return "سایر"

    return {
        "generated": int(now_ms or time.time() * 1000),
        "panel": "لیام تریدر ۹",
        "stage": stage or STAGE, "min_n": MIN_N,
        "verdict": verdict, "why": why,
        "gross": c_gross, "net": c_net,
        "by_dir": slice_by(lambda r: (r.get("dir") or "").upper() or None),
        "by_mode": slice_by(_mode),
        "by_tf": slice_by(lambda r: r.get("tf")),
        "note": ("ضدواقع است نه سیگنال: این ستاپ‌ها ارسال نشدند. حکم "
                 "مشاوره‌ای است — هیچ آستانه‌ای این‌جا عوض نمی‌شود "
                 "(قانون ۰۳/۱۲)."),
        "boundary": ("R از دفتر کاغذی است نه اجرای واقعی؛ کارمزد از منبع "
                     "واحد بازمحاسبه شد نه از fee_r ذخیره‌شده. ردیف‌ها بر "
                     "هویت معامله یکتا شده‌اند."),
    }


def render(v):
    L = [f"### دفترِ ضدواقعیتِ دروازهٔ روند — {v['verdict']}", f"  {v['why']}", ""]
    for lbl, c in (("ناخالص", v["gross"]), ("خالص ", v["net"])):
        if c:
            L.append(f"  {lbl}  n={c['n']:<5} {c['mean']:+.4f}R "
                     f"CI[{c['lo']:+.4f}, {c['hi']:+.4f}]  {c['verdict']}")
    for title, key in (("جهت", "by_dir"), ("نوع وتو", "by_mode"),
                       ("تایم‌فریم", "by_tf")):
        if v[key]:
            L.append(f"\n  — برش بر {title}")
            for k, d in v[key].items():
                n = d["net"]
                g = d["gross"]
                if not n:
                    continue
                L.append(f"    {k:<26} n={n['n']:<5} ناخالص {g['mean']:+.4f} · "
                         f"خالص {n['mean']:+.4f} CI[{n['lo']:+.4f},{n['hi']:+.4f}] "
                         f"{n['verdict']}")
    L.append(f"\n  ⚖️ {v['boundary']}")
    return "\n".join(L)


LABELS = {"delivery": "گلوگاه ارسال (ضدواقعِ تمیز)",
          "stage": "مرحلهٔ انتشار (پرحجم‌تر)"}


def judge_all(path=None, now_ms=None):
    """هر دو جمعیت، **کنار هم و جدا** — نه جمع‌شده (دستور ضد-merge)."""
    pops = {k: judge(path, now_ms, stage=st) for k, st in STAGES.items()}
    return {"generated": pops["delivery"]["generated"],
            "panel": "لیام تریدر ۹", "min_n": MIN_N,
            "populations": pops,
            # حکمِ مرجع همان ضدواقعِ تمیز است؛ برشِ مرحله شاهدِ زودرس است
            # نه جایگزین. هرگز جای هم نمی‌نشینند.
            "verdict": pops["delivery"]["verdict"],
            "note": ("دو جمعیتِ جدا: «گلوگاه ارسال» یعنی سیگنالی که واقعاً "
                     "می‌رفت و فقط دروازهٔ روند نگذاشت — حکمِ مرجع همین "
                     "است. «مرحلهٔ انتشار» سریع‌تر پر می‌شود ولی از "
                     "دروازه‌های پایین‌دست رد نشده، پس شاهدِ زودرس است. "
                     "جمعشان نکن."),
            "boundary": pops["delivery"]["boundary"]}


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    v = judge_all()
    for k, pv in v["populations"].items():
        print(f"\n══ {LABELS[k]} — stage={STAGES[k]}")
        print(render(pv))
    print(f"\n⚖️ {v['note']}")
    if "--write" in argv:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(v, ensure_ascii=False, indent=1),
                       encoding="utf-8")
        print(f"\n→ {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
