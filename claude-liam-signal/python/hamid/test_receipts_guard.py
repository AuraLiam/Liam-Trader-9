"""پاسبان بقای رسید — بازسازی دقیقِ «رسید گم‌شدهٔ یونی» (۳۰ اوت).

سیگنال `smc|UNIUSDT|5m|LONG` رفت، حمید دیدش و معامله کرد، و در ریپو
هیچ رسیدی از آن نماند. علت: عکس‌فوریِ `$BK` **قبل از** اسکن گرفته
می‌شود، و حلقهٔ پوش با `git reset --hard` هرچه اسکن نوشته بود پاک
می‌کرد؛ فقط فهرستِ بکاپ برمی‌گشت و رسیدها در آن فهرست نبودند.

این آزمون همان توالی را بازی می‌کند: بکاپِ پیش‌ازاسکن → ارسال →
عکس‌فوریِ رسید → reset → بازگردانی. اگر ردیف یونی برنگردد، سرخ می‌شود.

سه چیزی که قفل می‌شود:
۱. رسید از reset جان به در می‌برد.
۲. بازگردانی **اجتماع** است نه بازنویسی — ردیف‌های تازهٔ درخت (که در
   عکس‌فوری نبودند) نباید قربانی شوند. قانون ضد-merge.
۳. عکس‌فوری در ورک‌فلو واقعاً **بعد از** اسکن گرفته می‌شود — وگرنه کل
   این ماشین همان عیبِ قبلی را با اسم تازه تکرار می‌کند.
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
ROOT = PY.parents[1]
sys.path.insert(0, str(PY))

from hamid import receipts_guard as RG                       # noqa: E402

OK = 0
FAIL = []


def check(name, cond, extra=""):
    global OK
    if cond:
        OK += 1
        print(f"  ✓ {name}")
    else:
        FAIL.append(name)
        print(f"  ✗ {name}")
        if extra:
            print(f"      ↳ {extra}")


def jl(rows):
    return "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)


def run():
    tmp = Path(tempfile.mkdtemp())
    sig = tmp / "signals"
    (sig / "archive").mkdir(parents=True)
    RG.ROOT, RG.SIG, RG.ARCHIVE = tmp, sig, sig / "archive"

    day = "20260830"
    arch = sig / "archive" / f"telegram-sent-{day}.jsonl"

    # ── وضعیت پیش از اسکن: ۹ ارسالِ قبلی ───────────────────────────────
    before = [{"n": i, "at": 1788000000000 + i * 1000, "sym": f"OLD{i}USDT",
               "tf": "5m", "dir": "LONG"} for i in range(1, 10)]
    arch.write_text(jl(before))
    (sig / "telegram-log.json").write_text(json.dumps(
        {"generated": 1788000009000, "sent": [{"at": r["at"], "sym": r["sym"]}
                                              for r in before]}))
    (sig / "telegram-feed.json").write_text(json.dumps(
        {"rows": [{"at": r["at"], "kind": "signal", "title": r["sym"],
                   "msg_id": 1400 + r["n"]} for r in before]}))

    bk = tmp / "bk"
    bk.mkdir()
    # بکاپِ ورک‌فلو، **قبل** از اسکن — همان کاری که امروز می‌کند
    shutil.copy(sig / "telegram-log.json", bk / "telegram-log.json")
    pre_snapshot = sig.read_bytes if False else None          # noqa: F841

    # ── اسکن: یونی می‌رود و رسیدش نوشته می‌شود ─────────────────────────
    uni = {"n": 10, "at": 1788091730458, "sym": "UNIUSDT", "tf": "5m",
           "dir": "LONG", "entry": 5.192, "strategy": "smc", "tg_msg_id": 1533}
    arch.write_text(jl(before + [uni]))
    log = json.loads((sig / "telegram-log.json").read_text())
    log["sent"].insert(0, {"at": uni["at"], "sym": "UNIUSDT", "dir": "LONG"})
    log["generated"] = uni["at"] + 100
    (sig / "telegram-log.json").write_text(json.dumps(log))
    feed = json.loads((sig / "telegram-feed.json").read_text())
    feed["rows"].insert(0, {"at": uni["at"], "kind": "signal",
                            "title": "UNIUSDT 5m LONG", "msg_id": 1533})
    (sig / "telegram-feed.json").write_text(json.dumps(feed))

    # ── رفع، نیمهٔ اول: عکس‌فوری **بعد از** اسکن ────────────────────────
    n_files = RG.snapshot(bk)
    check("عکس‌فوری رسید بعد از اسکن گرفته می‌شود", n_files >= 3, str(n_files))

    # ── حلقهٔ پوش: reset --hard، درخت به وضعیت پیش‌ازاسکن برمی‌گردد ─────
    arch.write_text(jl(before))
    shutil.copy(bk / "telegram-log.json", sig / "telegram-log.json")
    (sig / "telegram-feed.json").write_text(json.dumps(
        {"rows": [{"at": r["at"], "kind": "signal", "title": r["sym"],
                   "msg_id": 1400 + r["n"]} for r in before]}))
    check("شبیه‌سازی درست است: بعد از reset، یونی واقعاً نیست",
          "UNIUSDT" not in arch.read_text())

    # ── رفع، نیمهٔ دوم: بازگردانی با اجتماع ────────────────────────────
    r = RG.restore(bk)
    check("بازگردانی ردیف‌های گم‌شده را برمی‌گرداند", r["restored"] >= 3, str(r))
    rows = [json.loads(l) for l in arch.read_text().splitlines() if l.strip()]
    check("ردیف یونی در آرشیو برگشت",
          any(x["sym"] == "UNIUSDT" for x in rows), str(len(rows)))
    check("ردیف‌های قبلی هم سرِ جایشان‌اند (اجتماع، نه بازنویسی)",
          len(rows) == 10, f"{len(rows)} ردیف")
    check("شماره‌گذاری پیاپی بازسازی شد",
          [x["n"] for x in rows] == list(range(1, 11)),
          str([x["n"] for x in rows]))
    log2 = json.loads((sig / "telegram-log.json").read_text())
    check("ردیف یونی در telegram-log برگشت",
          any(x.get("sym") == "UNIUSDT" for x in log2["sent"]))
    feed2 = json.loads((sig / "telegram-feed.json").read_text())
    check("ردیف یونی در فید پنل برگشت",
          any("UNI" in str(x.get("title")) for x in feed2["rows"]))
    check("مهر زمان عقب نمی‌رود (پاسبان کهنگی گول نمی‌خورد)",
          log2["generated"] >= uni["at"], str(log2["generated"]))

    # ── اجتماع واقعی است: ردیفِ تازهٔ درخت قربانی نمی‌شود ───────────────
    fresh = {"n": 99, "at": 1788098094431, "sym": "PUMPUSDT", "tf": "5m",
             "dir": "LONG"}
    arch.write_text(jl(rows + [fresh]))
    RG.restore(bk)
    rows3 = [json.loads(l) for l in arch.read_text().splitlines() if l.strip()]
    syms = {x["sym"] for x in rows3}
    check("ردیفِ تازهٔ درخت با بازگردانی پاک نمی‌شود",
          "PUMPUSDT" in syms and "UNIUSDT" in syms, str(sorted(syms))[:120])
    check("بازگردانی دوباره، ردیف تکراری نمی‌سازد", len(rows3) == 11,
          f"{len(rows3)} ردیف")

    # ── بدون عکس‌فوری، صادقانه می‌گوید چرا ─────────────────────────────
    empty = RG.restore(tmp / "nothing")
    check("نبودِ عکس‌فوری، دلیلِ صریح دارد نه سکوت",
          empty["restored"] == 0 and "why" in empty, str(empty))

    # ── ورک‌فلو: عکس‌فوری بعد از اسکن، بازگردانی داخل حلقه ─────────────
    wf = (ROOT / ".github/workflows/pump-radar.yml").read_text(encoding="utf-8")
    check("ورک‌فلو عکس‌فوری رسید را می‌گیرد",
          "receipts_guard --snapshot" in wf)
    check("ورک‌فلو رسیدها را در حلقه برمی‌گرداند",
          "receipts_guard --restore" in wf)
    i_scan = wf.find("scan.py --symbols")
    i_snap = wf.find("receipts_guard --snapshot")
    check("عکس‌فوری **بعد از** اسکن است (قلبِ همین عیب)",
          0 <= i_scan < i_snap, f"scan={i_scan} snapshot={i_snap}")
    i_reset = wf.find("reset --hard origin/main")
    i_rest = wf.find("receipts_guard --restore")
    check("بازگردانی **بعد از** reset است",
          0 <= i_reset < i_rest, f"reset={i_reset} restore={i_rest}")

    # ── دفترهای پیپر هم باید جان به در ببرند (تکمیل ۱ سپتامبر) ────────
    #
    # نیمهٔ باقی‌ماندهٔ همین عیب: رسیدها نجات یافتند، دفتر یادگیری نه.
    # اثرش را ممیزِ حلقه شمرد — ۴ سیگنال از ۴۰ ارسالِ ۷۲ ساعت اخیر
    # (AAVE، FET، TRX، ETH) بدون هیچ ردیف یادگیری: تلگرام رفته،
    # `sent.json` یادش مانده، ردیف دفتر پاک شده و چون ضدتکرار درست کار
    # می‌کند دیگر هرگز ساخته نمی‌شود.
    import json as _json
    import tempfile as _tf
    _T = Path(_tf.mkdtemp())
    (_T / "brain/paper").mkdir(parents=True)
    (_T / "signals/archive").mkdir(parents=True)
    _old = (RG.ROOT, RG.SIG, RG.ARCHIVE)
    try:
        RG.ROOT, RG.SIG, RG.ARCHIVE = _T, _T / "signals", _T / "signals/archive"

        def _row(sym, opened=1000, stage="sig-ibs"):
            return {"sym": sym, "dir": "LONG", "entry": 1.0, "sl": 0.9,
                    "tp1": 1.2, "opened": opened, "why": {"stage": stage}}

        _op, _cl = _T / "brain/paper/open.jsonl", _T / "brain/paper/closed.jsonl"
        _op.write_text("".join(_json.dumps(_row(s)) + "\n"
                               for s in ("AAVEUSDT", "FETUSDT")), encoding="utf-8")
        _cl.write_text("", encoding="utf-8")
        _bk = _T / "bk"
        _bk.mkdir()
        check("عکس‌فوری دفترهای پیپر را هم برمی‌دارد", RG.snapshot(_bk) >= 2)

        _op.write_text("", encoding="utf-8")          # بازگردانیِ سختِ درخت
        _cl.write_text("", encoding="utf-8")
        RG.restore(_bk)
        _back = [_json.loads(x) for x in _op.read_text().splitlines() if x.strip()]
        check("ردیفِ یادگیریِ سیگنالِ رفته برمی‌گردد",
              {r["sym"] for r in _back} == {"AAVEUSDT", "FETUSDT"}, str(_back))

        # تسویه‌شده به دفتر باز برنمی‌گردد (وگرنه ردیف تکراریِ ۲۴ اوت)
        _cl.write_text(_json.dumps(_row("AAVEUSDT")) + "\n", encoding="utf-8")
        _op.write_text("", encoding="utf-8")
        RG.restore(_bk)
        _b2 = [_json.loads(x) for x in _op.read_text().splitlines() if x.strip()]
        check("معاملهٔ تسویه‌شده دوباره باز نمی‌شود",
              {r["sym"] for r in _b2} == {"FETUSDT"}, str(_b2))

        # اجتماع است نه بازنویسی: ردیفِ تازهٔ درخت نباید پاک شود
        _cl.write_text("", encoding="utf-8")
        _op.write_text(_json.dumps(_row("XUSDT", opened=2000)) + "\n",
                       encoding="utf-8")
        RG.restore(_bk)
        _b3 = [_json.loads(x) for x in _op.read_text().splitlines() if x.strip()]
        check("ردیفِ تازهٔ درخت با بازگردانی پاک نمی‌شود (اجتماع)",
              {r["sym"] for r in _b3} == {"XUSDT", "AAVEUSDT", "FETUSDT"}, str(_b3))
        n_before = len(_b3)
        RG.restore(_bk)
        _b4 = [_json.loads(x) for x in _op.read_text().splitlines() if x.strip()]
        check("بازگردانیِ دوباره ردیف تکراری نمی‌سازد",
              len(_b4) == n_before, f"{n_before} → {len(_b4)}")
    finally:
        RG.ROOT, RG.SIG, RG.ARCHIVE = _old
    check("هویتِ ردیف همان کلیدِ معاملهٔ paper است (درس ۲۴ اوت)",
          "trade_key" in (PY / "hamid" / "receipts_guard.py").read_text(
              encoding="utf-8"))

    print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(run())
