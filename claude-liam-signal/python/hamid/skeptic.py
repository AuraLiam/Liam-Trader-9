"""شکاک — بازجویی زنجیره از E01 تا E25، هر ۱۰ دقیقه (دستور حمید، ۱ سپتامبر).

حمید: «تو باید آن آدم شکاک باشی که به همه چیز گیر می‌دهد تا بهت ثابت کنند
درست می‌گویند یا نتوانند ثابت کنند… از ایجنتی که هر ۱۵ دقیقه ۲۰۰ ارز برتر
را می‌آورد شروع به سؤال‌پرسیدن می‌کنی تا برسی به ایجنت آخری که سیگنال را
می‌فرستد… و سؤال ثابت نپرس.»

## چرا این ماژول لازم بود — و چرا فقط «سلامت» کافی نیست

پاسبان‌های موجود می‌پرسند «آیا کار می‌کند؟». شکاک می‌پرسد **«ثابت کن»**.
فرقش را همین هفته دیدیم: چرخهٔ حمید ۲۶ گام سبز داد و دیده‌بان هم گفت
«۹ سالم · ۰ خراب» — در حالی که همان اجرا هیچ‌چیز منتشر نکرده بود و
فایل‌هایش ۹ ساعت کهنه بودند. هر جزء درست جواب می‌داد؛ **نتیجه** غلط بود.

پس شکاک از خودِ انجین نمی‌پرسد حالت چطور است؛ **ردپایش را می‌شمارد**.

## چهار خانوادهٔ سؤال — همه شاهدمحور

| خانواده | سؤال | چه چیزی ردش می‌کند |
|---|---|---|
| **پوشش** | چند تا را واقعاً دیدی؟ | عددِ خروجی از سند کمتر است |
| **تازگی** | خروجی‌ات چقدر کهنه است؟ | از سقف قرارداد گذشته |
| **ردپا** | حکمت روی چند معاملهٔ بسته نشست؟ | صفر — یعنی وجودش قابل‌سنجش نیست |
| **نتیجه‌گیری** | خودِ عددت درست ساخته شده؟ | یکتایی، منبع کارمزد، توزیع دلیل |

خانوادهٔ چهارم مهم‌ترین است و همان چیزی است که حمید گفت: «شاید
نتیجه‌گیری درست انجام نمی‌شود». چهار عیبِ اندازه‌گیریِ همین هفته
(دو تعریف کارمزد · کلیدی که دو بازوی A/B را یکی می‌دید · پوشش ۲۶۱۱٪ ·
مترِ سخت‌گیرتر از قرارداد) همه از این جنس بودند و هیچ‌کدام را پاسبانِ
«آیا کار می‌کند» نمی‌گرفت.

## سؤال ثابت نپرس — چرخش قطعی

هر نوبت، از استخرِ سؤالِ هر انجین یکی انتخاب می‌شود با چرخشی که به
**شمارهٔ نوبت** گره خورده (قطعی و بازتولیدپذیر، نه تصادفی)، و انجینی که
کارنامه‌اش قرمز است یا نوبت قبل نتوانست ثابت کند **سؤال بیشتری** می‌گیرد.
یعنی فشار روی ضعف می‌رود، نه یکنواخت روی همه.

## آلارم فقط برای شکستِ پابرجا

یک «نتوانست ثابت کند» خبر نیست؛ ممکن است لحظه‌ای باشد. سه نوبتِ پیاپیِ
همان سؤال یعنی مشکل واقعی، و آن‌وقت از دروازهٔ آلارم (قانون ۰۷) رد
می‌شود. دفتر: `brain/skeptic-log.jsonl` (append-only).

## مرز

شکاک **هیچ دروازه‌ای را عوض نمی‌کند** و هیچ سیگنالی صادر یا وتو
نمی‌کند. فقط می‌پرسد، می‌شمارد، و ثبت می‌کند.

اجرا: `python3 -m hamid.skeptic [--write] [--telegram]`
"""
import json
import os
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
sys.path.insert(0, str(PY))
ROOT = PY.parent.parent
SIG = ROOT / "signals"
OUT = SIG / "skeptic.json"
LOG = ROOT / "brain" / "skeptic-log.jsonl"

FAIL_STREAK_ALARM = 3     # چند نوبتِ پیاپی تا آلارم
ROUND_MIN = 10            # کادنس اسمی (دقیقه) — برای شمارهٔ نوبت


def _j(rel, default=None):
    try:
        return json.loads((ROOT / rel).read_text(encoding="utf-8"))
    except Exception:                                # noqa: BLE001
        return default


def _age_min(rel, now):
    d = _j(rel, {}) or {}
    g = d.get("generated") or d.get("at")
    if isinstance(g, str):
        return None
    return round((now - g) / 60000) if g else None


def ok(q, evidence, detail=""):
    return {"q": q, "verdict": "PROVED", "evidence": evidence, "detail": detail}


def no(q, why, detail=""):
    return {"q": q, "verdict": "UNPROVED", "evidence": why, "detail": detail}


def na(q, why):
    """نه قبول نه رد — دادهٔ لازم نیست. صفر گرفتن این حالت، دروغ است."""
    return {"q": q, "verdict": "NO_DATA", "evidence": why, "detail": ""}


# ── استخر سؤال‌ها ────────────────────────────────────────────────────────
#
# هر سؤال یک تابع است که شواهد را **می‌شمارد**، نه اینکه حال بپرسد.

def q_breadth(now):
    lt = _j("signals/latest.json", {}) or {}
    n = lt.get("symbols") or 0
    return (ok if n >= 200 else no)(
        "چند نماد را واقعاً در آخرین اسکن دیدی؟",
        f"{n} نماد" if n else "خروجی اسکن پهنا اعلام نکرده",
        "سند می‌گوید ۲۰۰ (ممیزی ۳۰ اوت)")


def q_scout_sources(now):
    wl = _j("signals/watchlist.json", {}) or {}
    okc, err = len(wl.get("sources_ok") or []), len(wl.get("sources_err") or [])
    return (ok if okc >= 4 else no)(
        "چند منبع صرافی واقعاً جواب دادند؟",
        f"{okc} سالم · {err} خطا",
        "قاعدهٔ گشت: هر ردیف دست‌کم دو منبع")


def q_fresh(rel, cap, label):
    def f(now):
        a = _age_min(rel, now)
        if a is None:
            return na(f"خروجی {label} چقدر کهنه است؟", f"{rel} مهر ندارد یا نیست")
        return (ok if a <= cap else no)(
            f"خروجی {label} چقدر کهنه است؟", f"{a} دقیقه", f"سقف قرارداد {cap}")
    return f


def q_funnel_degenerate(now):
    """توزیعِ دلیلِ رد نباید تک‌قله باشد — دروازه‌ای که همیشه یک دلیل
    می‌آورد، یا واقعاً یک دروازه است یا بقیه اصلاً اجرا نمی‌شوند."""
    fn = _j("signals/funnel.json", {}) or {}
    top = fn.get("top_reasons") or {}
    if not top:
        return na("دلیلِ ردها متنوع است یا یک دلیل همه را می‌خورد؟",
                  "قیف دلیلی ثبت نکرده")
    tot = sum(top.values())
    share = max(top.values()) / tot if tot else 0
    return (ok if share < 0.8 else no)(
        "دلیلِ ردها متنوع است یا یک دلیل همه را می‌خورد؟",
        f"سهم دلیلِ غالب {share:.0%} از {tot}",
        "بالای ۸۰٪ یعنی بقیهٔ دروازه‌ها احتمالاً اصلاً به حرف نمی‌آیند")


def q_fingerprint(key, label):
    """حکمِ این انجین روی چند معاملهٔ بستهٔ اخیر ردپا گذاشته؟"""
    def f(now):
        try:
            from hamid.direction_autopsy import load
            rows = load("sig-")[-120:]
        except Exception as e:                       # noqa: BLE001
            return na(f"ردپای {label} روی معامله‌ها هست؟",
                      f"دفتر خوانده نشد: {type(e).__name__}")
        n = sum(1 for r in rows
                if (r.get("why") or {}).get(key) is not None)
        return (ok if n >= 10 else no)(
            f"ردپای {label} روی معامله‌ها هست؟",
            f"{n} از {len(rows)} معاملهٔ اخیر",
            "زیر ۱۰ یعنی اثرش قابل‌سنجش نیست")
    return f


def q_delivery_id(now):
    la = _j("signals/loop-audit.json", {}) or {}
    leaks = la.get("n_leaks")
    if leaks is None:
        return na("هر سیگنالِ رفته ردپای کامل دارد؟", "ممیز حلقه اجرا نشده")
    return (ok if leaks == 0 else no)(
        "هر سیگنالِ رفته ردپای کامل دارد؟",
        f"{leaks} نشتی از {la.get('n_closed_sig') or '?'} بسته")


def q_signal_sanity(now):
    """محتوای خودِ سیگنال‌های رفته — نه فقط این‌که رفتند.

    دستور حمید (۵ سپتامبر): «مرتب سیگنال‌های تلگرام رو چک کن که اگه
    خطایی توش بود سریع بررسی کنی و برطرف کنی.» دو سؤال قبلیِ E25
    ردپا و ضدتکرار را می‌سنجیدند — یعنی «رفت یا نه»، نه «درست بود یا
    نه». این سؤال خودِ عددها را می‌خواند.

    شش شرطِ سختِ همین ریپو، همه از سند خودِ پنل:
      · تایم‌فریم فقط ۱۵د/۵د (قانون ۱۱، `telegram.ALLOWED_TFS`)
      · ورود/استاپ/تارگت هر سه عددِ مثبت (قرارداد اجرا، ۲۰ اوت)
      · ترتیب قیمت‌ها با جهت بخواند (لانگ: استاپ < ورود < تارگت)
      · RR دست‌کم ۰.۸
      · وتوی روند: هر دو تایم بالا خلاف جهت = تخلف (دستور ۱۷ اوت)

    عمداً روی پنجرهٔ ۲۴ ساعت است نه کلِ تاریخ: متری که رفعِ ریشه هم
    سبزش نکند، آموزشِ نادیده‌گرفتن است (قانون ۰۷).
    """
    log = (_j("signals/telegram-log.json", {}) or {}).get("sent") or []
    lo = now - 24 * 3600 * 1000
    rows = [r for r in log if isinstance(r.get("at"), (int, float)) and r["at"] >= lo]
    if not rows:
        return na("سیگنال‌های رفتهٔ ۲۴ ساعت خطا داشتند؟", "ارسالی در پنجره نبود")
    faults = []
    for r in rows:
        e, sl, t1 = r.get("entry"), r.get("sl"), r.get("tp1")
        d, sym = r.get("dir"), r.get("sym")
        if r.get("tf") not in ("5m", "15m"):
            faults.append(f"{sym}: تایم‌فریم {r.get('tf')}")
        nums = all(isinstance(x, (int, float)) and x > 0 for x in (e, sl, t1))
        if not nums:
            faults.append(f"{sym}: ورود/استاپ/تارگت ناقص")
            continue
        if d == "LONG" and not sl < e < t1:
            faults.append(f"{sym}: ترتیب قیمت لانگ")
        if d == "SHORT" and not sl > e > t1:
            faults.append(f"{sym}: ترتیب قیمت شورت")
        if e != sl and abs(t1 - e) / abs(e - sl) < 0.8:
            faults.append(f"{sym}: RR زیر ۰.۸")
        opp = {"LONG": "down", "SHORT": "up"}.get(d)
        if opp and r.get("trend4") == opp and r.get("trend1") == opp:
            faults.append(f"{sym}: وتوی روند نقض شد")
    q = "سیگنال‌های رفتهٔ ۲۴ ساعت خطا داشتند؟"
    if faults:
        return no(q, f"{len(faults)} خطا در {len(rows)} ارسال",
                  " · ".join(faults[:4]))
    return ok(q, f"{len(rows)} ارسال، صفر خطا",
              "تایم‌فریم · استاپ/تارگت · ترتیب قیمت · RR · وتوی روند")


RECENT_H = 24            # پنجرهٔ حکم — پایین‌تر توضیح داده شده


def q_dedupe_contract(now):
    """قرارداد ضدتکرار — **از روی خودِ کد**، نه از روی سند.

    دو عیبِ اندازه‌گیری‌شدهٔ ۱ سپتامبر که این تابع را عوض کرد:

    ۱. **قراردادِ خیالی.** نسخهٔ قبلی عددها را سفت نوشته بود
       (۳س/۱۲س/سقف ۲ در ۱۲س) — همان چیزی که `trading-core.md` می‌گفت.
       ولی حمید ۲۷ اوت پنجره را از ۱۲ به ۶ ساعت آورد («تا سیگنال هست
       باید بدهد») و سند به‌روز نشد. نتیجه: ۶ «نقض» گزارش می‌شد که
       **۵تایش اصلاً نقض نبود** — بازرس علیه مشخصاتی می‌سنجید که کد
       هرگز اجرایش نمی‌کرد. حالا ثابت‌ها از `telegram` خوانده می‌شوند،
       پس مشخصات دیگر نمی‌تواند از کد جدا بیفتد.

    ۲. **متری که هرگز سبز نمی‌شود.** نسخهٔ قبلی کلِ تاریخ را می‌سنجید،
       پس یک نقضِ بسته‌شده تا ابد آلارم می‌داد. متری که رفعِ ریشه هم
       سبزش نکند، آموزشِ نادیده‌گرفتن است — دقیقاً همان چیزی که قانون
       ۰۷ بسته. حکم روی پنجرهٔ تازه است؛ تاریخ به‌عنوان زمینه گزارش
       می‌شود، نه به‌عنوان اتهامِ امروز.
    """
    from telegram import SKIP_TTL_MS, TTL_MS         # noqa: F401 — منبع واحد
    H = 3_600_000
    ttl_h = TTL_MS / H                               # پنجرهٔ هم‌استراتژی و سقف
    any_h = 3                                        # `_dup_any` / `_dup_pair`
    rows = sorted((_j("signals/telegram-log.json", {}) or {}).get("sent") or [],
                  key=lambda x: x.get("at") or 0)
    if not rows:
        return na("قرارداد ضدتکرار رعایت شده؟", "دفتر ارسال خالی است")
    last_any, last_pair, last_st, per = {}, {}, {}, {}
    bad, bad_recent = 0, 0
    for r in rows:
        t = r.get("at") or 0
        ak = (r.get("sym"), r.get("dir"), r.get("tf"))
        pk = (r.get("sym"), r.get("dir"))
        sk = ak + (r.get("name"),)
        hits = per.setdefault(r.get("sym"), [])
        if ((ak in last_any and t - last_any[ak] < any_h * H)
                or (pk in last_pair and t - last_pair[pk] < any_h * H)
                or (sk in last_st and t - last_st[sk] < ttl_h * H)
                or len([x for x in hits if t - x < ttl_h * H]) >= 2):
            bad += 1
            if now - t <= RECENT_H * H:
                bad_recent += 1
        last_any[ak] = last_pair[pk] = last_st[sk] = t
        hits.append(t)
    recent = [r for r in rows if now - (r.get("at") or 0) <= RECENT_H * H]
    return (ok if bad_recent == 0 else no)(
        "قرارداد ضدتکرار رعایت شده؟",
        f"{bad_recent} نقض از {len(recent)} ارسالِ {RECENT_H} ساعت اخیر "
        f"(کل تاریخ: {bad} از {len(rows)})",
        f"کلید بی‌استراتژی {any_h}س · جفت {any_h}س · هم‌استراتژی "
        f"{ttl_h:g}س · سقف ۲ در {ttl_h:g}س — ثابت‌ها از خودِ telegram.py")


def q_unique_rows(now):
    """درسِ ۲۴ اوت: CI فرض می‌کند هر ردیف یک مشاهدهٔ مستقل است."""
    try:
        from hamid.direction_autopsy import load, _identity
    except Exception as e:                           # noqa: BLE001
        return na("ردیف‌های دفتر یکتا هستند؟", f"{type(e).__name__}")
    rows = load("sig-")
    ids = [_identity(r) for r in rows]
    dup = len(ids) - len(set(ids))
    return (ok if dup == 0 else no)(
        "ردیف‌های دفتر یکتا هستند؟",
        f"{dup} تکراری از {len(ids)}",
        "ردیف تکراری بازهٔ اطمینان را به‌دروغ تنگ می‌کند")


def q_fee_single_source(now):
    """درسِ ۳۰ اوت: دو تعریفِ «خالص» در یک نمونه، خودش مخدوش‌کننده است."""
    try:
        from hamid.direction_autopsy import load
        rows = load("sig-")
    except Exception as e:                           # noqa: BLE001
        return na("خالصِ گزارش‌شده از منبع واحد کارمزد است؟", f"{type(e).__name__}")
    # سؤالِ درست: «آیا **تحلیل** بازمحاسبه می‌کند؟» — نه «آیا دفتر یکدست
    # است؟». دفتر هرگز یکدست نمی‌شود چون ردیف‌های گذشته بازنویسی
    # نمی‌شوند (قانون ضد-merge)، پس نسخهٔ قبلیِ این سؤال متری بود که هیچ
    # رفعی سبزش نمی‌کرد — و متری که همیشه قرمز است، آموزشِ نادیده‌گرفتن
    # است. اختلافِ تاریخی به‌عنوان زمینه گزارش می‌شود.
    bad = [r for r in rows if r.get("R") is not None
           and r.get("_fee_r") is not None
           and abs(round(r["R"] - r["_fee_r"], 4) - (r.get("R_net") or 0)) > 1e-3]
    diff = [abs(r["_R_net_stored"] - r["R_net"]) for r in rows
            if r.get("_R_net_stored") is not None and r.get("R_net") is not None]
    med = statistics.median(diff) if diff else 0.0
    return (ok if not bad else no)(
        "خالصِ گزارش‌شده از منبع واحد کارمزد است؟",
        f"{len(bad)} ردیف از {len(rows)} بازمحاسبه‌نشده "
        f"(اختلاف تاریخیِ دفتر: میانهٔ {med:.3f}R — بازنویسی نمی‌شود)",
        "معیار: تحلیل باید بازمحاسبه کند، نه اینکه دفترِ گذشته یکدست شود")


def q_scorecard_red(now):
    sc = _j("signals/scorecard.json", {}) or {}
    cards = sc.get("cards") or []
    if not cards:
        return na("کارنامهٔ انجین‌ها ساخته شده؟", "scorecard.json نیست")
    red = [c["id"] for c in cards
           if c.get("verdict") in ("FAULT", "NEGATIVE", "UNDER")]
    return (ok if len(red) <= 4 else no)(
        "چند انجین نمرهٔ قرمز دارند؟",
        f"{len(red)} قرمز: {'، '.join(red[:8])}",
        "بالای ۴ یعنی مشکل سامانه‌ای نه موردی")


def q_state_bus(now):
    ss = _j("signals/system-state.json", {}) or {}
    v = ss.get("verdict")
    if not v:
        return na("گذرگاه وضعیت چه می‌گوید؟", "system-state.json نیست")
    return (ok if v == "HEALTHY" else no)(
        "گذرگاه وضعیت چه می‌گوید؟",
        f"{v} · {ss.get('n_faults', '?')} عیب از {ss.get('n_files', '?')} فایل")


def q_orphans(now):
    reg = _j("config/state_registry.json", {}) or {}
    files = set(reg.get("files", reg))
    have = {p.name for p in SIG.glob("*.json")}
    orph = sorted(have - files)
    return (ok if not orph else no)(
        "فایلِ بی‌مالک در signals هست؟",
        f"{len(orph)} یتیم: {'، '.join(orph[:5])}" if orph else "هیچ",
        "قانون ۱۳: هر فایل باید مالک و سقف کهنگی داشته باشد")


# نگاشت انجین → استخر سؤال. ترتیب همان ترتیبِ زنجیره: از جهانِ نمادها
# تا فرستنده — دقیقاً مسیری که حمید خواست.
BANK = [
    ("E01", "جهانِ نمادها", [q_breadth, q_scout_sources,
                             q_fresh("signals/watchlist.json", 360, "گشت")]),
    ("E02", "کیفیت داده", [q_fresh("signals/depth-health.json", 360, "عمق")]),
    ("E03", "دامیننس تتر", [q_fresh("signals/dominance.json", 45, "دامیننس"),
                            q_fingerprint("dom_tf_regime", "رژیم دامیننس")]),
    ("E06", "بیت‌کوین", [q_fresh("signals/btc-patterns.json", 120, "الگوهای BTC")]),
    ("E07", "ساختار", [q_fingerprint("supertrend_align", "هم‌ترازی ساختار")]),
    ("E08", "اردر بلاک", [q_fingerprint("ob_align", "هم‌ترازی OB"),
                          q_fresh("signals/ob-radar.json", 240, "رادار OB")]),
    ("E09", "کندل", [q_fingerprint("pattern_align", "الگوی کندلی")]),
    ("E10", "نقدینگی", [q_fresh("signals/top-liquidity.json", 360, "نقدینگی")]),
    ("E17", "کمیتهٔ سیگنال", [q_funnel_degenerate,
                              q_fresh("signals/latest.json", 45, "اسکن")]),
    ("E21", "حافظه", [q_fingerprint("exp_used", "لایهٔ تجربه")]),
    ("E23", "ناظر", [q_state_bus, q_orphans]),
    ("E25", "تحویل", [q_delivery_id, q_dedupe_contract, q_signal_sanity]),
    # بازرسیِ نتیجه‌گیری — همان چیزی که حمید گفت باید به آن شک کرد
    ("**", "بازرسیِ نتیجه‌گیری", [q_unique_rows, q_fee_single_source,
                                  q_scorecard_red]),
]


def where():
    """کجا اجرا شده — رانرِ تولید یا نشستِ محلی.

    این تفکیک آرایشی نیست. سؤال‌های «تازگی» سنِ فایل‌های **همین
    درخت** را می‌سنجند؛ روی رانر یعنی سنِ واقعیِ تولید، ولی در یک
    نشستِ محلی یعنی «آخرین بار کِی fetch کردم». اندازه‌گیریِ ۱ سپتامبر:
    شکاکِ محلی گفت دامیننس ۴۱۹ دقیقه کهنه است، در حالی که همان لحظه
    گذرگاه وضعیت ۳ دقیقه می‌دید — چون بین آن دو، fetch اتفاق افتاده
    بود. هیچ‌کدام دروغ نگفتند؛ دو چیزِ متفاوت را می‌سنجیدند.
    """
    return "ci" if os.environ.get("GITHUB_ACTIONS") else "local"


def _history():
    """شمارشِ شکستِ پیاپی — **فقط از نوبت‌های رانر**.

    وگرنه یک اجرای اکتشافیِ محلی (روی درختِ کهنه) می‌تواند شمارنده را
    باد کند و آلارمِ تلگرام را دربارهٔ چیزی که اصلاً خراب نیست شلیک
    کند. ردیفِ بی‌برچسب مالِ پیش از ۱ سپتامبر است و محافظه‌کارانه
    رانر فرض می‌شود.
    """
    out = {}
    try:
        for line in LOG.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("{"):
                r = json.loads(line)
                if r.get("env", "ci") != "ci":
                    continue
                for a in r.get("answers") or []:
                    k = (a["engine"], a["q"])
                    out[k] = out.get(k, 0) + (1 if a["verdict"] == "UNPROVED" else -99)
    except Exception:                                # noqa: BLE001
        pass
    return {k: max(0, v) for k, v in out.items()}


def interrogate(now_ms=None, rnd=None):
    """یک نوبت بازجویی — از E01 تا E25، با سؤالِ چرخشی."""
    now = now_ms or int(time.time() * 1000)
    rnd = now // (ROUND_MIN * 60_000) if rnd is None else rnd
    hist = _history()
    sc = {c["id"]: c for c in (_j("signals/scorecard.json", {}) or {}).get("cards") or []}
    answers = []
    for eid, label, pool in BANK:
        # فشار روی ضعف: قرمز در کارنامه، یا سابقهٔ «نتوانست ثابت کند»
        # روی همین انجین ⇒ سؤال بیشتر. (نسخهٔ اول این‌جا
        # `any(... for _ in ())` داشت که همیشه False است — یعنی سابقه
        # اصلاً خوانده نمی‌شد و فشار فقط از کارنامه می‌آمد.)
        weak = (sc.get(eid, {}).get("verdict") in ("FAULT", "NEGATIVE", "UNDER")
                or any(k[0] == eid and v > 0 for k, v in hist.items()))
        n_ask = 2 if (weak or eid == "**") else 1
        n_ask = min(n_ask, len(pool))
        for i in range(n_ask):
            fn = pool[(rnd + i) % len(pool)]
            try:
                a = fn(now)
            except Exception as e:                   # noqa: BLE001
                a = na("سؤال اجرا نشد", f"{type(e).__name__}: {e}")
            a["engine"], a["label"] = eid, label
            a["streak"] = hist.get((eid, a["q"]), 0) + (
                1 if a["verdict"] == "UNPROVED" else 0)
            answers.append(a)
    proved = sum(1 for a in answers if a["verdict"] == "PROVED")
    unproved = [a for a in answers if a["verdict"] == "UNPROVED"]
    persistent = [a for a in unproved if a["streak"] >= FAIL_STREAK_ALARM]
    return {
        "generated": now, "round": rnd, "panel": "لیام تریدر ۹",
        "n": len(answers), "proved": proved, "unproved": len(unproved),
        "no_data": len(answers) - proved - len(unproved),
        "answers": answers, "persistent": persistent,
        "boundary": ("شکاک هیچ دروازه‌ای را عوض نمی‌کند و سیگنالی صادر یا "
                     "وتو نمی‌کند — فقط می‌پرسد، می‌شمارد، ثبت می‌کند."),
    }


def caption(res):
    p = res.get("persistent") or []
    if not p:
        return None
    L = [f"🕵️ شکاک — {len(p)} مورد که {FAIL_STREAK_ALARM} نوبت پیاپی "
         f"ثابت نشد", ""]
    for a in p:
        L.append(f"• {a['engine']} {a['label']}")
        L.append(f"    «{a['q']}»")
        L.append(f"    شواهد: {a['evidence']}")
        if a.get("detail"):
            L.append(f"    {a['detail']}")
        L.append("")
    L.append(f"از {res['n']} سؤال این نوبت: {res['proved']} ثابت · "
             f"{res['unproved']} نشد · {res['no_data']} بی‌داده")
    L.append("")
    try:
        import telegram as tg                        # ماژول ریشه، نه hamid.*
        L.append(getattr(tg, "PANEL_NAME", "لیام تریدر ۹"))
    except Exception:                                # noqa: BLE001
        L.append("لیام تریدر ۹")
    return "\n".join(L)


def main(argv=()):
    res = interrogate()
    print(f"### شکاک — نوبت {res['round']} · {res['proved']} ثابت · "
          f"{res['unproved']} نشد · {res['no_data']} بی‌داده\n")
    cur = None
    for a in res["answers"]:
        if a["engine"] != cur:
            cur = a["engine"]
            print(f"— {a['engine']} {a['label']}")
        mark = {"PROVED": "✓", "UNPROVED": "✗", "NO_DATA": "○"}[a["verdict"]]
        print(f"  {mark} {a['q']}")
        print(f"      {a['evidence']}"
              + (f"  ({a['detail']})" if a["detail"] else "")
              + (f"  [شکستِ پیاپی {a['streak']}]" if a["streak"] >= 2 else ""))
    print(f"\n### مرز\n  {res['boundary']}")
    if "--write" in argv:
        OUT.parent.mkdir(exist_ok=True)
        OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1),
                       encoding="utf-8")
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"generated": res["generated"],
                                "round": res["round"], "env": where(),
                                "answers": [{"engine": a["engine"], "q": a["q"],
                                             "verdict": a["verdict"]}
                                            for a in res["answers"]]},
                               ensure_ascii=False) + "\n")
        print(f"\n  نوشته شد: {OUT.name}")
    if "--telegram" in argv and res.get("persistent"):
        # نشستِ محلی حق ندارد به حمید پیام بدهد: سؤال‌های تازگی این‌جا
        # سنِ درختِ محلی را می‌سنجند نه تولید را، پس آلارمش می‌تواند
        # دربارهٔ چیزی باشد که اصلاً خراب نیست. (قانون ۰۷: آلارم فقط
        # برای چیزی که حمید می‌تواند و باید رویش عمل کند.)
        if where() != "ci":
            print("  تلگرام: نرفت (اجرای محلی — آلارم فقط از رانر)")
            return 0
        from hamid import alert_gate
        key = "skeptic|" + "|".join(sorted(f"{a['engine']}:{a['q'][:20]}"
                                           for a in res["persistent"]))
        sent, why = alert_gate.send("شکاک", key, caption(res))
        print(f"  تلگرام: {'رفت' if sent else 'نرفت'} ({why})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
