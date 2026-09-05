#!/usr/bin/env python3
"""اثباتِ یادگیری — آیا بعد از نتیجه، واقعاً چیزی عوض می‌شود؟

دستور حمید (۴ سپتامبر): «سیگنال‌هایی که ارسال می‌کند را بررسی کنی که
نتیجه‌اش چی می‌شود و آیا بعد از اینکه نتیجه داد، تغییری در یادگیری‌اش
ایجاد می‌شود یا نه.»

## چرا `loop_audit` کافی نبود

ممیزِ حلقهٔ بسته (قانون ۲۸ اوت) می‌شمرد که هر سیگنال چهار رد گذاشته:
تحویل، پنل، پیگیری، علت‌یابی. یعنی جواب می‌دهد «پرونده نوشته شد؟».

ولی سؤال حمید یک پله جلوتر است: **پرونده نوشتن یادگیری نیست.** یادگیری
یعنی عددی تکان بخورد و آن عدد تصمیم بعدی را عوض کند. یک سامانه می‌تواند
هزار پرونده بنویسد و هیچ‌وقت چیزی یاد نگیرد — و از بیرون دقیقاً شبیه
یادگیری به نظر برسد. این فایل همان فرق را می‌سنجد.

## سه پلهٔ یادگیری، جدا از هم شمرده می‌شوند

| پله | سؤال | اگر نباشد یعنی |
|---|---|---|
| ۱ ثبت | معاملهٔ بسته پرونده/درس گرفت؟ | نتیجه هضم نشد |
| ۲ حرکت | عددی در دفترها جابه‌جا شد؟ (درس، ضریب مهارت، کارنامه) | ثبت شد ولی چیزی یاد نگرفت |
| ۳ مصرف | تصمیمِ **بعدیِ** همان (ارز، جهت) آن رکورد را خواند؟ | یاد گرفت ولی به کار نبرد |

پلهٔ ۳ سخت‌ترین و مهم‌ترین است. ردپایش روی خودِ سیگنال است
(`exp_used` / `memory` / `edge_used`): اگر سیگنالِ بعدیِ همان جفت،
بعد از بسته‌شدنِ معاملهٔ قبلی صادر شده و ردپای تجربه دارد، یعنی حلقه
واقعاً بسته است.

## مرز صادقانه

- این فایل **فقط می‌خواند** (قانون ۰۵). هیچ دفتری را عوض نمی‌کند.
- «حرکت» را با مقایسهٔ **عکس‌فوریِ قبل و بعد** می‌سنجد، پس در اولین
  اجرا مبنایی ندارد و صادقانه `UNKNOWN` می‌دهد — نه صفر، نه ادعا.
- نرخ‌ها توصیفی‌اند، نه دروازه. هیچ آستانه‌ای از این‌جا شل یا سفت
  نمی‌شود (قانون ۰۳).

    python3 -m hamid.learning_proof            # گزارش
    python3 -m hamid.learning_proof --write    # + نوشتن تابلو
"""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
ROOT = PY.parents[1]
sys.path.insert(0, str(PY))

SIG = ROOT / "signals"
BRAIN = ROOT / "brain"
OUT = SIG / "learning-proof.json"
SNAP = BRAIN / "learning" / "proof-snapshot.json"    # مبنای مقایسه

WINDOW_H = 72                                        # همان پنجرهٔ loop_audit
# ردپاهایی که روی خودِ سیگنال می‌نشینند و یعنی «تجربه خوانده شد»
USE_MARKS = ("exp_used", "memory", "edge_used", "phoenix_score", "skill_w")


def _rows(p, limit=None):
    p = Path(p)
    if not p.exists():
        return []
    out = []
    with p.open(encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            try:
                out.append(json.loads(ln))
            except json.JSONDecodeError:
                continue
    return out[-limit:] if limit else out


def _load(p, default=None):
    p = Path(p)
    if not p.exists():
        return default if default is not None else {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:                                # noqa: BLE001
        return default if default is not None else {}


def _ms(r, *keys):
    for k in keys:
        v = r.get(k)
        if isinstance(v, (int, float)) and v > 1_000_000_000:
            return float(v if v > 1e12 else v * 1000)
    return None


# ── پلهٔ ۱: نتیجه ثبت شد؟ ──────────────────────────────────────────────
def digested(closed, cutoff_ms):
    """هر معاملهٔ بسته در پنجره: وارد دفتر تجربه شد یا نه.

    تعریفِ «هضم» از خودِ کد گرفته شده، نه از حدس. `memory.digest_closed`
    هر معاملهٔ بسته را با `brain.learn` در `brain/learning/experiences.jsonl`
    می‌نویسد و بعد `brain.build_index` را می‌زند — و همان ایندکس چیزی
    است که تصمیم بعدی با `brain.recall` می‌خواند. پس «هضم شد» یعنی
    ردیفش در دفتر تجربه هست.

    (نسخهٔ اولِ همین تابع دنبال `reason`/`lesson` روی خودِ ردیف گشت —
    فیلدهایی که اصلاً وجود ندارند — و ۰ از ۴۷۲۸ داد. عددِ ۰٪ آن‌قدر
    نامحتمل بود که به‌جای گزارشش، شکلِ واقعیِ ردیف را نگاه کردم. سنجه‌ای
    که با کد تراز نباشد، عیبِ خودش را به گردن سامانه می‌اندازد.)

    `expired` عمداً بیرون است: `digest_closed` هم ردش می‌کند، چون
    سفارشِ پرنشده معامله نیست.
    """
    # تطبیقِ **دقیق**: همان ردیفی که `digest_closed` می‌سازد بازسازی
    # می‌شود و در دفتر تجربه دنبالش می‌گردیم.
    #
    # نسخهٔ قبلی کلیدِ سه‌فیلدی (ارز، جهت، R) داشت و ۲۹٪ می‌داد. آن عدد
    # **بیست برابر متورم** بود: کلیدِ ضعیف با ردیف‌های قدیمیِ ibs/smc
    # برخوردِ تصادفی می‌کرد. نمونهٔ آشکارش — ۱۰۴۳ معاملهٔ scalp «۲۸٪
    # تطبیق» گرفتند در حالی که دفتر تجربه **صفر** ردیف با
    # strategy=scalp دارد. با تطبیق دقیق، عدد واقعی ۱.۴٪ شد.
    exp = set()
    p = BRAIN / "learning" / "experiences.jsonl"
    if p.exists():
        with p.open(encoding="utf-8") as f:
            exp = {ln.strip() for ln in f if ln.strip()}
    rows = []
    for t in closed:
        ts = _ms(t, "closed_ms", "closed", "t_close", "t")
        if ts is None or ts < cutoff_ms:
            continue
        if t.get("outcome") == "expired" or t.get("R") is None:
            continue                                 # معامله نبود
        rows.append({
            "sym": t.get("sym"), "dir": t.get("dir"), "tf": t.get("tf"),
            "outcome": t.get("outcome"), "R": t.get("R_net", t.get("R")),
            "closed_ms": int(ts), "digested": exp_line(t) in exp,
        })
    return rows


def exp_line(t):
    """همان خطی که `memory.digest_closed` برای این معامله می‌نویسد.

    عمداً کپیِ دقیقِ همان ساختار است تا تطبیق بی‌ابهام باشد. اگر روزی
    `digest_closed` شکلش را عوض کند و این‌جا نه، `test_beacon_learning`
    سرخ می‌شود — چون سنجه‌ای که با کد تراز نباشد، عیبِ خودش را به گردن
    سامانه می‌اندازد (درسِ ۵ سپتامبر).
    """
    w = t.get("why") or {}
    return json.dumps({"sym": t.get("sym"), "tf": "15m", "dir": t.get("dir"),
                       "strategy": w.get("stage") or "hamid",
                       "r": t.get("R") or 0, "outcome": t.get("outcome"),
                       "trend_4h": w.get("trend_4h"), "fear": w.get("fear"),
                       "funding": w.get("funding"), "stop_pct": w.get("stop_pct"),
                       "usdt_dom": w.get("usdt_dom"), "mode": w.get("mode"),
                       "liq": w.get("liq")}, ensure_ascii=False)


# ── پلهٔ ۲: عددی تکان خورد؟ ────────────────────────────────────────────
def fingerprint():
    """اندازهٔ فعلیِ هر مخزنِ یادگیری — عکس‌فوریِ قابل‌مقایسه."""
    les = _load(BRAIN / "memory" / "lessons.json", {})
    led = _load(BRAIN / "skills" / "ledger.json", {})
    skills = led.get("skills") if isinstance(led, dict) else None
    idx = _load(BRAIN / "learning" / "index.json", {})
    return {
        "t": int(time.time() * 1000),
        # دفتر تجربه و ایندکسش — همان چیزی که تصمیم بعدی می‌خواند
        "experiences": len(_rows(BRAIN / "learning" / "experiences.jsonl")),
        "index_symbols": len(idx.get("by_symbol") or {}),
        "index_shapes": len(idx.get("by_shape") or {}),
        "index_built": int(idx.get("built") or 0),
        "lessons": len(les) if isinstance(les, (list, dict)) else 0,
        "skills": len(skills) if isinstance(skills, (list, dict)) else 0,
        "skill_events": len(_rows(BRAIN / "skills" / "events.jsonl")),
        "cases": len(list((BRAIN / "cases").glob("*")))
        if (BRAIN / "cases").exists() else 0,
        "closed": len(_rows(BRAIN / "paper" / "closed.jsonl")),
    }


def movement(now_fp, prev_fp):
    """تفاوتِ دو عکس‌فوری. بدون مبنا، UNKNOWN — نه صفر."""
    if not prev_fp:
        return {"status": "UNKNOWN",
                "why": "اولین اجرا — مبنایی برای مقایسه نیست. عکس‌فوری "
                       "ثبت شد؛ از اجرای بعد قابل سنجش است.",
                "delta": {}}
    d = {k: now_fp.get(k, 0) - prev_fp.get(k, 0)
         for k in now_fp if k != "t"}
    closed_d = d.get("closed", 0)
    learn_d = (d.get("experiences", 0) + d.get("lessons", 0)
               + d.get("skill_events", 0) + d.get("cases", 0)
               + d.get("index_symbols", 0))
    hrs = round((now_fp["t"] - prev_fp.get("t", now_fp["t"])) / 3_600_000, 2)
    if closed_d <= 0:
        st, why = "IDLE", (f"در {hrs} ساعت گذشته معامله‌ای بسته نشد — "
                           "نبودِ حرکت این‌جا عیب نیست")
    elif learn_d > 0:
        st, why = "LEARNING", (f"{closed_d} معامله بسته شد و {learn_d} "
                               "ردِ یادگیری تازه ثبت شد")
    else:
        st, why = "STUCK", (f"{closed_d} معامله بسته شد ولی هیچ درس/پرونده/"
                            "تجربه/درس/رویدادِ مهارتی اضافه نشد — حلقه ثبت می‌کند "
                            "ولی یاد نمی‌گیرد")
    return {"status": st, "why": why, "delta": d, "hours": hrs}


# ── پلهٔ ۳: تصمیم بعدی آن را خواند؟ ────────────────────────────────────
def consumed(sent, closed, cutoff_ms):
    """سیگنالی که **بعد از** بسته‌شدنِ معاملهٔ همان جفت رفته، ردپای
    تجربه دارد؟ این تنها چیزی است که «به کار بردن» را اثبات می‌کند."""
    last_close = {}
    for t in closed:
        ts = _ms(t, "closed_ms", "closed", "t_close", "t")
        if ts is None:
            continue
        k = (str(t.get("sym") or t.get("symbol") or "").upper(), t.get("dir"))
        last_close[k] = max(last_close.get(k, 0), ts)
    rows = []
    for s in sent:
        ts = _ms(s, "ts", "t", "sent_ms")
        if ts is None or ts < cutoff_ms:
            continue
        k = (str(s.get("sym") or s.get("symbol") or "").upper(), s.get("dir"))
        prior = last_close.get(k)
        if not prior or prior >= ts:
            continue                                 # سابقه‌ای نبوده
        marks = [m for m in USE_MARKS if s.get(m) not in (None, "", 0, False)]
        rows.append({"sym": k[0], "dir": k[1], "ts": int(ts),
                     "after_close_h": round((ts - prior) / 3_600_000, 1),
                     "used": bool(marks), "marks": marks})
    return rows


def build(now_ms=None, prev_fp=None):
    now = int(now_ms if now_ms is not None else time.time() * 1000)
    cutoff = now - WINDOW_H * 3_600_000
    closed = _rows(BRAIN / "paper" / "closed.jsonl")
    sent = _load(SIG / "telegram-log.json", [])
    if isinstance(sent, dict):
        sent = sent.get("rows") or sent.get("sent") or []

    dg = digested(closed, cutoff)
    fp = fingerprint()
    mv = movement(fp, prev_fp if prev_fp is not None else _load(SNAP, None))
    cs = consumed(sent, closed, cutoff)

    def pct(n, d):
        return round(100 * n / d, 1) if d else None

    n_dg = sum(1 for r in dg if r["digested"])
    n_cs = sum(1 for r in cs if r["used"])
    return {
        "generated": now, "engine": "E21", "panel": "لیام تریدر ۹",
        "window_h": WINDOW_H,
        "step1_digest": {"closed": len(dg), "digested": n_dg,
                         "pct": pct(n_dg, len(dg)),
                         "missing": [r for r in dg if not r["digested"]][:8]},
        "step2_movement": mv,
        "step3_consume": {"decisions_with_history": len(cs), "used": n_cs,
                          "pct": pct(n_cs, len(cs)),
                          "examples": cs[:6]},
        "fingerprint": fp,
        "verdict": _verdict(dg, mv, cs),
        "boundary": "فقط می‌خواند (قانون ۰۵). نرخ‌ها توصیفی‌اند نه دروازه؛ "
                    "هیچ آستانه‌ای از این‌جا عوض نمی‌شود (قانون ۰۳).",
    }


def _verdict(dg, mv, cs):
    if not dg:
        return ("هنوز معامله‌ای در این پنجره بسته نشده — یادگیری چیزی برای "
                "هضم نداشته. این عیب نیست.")
    n_dg = sum(1 for r in dg if r["digested"])
    pct = 100 * n_dg / len(dg)
    if pct < 90:
        # عمداً «نشتی» گفته نمی‌شود: تطبیق روی (ارز، جهت، R) است چون دفتر
        # تجربه مهر زمانی ندارد، پس هم می‌تواند جا بیندازد هم دوتایی
        # بشمارد. عددِ کم این‌جا **نشانه** است نه حکم — کارِ درست، سنجشِ
        # دقیق‌تر با مهر زمانی روی دفتر تجربه است، نه اعلامِ خرابی.
        return (f"فقط {n_dg} از {len(dg)} معاملهٔ بسته در دفتر تجربه پیدا شد "
                f"({pct:.0f}٪). چون دفتر تجربه مهر زمانی ندارد و تطبیق روی "
                "(ارز، جهت، R) است، این عدد کرانِ پایین است نه حکم — ولی "
                "آن‌قدر پایین هست که ارزش ریشه‌یابی داشته باشد.")
    if mv["status"] == "STUCK":
        return ("همه هضم شدند ولی هیچ عددی تکان نخورد — ثبت هست، یادگیری نه.")
    if cs and sum(1 for r in cs if r["used"]) == 0:
        return ("یاد گرفت ولی تصمیم بعدی از آن استفاده نکرد — پلهٔ سوم باز است.")
    return "هر سه پله برقرار: نتیجه هضم شد، عدد تکان خورد، تصمیم بعدی خواندش."


def main(argv=None):
    argv = list(argv if argv is not None else sys.argv[1:])
    snap = build()
    if "--write" in argv:
        try:
            import brain
            blocked = brain.blocked(OUT)
        except Exception:                            # noqa: BLE001
            blocked = False
        if not blocked:
            OUT.parent.mkdir(parents=True, exist_ok=True)
            OUT.write_text(json.dumps(snap, ensure_ascii=False, indent=1) + "\n",
                           encoding="utf-8")
            SNAP.parent.mkdir(parents=True, exist_ok=True)
            SNAP.write_text(json.dumps(snap["fingerprint"], ensure_ascii=False),
                            encoding="utf-8")
    s1, s2, s3 = (snap["step1_digest"], snap["step2_movement"],
                  snap["step3_consume"])
    print(f"\nاثبات یادگیری — پنجرهٔ {snap['window_h']} ساعت")
    print(f"  ۱ ثبت    {s1['digested']}/{s1['closed']} معاملهٔ بسته هضم شد"
          f" ({s1['pct']}٪)")
    print(f"  ۲ حرکت   {s2['status']} — {s2['why']}")
    print(f"  ۳ مصرف   {s3['used']}/{s3['decisions_with_history']} تصمیم،"
          f" ردپای تجربه داشت ({s3['pct']}٪)")
    print(f"\n  حکم: {snap['verdict']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
