#!/usr/bin/env python3
"""پاسبان دفترِ ضدواقعیتِ دروازهٔ روند (۶ سپتامبر) — آفلاین، بدون شبکه.

قفل می‌کند: ثبتِ ردیف در گلوگاه وتو · ضدواقع بودنش (هرگز «سیگنال ارسالی»
شمرده نشود) · یکتاسازی پیش از CI · کارمزد از منبع واحد نه از fee_r
ذخیره‌شده · سه حکم با قاعدهٔ توقفِ از پیش ثبت‌شده · مشاوره‌ای بودن
(هیچ آستانه‌ای عوض نمی‌شود) · ردیف قرارداد و اجرا در چرخه.
"""
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
ROOT = PY.parents[1]
sys.path.insert(0, str(PY))

from hamid import gate_verdict as GV                  # noqa: E402
from hamid import paper as P                          # noqa: E402

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


def _ledger(rows):
    p = Path(tempfile.mkdtemp(prefix="liam9-gv-")) / "closed.jsonl"
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows)
                 + "\n", encoding="utf-8")
    return p


def _row(i, direction="SHORT", R=1.0, reason="هر دو تایم بالا خلاف SHORT است",
         stage="gate-vetoed", tf="15m"):
    return {"sym": f"X{i}", "dir": direction, "entry": 100.0,
            "sl": 102.0 if direction == "SHORT" else 98.0,
            "opened": i, "outcome": "target", "R": R, "tf": tf,
            "why": {"stage": stage, "veto_why": "trend_gate",
                    "gate_reason": reason}}


# ── ۱. ضدواقع است، نه سیگنال ──────────────────────────────────────────────
#
# اگر این نباشد، هر ستاپِ وتوشده در شمارشِ «سیگنال ارسالی» می‌نشیند و آمار
# محصول را باد می‌کند — همان درسِ ۳×ETH که ۵ سپتامبر تصحیح شد.
check("مرحلهٔ gate-vetoed در فهرست «سیگنال نیست» است",
      "gate-vetoed" in P._NOT_SIGNAL, str(P._NOT_SIGNAL))
_mixed = [{"sym": "A", "dir": "SHORT", "R": 1.0, "outcome": "target",
           "closed": 1, "why": {"stage": "gate-vetoed", "tg_msg_id": 7}},
          {"sym": "A", "dir": "SHORT", "R": 1.0, "outcome": "target",
           "closed": 1, "why": {"stage": "sig-ibs", "tg_msg_id": 7}}]
check("ردیف ضدواقع در شمارشِ سیگنالِ ارسالی نمی‌آید",
      all((t["why"]["stage"] or "").startswith("sig-")
          for t in P.sent_signals(_mixed)))

# ── ۲. گلوگاه وتو واقعاً ردیف می‌سازد ────────────────────────────────────
_tg = (PY / "telegram.py").read_text(encoding="utf-8")
check("گلوگاه وتوی روند ردیف ضدواقع باز می‌کند",
      '"stage_tag": "gate-vetoed"' in _tg)
check("و دلیلِ وتو با جهتِ روندِ هر دو تایم ثبت می‌شود",
      '"veto_why": "trend_gate"' in _tg
      and '"trend_4h": _ta.get("t4")' in _tg
      and '"trend_1h": _ta.get("t1")' in _tg)
# رفتار عوض نمی‌شود: بعد از ثبت، هنوز continue می‌کند (سیگنال نمی‌رود)
_i_open = _tg.find('"stage_tag": "gate-vetoed"')
_i_skip = _tg.find('sent[f"skip|{_key(s)}"] = now_ms', _i_open)
check("ثبت، وتو را باطل نمی‌کند (ستاپ همچنان رد می‌شود)",
      0 < _i_open < _i_skip and "continue" in _tg[_i_skip:_i_skip + 120])
check("خطای دفتر جلوی وتو را نمی‌گیرد",
      "دفتر اختیاری است؛ وتو نه" in _tg)

# ── ۳. یکتاسازی پیش از هر CI ─────────────────────────────────────────────
#
# تصحیح ۲۴ اوت: بازهٔ اطمینان فرض می‌کند هر ردیف یک مشاهدهٔ مستقل است.
# ردیف تکراری، CI را ساختگی تنگ می‌کند — یعنی حکمِ زودرس.
_dup = [_row(0), _row(0), _row(1)]
check("ردیف تکراری یک بار شمرده می‌شود",
      len(GV.rows(_ledger(_dup))) == 2, str(len(GV.rows(_ledger(_dup)))))

# ── ۴. کارمزد از منبع واحد، نه از fee_r ذخیره‌شده ────────────────────────
#
# `fee_r` روی ~۴۹٪ ردیف‌ها هست و زیرنمونه‌اش سوگیری دارد؛ سنجه‌ای که از آن
# بخواند می‌تواند علامتِ نتیجه را برگرداند (درسِ ۶ سپتامبر).
_liar = _row(9)
_liar["fee_r"] = 0.0                      # عددِ دروغینِ ذخیره‌شده
_got = GV.rows(_ledger([_liar]))[0]
check("خالص از entry/sl بازمحاسبه می‌شود، نه از fee_r ردیف",
      _got["_fee"] is not None and _got["_fee"] > 0
      and abs(_got["_net"] - (_got["_gross"] - _got["_fee"])) < 1e-9,
      f"fee={_got['_fee']} net={_got['_net']}")
_src = (HERE / "gate_verdict.py").read_text(encoding="utf-8")
check("و منبعش hamid/fees است", "from hamid import fees" in _src)

# ── ۵. سه حکم، با قاعدهٔ توقفِ از پیش ثبت‌شده ────────────────────────────
check("قاعدهٔ توقف از پیش ثبت شده (n و آستانه ثابت‌اند)",
      isinstance(GV.MIN_N, int) and GV.MIN_N >= 100, str(GV.MIN_N))
_few = GV.judge(path=_ledger([_row(i) for i in range(20)]))
check("زیر کف نمونه → UNDECIDED، نه حکمِ زودرس",
      _few["verdict"] == "UNDECIDED", _few["verdict"])
check("و می‌گوید چند نمونهٔ دیگر لازم است", "نمونهٔ دیگر" in _few["why"])
_lose = GV.judge(path=_ledger([_row(i, R=-1.0 + (0.02 if i % 2 else -0.02))
                               for i in range(GV.MIN_N + 40)]))
check("وتوشده‌های بازنده → GATE_PAYS (وتو پول نجات داد)",
      _lose["verdict"] == "GATE_PAYS", _lose["verdict"])
_win = GV.judge(path=_ledger([_row(i, R=2.0 + (0.02 if i % 2 else -0.02))
                              for i in range(GV.MIN_N + 40)]))
check("وتوشده‌های برنده → LOOSEN_CANDIDATE (پولِ روی میز رد شد)",
      _win["verdict"] == "LOOSEN_CANDIDATE", _win["verdict"])

# ── ۶. برش‌هایی که سؤال حمید را جواب می‌دهند ─────────────────────────────
_mix = ([_row(i, "SHORT", 1.4) for i in range(60)]
        + [_row(500 + i, "LONG", -1.0,
                reason="خلاف روند ۴س (down) و تأییدیه ناقص است", tf="5m")
           for i in range(60)])
_v = GV.judge(path=_ledger(_mix))
check("برش بر جهت هست (شورت در برابر لانگ)",
      set(_v["by_dir"]) == {"SHORT", "LONG"}, str(list(_v["by_dir"])))
check("و شورت و لانگ جدا داوری می‌شوند",
      _v["by_dir"]["SHORT"]["net"]["verdict"] == "بالای صفر"
      and _v["by_dir"]["LONG"]["net"]["verdict"] == "زیر صفر")
check("وتوی مطلقِ دو-تایم از تأییدِ ناقصِ یک-تایم جدا شمرده می‌شود",
      len(_v["by_mode"]) == 2 and any("مطلق" in k for k in _v["by_mode"])
      and any("ناقص" in k for k in _v["by_mode"]), str(list(_v["by_mode"])))

# ── ۷. مشاوره‌ای: هیچ آستانه‌ای این‌جا عوض نمی‌شود ───────────────────────
check("ماژول هیچ فایلی جز خروجی خودش نمی‌نویسد (قانون ۰۵)",
      _src.count("write_text") == 1 and "OUT.write_text" in _src)
check("مرز صادقانه روی خروجی نوشته می‌شود",
      "boundary" in _v and "قانون ۰۳" in _v["note"])
check("حکم LOOSEN فقط «نامزد» است، نه اجرا",
      "LOOSEN_CANDIDATE" in _src and "حمید تصمیم" in _src)

# ── ۸. قرارداد و اجرا (قانون ۱۳) ─────────────────────────────────────────
_reg = json.loads((ROOT / "config" / "state_registry.json")
                  .read_text(encoding="utf-8"))["files"]
check("خروجی ردیف قرارداد وضعیت دارد (یتیم نیست)",
      "gate-verdict.json" in _reg)
check("و مالک/تولیدکننده‌اش درست ثبت شده",
      _reg.get("gate-verdict.json", {}).get("owner") == "E17"
      and "gate_verdict" in (_reg.get("gate-verdict.json", {})
                             .get("producer") or ""))
_wf = (ROOT / ".github" / "workflows" / "hamid-cycle.yml").read_text(
    encoding="utf-8")
check("چرخه هر نوبت داوری را اجرا می‌کند",
      "hamid.gate_verdict --write" in _wf)

print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
sys.exit(1 if FAIL else 0)
