"""ناظر پیش‌بینی دامیننس — دستور حمید، ۱۷ اوت.

هر نوبتِ اتاق دامیننس (زنجیرهٔ رادار، گام مؤثر ~۳-۵ دقیقه) دو کار می‌کند:

۱. **صدور پیش‌بینی با دلیل** — تحلیلگر (کد قطعی، قانون ۰۶) برای USDT.D و
   BTC.D مسیر احتمالی افق‌های HORIZONS_MIN را می‌گوید (UP/DOWN/FLAT) و
   موظف است دلایلش را بنویسد. «ایجنت» تأییدکننده همین‌جاست: پیش‌بینی
   جهت‌دار فقط با ≥۲ شاهد هم‌جهت و دادهٔ تازه (≤۱۰ دقیقه) ثبت می‌شود؛
   دادهٔ کهنه یا شواهد متضاد = NO_FORECAST (قانون ۱ — حدس ممنوع).

۲. **نمره‌دهی پیش‌بینی‌های سررسیدشده** — پیش‌بینی قبلی با حرکت واقعی
   سنجیده و در کارنامه ثبت می‌شود: تعداد، اصابت، درصد اصابت به تفکیک
   متریک و افق. خطا پنهان نمی‌شود — کارنامه روی signals/dominance.json
   می‌نشیند و پنل همان را نشان می‌دهد.

آستانه‌ها: حرکت واقعی = |Δ| ≥ آستانهٔ همان افق؛ زیر آن FLAT است. آستانه
از **نوسانِ واقعیِ همان افق در سری** می‌آید (`horizon_noise`) با NOISE
به‌عنوان کفِ مطلق — چون ۰.۰۲ واحد در ۳۰ دقیقه و در ۲۴ ساعت دو چیزند.
دفتر: brain/dom-forecasts.json (open + دنبالهٔ graded + score تجمیعی).
"""
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
LEDGER = ROOT / "brain" / "dom-forecasts.json"

# افق‌ها (بازنگری ۲۹ اوت، بند ۴ پرامپت). اندازه‌گیری همان روز: روی
# ۳۰د و ۱۲۰د موتور در ۸۷.۶٪ نوبت‌ها مجبور بود FLAT بگوید، چون دامیننس
# در آن بازه‌ها عمدتاً لرزش است نه حرکت. دامیننس روی ۴س و روزانه روند
# دارد، پس دو افق بلند اضافه شد تا موتور جایی حرف بزند که حرفی هست.
# افق‌های کوتاه حذف نشدند — مقایسه‌شان همان بنچمارکِ لازم را می‌سازد.
HORIZONS_MIN = (30, 120, 240, 1440)

# آستانهٔ «حرکت معنادار» — از این پس نسبت به نوسانِ واقعیِ همان افق،
# نه عددِ ثابت. دلیل: ۰.۰۲ واحد در ۳۰ دقیقه یک چیز است و در ۲۴ ساعت
# چیز دیگری؛ با آستانهٔ ثابت، افقِ بلند تقریباً همیشه «حرکت» می‌دید و
# افقِ کوتاه تقریباً هیچ‌وقت. NOISE کفِ مطلق می‌ماند تا در بازارِ
# بی‌نوسان، لرزشِ ذره‌ای «حرکت» شمرده نشود.
NOISE = 0.02          # کفِ مطلق؛ زیر این، حرکت نیست — لرزش است
NOISE_VOL_MULT = 0.5  # آستانه = بیشینهٔ(NOISE، این ضریب × نوسانِ افق)
VOL_MIN_N = 12        # زیر این تعداد پنجره، نوسان را نمی‌سنجیم — کف می‌ماند
VOL_MAX_WINDOWS = 240  # سقف نمونه‌گیری؛ سری ۴۰۰۰ نقطه‌ای را کند نکند
FRESH_MS = 10 * 60000  # دادهٔ کهنه‌تر از ۱۰ دقیقه = پیش‌بینی ممنوع
KEEP_GRADED = 400      # دنبالهٔ کارنامه، برای عیب‌یابی

# ── حلقهٔ تجربه (سؤال حمید، ۲۵ اوت: «مگر حافظه ندارد که کمتر اشتباه
# کند؟») — تا امروز کارنامه فقط نوشته می‌شد و make_forecast هرگز
# نمی‌خواندش؛ BTC.D|120m با ۱۷.۹٪ اصابت از ۸۴ نمونه همان ادعا را هر
# نوبت تکرار می‌کرد. قاعدهٔ پیش‌ثبت‌شده (الگوی دروازهٔ تجربهٔ قانون ۰۳):
# ادعای جهت‌داری که در پنجرهٔ اخیرِ کارنامه سابقهٔ بدِ نمونه‌دار دارد
# پس گرفته می‌شود (FLAT با دلیل صریح)؛ و هر REPROBE_EVERY بارِ متوالی،
# یک بار ادعای اصلی عمداً صادر می‌شود تا نمونه‌گیری نمیرد و اگر رژیم
# عوض شد، کارنامه بتواند دوباره خوب شود.
HIST_WINDOW = 60       # فقط nِ آخر هر سطل — گناه قدیمی ابدی نیست
BAD_N = 20             # زیر این نمونه، حکم نمی‌دهیم (نمونهٔ کم دروغ می‌گوید)
BAD_HIT_PCT = 30.0     # بدتر از کف شانس سه‌حالته (~۳۳٪) = سیستماتیک خطا
REPROBE_EVERY = 5      # هر ۵ سرکوبِ متوالی، یک بازآزمایی


def bucket_stats(st, metric, horizon, path, window=HIST_WINDOW):
    """کارنامهٔ شمرده‌شدهٔ همین ادعا (متریک|افق|جهت) در پنجرهٔ اخیر.
    عدد ساخته نمی‌شود — فقط شمارش ردیف‌های نمره‌خورده."""
    rows = [g for g in (st or {}).get("graded", [])
            if g.get("metric") == metric and g.get("horizon_min") == horizon
            and g.get("path") == path and g.get("result") in ("HIT", "MISS")]
    rows = rows[-window:]
    n = len(rows)
    if not n:
        return {"n": 0, "hit_pct": None}
    hit = sum(1 for g in rows if g["result"] == "HIT")
    return {"n": n, "hit_pct": round(100 * hit / n, 1)}


def horizon_noise(points, key, horizon_min):
    """آستانهٔ «حرکت معنادار» برای همین متریک و همین افق — از خودِ سری.

    چرا عدد ثابت غلط بود (اندازه‌گیری ۲۹ اوت): ۰.۰۲ واحد در ۳۰ دقیقه
    حرکتی بزرگ است و در ۲۴ ساعت تقریباً هیچ. با آستانهٔ ثابت، افقِ بلند
    عملاً هرگز FLAT نمی‌دید و افقِ کوتاه تقریباً همیشه — یعنی نمرهٔ دو
    افق اصلاً یک چیز را نمی‌سنجید و مقایسه‌شان بی‌معنا بود.

    روش: بزرگی حرکتِ واقعیِ همین افق در گذشتهٔ سری شمرده می‌شود و
    میانه‌اش گرفته می‌شود (میانه، نه میانگین — یک جهشِ خبری نباید
    آستانهٔ کل دوره را بالا ببرد). آستانه = بیشینهٔ(کفِ مطلق،
    ضریب × میانه).

    نمونهٔ کم = آستانه همان کفِ مطلق؛ عدد ساخته نمی‌شود (قانون ۱).
    خروجی: (آستانه، تعداد پنجره، میانهٔ |Δ| یا None)."""
    pts = [p for p in (points or []) if key in p]
    if len(pts) < VOL_MIN_N + 1:
        return NOISE, 0, None
    span = horizon_min * 60000
    tol = max(span * 0.2, 15 * 60000)
    times = [p["t"] for p in pts]
    step = max(1, len(pts) // VOL_MAX_WINDOWS)
    deltas = []
    j = 0
    for i in range(0, len(pts), step):
        target = times[i] - span
        if target < times[0]:
            continue
        while j + 1 < len(pts) and abs(times[j + 1] - target) <= abs(times[j] - target):
            j += 1
        # j ممکن است از هدفِ این i جلو افتاده باشد وقتی step بزرگ است
        best = min(range(max(0, j - 2), min(len(pts), j + 3)),
                   key=lambda x: abs(times[x] - target))
        if abs(times[best] - target) > tol:
            continue
        deltas.append(abs(pts[i][key] - pts[best][key]))
    if len(deltas) < VOL_MIN_N:
        return NOISE, len(deltas), None
    deltas.sort()
    m = len(deltas)
    med = (deltas[m // 2] if m % 2 else (deltas[m // 2 - 1] + deltas[m // 2]) / 2)
    return round(max(NOISE, NOISE_VOL_MULT * med), 4), m, round(med, 4)


MIN_P_N = 25          # زیر این نمونه، احتمال چاپ نمی‌شود (شمارش کم دروغ می‌گوید)


def probabilities(st, metric, horizon, path, ev_n=None, window=HIST_WINDOW):
    """احتمالِ سه‌حالته از **شمارشِ دفتر** — ساخته نمی‌شود (بند ۵، ۲۹ اوت).

    چرا برچسب کافی نیست: «UP» و «UP» دو ادعای هم‌ارز به نظر می‌رسند، ولی
    UP با چهار شاهد هم‌جهت و UP با دو شاهد، تاریخچهٔ متفاوتی دارند. عدد
    کالیبره این تفاوت را نشان می‌دهد و — برخلاف برچسب — با نمرهٔ برایر
    قابل سنجش است.

    روش: ردیف‌های نمره‌خوردهٔ همان سطل شمرده می‌شوند و نسبتِ نتیجهٔ
    واقعی (UP/DOWN/FLAT) برگردانده می‌شود. اول سطلِ دقیق (با شمار شواهد)؛
    اگر نمونه‌اش کم بود، سطلِ درشت‌تر (بدون شمار شواهد). اگر باز هم کم
    بود، None با دلیل — نه عددِ خوش‌بینانه."""
    def _rows(with_ev):
        out = []
        for g in (st or {}).get("graded", []):
            if (g.get("metric") != metric or g.get("horizon_min") != horizon
                    or g.get("path") != path
                    or g.get("real_path") not in ("UP", "DOWN", "FLAT")):
                continue
            if with_ev and g.get("ev_n") != ev_n:
                continue
            out.append(g)
        return out[-window:]

    rows = _rows(True) if ev_n is not None else []
    bucket = "دقیق (با شمار شواهد)"
    if len(rows) < MIN_P_N:
        rows = _rows(False)
        bucket = "درشت (بدون شمار شواهد)"
    n = len(rows)
    if n < MIN_P_N:
        return {"p": None, "n": n,
                "why": f"نمونه {n} < {MIN_P_N} — احتمال شمرده نمی‌شود (قانون ۱)"}
    cnt = {"UP": 0, "DOWN": 0, "FLAT": 0}
    for g in rows:
        cnt[g["real_path"]] += 1
    return {"p": {k: round(v / n, 3) for k, v in cnt.items()},
            "n": n, "bucket": bucket}


def brier(p, real):
    """نمرهٔ برایر سه‌حالته: میانگین مربعِ خطای احتمال. کمتر = بهتر.

    مرجعِ خواندنش: حدسِ کاملاً بی‌اطلاع (⅓ برای هر حالت) نمرهٔ ۰.۶۶۷
    می‌گیرد. عددِ بدون این مرجع، معنا ندارد."""
    if not p or real not in ("UP", "DOWN", "FLAT"):
        return None
    return round(sum((p.get(k, 0) - (1.0 if k == real else 0.0)) ** 2
                     for k in ("UP", "DOWN", "FLAT")), 4)


def _load():
    try:
        d = json.loads(LEDGER.read_text())
        return {"open": d.get("open") or [], "graded": d.get("graded") or [],
                "score": d.get("score") or {}, "probe": d.get("probe") or {}}
    except Exception:                                # noqa: BLE001
        return {"open": [], "graded": [], "score": {}, "probe": {}}


def _save(st):
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    st["graded"] = st["graded"][-KEEP_GRADED:]
    LEDGER.write_text(json.dumps(st, ensure_ascii=False))


def _evidence(metric, chg1, chg4, trend1, trend4):
    """شواهد جهت‌دار؛ هر شاهد یک (جهت، دلیل فارسی)."""
    ev = []
    if chg1 is not None and abs(chg1) >= 0.05:
        ev.append(("UP" if chg1 > 0 else "DOWN",
                   f"دلتای ۱س {metric} = {chg1:+.3f}"))
    if chg4 is not None and abs(chg4) >= 0.15:
        ev.append(("UP" if chg4 > 0 else "DOWN",
                   f"دلتای ۴س {metric} = {chg4:+.3f}"))
    if trend1 in ("up", "down"):
        ev.append(("UP" if trend1 == "up" else "DOWN",
                   f"ساختار ۱س {metric}: {trend1}"))
    if trend4 in ("up", "down"):
        ev.append(("UP" if trend4 == "up" else "DOWN",
                   f"ساختار ۴س {metric}: {trend4}"))
    return ev


def make_forecast(points, struct, now_ms=None, st=None):
    """پیش‌بینی این نوبت؛ دلیل اجباری است. برمی‌گرداند لیست (شاید خالی).

    st (دفتر کارنامه) اگر داده شود، حلقهٔ تجربه فعال است: ادعای جهت‌دار
    با سابقهٔ بدِ نمونه‌دار پس گرفته می‌شود (بالا، ثابت‌های HIST_*)."""
    if not points:
        return []
    now = now_ms or int(time.time() * 1000)
    if now - points[-1]["t"] > FRESH_MS:
        return []                       # دادهٔ کهنه — قانون ۱
    su = (struct or {}).get("usdt") or {}
    sb = (struct or {}).get("btc_d") or {}

    def _chg(key, minutes):
        t0 = points[-1]["t"] - minutes * 60000
        past = min(points, key=lambda p: abs(p["t"] - t0))
        if abs(past["t"] - t0) > minutes * 60000:
            return None
        return round(points[-1][key] - past[key], 3)

    out = []
    for metric, key, s in (("USDT.D", "u", su), ("BTC.D", "b", sb)):
        t4 = s.get("trend_4h")
        t4 = t4 if t4 in ("up", "down", "range") else None
        ev = _evidence(metric, _chg(key, 60), _chg(key, 240),
                       s.get("trend_1h"), t4)
        ups = [r for d, r in ev if d == "UP"]
        downs = [r for d, r in ev if d == "DOWN"]
        if len(ups) >= 2 and not downs:
            path, reasons = "UP", ups
        elif len(downs) >= 2 and not ups:
            path, reasons = "DOWN", downs
        elif ev:
            path = "FLAT"
            reasons = [f"شواهد ناهم‌جهت یا ناکافی ({len(ups)}↑/{len(downs)}↓)"]
        else:
            path, reasons = "FLAT", ["هیچ شاهد جهت‌داری نیست"]
        ev_n = len(ups) if path == "UP" else (
            len(downs) if path == "DOWN" else len(ev))
        for h in HORIZONS_MIN:
            f = {"made": now, "due": now + h * 60000, "metric": metric,
                 "key": key, "horizon_min": h, "path": path,
                 "base": points[-1][key], "reasons": list(reasons),
                 "ev_n": ev_n}
            # احتمال کالیبره کنارِ برچسب (بند ۵) — از شمارش دفتر، وگرنه None
            if st is not None:
                pr = probabilities(st, metric, h, path, ev_n)
                f["p"] = pr.get("p")
                f["p_n"] = pr.get("n")
                if pr.get("p") is None:
                    f["p_why"] = pr.get("why")
                else:
                    f["p_claim"] = pr["p"].get(path)
                    f["p_bucket"] = pr.get("bucket")
            if st is not None and path in ("UP", "DOWN"):
                hist = bucket_stats(st, metric, h, path)
                f["hist"] = hist
                if (hist["n"] >= BAD_N and hist["hit_pct"] is not None
                        and hist["hit_pct"] < BAD_HIT_PCT):
                    pk = f"{metric}|{h}|{path}"
                    cnt = st.setdefault("probe", {}).get(pk, 0) + 1
                    st["probe"][pk] = cnt
                    if cnt % REPROBE_EVERY == 0:
                        f["reprobe"] = True
                        f["reasons"].append(
                            f"بازآزمایی {cnt}: ادعا با وجود کارنامهٔ بد "
                            "عمداً صادر شد تا نمونه‌گیری زنده بماند")
                    else:
                        # بازنگری ۲۹ اوت (بند ۱ پرامپت) — تلهٔ خودتقویت‌شونده:
                        # نسخهٔ قبل ادعای بدکارنامه را به FLAT تنزل می‌داد.
                        # نتیجه‌اش مارپیچ بود: تنزل → FLAT بیشتر → کارنامهٔ
                        # جهت‌دار نمونهٔ تازه نمی‌گرفت → همان کارنامهٔ بد
                        # ابدی می‌شد. اندازه‌گیری: ۸۷.۶٪ همهٔ پیش‌بینی‌ها
                        # FLAT شده بود و فقط ۴۹ ادعای جهت‌دار در کل دفتر
                        # مانده بود.
                        #
                        # حالا ادعا **سرِ جایش می‌ماند** ولی با وزن اعتمادِ
                        # کم و برچسب صریح. مصرف‌کننده می‌تواند نادیده‌اش
                        # بگیرد؛ ولی کارنامه نمونهٔ تازه می‌گیرد و اگر رژیم
                        # عوض شد، خودش خوب می‌شود. حکم عوض نمی‌شود، وزنش
                        # عوض می‌شود — همان تفاوت «شاهد» و «دروازه».
                        f["low_confidence"] = True
                        f["confidence"] = 0.25
                        f["reasons"] = [
                            f"ادعای {path} با اعتماد کم صادر شد — کارنامهٔ "
                            f"همین ادعا در {hist['n']} نوبت اخیر فقط "
                            f"{hist['hit_pct']}٪ اصابت داشت؛ حکم پس گرفته "
                            "نشد تا نمونه‌گیری زنده بماند (بند ۱، ۲۹ اوت)"
                        ] + [f"شاهد: {r}" for r in reasons[:2]]
            out.append(f)
    return out


def grade_due(st, points, now_ms=None):
    """پیش‌بینی‌های سررسیدشده را با واقعیت می‌سنجد و کارنامه را به‌روز می‌کند."""
    now = now_ms or int(time.time() * 1000)
    still, graded_now = [], 0
    for f in st["open"]:
        if f["due"] > now:
            still.append(f)
            continue
        actual = min(points, key=lambda p: abs(p["t"] - f["due"])) if points else None
        if actual is None or abs(actual["t"] - f["due"]) > 15 * 60000:
            f["result"] = "UNGRADABLE"   # دادهٔ آن لحظه را نداریم — جعل نمی‌کنیم
            st["graded"].append(f)
            continue
        delta = round(actual[f["key"]] - f["base"], 3)
        # آستانه از نوسانِ همان افق می‌آید، نه از عددِ ثابت (بند ۴، ۲۹ اوت).
        # روی خودِ ردیف ثبت می‌شود تا نمره بعداً قابل بازتولید باشد.
        thr, vol_n, vol_med = horizon_noise(points, f["key"], f["horizon_min"])
        f["noise_used"], f["noise_windows"] = thr, vol_n
        if vol_med is not None:
            f["noise_median_move"] = vol_med
        real = "FLAT" if abs(delta) < thr else ("UP" if delta > 0 else "DOWN")
        f["actual_delta"], f["real_path"] = delta, real
        f["result"] = "HIT" if real == f["path"] else "MISS"
        # نمرهٔ برایر روی همان احتمالی که *قبل از* دیدن نتیجه چاپ شده بود
        bs = brier(f.get("p"), real)
        if bs is not None:
            f["brier"] = bs
        st["graded"].append(f)
        k = f"{f['metric']}|{f['horizon_min']}m"
        sc = st["score"].setdefault(k, {"n": 0, "hit": 0})
        sc["n"] += 1
        sc["hit"] += 1 if f["result"] == "HIT" else 0
        if bs is not None:
            sc["brier_sum"] = round(sc.get("brier_sum", 0.0) + bs, 4)
            sc["brier_n"] = sc.get("brier_n", 0) + 1
        graded_now += 1
    st["open"] = still
    return graded_now


def scoreboard(st):
    """کارنامه — با تفکیکِ اجباریِ «ادعای جهت‌دار» از «گفتم تکان نمی‌خورد».

    اندازه‌گیری ۲۹ اوت که این تفکیک را لازم کرد: نرخ اصابتِ کل برای
    USDT.D|30m ‏۷۳.۵٪ بود و همین عدد روی گزارش ساعتی به‌عنوان اعتبارنامه
    چاپ می‌شد. ولی **۸۷.۶٪ همهٔ پیش‌بینی‌ها FLAT بودند** و دامیننس در
    ۳۰ دقیقه معمولاً تکان معناداری نمی‌خورد؛ یعنی آن ۷۳.۵٪ عمدتاً پاداشِ
    گفتنِ «تغییری نمی‌کند» بود، نه تشخیص مسیر.

    دو عددی که واقعیت را نشان می‌دهند و از این پس کنار هم می‌آیند:

      · `dir_*`  — فقط ادعاهای UP/DOWN. سنجش روی ۴۹ ادعا: ۳۰.۶٪ اصابت،
        یعنی **زیر شانسِ تصادفیِ سه‌حالته (~۳۳٪)**.
      · `skill`  — اصابت منهای بنچمارکِ «همیشه بگو FLAT». برای
        USDT.D|30m این عدد **−۳.۹** بود: موتور از سکوتِ محض هم بدتر.

    عددی که بنچمارک ندارد، مهارت را اثبات نمی‌کند — فقط توزیعِ بازار را
    بازتاب می‌دهد."""
    by_key = {}
    for f in st.get("graded", []):
        if f.get("result") not in ("HIT", "MISS"):
            continue
        k = f"{f['metric']}|{f['horizon_min']}m"
        b = by_key.setdefault(k, {"dir_n": 0, "dir_hit": 0,
                                  "flat_real": 0, "graded": 0})
        b["graded"] += 1
        if f.get("real_path") == "FLAT":
            b["flat_real"] += 1
        if f.get("path") in ("UP", "DOWN"):
            b["dir_n"] += 1
            b["dir_hit"] += 1 if f["result"] == "HIT" else 0

    out = {}
    for k, v in sorted(st["score"].items()):
        row = {"n": v["n"], "hit": v["hit"],
               "hit_pct": round(100 * v["hit"] / v["n"], 1) if v["n"] else None}
        b = by_key.get(k)
        if b and b["graded"]:
            row["dir_n"] = b["dir_n"]
            row["dir_hit_pct"] = (round(100 * b["dir_hit"] / b["dir_n"], 1)
                                  if b["dir_n"] else None)
            base = round(100 * b["flat_real"] / b["graded"], 1)
            row["baseline_flat_pct"] = base
            hp = round(100 * v["hit"] / v["n"], 1) if v["n"] else None
            row["skill"] = round(hp - base, 1) if hp is not None else None
        # برایر (بند ۵): عدد کالیبره، با مرجعِ «اقلیمِ همین سطل» تا معنا
        # داشته باشد. برایرِ بی‌مرجع همان اشتباهِ درصدِ اصابتِ بی‌بنچمارک است.
        if v.get("brier_n"):
            row["brier"] = round(v["brier_sum"] / v["brier_n"], 4)
            row["brier_n"] = v["brier_n"]
            if b and b["graded"]:
                q = b["flat_real"] / b["graded"]
                # اقلیم: همیشه همان نرخ پایهٔ FLAT/غیرFLAT را بگو
                clim = {"FLAT": q, "UP": (1 - q) / 2, "DOWN": (1 - q) / 2}
                cs = [brier(clim, g.get("real_path"))
                      for g in st.get("graded", [])
                      if f"{g.get('metric')}|{g.get('horizon_min')}m" == k
                      and g.get("real_path") in ("UP", "DOWN", "FLAT")]
                cs = [c for c in cs if c is not None]
                if cs:
                    row["brier_climate"] = round(sum(cs) / len(cs), 4)
                    row["brier_skill"] = round(row["brier_climate"]
                                               - row["brier"], 4)
        out[k] = row
    return out


def update(points, struct, now_ms=None):
    """یک نوبت کامل: نمره‌دهی سررسیدها + صدور پیش‌بینی تازه. خروجی برای پنل."""
    st = _load()
    graded_now = grade_due(st, points, now_ms)
    # ضدتکرار درست (درس ۱۸ اوت): پیش‌بینی باز تا سررسیدش **دست‌نخورده می‌ماند**.
    # نسخهٔ اول تازه را جایگزین می‌کرد و چون زنجیره هر ~۳ دقیقه می‌چرخد،
    # هیچ پیش‌بینی‌ای به سررسید نمی‌رسید و کارنامه ابدی خالی می‌ماند.
    open_slots = {(f["metric"], f["horizon_min"]) for f in st["open"]}
    fresh = [f for f in make_forecast(points, struct, now_ms, st=st)
             if (f["metric"], f["horizon_min"]) not in open_slots]
    st["open"] += fresh
    _save(st)
    return {"made_now": [{k: f[k] for k in
                          ("metric", "horizon_min", "path", "reasons",
                           "hist", "low_confidence", "confidence",
                           "reprobe", "p", "p_claim", "p_n", "p_why",
                           "ev_n") if k in f}
                         for f in fresh],
            "graded_now": graded_now,
            "scoreboard": scoreboard(st),
            "open": len(st["open"])}
