"""پاسبان «یک منبع برای کارمزد» + قرینگی نردبان تریل در شورت.

## عیبی که این آزمون برای بستنش نوشته شد (۳۰ اوت شب)

داخل **یک تابع** (`paper._settle_one`) دو ثابت کارمزد ناسازگار بود:

- نردبان تریل با `entry * 0.0015` (۰.۱۵٪) کار می‌کرد
- ولی `R_net` دفتر با `0.001 * entry / risk` (۰.۱٪) ساخته می‌شد

مدل رسمی (`liam9_strategy.PARAMS["fee_round_trip_pct"]`) و اعداد
راستی‌آزمایی‌شدهٔ صرافی (`config/fees.json` → `hamid/fees.py`) هر دو
۰.۱۵٪ می‌گویند. پس هر عددِ «خالص» دفتر یک‌سومِ کارمزد را نمی‌دید.

چرا این مهم است و نه یک گِرد‌کردنِ کوچک: سهم کارمزد از R برابر
`کارمزد٪ ÷ استاپ٪` است. روی استاپ ۰.۳۵٪ اختلافِ ۰.۰۵٪ می‌شود **۰.۱۴R
در هر معامله** — و همهٔ بازه‌های اطمینانی که روی `R_net` ساخته می‌شدند
(از جمله ماشین بونفرونیِ شبانه که تصمیم می‌گیرد چه قاعده‌ای وارد تولید
شود) سوگیری مثبت داشتند. اندازه‌گیری روی دفتر: جابه‌جایی میانه
−۰.۰۹۴R در هر معامله.

## چه چیزی قفل می‌شود

۱. هیچ ثابت کارمزدِ دست‌ساز در `paper.py` نماند — همه از `hamid/fees.py`.
۲. مدل رسمی و منبع واحد یک عدد بدهند (واگرایی = چرخه سرخ).
۳. نردبان تریل برای SHORT دقیقاً قرینهٔ LONG باشد — تستِ قبلی
   (`test_paper.py::t_trailing_stop`) فقط دو سناریوی LONG داشت، پس
   برعکس‌شدنِ علامت در شاخهٔ شورت هیچ‌جا سرخ نمی‌شد.
"""
import re
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
sys.path.insert(0, str(PY))

from hamid import fees as F                                   # noqa: E402
from hamid import paper as P                                  # noqa: E402

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


def run():
    src = (PY / "hamid" / "paper.py").read_text(encoding="utf-8")

    # ── ۱) یک منبع، بدون ثابت دست‌ساز ─────────────────────────────────
    body = src[src.find("def _settle_one"):]
    body = body[:body.find("\ndef ", 10)] if "\ndef " in body[10:] else body
    hard = re.findall(r"0\.00\d+\s*\*\s*p\[|p\[\"entry\"\]\s*\*\s*0\.00\d+", body)
    check("هیچ ثابت کارمزد دست‌سازی در تسویه نمانده", not hard, str(hard))
    check("تسویه از کمک‌تابع منبع‌واحد استفاده می‌کند",
          "_fee_pct(p)" in body, body[:0] or "پیدا نشد")
    check("کمک‌تابع از hamid/fees می‌خواند",
          "from hamid import fees" in src and "round_trip_pct" in src)

    # ── ۲) مدل رسمی و منبع واحد یک عدد بدهند ──────────────────────────
    canon = F.round_trip_pct(None)
    strat = (PY / "liam9_strategy.py").read_text(encoding="utf-8")
    m = re.search(r'"fee_round_trip_pct":\s*([0-9.]+)', strat)
    check("مدل رسمی عدد کارمزد دارد", m is not None)
    check("منبع واحد و مدل رسمی یکی‌اند",
          m is not None and abs(float(m.group(1)) - canon) < 1e-9,
          f"fees={canon} · PARAMS={m.group(1) if m else '?'}")
    check("عدد کارمزد همان ~۰.۱۵٪ راستی‌آزمایی‌شده است",
          abs(canon - 0.15) < 1e-9, str(canon))
    check("کمک‌تابع پیش‌فرضِ امن دارد (نه صفر)",
          P._fee_pct({"sym": "___NOSUCH___"}) > 0)

    # ── ۳) اثر عددی — همان چیزی که بازه‌ها را جابه‌جا کرد ──────────────
    e, s = 100.0, 100.35                     # استاپ ۰.۳۵٪ (میانهٔ ibs)
    old = 0.001 * e / abs(e - s)
    new = F.cost_in_r(e, s, None)
    check("کارمزد روی استاپ تنگ حالا بزرگ‌تر (و درست) است",
          new > old, f"{old:.4f} → {new:.4f}")
    check("و اختلافش روی استاپ تنگ ≥۰.۱R است",
          new - old >= 0.10, f"{new - old:.4f}")
    ew, sw = 100.0, 102.0                    # استاپ ۲٪ (هندسهٔ smc)
    check("روی استاپ گشاد همان اختلاف کوچک است (کارمزد٪÷استاپ٪)",
          F.cost_in_r(ew, sw, None) - 0.001 * ew / abs(ew - sw) < 0.03)

    # ── ۴) قرینگی نردبان تریل — تستِ غایبِ شورت ───────────────────────
    def one(direction):
        """یک معاملهٔ کامل: تا ⅔ مسیر می‌رود، بعد کامل برمی‌گردد.

        با نردبان درست، استاپ باید در سود قفل شده باشد — پس نتیجه
        نمی‌تواند ۱R- باشد. قرینهٔ دقیق دو جهت را می‌سنجیم."""
        sgn = 1 if direction == "LONG" else -1
        entry, risk = 100.0, 1.0
        sl = entry - sgn * risk
        tp1 = entry + sgn * risk * 1.5
        p = {"sym": "TESTUSDT", "dir": direction, "entry": entry, "sl": sl,
             "tp1": tp1, "tp2": entry + sgn * risk * 3, "filled": 0,
             "opened": 0, "why": {"stage": "sig-test"}}
        # کندل‌ها: تا ⅔ مسیر تارگت پیش می‌رود، بعد به ورود و پایین‌تر برمی‌گردد
        far = entry + sgn * risk * 1.05          # فراتر از ⅔ مسیر (۱.۰ از ۱.۵)
        seq = [entry, far, entry, entry - sgn * risk * 2]
        cd = []
        for i, px in enumerate(seq):
            prev = seq[i - 1] if i else entry
            cd.append({"t": i * 900_000, "o": prev, "c": px,
                       "h": max(prev, px), "l": min(prev, px), "v": 1.0})
        return p, cd

    res = {}
    real_candles, real_closed = P._candles_since, P.CLOSED
    # دفترِ **واقعی** نباید ردیف آزمونی بگیرد. (این را سرِ همین آزمون
    # یاد گرفتم: نسخهٔ اولش ۱۵ ردیف `sig-test` به `closed.jsonl` نوشت.
    # آزمونی که دادهٔ تولید را آلوده کند، خودش یک عیب است.)
    tmp = Path(tempfile.mkdtemp())
    P.CLOSED = tmp / "closed.jsonl"
    for d in ("LONG", "SHORT"):
        p, cd = one(d)
        # کندل‌ها را خودِ تابع فچ می‌کند؛ این‌جا سری قطعیِ آزمون را
        # جایش می‌گذاریم تا نتیجه به شبکه و به بازارِ امروز بند نباشد.
        P._candles_since = lambda sym, since, _cd=cd: _cd
        try:
            P._settle_one(p, cd[-1]["t"] + 60_000, [], [0])
        except Exception as e:                       # noqa: BLE001
            check(f"تسویهٔ {d} بدون خطا اجرا شد", False, repr(e)[:140])
            continue
        finally:
            P._candles_since = real_candles
        res[d] = p
        check(f"{d}: معامله بسته شد", p.get("outcome") is not None,
              str(p.get("outcome")))
        check(f"{d}: بعد از رفتن تا ⅔ مسیر، ضرر کامل نخورد",
              (p.get("R") or 0) > -0.99,
              f"outcome={p.get('outcome')} R={p.get('R')}")
    P.CLOSED = real_closed
    check("آزمون به دفتر واقعی چیزی ننوشت",
          not any('"sym": "TESTUSDT"' in ln for ln in
                  real_closed.read_text(encoding="utf-8").splitlines()[-500:]))
    if len(res) == 2:
        check("نردبان قرینه است: R دو جهت یکی است",
              abs((res["LONG"].get("R") or 0)
                  - (res["SHORT"].get("R") or 0)) < 1e-6,
              f"L={res['LONG'].get('R')} S={res['SHORT'].get('R')}")
        check("و نوع خروج هم یکی است",
              res["LONG"].get("outcome") == res["SHORT"].get("outcome"),
              f"{res['LONG'].get('outcome')} / {res['SHORT'].get('outcome')}")
        check("کارمزد هر دو جهت با منبع واحد خوانده شد",
              res["LONG"].get("fee_model") == res["SHORT"].get("fee_model")
              == P.FEE_MODEL, str(res["LONG"].get("fee_model")))

    # ── ۵) موتور سنجش نباید به عددِ ذخیره‌شده اعتماد کند ───────────────
    da = (PY / "hamid" / "direction_autopsy.py").read_text(encoding="utf-8")
    check("کالبدشکافی خالص را بازمحاسبه می‌کند", "apply_net" in da)
    check("و عددِ ذخیره‌شده را برای مقایسه نگه می‌دارد",
          "_R_net_stored" in F.apply_net([{"R": 1.0, "entry": 100,
                                           "sl": 99, "R_net": 0.5}])[0])

    # ── ۶) «منبع واحد» یعنی یک پیاده‌سازی، نه چند کپیِ هم‌شکل ──────────
    #
    # عیب ۱ سپتامبر: منطق بازمحاسبه در `direction_autopsy` کپی شده بود و
    # `work_report` نسخهٔ خودش را نداشت — یعنی گزارشی که حمید سه بار در
    # روز می‌خواند، `R_net` **ذخیره‌شده** را می‌خواند. اندازه‌گیری: در
    # پنجرهٔ ۷ روزه ‎−۰.۰۶۳R خطا (گزارش خوش‌بینانه‌تر از واقعیت)، و بدتر
    # از آن ۵۸۰ ردیفِ «تمرین» اصلاً `R_net` نداشتند، پس نرخ برد روی یک
    # جمعیت حساب می‌شد و خالص روی جمعیتی دیگر.
    row = {"R": 1.0, "entry": 100.0, "sl": 99.0, "sym": "BTCUSDT",
           "R_net": 0.9}
    out = F.apply_net([row])[0]
    check("بازمحاسبه خالص را از entry/sl می‌سازد، نه از عددِ ذخیره‌شده",
          out["R_net"] != 0.9 and out["_R_net_stored"] == 0.9, str(out))
    check("ردیفِ بی‌خالصِ ذخیره‌شده هم خالص می‌گیرد (نه اینکه بیفتد)",
          F.apply_net([{"R": 1.0, "entry": 100.0, "sl": 99.0}])[0]["R_net"]
          is not None)
    twice = F.apply_net(F.apply_net([{"R": 1.0, "entry": 100.0, "sl": 99.0,
                                      "R_net": 0.9}]))[0]
    check("اعمالِ دوباره عددِ اصلِ ذخیره‌شده را خراب نمی‌کند (idempotent)",
          twice["_R_net_stored"] == 0.9, str(twice))
    check("ورودیِ نامعتبر ردیف را نمی‌کُشد",
          F.apply_net([{"R": 1.0, "entry": 0, "sl": 0}])[0].get("R") == 1.0)

    # رفتار سنجیده می‌شود، نه متنِ سورس. (اولین نسخهٔ همین بررسی
    # `"apply_net" in source` بود؛ وقتی عمداً صدازدنش را برداشتم، همچنان
    # سبز ماند — چون رشته در کامنت هم پیدا می‌شد. همان کلاسِ «متن به‌جای
    # رفتار» که امروز در test_short_sampler هم اصلاح شد.)
    import json as _json
    _d = Path(tempfile.mkdtemp())
    _led = _d / "closed.jsonl"
    _row = {"sym": "BTCUSDT", "dir": "LONG", "entry": 100.0, "sl": 99.0,
            "tp1": 103.0, "R": 1.0, "R_net": 0.9, "closed": 10**13,
            "outcome": "target", "why": {"stage": "practice"}}
    _led.write_text(_json.dumps(_row, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    from hamid import work_report as _WR
    _got = _WR.load(path=_led)
    check("گزارش کار خالص را بازمحاسبه می‌کند (رفتار، نه متنِ سورس)",
          _got and _got[0]["R_net"] != 0.9
          and _got[0]["_R_net_stored"] == 0.9,
          str(_got[:1]))
    from hamid import daily_report as _DR
    _got2 = _DR.rows(_led)
    check("گزارش روزانه هم بازمحاسبه می‌کند",
          _got2 and _got2[0]["R_net"] != 0.9, str(_got2[:1]))
    _led2 = _d / "c2.jsonl"
    _r2 = dict(_row, why={"stage": "sig-ibs"}, opened=10**12, filled=10**12)
    _led2.write_text(_json.dumps(_r2, ensure_ascii=False) + "\n",
                     encoding="utf-8")
    from hamid import direction_autopsy as _DA
    _old_cl = _DA.CLOSED
    try:
        _DA.CLOSED = _led2
        _got3 = _DA.load("sig-")
    finally:
        _DA.CLOSED = _old_cl
    check("کالبدشکافی هم بازمحاسبه می‌کند",
          _got3 and _got3[0]["R_net"] != 0.9, str(_got3[:1]))
    fs = (PY / "hamid" / "fees.py").read_text(encoding="utf-8")
    check("و بازمحاسبه فقط یک جا تعریف شده", fs.count("def apply_net") == 1)
    check("هیچ مصرف‌کننده‌ای فرمولِ خودش را ننوشته",
          all("R\"] - fr" not in (PY / "hamid" / f"{m}.py").read_text(
              encoding="utf-8")
              for m in ("work_report", "daily_report", "direction_autopsy")))

    print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(run())
