"""پاسبانِ بازبینیِ سیگنال — هر بررسی باید خرابیِ ساختگیِ خودش را بگیرد.

قاعدهٔ همیشگی: بررسی‌ای که هیچ‌وقت قرمز نشود، آموزشِ نادیده‌گرفتن است.
پس هر یک از هشت بررسی این‌جا دو بار صدا زده می‌شود — یک‌بار روی دادهٔ
سالم (باید سبز شود) و یک‌بار روی دادهٔ عمداً خراب (باید قرمز شود).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
sys.path.insert(0, str(PY))

from hamid import signal_audit as A                  # noqa: E402

OK = 0
FAIL = []
NOW = 1_800_000_000_000
H = 3_600_000


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


def snt(sym, at, d="LONG", tf="5m", entry=100.0, sl=95.0, tp1=110.0, mid=None):
    return {"at": at, "sym": sym, "dir": d, "tf": tf, "entry": entry,
            "sl": sl, "tp1": tp1, "tg_msg_id": mid, "strategy": "ibs"}


def lg(sym, d="LONG", tf="5m", entry=100.0, sl=95.0, tp1=110.0,
       t4="up", t1="up"):
    return {"at": NOW - H, "sym": sym, "dir": d, "tf": tf, "entry": entry,
            "sl": sl, "tp1": tp1, "trend4": t4, "trend1": t1}


def bk(mid, stage, r=0.5, outcome="trail", entry=100.0, sym="AAAUSDT"):
    return {"sym": sym, "dir": "LONG", "entry": entry, "R": r,
            "outcome": outcome, "closed": NOW - H,
            "why": {"stage": stage, "tg_msg_id": mid}}


def run():
    # ۱) محتوا
    check("محتوا: ردیف سالم سبز است", A.c_content([], [lg("AAAUSDT")])["ok"])
    check("محتوا: تایم‌فریم ۱د قرمز است",
          not A.c_content([], [lg("A", tf="1m")])["ok"])
    check("محتوا: بی‌استاپ قرمز است",
          not A.c_content([], [lg("A", sl=None)])["ok"])
    check("محتوا: ترتیب قیمت غلط قرمز است",
          not A.c_content([], [lg("A", sl=105.0)])["ok"])
    check("محتوا: RR کم قرمز است",
          not A.c_content([], [lg("A", tp1=102.0)])["ok"])
    check("محتوا: بی‌ارسال، سبز و با اقدامِ «کاری نکن»",
          A.c_content([], [])["ok"] and "کاری نکن" in A.c_content([], [])["action"])

    # ۲) وتوی روند
    check("وتو: هم‌جهت سبز است", A.c_trend_veto([lg("A")])["ok"])
    check("وتو: هر دو تایم خلاف، قرمز",
          not A.c_trend_veto([lg("A", t4="down", t1="down")])["ok"])
    check("وتو: فقط یک تایم خلاف، قرمز نیست (خلافِ روندِ مجاز)",
          A.c_trend_veto([lg("A", t4="down", t1="up")])["ok"])

    # ۳) ضدتکرار
    check("ضدتکرار: دو ارسال با فاصلهٔ ۵ ساعت سبز",
          A.c_dedupe([snt("A", NOW - 6 * H), snt("A", NOW - H)])["ok"])
    check("ضدتکرار: همان جفت داخل ۳ ساعت قرمز",
          not A.c_dedupe([snt("A", NOW - 2 * H), snt("A", NOW - H)])["ok"])
    check("ضدتکرار: سه ارسال یک ارز در ۶ ساعت قرمز",
          not A.c_dedupe([snt("A", NOW - 5 * H), snt("A", NOW - 4 * H, d="SHORT"),
                          snt("A", NOW - H, d="SHORT", tf="15m")])["ok"])

    # ۴) حسابِ سیگنال — همان عیبی که حمید دید
    good = [bk(1, "sig-ibs"), bk(1, "exp-trail-g65"), bk(1, "exp-trail-g80"),
            bk(2, "sig-smc")]
    r4 = A.c_count_truth([], good)
    check("حساب: سه بازو + یک ردیف واقعی = دو سیگنال، سبز", r4["ok"], r4["evidence"])
    check("حساب: تورمِ خام گزارش می‌شود (۲× در این نمونه)",
          "تورمِ خام 2.0×" in r4["evidence"], r4["evidence"])
    check("حساب: پیامی که فقط بازویش بسته شده، کم‌شماری حساب نمی‌شود",
          A.c_count_truth([], [bk(3, "exp-trail-g65")])["ok"])

    # ۵) پیوند ارسال↔دفتر
    check("پیوند: ارسالِ دارای ردیف سبز",
          A.c_ledger_match([snt("A", NOW - H, mid=9)], [bk(9, "sig-ibs")], [])["ok"])
    r5 = A.c_ledger_match([snt("A", NOW - H, mid=9)], [], [])
    check("پیوند: ارسالِ بی‌ردیف قرمز و شدتش بالاست",
          not r5["ok"] and r5["sev"] == "high", str(r5))

    # ۶) پوزیشن معلق
    op = [{"sym": "A", "filled": NOW - 20 * H, "why": {"tg_msg_id": i}}
          for i in (1, 2, 3)]
    check("معلق: سه پوزیشنِ ۲۰ ساعته قرمز",
          not A.c_stuck([snt("A", NOW - H, mid=i) for i in (1, 2, 3)],
                        op, NOW)["ok"])
    check("معلق: دو تا هنوز سبز (آستانه سه است)",
          A.c_stuck([snt("A", NOW - H, mid=i) for i in (1, 2)],
                    op[:2], NOW)["ok"])

    # ۷) توازن جهت
    check("جهت: زیر ۸ ارسال حکم نمی‌دهد",
          A.c_direction_bias([snt("A", NOW - H) for _ in range(5)])["ok"])
    check("جهت: ۱۰ لانگ از ۱۰ قرمز",
          not A.c_direction_bias([snt("A", NOW - H) for _ in range(10)])["ok"])
    mixed = ([snt("A", NOW - H) for _ in range(8)]
             + [snt("A", NOW - H, d="SHORT") for _ in range(2)])
    check("جهت: ۸ به ۲ سبز است (۸۰٪ زیر آستانه)",
          A.c_direction_bias(mixed)["ok"])

    # ۸) ستاپِ تکرارشوندهٔ منقضی — پروندهٔ LOKA
    exp2 = [bk(None, "sig-smc", r=None, outcome="expired", entry=0.1236,
               sym="LOKAUSDT") for _ in range(3)]
    check("منقضیِ تکراری: ورودِ ۳بار منقضی‌شده، دوباره فرستاده = قرمز",
          not A.c_repeat_expired([snt("LOKAUSDT", NOW - H, entry=0.1236)],
                                 exp2)["ok"])
    check("منقضیِ تکراری: یک‌بار منقضی هنوز سبز (آستانه ۲ است)",
          A.c_repeat_expired([snt("LOKAUSDT", NOW - H, entry=0.1236)],
                             exp2[:1])["ok"])
    check("منقضیِ تکراری: ورودِ متفاوت سبز است",
          A.c_repeat_expired([snt("LOKAUSDT", NOW - H, entry=0.2)], exp2)["ok"])

    # ── ساختار خروجی و مرزها ──────────────────────────────────────────
    snap = A.build()
    check("خروجی حکم دارد",
          snap["verdict"] in ("HEALTHY", "DEGRADED", "SICK"), snap["verdict"])
    check("هر بررسی اقدام دارد (یافتهٔ بی‌اقدام فقط شکایت است)",
          all(f.get("action") for f in snap["findings"]))
    check("شمار بررسی‌ها با ثابت می‌خواند",
          len(snap["findings"]) == A.CHECKS_N, str(len(snap["findings"])))
    check("فهرست «چه بکن» و «چه نکن» جدا هستند",
          "todo" in snap and "leave_alone" in snap)
    check("بستهٔ شواهد کامل است (قانون ۱۲)", not snap["packet_faults"],
          str(snap["packet_faults"]))
    check("مرز صادقانه روی خروجی نوشته شده", "قانون ۰۵" in snap["boundary"])
    check("امضای پنل دارد (دستور ۱۶ اوت)", snap["panel"] == "لیام تریدر ۹")

    src = (HERE / "signal_audit.py").read_text(encoding="utf-8")
    check("فقط خروجی خودش را می‌نویسد (قانون ۰۵)", src.count("write_text") == 1)
    check("هیچ ارسال مستقیم تلگرام ندارد — از دروازهٔ آلارم رد می‌شود (قانون ۰۷)",
          "alert_gate.send" in src and "_post(" not in src)
    check("آلارم فقط برای حکم SICK", 'snap["verdict"] == "SICK"' in src)

    reg = json.loads((PY.parent.parent / "config" / "state_registry.json")
                     .read_text(encoding="utf-8"))["files"]
    check("ردیف قرارداد دارد (قانون ۱۳)", "signal-audit.json" in reg)
    check("و مالکش E25 است", reg.get("signal-audit.json", {}).get("owner") == "E25")

    chain = (PY.parent.parent / ".github" / "workflows" / "pump-radar.yml"
             ).read_text(encoding="utf-8")
    check("روی زنجیره اجرا می‌شود (کادنس ≤۱۵ دقیقه)",
          "hamid.signal_audit --write --alert" in chain)

    print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(run())
