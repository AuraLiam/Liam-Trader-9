#!/usr/bin/env python3
"""بودجهٔ پیام — «چند پیام رفت» را از خودِ محصول می‌شمارد، نه از وعدهٔ کد.

## چرا این فایل هست (شکایت حمید، ۷ سپتامبر)

«روزانه بارها پیام خطا می‌آید و بارها پیام نقص. پیدا کردن مشکل مهم است
ولی برطرف کردن آن به صورت دائمی مهم‌تر است.»

سه چیز از همان شکایت بیرون آمد و هر سه ریشه‌ای‌اند:

۱. **کادنسِ اعلام‌شده هیچ‌جا سنجیده نمی‌شد.** گزارش دامیننس سند دارد که
   «ساعتی» است و کدش ضدتکرارِ ۵۰دقیقه‌ای دارد — و روی محصول ۳۳ تا ۴۲ بار
   در روز می‌رفت. هیچ آزمونی این را نمی‌گرفت چون همه‌شان **اسکریپت** را
   می‌سنجیدند («این شرط نوشته شده؟») نه **محصول** را («واقعاً چند تا
   رفت؟»). این همان درسِ ۶ سپتامبر است: اسکریپتِ سبز ≠ محصولِ درست.
۲. **آلارم‌ها اصلاً دفتر نداشتند.** هر نُه پاسبان از `telegram.send_text`
   می‌فرستادند و هیچ ردیفی نمی‌ماند. شکایتِ درستِ حمید عملاً
   **غیرقابل‌شمارش** بود — و چیزی که شمرده نمی‌شود، «رفعِ دائمی»‌اش هم
   اثبات ندارد. (رفع در همان `send_text`: هر آلارم `kind="alert"`.)
۳. **بودجه‌ای اعلام نشده بود.** «زیاد» عددی نبود که بشود ردش کرد.

## قرارداد

هر نوع پیام بودجهٔ روزانه دارد. شمارش از `signals/archive/
telegram-feed-*.jsonl` (append-only، اجتماع‌شونده) در پنجرهٔ ۲۴ ساعت.
بیش از بودجه = `OVER` و با `--check` چرخه سرخ می‌شود.

## چرا `EFFECTIVE_FROM`

دفترِ قبل از رفع، **شاهدِ بیماری** است نه شکستِ درمان. اگر پنجره را روی
آن باز بگذارم، دروازه از همان دقیقهٔ اول سرخ می‌شود و — دقیقاً مثل
آلارمِ کاذبِ sentinel در ۲۵ اوت — کلِ زنجیره را می‌خواباند. پس شمارش از
لحظهٔ رفع شروع می‌شود و این عدد روی خودِ فایل نوشته است تا کسی نتواند
بی‌سروصدا جابه‌جایش کند.
"""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
ROOT = HERE.parents[2]
ARCHIVE = ROOT / "signals" / "archive"
OUT = ROOT / "signals" / "msg-budget.json"

# لحظهٔ رفعِ کادنس و روشن‌شدنِ دفترِ آلارم (۷ سپتامبر ۲۰۲۶، ۰۷:۳۰ UTC).
EFFECTIVE_FROM = 1788766200000

WINDOW_H = 24

# بودجهٔ روزانه — هر عدد از یک سند می‌آید، نه از سلیقه.
BUDGET = {
    "signal":      (24, "سقف روزانه، دستور ۲۹ اوت (telegram.DAILY_CAP)"),
    "dom_report":  (26, "ساعتی (قانون ۱۱) + ۲ لقی برای لرزش زمان‌بند"),
    "pump_report": (6,  "پنج نوبت در روز (قانون ۰۷) + ۱ لقی"),
    "work_report": (4,  "سه نوبت در روز (قانون ۱۱) + ۱ لقی"),
    "alert":       (12, "دروازهٔ ۶ساعته روی ۹ پاسبان (قانون ۰۷) — "
                        "نه هر پاسبان ۴ بار، که می‌شود ۳۶"),
}

# نتیجهٔ معامله ریپلای همان سیگنال است و تعدادش را پوزیشن‌های باز تعیین
# می‌کند، نه یک کادنس. شمرده می‌شود، بودجه ندارد — بودجهٔ ساختگی برایش
# یعنی یا نتیجه‌ای گم می‌شود یا سقف بی‌معنا می‌شود.
#
# یازده فرستندهٔ تازه‌دفتردار (۷ سپتامبر) هم فعلاً همین‌جااند — ولی به
# دلیلِ دیگری: **تاریخچه ندارند.** تا دیروز هیچ ردی نمی‌گذاشتند، پس
# عددی وجود ندارد که بشود بودجه را از آن درآورد. بودجهٔ حدسی برایشان
# دقیقاً همان کاری است که «قانون عددِ درست» منع می‌کند. اول شمرده
# می‌شوند، بعد بودجه‌شان از دادهٔ خودشان نوشته می‌شود.
NO_BUDGET = {"outcome"}
OBSERVE_ONLY = {
    "pump_probe": "کاوش پامپ (فقط با dispatch)",
    "deep": "تحلیل عمیق نماد (فقط با dispatch)",
    "btc_pattern": "الگوی تازهٔ بیت‌کوین (زنجیرهٔ سیگنال)",
    "reply": "پاسخ به پیام حمید",
    "ignition": "شلیک دفتر انتظار",
    "health": "کاوش سلامت تلگرام",
}


def rows(now_ms=None, window_h=WINDOW_H, archive=None):
    """ردیف‌های پنجره — یکتا بر (at, kind, title) چون دو اجرا ممکن است
    یک ردیف را دوباره در آرشیو بنویسند و شمارشِ باددار، حکمِ باددار
    می‌سازد (تصحیح ۲۴ اوت)."""
    now = now_ms or int(time.time() * 1000)
    lo = now - window_h * 3600_000
    d = Path(archive) if archive else ARCHIVE
    seen, out = set(), []
    # تعداد فایلِ روزانه از خودِ پنجره مشتق می‌شود، نه ثابتِ ۲ — وگرنه
    # پنجرهٔ ۱۲۰ساعته بی‌صدا فقط ۴۸ ساعت را می‌شمرد و عددِ کم را «سبز»
    # گزارش می‌کند. (قانون عددِ درست: عددِ نامحتمل، اول به خودت شک کن.)
    days = int(window_h // 24) + 2
    for delta in [i * 86400_000 for i in range(days)]:
        day = time.strftime("%Y%m%d", time.gmtime((now - delta) / 1000))
        f = d / f"telegram-feed-{day}.jsonl"
        if not f.exists():
            continue
        for ln in f.read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if not ln:
                continue
            try:
                r = json.loads(ln)
            except Exception:                        # noqa: BLE001
                continue
            at = int(r.get("at") or 0)
            if at < lo or at > now:
                continue
            ident = (at, r.get("kind"), r.get("title"))
            if ident in seen:
                continue
            seen.add(ident)
            out.append(r)
    return out


def judge(now_ms=None, window_h=WINDOW_H, archive=None,
          effective_from=None):
    now = now_ms or int(time.time() * 1000)
    eff = EFFECTIVE_FROM if effective_from is None else effective_from
    rs = rows(now_ms=now, window_h=window_h, archive=archive)
    counted = [r for r in rs if int(r.get("at") or 0) >= eff]
    # سهمِ پنجره که بعد از رفع است — بدونش «۳ تا از بودجهٔ ۲۶» در ساعتِ
    # اولِ رفع، سبزِ بی‌معنا است و باید صریح گفته شود.
    covered_h = max(0.0, min(window_h, (now - eff) / 3600_000.0))
    per = {}
    for kind, (cap, why) in BUDGET.items():
        n = sum(1 for r in counted if r.get("kind") == kind)
        # تا وقتی پنجره کامل نشده، **حکم داده نمی‌شود**.
        #
        # نسخهٔ اولِ همین تابع سقف را با سهمِ پوشش مقیاس می‌کرد: در ساعتِ
        # اول می‌شد ۱، و دو پیام — که یک لرزشِ زمان‌بند هم می‌سازدش —
        # چرخه را سرخ می‌کرد. یعنی دقیقاً همان آلارمِ کاذبِ ۲۵ اوت که
        # کلِ زنجیره را خواباند، این‌بار از دستِ خودِ محافظ. پس گرم‌شدن
        # صریح است: می‌شمارد، نرخِ برآوردی را چاپ می‌کند، و نمی‌بندد.
        warming = covered_h < window_h
        per[kind] = {"n": n, "budget": cap, "warming": warming,
                     "rate_per_day": (round(n * 24.0 / covered_h, 1)
                                      if covered_h >= 1 else None),
                     "over": (not warming) and n > cap, "why": why}
    for kind in sorted({r.get("kind") for r in counted} - set(BUDGET)):
        n = sum(1 for r in counted if r.get("kind") == kind)
        if kind in NO_BUDGET:
            why = "بدون بودجه — تعدادش را پوزیشن‌های باز تعیین می‌کند"
        elif kind in OBSERVE_ONLY:
            why = f"فقط شمارش تا جمع‌شدن تاریخچه — {OBSERVE_ONLY[kind]}"
        else:
            why = "نوعِ ثبت‌نشده — بودجه‌اش را در BUDGET بنویس"
        per[kind] = {"n": n, "budget": None, "warming": covered_h < window_h,
                     "rate_per_day": (round(n * 24.0 / covered_h, 1)
                                      if covered_h >= 1 else None),
                     "over": False, "why": why}
    over = sorted(k for k, v in per.items() if v["over"])
    return {
        "generated": now,
        "window_h": window_h,
        "covered_h": round(covered_h, 2),
        "effective_from": eff,
        "verdict": ("OVER" if over else
                    ("WARMING" if covered_h < window_h else "OK")),
        "over": over,
        "kinds": per,
        "total": len(counted),
        "note": ("شمارش از دفترِ append-only محصول است، نه از متنِ کد. "
                 "پنجرهٔ پیش از EFFECTIVE_FROM شاهدِ بیماری است و شمرده "
                 "نمی‌شود."),
        "boundary": ("پیامی که `record_out` نمی‌زند در این شمارش نیست — "
                     "محافظ `test_msg_budget` جلوی فرستندهٔ بی‌دفتر را "
                     "می‌گیرد، ولی تا وقتی همهٔ فرستنده‌ها دفتر بگیرند، "
                     "این عدد کفِ واقعیت است نه خودِ آن."),
    }


def render(v):
    L = [f"### بودجهٔ پیام — {v['verdict']} · {v['total']} پیام در "
         f"{v['covered_h']}ساعتِ سنجیده"]
    for kind, d in sorted(v["kinds"].items(), key=lambda kv: -kv[1]["n"]):
        cap = d["budget"]
        mark = "✗" if d["over"] else ("…" if d.get("warming") else "✓")
        cap_s = "—" if cap is None else str(cap)
        r = d.get("rate_per_day")
        rate = f" (~{r}/روز)" if r is not None else ""
        L.append(f"  {mark} {kind:<12} {d['n']:>3} / {cap_s:<4}{rate}  {d['why']}")
    L.append(f"  {v['note']}")
    L.append(f"  مرز: {v['boundary']}")
    return "\n".join(L)


def main(argv):
    v = judge()
    print(render(v))
    if "--write" in argv:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(v, ensure_ascii=False, indent=1),
                       encoding="utf-8")
        print(f"نوشته شد: {OUT}")
    if "--check" in argv and v["verdict"] == "OVER":
        print("بودجهٔ پیام شکسته شد: " + "، ".join(v["over"]))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
