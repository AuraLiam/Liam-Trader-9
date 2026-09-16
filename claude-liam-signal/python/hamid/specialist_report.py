#!/usr/bin/env python3
"""گزارش فارسیِ میز متخصصین — همان چیزی که حمید ساعت ۱۰ صبح می‌خواهد.

«اسم متخصصین و نوع استراتژی و اسم استراتژی هر کدام را جلوی اسمشان
می‌نویسی و بهم تحویل می‌دهی… می‌گویی که چه استراتژی‌ای چه بوده و چه
تغییراتی درش ایجاد شده و نتایجشان به چه صورت تمام شده.»

خروجی: `signals/specialist-report.md` + چاپ روی ترمینال.
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
ROOT = HERE.parent.parent.parent
SRC = ROOT / "signals" / "specialist-lab.json"
OUT = ROOT / "signals" / "specialist-report.md"

FA_DIGIT = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def fa(x):
    return str(x).translate(FA_DIGIT)


def _num(v, nd=4):
    return "—" if v is None else fa(f"{v:+.{nd}f}" if isinstance(v, float) else v)


def render(d):
    L = []
    gen = d.get("generated")
    L.append("# میز مستقل ۱۲ متخصص — نتیجهٔ پیپر تریدینگ\n")
    L.append(f"تایم‌فریم **{d.get('tf')}** · {fa(d.get('n_symbols'))} ارز · "
             f"{fa(d.get('per_symbol'))} ترید بر ارز · "
             f"**{fa(d.get('trades_total'))} ترید** · "
             f"اجرا {fa(round((d.get('seconds') or 0) / 60, 1))} دقیقه\n")
    L.append("عددِ هر متخصص از **نیمهٔ دومِ تاریخ** است — دادهٔ دیده‌نشده. "
             "نیمهٔ اول فقط برای انتخاب ایده به کار رفت.\n")

    L.append("\n## جدول کوتاه\n")
    L.append("| متخصص | نوع استراتژی | نام استراتژی | n | خالص R | CI۹۵ | برد | حکم |")
    L.append("|---|---|---|---|---|---|---|---|")
    rows = sorted(d["desks"].items(),
                  key=lambda kv: (kv[1]["result_out_of_sample"].get("net") is None,
                                  -(kv[1]["result_out_of_sample"].get("net") or 0)))
    for _id, v in rows:
        r = v["result_out_of_sample"]
        ci = r.get("ci") or [None, None]
        L.append(f"| {v['sign']} {v['fa']} | {v['family']} | {v['strategy_fa']} "
                 f"({v['strategy_en']}) | {fa(r.get('n') or 0)} | {_num(r.get('net'))} | "
                 f"[{_num(ci[0])}, {_num(ci[1])}] | "
                 f"{fa(r.get('win_pct') or '—')}٪ | {r.get('verdict', '—')} |")

    L.append("\n## هر متخصص، یکی‌یکی\n")
    for _id, v in rows:
        r = v["result_out_of_sample"]
        imp = v.get("improvement") or {}
        L.append(f"### {v['sign']} {v['fa']} — «{v['strategy_fa']}» "
                 f"({v['strategy_en']}) · {v['family']}\n")
        L.append(f"**ایدهٔ استراتژی:** {v['idea']}\n")
        L.append(f"**پارامتر پایه:** `{json.dumps(v['params_base'], ensure_ascii=False)}`")
        if imp.get("adopted"):
            L.append(f"**تغییری که خودش داد:** `{json.dumps(imp.get('change'), ensure_ascii=False)}` "
                     f"— {imp.get('why')}")
            L.append(f"**اثر تغییر روی دادهٔ دیده‌نشده:** پایه {_num(imp.get('base_net_out'))}R "
                     f"→ جدید {_num(imp.get('cand_net_out'))}R "
                     f"(اختلاف {_num(imp.get('diff_out'))}R، CI "
                     f"[{_num((imp.get('diff_ci') or [None, None])[0])}, "
                     f"{_num((imp.get('diff_ci') or [None, None])[1])}])")
        else:
            L.append(f"**تغییر:** پذیرفته نشد — {imp.get('why', '—')}")
        tried = imp.get("tried") or []
        if tried:
            L.append("**ایده‌های امتحان‌شده (نیمهٔ اول):** " + " · ".join(
                f"`{json.dumps(t['change'], ensure_ascii=False)}` n={fa(t['n'])} "
                f"خالص={_num(t.get('net_in'))}" for t in tried))
        outs = r.get("outcomes") or {}
        L.append(f"**نتیجه:** n={fa(r.get('n') or 0)} · خالص {_num(r.get('net'))}R "
                 f"· ناخالص {_num(r.get('gross'))}R · برد {fa(r.get('win_pct') or '—')}٪ "
                 f"· جمع {_num(r.get('sum_net'), 2)}R")
        L.append(f"**هندسه:** میانهٔ استاپ {fa(r.get('median_stop_pct') or '—')}٪ · "
                 f"میانهٔ کارمزد {fa(r.get('median_fee_r') or '—')}R · "
                 f"خروج‌ها: " + "، ".join(f"{k}={fa(n)}" for k, n in outs.items()))
        L.append(f"**حکم:** {r.get('verdict', '—')}\n")

    L.append("\n## مرز صادقانه\n")
    L.append(d.get("boundary", ""))
    L.append("\n" + d.get("method", ""))
    return "\n".join(L)


def main(argv=()):
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args(list(argv))
    try:
        d = json.loads(SRC.read_text(encoding="utf-8"))
    except Exception as e:                           # noqa: BLE001
        print(f"خروجی میز خوانده نشد: {type(e).__name__} — اول specialist_lab را بدوان")
        return 1
    txt = render(d)
    print(txt)
    if a.write:
        OUT.write_text(txt, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
