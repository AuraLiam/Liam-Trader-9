#!/usr/bin/env python3
"""میزِ زندهٔ هر متخصص — پیپرمودِ بی‌وقفه روی جریانِ اسکن (دستور حمید، ۱۲ سپتامبر).

حمید: «هر ۱۲ متخصص باید بر اساس استراتژیشون نظر بدن و هیچ استثنایی وجود
نداره. باید بر اساس استراتژیشون پیپرمود تریدینگ بدون وقفه داشته باشند…
و باید کسب تجربه کنند.»

═══════════════════════════════════════════════════════════════════════
  شکافی که این فایل می‌بندد
═══════════════════════════════════════════════════════════════════════

تا امروز رأیِ دوازده مراقب فقط در **گلوگاه ارسال** گرفته می‌شد
(`telegram.send_signals`)، یعنی روی ستاپ‌هایی که از همهٔ دروازه‌ها رد
شده و قرار است برای حمید برود. با سقفِ روزانهٔ ۲۴ سیگنال، هر متخصص روزی
~۲۴ بار نظر می‌داد و کارنامه‌اش ماه‌ها طول می‌کشید تا نمونه‌دار شود.
اندازه‌گیری: کلِ دفترِ رأی ۱۴۰ ردیف داشت.

این میز همان رأی را روی **هر ستاپِ SIGNALِ هر چرخه** می‌گیرد — همان
جهانی که موتور واقعاً می‌سازد، ولی بدونِ محدودیتِ بودجهٔ پیام. هر مراقب
که رأیش از آستانهٔ تأیید قانون ۱۶ (‎+۰.۱۵‎) رد شود، در **دفترِ خودش** یک
معاملهٔ کاغذی باز می‌کند و `paper.mark` با کندلِ واقعی می‌بنددش.

═══════════════════════════════════════════════════════════════════════
  چهار قیدی که این را از «سیل ردیف» جدا می‌کند
═══════════════════════════════════════════════════════════════════════

۱. **فقط SIGNAL، و فقط بعد از دروازه‌ها.** ستاپی که دروازهٔ روند تنزلش
   داده باشد به این‌جا نمی‌رسد؛ یعنی جهانِ انتخاب همان چیزی است که
   واقعاً قابلِ معامله بود.
۲. **ضدتکرار روی (مراقب، نماد، جهت)** از خودِ دفترِ باز — همان الگوی
   `_stage_veto_open_keys`.
۳. **دو سقف**: هر مراقب در هر اجرا حداکثر `PER_GUARDIAN_CAP`، و کلِ اجرا
   `RUN_CAP`. بی این دو، یک چرخهٔ پرستاپ صدها ردیف می‌سازد.
۴. **هیچ ردیفی سیگنال شمرده نمی‌شود**: مرحله‌ها `gd-<id>` هستند و در
   `paper.GUARDIAN_STAGES` → `_NOT_SIGNAL` نشسته‌اند. این میز روی
   تلگرام، سقفِ روزانه، ضدتکرارِ ارسال و آمارِ محصول **هیچ اثری ندارد**.

مرزِ صادقانه: این میز می‌گوید «اگر هر متخصص تنها با رأیِ خودش از میان
همین ستاپ‌ها انتخاب می‌کرد، ته حساب چه می‌شد». نمی‌گوید آن متخصص ستاپِ
بهتری *کشف* می‌کرد — جهانِ ستاپ مشترک است و همان محدودیتِ میزِ بازپخش
این‌جا هم هست.

    python3 -m hamid.guardian_live --selftest
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
ROOT = HERE.parents[2]
VOTES = ROOT / "brain" / "guardians" / "live-votes.jsonl"

from hamid import phoenix as PH                              # noqa: E402

# آستانهٔ ورود = همان «تأیید» قانون ۱۶. از پیش ثبت‌شده، نه تنظیم‌شونده.
VOTE_MIN = 0.15
PER_GUARDIAN_CAP = 3
RUN_CAP = 24

GIDS = [g["id"] for g in PH.GUARDIANS]
FA = {g["id"]: f'{g["sign"]} {g["name"]}' for g in PH.GUARDIANS}


def stage_of(gid):
    return f"gd-{gid}"


def open_keys():
    """(مرحله، نماد، جهت)هایی که همین حالا ردیفِ باز دارند."""
    out = set()
    try:
        from hamid import paper as _p
        p = Path(_p.OPEN)
        if not p.exists():
            return out
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except Exception:                                # noqa: BLE001
                continue
            st = (r.get("why") or {}).get("stage") or r.get("stage_tag")
            if st and str(st).startswith("gd-"):
                out.add((st, r.get("sym"), (r.get("dir") or "").upper()))
    except Exception:                                        # noqa: BLE001
        pass
    return out


def _log_vote(v, sym, tf, direction, now_ms):
    """دفترِ رأیِ زنده — append-only، جدا از دفترِ ارسال (قانون ضد-merge).

    در حالت شنی (`LIAM9_SANDBOX=1`) هیچ‌چیز نوشته نمی‌شود — همان الگوی
    `paper._append_gatelog`. نسخهٔ اولِ این تابع این شرط را نداشت و
    خودآزماییِ همین فایل ۹۶ ردیفِ ساختگی (`AAAUSDT`، دلیل «آزمون») در
    دفترِ واقعی ریخت. اگر منتشر می‌شد، امتحانِ ققنوس آن‌ها را «مشارکت»
    می‌شمرد و کارنامهٔ هر دوازده مراقب مسموم می‌شد — دقیقاً همان دری که
    `test_paper` سالِ پیش برای `brain` بست، این بار از سمتِ میزِ زنده.
    """
    import brain as _b
    if getattr(_b, "SANDBOX", False):
        return
    try:
        VOTES.parent.mkdir(parents=True, exist_ok=True)
        row = {"at": int(now_ms), "sym": sym, "tf": tf, "dir": direction,
               "score": v.get("score"), "label": v.get("label"),
               "votes": {g: d.get("v") for g, d in (v.get("votes") or {}).items()},
               "why": {g: d.get("why") for g, d in (v.get("votes") or {}).items()},
               "source": "live-scan"}
        with VOTES.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:                                        # noqa: BLE001
        pass


def desk(setups, judge=None, opener=None, now_ms=None):
    """هر مراقب از میان ستاپ‌های SIGNAL، با رأیِ خودش، دفترِ خودش را باز می‌کند."""
    now_ms = now_ms or time.time() * 1000
    if judge is None:
        judge = PH.judge
    if opener is None:
        from hamid import paper as _p
        opener = _p.open_from
    seen = open_keys()
    per = {g: 0 for g in GIDS}
    total = 0
    n_setups = 0
    skipped = {"not_signal": 0, "no_geometry": 0, "dup": 0,
               "cap_guardian": 0, "cap_run": 0, "below_vote": 0,
               "abstain": 0}
    for s in setups or []:
        if (s.get("stage") or "") != "SIGNAL":
            skipped["not_signal"] += 1
            continue
        if not (s.get("entry") and s.get("sl")):
            skipped["no_geometry"] += 1
            continue
        n_setups += 1
        try:
            v = judge(s)
        except Exception:                                    # noqa: BLE001
            continue
        _log_vote(v, s.get("sym"), s.get("tf"), s.get("dir"), now_ms)
        for gid in GIDS:
            d = (v.get("votes") or {}).get(gid) or {}
            val = d.get("v")
            if val is None:
                skipped["abstain"] += 1
                continue
            if float(val) < VOTE_MIN:
                skipped["below_vote"] += 1
                continue
            if total >= RUN_CAP:
                skipped["cap_run"] += 1
                continue
            if per[gid] >= PER_GUARDIAN_CAP:
                skipped["cap_guardian"] += 1
                continue
            st = stage_of(gid)
            key = (st, s.get("sym"), (s.get("dir") or "").upper())
            if key in seen:
                skipped["dup"] += 1
                continue
            try:
                n = opener([{"symbol": s["sym"], "dir": s["dir"],
                             "entry": s["entry"], "sl": s["sl"],
                             "tp1": s.get("tp1") or s["entry"],
                             "tp2": s.get("tp2"), "stage_tag": st,
                             "tf": s.get("tf")}],
                           {"guardian": gid, "guardian_fa": FA[gid],
                            "guardian_vote": round(float(val), 3),
                            "guardian_why": str(d.get("why") or "")[:120],
                            "phoenix_score": v.get("score"),
                            "phoenix_label": v.get("label"),
                            "quality": s.get("quality"),
                            "trend_4h": s.get("trend4"),
                            "trend_1h": s.get("trend1")})
            except Exception:                                # noqa: BLE001
                n = 0
            if n:
                per[gid] += 1
                total += 1
                seen.add(key)
    return {"n_setups": n_setups, "opened": total,
            "per_guardian": {g: per[g] for g in GIDS if per[g]},
            "skipped": skipped,
            "caps": {"per_guardian": PER_GUARDIAN_CAP, "run": RUN_CAP},
            "vote_min": VOTE_MIN}


def _selftest():
    ok = fails = 0

    def chk(c, m):
        nonlocal ok, fails
        if c:
            ok += 1
        else:
            fails += 1
            print(f"  ✗ {m}")

    from hamid import paper
    # ── مرحله‌ها هرگز سیگنال شمرده نمی‌شوند ───────────────────────────
    chk(set(paper.GUARDIAN_STAGES) == {stage_of(g) for g in GIDS},
        "فهرستِ مرحله‌های میز با شورا نمی‌خواند")
    chk(all(stage_of(g) in paper._NOT_SIGNAL for g in GIDS),
        "مرحلهٔ میزِ مراقب از شمارشِ سیگنال مستثنا نیست")

    made = []

    def fake_open(rows, ctx):
        made.append((rows[0]["stage_tag"], rows[0]["symbol"], ctx["guardian"]))
        return 1

    A, B = GIDS[0], GIDS[1]

    def judge_all(s):
        # A موافقِ قوی · B زیرِ آستانه · بقیه ممتنع
        return {"score": 0.5, "label": "تأیید",
                "votes": {g: {"v": (0.9 if g == A else (0.05 if g == B else None)),
                              "w": 1, "why": "آزمون"} for g in GIDS}}

    sig = {"stage": "SIGNAL", "sym": "AAAUSDT", "dir": "LONG",
           "entry": 100.0, "sl": 99.0, "tp1": 103.0, "tf": "15m"}
    r = desk([sig], judge=judge_all, opener=fake_open)
    chk(r["opened"] == 1, f"فقط رأیِ بالای آستانه باید باز کند: {r['opened']}")
    chk(made and made[0][0] == stage_of(A), f"مرحلهٔ غلط: {made}")
    chk(r["skipped"]["below_vote"] == 1, f"زیرآستانه شمرده نشد: {r['skipped']}")
    chk(r["skipped"]["abstain"] == 10, f"ممتنع شمرده نشد: {r['skipped']}")

    # ── مرحلهٔ غیرِ SIGNAL رد می‌شود ──────────────────────────────────
    made.clear()
    r2 = desk([dict(sig, stage="ARMED"), dict(sig, stage="WATCH")],
              judge=judge_all, opener=fake_open)
    chk(r2["opened"] == 0 and r2["skipped"]["not_signal"] == 2,
        f"ARMED/WATCH وارد میز شد: {r2}")

    # ── هندسهٔ ناقص رد می‌شود ─────────────────────────────────────────
    made.clear()
    r3 = desk([dict(sig, sl=None)], judge=judge_all, opener=fake_open)
    chk(r3["opened"] == 0 and r3["skipped"]["no_geometry"] == 1,
        f"ستاپِ بی‌استاپ باز شد: {r3}")

    # ── سقفِ هر مراقب ────────────────────────────────────────────────
    made.clear()
    many = [dict(sig, sym=f"S{i}USDT") for i in range(10)]
    r4 = desk(many, judge=judge_all, opener=fake_open)
    chk(r4["opened"] == PER_GUARDIAN_CAP,
        f"سقفِ هر مراقب رعایت نشد: {r4['opened']}")
    chk(r4["skipped"]["cap_guardian"] > 0, "سقف شمرده نشد")

    # ── سقفِ کلِ اجرا: با ۱۲ مراقبِ موافق ─────────────────────────────
    def judge_every(s):
        return {"score": 0.9, "label": "تأیید قوی",
                "votes": {g: {"v": 0.9, "w": 1, "why": "آزمون"} for g in GIDS}}

    made.clear()
    r5 = desk([dict(sig, sym=f"T{i}USDT") for i in range(20)],
              judge=judge_every, opener=fake_open)
    chk(r5["opened"] <= RUN_CAP, f"سقفِ اجرا شکست: {r5['opened']}")
    chk(r5["opened"] == min(RUN_CAP, PER_GUARDIAN_CAP * len(GIDS)),
        f"سقف‌ها با هم نخواندند: {r5['opened']}")

    # ── ضدتکرار: همان (مراقب، نماد، جهت) دوباره باز نمی‌شود ──────────
    made.clear()
    # وصله روی **همین** ماژول: با `python -m` این فایل `__main__` است و
    # `import hamid.guardian_live` یک شیءِ دومِ ماژول می‌سازد؛ وصله روی
    # آن، گلوبالِ این‌جا را عوض نمی‌کند. (نسخهٔ اولِ همین آزمون دقیقاً
    # همین را اشتباه کرد و «ضدتکرار کار نمی‌کند» گزارش داد.)
    _g = globals()
    _old = _g["open_keys"]
    try:
        _g["open_keys"] = lambda: {(stage_of(A), "AAAUSDT", "LONG")}
        r6 = desk([sig], judge=judge_all, opener=fake_open)
        chk(r6["opened"] == 0 and r6["skipped"]["dup"] == 1,
            f"ردیفِ تکراری باز شد: {r6}")
    finally:
        _g["open_keys"] = _old

    # ── نگهبان: این ماژول به تلگرام و دفترِ سیگنال دست نمی‌زند ────────
    #
    # فقط **خطوطِ کد** سنجیده می‌شود: نسخهٔ اول کلِ متن را می‌خواند و روی
    # همان جمله‌ای می‌افتاد که در سندِ بالا توضیح می‌دهد این میز با
    # `telegram.send_signals` فرق دارد. آزمون باید رفتار را بسنجد نه نثر
    # را (درسِ ۶ سپتامبر).
    src = (HERE / "guardian_live.py").read_text(encoding="utf-8").split(
        "def _selftest(")[0]
    doc_end = src.find('"""', src.find('"""') + 3) + 3
    code = "\n".join(ln.split("#")[0] for ln in src[doc_end:].splitlines())
    for bad in ("telegram", "send_signals", "sent.json", "DAILY_CAP"):
        chk(bad not in code, f"میزِ زنده به مسیرِ ارسال دست زد: {bad}")
    chk("telegram" in src, "نگهبان دیگر چیزی برای سنجیدن ندارد")

    # ── دفترِ واقعی در حالت شنی دست‌نخورده می‌ماند ─────────────────────
    #
    # اثباتِ منفیِ لازم: خودِ همین آزمون‌ها بالا `desk()` را ده‌ها بار صدا
    # زدند. اگر `_log_vote` حالت شنی را نمی‌دید، تا این خط ده‌ها ردیفِ
    # ساختگی در دفترِ تولید نشسته بود — و دقیقاً همین اتفاق در نسخهٔ اول
    # افتاد (۹۶ ردیف).
    _before = VOTES.exists() and VOTES.stat().st_size or 0
    desk([sig], judge=judge_all, opener=fake_open)
    _after = VOTES.exists() and VOTES.stat().st_size or 0
    chk(_after == _before, f"دفترِ رأیِ تولید در آزمون رشد کرد: {_before}→{_after}")
    import brain as _b
    chk(getattr(_b, "SANDBOX", False),
        "آزمون در حالت شنی اجرا نشد — LIAM9_SANDBOX=1 لازم است")

    print(f"guardian_live: {ok} بررسی سبز" + (f" · {fails} قرمز" if fails else ""))
    return 1 if fails else 0


def main(argv=()):
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(list(argv))
    if a.selftest:
        return _selftest()
    print("این ماژول از داخل اسکن صدا زده می‌شود (scan.py).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
