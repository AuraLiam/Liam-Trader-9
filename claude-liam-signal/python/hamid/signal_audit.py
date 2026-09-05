"""بازبینی کامل سیگنال‌های ارسالی — هر ۱۵ دقیقه (دستور حمید، ۵ سپتامبر).

حمید: «هر ۱۵ دقیقه سیگنال‌های ارسالی به تلگرام را کامل بررسی می‌کنی و بر
اساس آن می‌توانی تشخیص بدهی چه انجام بدهی و چه انجام ندهی و کجاها نیاز به
تعمیر یا سیستم جایگزین دارد.»

## چرا این ماژول لازم شد

شکاک (`hamid/skeptic.py`) از قبل محتوای سیگنال را می‌سنجید: تایم‌فریم،
استاپ/تارگت، ترتیب قیمت، RR، وتوی روند. ولی خرابی‌ای که حمید همان شب
دید از جنس دیگری بود: **هیچ سیگنالی خراب نبود؛ شمارشِ سیگنال‌ها خراب
بود.** اعلام دوساعته «۶ سیگنال، ۳ ETH و ۳ XRP» گفت در حالی که در آرشیو
ارسال یک ETH و یک XRP بود. علت: بازوهای آزمایشِ تریل همان `tg_msg_id` را
به ارث می‌برند و گزارش هر ردیف را یک سیگنال شمرد.

درسِ کلاس: **پاسبانِ محتوا، پاسبانِ حساب نیست.** یکی می‌پرسد «این سیگنال
درست بود؟»، این یکی می‌پرسد «آنچه دربارهٔ سیگنال‌ها می‌گوییم با آنچه
واقعاً فرستادیم می‌خواند؟» — و همان است که یک عددِ سه‌برابر را می‌گیرد.

## هفت بررسی، هر کدام با یک اقدام

هر یافته سه چیز دارد: شواهدِ شمرده‌شده، شدت، و **اقدام** — «تعمیر کن»،
«جایگزین لازم است»، یا «کاری نکن، این طبیعی است». بدون اقدام، یافته فقط
یک شکایت است.

## مرز

فقط می‌خواند و داوری می‌کند (قانون ۰۵). هیچ سیگنالی صادر، وتو یا اصلاح
نمی‌کند و هیچ آستانه‌ای را عوض نمی‌کند. آلارمش از دروازهٔ قانون ۰۷ رد
می‌شود و «برطرف شد» هرگز به تلگرام نمی‌رود (قانون ۱۱ بند ۳).

اجرا: `python3 -m hamid.signal_audit [--write] [--alert]`
"""
from __future__ import annotations

import glob
import json
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
sys.path.insert(0, str(PY))
ROOT = PY.parent.parent
SIG = ROOT / "signals"
OUT = SIG / "signal-audit.json"

WINDOW_H = 24            # پنجرهٔ حکم — کوتاه‌تر از این، نمونه نمی‌ماند
ALLOWED_TFS = ("5m", "15m")
MIN_RR = 0.8
PAIR_CAP_H = 3           # همان پنجرهٔ `telegram._dup_pair`
SYM_CAP_6H = 2           # همان سقف «۲ به ازای هر ارز در ۶ ساعت»


def _j(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:                                # noqa: BLE001
        return default


def archive_sent(now_ms, hours=WINDOW_H):
    """آنچه **واقعاً** فرستاده شد — از آرشیو شماره‌دار append-only.

    آرشیو مرجع است نه `telegram-log.json`، چون لاگ فقط ۴۰ ردیف آخر را
    نگه می‌دارد و پنجرهٔ ۲۴ ساعت می‌تواند از آن بلندتر باشد.
    """
    lo = now_ms - hours * 3600 * 1000
    rows = []
    for f in glob.glob(str(SIG / "archive" / "telegram-sent-*.jsonl")):
        try:
            for line in Path(f).read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except Exception:                    # noqa: BLE001
                    continue
                if isinstance(r, dict) and isinstance(r.get("at"), (int, float)) \
                        and lo <= r["at"] <= now_ms:
                    rows.append(r)
        except Exception:                            # noqa: BLE001
            continue
    rows.sort(key=lambda r: r["at"])
    return rows


def _finding(check, ok, evidence, action, sev="low", detail=""):
    return {"check": check, "ok": bool(ok), "evidence": evidence,
            "action": action, "sev": sev, "detail": detail}


# ── هفت بررسی ───────────────────────────────────────────────────────────

def c_content(sent, log_rows):
    """محتوای هر سیگنال: تایم‌فریم، استاپ/تارگت، ترتیب قیمت، RR."""
    rows = log_rows or sent
    if not rows:
        return _finding("محتوای سیگنال", True, "ارسالی در پنجره نبود",
                        "کاری نکن — سکوت با ستاپ‌نداشتن هم سازگار است")
    bad = []
    for r in rows:
        e, sl, t1 = r.get("entry"), r.get("sl"), r.get("tp1")
        d, sym = r.get("dir"), r.get("sym")
        if r.get("tf") not in ALLOWED_TFS:
            bad.append(f"{sym}: تایم‌فریم {r.get('tf')}")
        if not all(isinstance(x, (int, float)) and x > 0 for x in (e, sl, t1)):
            bad.append(f"{sym}: ورود/استاپ/تارگت ناقص")
            continue
        if d == "LONG" and not sl < e < t1:
            bad.append(f"{sym}: ترتیب قیمت لانگ")
        if d == "SHORT" and not sl > e > t1:
            bad.append(f"{sym}: ترتیب قیمت شورت")
        if e != sl and abs(t1 - e) / abs(e - sl) < MIN_RR:
            bad.append(f"{sym}: RR زیر {MIN_RR}")
    return _finding("محتوای سیگنال", not bad,
                    f"{len(bad)} خطا در {len(rows)} ارسال",
                    "تعمیر فوریِ گلوگاه ارسال — سیگنالِ بی‌استاپ/بدترتیب "
                    "نباید از قرارداد اجرا رد شود" if bad else
                    "کاری نکن — قرارداد اجرا برقرار است",
                    sev="high" if bad else "low", detail=" · ".join(bad[:5]))


def c_trend_veto(log_rows):
    """وتوی روند: هر دو تایم بالا خلاف جهت = تخلف (دستور ۱۷ اوت)."""
    if not log_rows:
        return _finding("وتوی روند", True, "ردیفی با دادهٔ روند نبود",
                        "کاری نکن")
    bad = []
    for r in log_rows:
        opp = {"LONG": "down", "SHORT": "up"}.get(r.get("dir"))
        if opp and r.get("trend4") == opp and r.get("trend1") == opp:
            bad.append(f"{r.get('sym')} {r.get('dir')}")
    return _finding("وتوی روند", not bad, f"{len(bad)} تخلف از {len(log_rows)}",
                    "تعمیر `trend_gate` — وتوی مطلق دور زده شده" if bad
                    else "کاری نکن — وتو برقرار است",
                    sev="high" if bad else "low", detail=" · ".join(bad[:5]))


def c_dedupe(sent):
    """ضدتکرار: یک جفتِ ارز-جهت در پنجرهٔ ۳ ساعت، و سقف ۲ در ۶ ساعت."""
    pair_hits, sym_hits = [], []
    by_pair, by_sym = {}, {}
    for r in sent:
        p = (r.get("sym"), r.get("dir"))
        prev = by_pair.get(p)
        if prev is not None and r["at"] - prev < PAIR_CAP_H * 3600 * 1000:
            pair_hits.append(f"{p[0]} {p[1]}")
        by_pair[p] = r["at"]
        by_sym.setdefault(r.get("sym"), []).append(r["at"])
    for sym, ts in by_sym.items():
        for i, t in enumerate(ts):
            n6 = sum(1 for u in ts if 0 <= t - u < 6 * 3600 * 1000)
            if n6 > SYM_CAP_6H:
                sym_hits.append(f"{sym}×{n6} در ۶س")
                break
    bad = pair_hits + sym_hits
    return _finding("ضدتکرار ارسال", not bad,
                    f"{len(bad)} نقض در {len(sent)} ارسال",
                    "تعمیر حافظهٔ ضدتکرار — همان کلاسِ PAXG×۵" if bad
                    else "کاری نکن — ضدتکرار برقرار است",
                    sev="high" if bad else "low",
                    detail=" · ".join(dict.fromkeys(bad))[:200])


def c_count_truth(sent, closed):
    """حسابِ سیگنال: پیام یکتا در برابر ردیفِ دفتر که شناسه دارد.

    همان چیزی که ۵ سپتامبر از دست رفت — و تنها بررسی‌ای که می‌گرفتش.
    """
    from hamid import paper as _p
    mids, mids_grade = Counter(), set()
    for t in closed:
        w = t.get("why") or {}
        m = w.get("tg_msg_id")
        if not m:
            continue
        mids[m] += 1
        if (w.get("stage") or "") not in _p._NOT_SIGNAL:
            mids_grade.add(m)
    rows = sum(mids.values())
    graded = len(_p.sent_signals(closed))
    # ملاک درست: شمارنده باید دقیقاً یک ردیف به ازای هر پیامی بدهد که
    # ردیفِ سیگنال‌گرید دارد. پیامی که فقط بازوی آزمایشش بسته شده (ردیف
    # واقعی‌اش هنوز باز است) نباید «کم‌شماری» تلقی شود — نبودش درست است.
    ok = graded == len(mids_grade)
    infl = rows / graded if graded else 1.0
    return _finding("حسابِ سیگنال (پیام یکتا در برابر ردیف)", ok,
                    f"{len(mids)} پیام یکتا · {rows} ردیف شناسه‌دار · "
                    f"{graded} سیگنال‌گرید (تورمِ خام {infl:.1f}×)",
                    "تعمیر شمارنده — هر گزارشی که ردیف را سیگنال بشمارد "
                    "عدد را باددار می‌کند (بازوهای آزمایش شناسه را ارث "
                    "می‌برند)" if not ok else
                    (f"کاری نکن — شمارنده {rows - graded} ردیفِ بازو را "
                     "جدا نگه داشت" if rows > graded else
                     "کاری نکن — شمارش با آرشیو می‌خواند"),
                    sev="high" if not ok else "low",
                    detail=f"{len(mids) - len(mids_grade)} پیام فقط بازوی "
                           "بسته دارد (ردیف واقعی هنوز باز است)")


def c_ledger_match(sent, closed, open_rows):
    """هر ارسال باید ردپای دفتر داشته باشد — وگرنه نتیجه‌اش گم می‌شود."""
    ids_sent = {r.get("tg_msg_id") for r in sent if r.get("tg_msg_id")}
    if not ids_sent:
        return _finding("پیوند ارسال↔دفتر", True, "ارسالی با شناسه نبود",
                        "کاری نکن")
    ids_book = {(t.get("why") or {}).get("tg_msg_id")
                for t in (list(closed) + list(open_rows))}
    orphan = ids_sent - ids_book
    return _finding("پیوند ارسال↔دفتر", not orphan,
                    f"{len(orphan)} ارسال بی‌ردیف از {len(ids_sent)}",
                    "تعمیر `paper.open_from` — سیگنالی که ردیف دفتر ندارد "
                    "هرگز نتیجه نمی‌گیرد و ریپلای نتیجه هم نمی‌خورد"
                    if orphan else "کاری نکن — هر ارسال ردپای دفتر دارد",
                    sev="high" if orphan else "low",
                    detail=" · ".join(str(x) for x in list(orphan)[:6]))


def c_stuck(sent, open_rows, now_ms):
    """ارسالی که خیلی وقت است باز مانده — نه استاپ، نه تارگت."""
    ids_sent = {r.get("tg_msg_id") for r in sent if r.get("tg_msg_id")}
    stuck = [t for t in open_rows
             if (t.get("why") or {}).get("tg_msg_id") in ids_sent
             and isinstance(t.get("filled"), (int, float))
             and now_ms - t["filled"] > 12 * 3600 * 1000]
    return _finding("پوزیشنِ معلق", len(stuck) < 3,
                    f"{len(stuck)} ارسالِ پرشدهٔ ۱۲+ ساعت بی‌نتیجه",
                    "بررسی چرخش بین دو اردر بلاک مخالف — قاعدهٔ "
                    "NO_TRADE_ROTATION؛ سیستم جایگزین لازم نیست، سقف "
                    "نگهداری لازم است" if len(stuck) >= 3 else
                    "کاری نکن — پوزیشن معلقِ معنادار نیست",
                    sev="medium" if len(stuck) >= 3 else "low")


def c_direction_bias(sent):
    """همه‌لانگ/همه‌شورت بودن: یا رژیم است یا سوگیریِ موتور."""
    if len(sent) < 8:
        return _finding("توازن جهت", True, f"{len(sent)} ارسال — نمونه کم",
                        "کاری نکن — زیر ۸ ارسال حکم نمی‌دهیم")
    c = Counter(r.get("dir") for r in sent)
    top, n = c.most_common(1)[0]
    share = n / len(sent)
    return _finding("توازن جهت", share <= 0.9,
                    f"{top} {n} از {len(sent)} ({share:.0%})",
                    "با دامیننس و روند BTC تطبیق بده — اگر بستر هم‌جهت "
                    "است این رژیم است نه عیب؛ اگر نیست، سوگیریِ موتور را "
                    "بسنج" if share > 0.9 else "کاری نکن — توازن طبیعی است",
                    sev="medium" if share > 0.9 else "low")


def c_repeat_expired(sent, closed_all):
    """همان ستاپِ منقضی، دوباره فرستاده شده؟

    یافتهٔ ۵ سپتامبر: `LOKAUSDT` از ۲۳ اوت **نُه بار** سیگنال شد، هر بار
    با ورودِ **دقیقاً یکسان ۰.۱۲۳۶**، و هر بار `expired` — یعنی قیمت
    هرگز به ورود نرسید. ضدتکرارِ موجود این را نمی‌گیرد چون پنجره‌هایش
    ۳ و ۶ ساعت است و این ارسال‌ها ۱۴+ ساعت فاصله دارند.

    ستاپی که بارها منقضی شده یعنی ورودش از بازار دور است؛ فرستادنِ
    دوباره‌اش نه سیگنال است نه ضرر — ولی اعتماد را می‌خورد و سقف روزانه
    را اشغال می‌کند.

    **این بررسی دروازه نیست** (قانون ۰۳): فقط می‌شمارد و اقدام پیشنهاد
    می‌دهد. ورودش به دروازه فقط با CI بالای صفر و تأیید حمید.
    """
    exp = {}
    for t in closed_all:
        if t.get("outcome") != "expired":
            continue
        e = t.get("entry")
        if isinstance(e, (int, float)):
            exp.setdefault((t.get("sym"), round(float(e), 10)), 0)
            exp[(t.get("sym"), round(float(e), 10))] += 1
    hits = []
    for r in sent:
        k = (r.get("sym"), round(float(r["entry"]), 10)) if isinstance(
            r.get("entry"), (int, float)) else None
        if k and exp.get(k, 0) >= 2:
            hits.append(f"{k[0]} @ {k[1]} (قبلاً {exp[k]}× منقضی)")
    hits = list(dict.fromkeys(hits))
    return _finding("ستاپِ تکرارشوندهٔ منقضی", not hits,
                    f"{len(hits)} ارسال روی ورودی که قبلاً ۲+ بار منقضی شده",
                    "بررسیِ سنجش‌پذیر: ورودِ ثابتی که بارها پر نشده یعنی "
                    "ستاپ یخ‌زده است — کاندیدای دروازهٔ تازه، بعد از CI "
                    "(قانون ۰۳)" if hits else
                    "کاری نکن — ستاپ یخ‌زده‌ای دوباره نرفته",
                    sev="medium" if hits else "low",
                    detail=" · ".join(hits[:5]))


CHECKS_N = 8


def build(now_ms=None):
    now_ms = int(now_ms or time.time() * 1000)
    from hamid import paper as _p
    sent = archive_sent(now_ms)
    log_rows = [r for r in ((_j(SIG / "telegram-log.json", {}) or {}).get("sent") or [])
                if isinstance(r.get("at"), (int, float))
                and r["at"] >= now_ms - WINDOW_H * 3600 * 1000]
    lo = now_ms - WINDOW_H * 3600 * 1000
    closed_all = _p._read(_p.CLOSED)
    closed = [t for t in closed_all
              if isinstance(t.get("closed"), (int, float)) and t["closed"] >= lo]
    open_rows = _p._read(_p.OPEN)

    findings = [c_content(sent, log_rows), c_trend_veto(log_rows),
                c_dedupe(sent), c_count_truth(sent, closed),
                c_ledger_match(sent, closed, open_rows),
                c_stuck(sent, open_rows, now_ms), c_direction_bias(sent),
                c_repeat_expired(sent, closed_all)]
    bad = [f for f in findings if not f["ok"]]
    high = [f for f in bad if f["sev"] == "high"]
    verdict = "SICK" if high else ("DEGRADED" if bad else "HEALTHY")

    from hamid import evidence_packet as _ep
    graded = _p.sent_signals(closed)
    wins = [t for t in graded if (t.get("R") or 0) > 0]
    packet = _ep.build(
        claim=(f"بازبینی ۲۴ ساعت ارسال: {verdict} — "
               f"{len(bad)} یافته از {CHECKS_N} بررسی"),
        numbers={"ارسال (آرشیو)": len(sent),
                 "سیگنال‌گرید بسته": len(graded),
                 "بردِ بسته‌ها": f"{len(wins)}/{len(graded)}" if graded else "۰/۰",
                 "یافته": len(bad), "حکم": verdict},
        track_record=(f"{len(graded)} سیگنال بسته در پنجره"
                      if graded else "کارنامه: هنوز بسته‌ای در پنجره نیست"),
        scenario_up="یافته‌ها رفع شوند → گزارش‌ها با آرشیو ارسال یکی می‌شوند "
                    "و عددی که حمید می‌خواند قابل اتکا می‌ماند",
        scenario_down="یافته پابرجا بماند → عددِ گزارش از واقعیتِ ارسال جدا "
                      "می‌ماند و تصمیم روی عدد باددار گرفته می‌شود",
        invalidator="اجرای تازهٔ همین بازبینی با آرشیو به‌روز، این حکم را "
                    "باطل می‌کند",
        sources=["signals/archive/telegram-sent-*.jsonl",
                 "signals/telegram-log.json", "brain/paper/closed.jsonl"],
        limit="فقط می‌خواند و داوری می‌کند؛ هیچ سیگنالی را اصلاح یا وتو "
              "نمی‌کند و هیچ آستانه‌ای را عوض نمی‌کند (قانون ۰۵/۰۳)")
    return {"generated": now_ms, "panel": "لیام تریدر ۹", "engine": "E25",
            "window_h": WINDOW_H, "verdict": verdict,
            "n_sent": len(sent), "n_checks": CHECKS_N, "n_findings": len(bad),
            "findings": findings,
            "todo": [f["action"] for f in bad],
            "leave_alone": [f["action"] for f in findings if f["ok"]],
            "packet": packet, "packet_faults": _ep.validate(packet),
            "boundary": "بازبینی هر ۱۵ دقیقه؛ خواندنی و بی‌دخالت (قانون ۰۵)."}


def alarm_text(snap):
    bad = [f for f in snap["findings"] if not f["ok"]]
    lines = [f"🏷 {snap['panel']}", "🔎 <b>بازبینی سیگنال‌های ارسالی</b>", ""]
    for f in bad:
        lines.append(f"• {f['check']}: {f['evidence']}")
        lines.append(f"  ↳ {f['action']}")
    return "\n".join(lines)


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
            OUT.write_text(json.dumps(snap, ensure_ascii=False, indent=1),
                           encoding="utf-8")
    print(f"بازبینی سیگنال: {snap['verdict']} — {snap['n_findings']} یافته "
          f"از {snap['n_checks']} بررسی · {snap['n_sent']} ارسال در "
          f"{snap['window_h']} ساعت")
    for f in snap["findings"]:
        print(f"  {'✓' if f['ok'] else '✗'} {f['check']}: {f['evidence']}")
        if not f["ok"]:
            print(f"      ↳ {f['action']}")
    # آلارم فقط برای یافتهٔ جدی، و فقط از دروازهٔ قانون ۰۷ (بی‌تکرار).
    if "--alert" in argv and snap["verdict"] == "SICK":
        try:
            from hamid import alert_gate
            key = "|".join(sorted(f["check"] for f in snap["findings"]
                                  if not f["ok"] and f["sev"] == "high"))
            alert_gate.send("signal_audit", key, alarm_text(snap))
        except Exception as e:                       # noqa: BLE001
            print(f"آلارم بازبینی: {type(e).__name__}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
