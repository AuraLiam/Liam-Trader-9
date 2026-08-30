"""نمونه‌گیر شورت — پرکردن دو باندِ کم‌نمونه در پیپرمود (دستور حمید، ۳۰ اوت).

حمید، بعد از دیدن جدول کمبود آزمایشگاه شورت: «خب پس اون ۱۳۰ و ۱۵۰
شورت رو تو پیپرمود بگیر.»

## چه چیزی گرفته می‌شود — و چرا فقط همین

اندازه‌گیری `hamid/short_lab.py` (۳۰ اوت، ۱٬۴۵۱ شورت بسته):

| باند استاپ | داریم | لازم (نیم‌پهنای ±۰.۱R) | کمبود | چرا مهم |
|---|---|---|---|---|
| ۰–۰.۵٪ | ۷۰۲ | ۴۸۴ | ۰ | جوابش قطعی است: ناخالص بالای صفر، خالص زیر صفر — کارمزدخوار |
| **۰.۵–۰.۸٪** | ۲۶۲ | ۳۹۲ | **۱۳۰** | ناخالص CI بالای صفر (+۰.۲۰۴)؛ خالص هنوز مبهم |
| **۰.۸–۱.۵٪** | ۲۰۳ | ۳۵۳ | **۱۵۰** | بهترین نسبت کارمزد؛ خالص هنوز مبهم |
| >۱.۵٪ | ۲۸۳ | ۲۷۳ | ۰ | لبهٔ ناخالص همان‌جا تمام می‌شود |

شورتِ بیشتر با استاپ زیر ۰.۵٪ فقط بازهٔ منفی را تنگ‌تر می‌کند — تلهٔ
آماری‌ای که E18 هشدارش را داد. پس نمونهٔ تازه **فقط** در دو باند وسط
گرفته می‌شود، و بودجه هر باند دقیقاً همان کمبود است. باند که پر شد،
نمونه‌گیری همان‌جا می‌ایستد و حکم با ماشین CI ساخته می‌شود.

## هندسهٔ هر نمونه

نامزد = هر ستاپ SHORT واقعیِ موتور (کیفیت ≥ ۴۵ — یعنی دست‌کم ARMED؛
ستاپِ ساختگی نمونه نیست، قانون ۱). روی همان نامزد، استاپ به میانهٔ باند
هدف برده می‌شود و تارگت با همان RRِ خودِ ستاپ مقیاس می‌شود — یعنی فقط
**هندسه** عوض می‌شود، نه ستاپ، نه جهت، نه زمان. این دقیقاً A/B روی
هندسه است (بند ۴ دستور شب ۲۶ اوت: «معماری هم آزمایش‌پذیر است»)، و چون
ستاپِ پایه همان است، مقایسه با دفترهای موجودِ همان ستاپ‌ها معنا دارد.

## مرزها — هر پنج قید دستورهای قبلی

۱. **دفتر جدا**: برچسب `exp-short-b1` / `exp-short-b2`. در هر هفت
   فهرست جداسازی (کارنامهٔ تجربه، دروازهٔ کارمزد، تراز، نمرهٔ سیگنال،
   گزارش کار، پل یادگیری، طبقه‌بند) ثبت شده تا با دفتر سیگنال قاطی
   نشود — همان کلاسِ عیبی که ۲۴ اوت CI باددار ساخت.
۲. **صفر تلگرام**: این ماژول فقط `paper.open_from` صدا می‌زند که فقط
   دفتر می‌نویسد. به `stage` هیچ ستاپی هم دست نمی‌زند، پس چیزی واردِ
   مسیر ارسال نمی‌شود.
۳. **هیچ دروازهٔ تولیدی شل نمی‌شود**: نمونه بعد از دروازه‌ها برداشته
   می‌شود و روی خروجی پنل/سیگنال اثر ندارد.
۴. **بودجهٔ سخت**: سقف هر باند = کمبودِ اندازه‌گیری‌شده؛ سقف هر چرخه
   کوچک است تا نمونه در زمان پخش شود، نه همه از یک لحظهٔ بازار.
۵. **حکم فقط با CI**: خروجی این دفتر از مسیر `short_lab` و ماشین شبانه
   داوری می‌شود؛ PROMOTE فقط با CI خالصِ بالای صفر و تأیید صریح حمید
   (الگوی `scalp_verdict`، قانون ۰۳/۱۲).
"""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent
DOM = ROOT / "signals" / "dominance.json"

# برچسب → (کف باند٪، سقف باند٪، استاپِ هدف٪ = میانهٔ باند، بودجه = کمبود)
BANDS = {
    "exp-short-b1": (0.5, 0.8, 0.65, 130),
    "exp-short-b2": (0.8, 1.5, 1.15, 150),
}
TAGS = tuple(BANDS)
PER_CYCLE = 4          # سقف هر باند در هر اسکن — پخش در زمان، نه یک لحظه
MIN_QUALITY = 45       # کف ARMED — ستاپی که موتور جدی نگرفته، نمونه نیست
RR_MIN, RR_MAX = 1.2, 2.5


def counts():
    """چند نمونه در هر باند داریم — از خودِ دفترها، نه از یک شمارندهٔ جدا.

    شمارندهٔ جدا همان «فایل وضعیت بی‌مالک» می‌شد که قانون ۱۳ منعش کرده؛
    دفترِ باز+بسته خودش منبع حقیقت است. یکتاسازی بر هویت معامله (درس
    ۲۴ اوت)."""
    from hamid import paper
    out = {t: set() for t in TAGS}
    for path in (paper.OPEN, paper.CLOSED):
        try:
            rows = paper._read(path)
        except Exception:                            # noqa: BLE001
            continue
        for r in rows:
            st = (r.get("why") or {}).get("stage") or r.get("stage_tag") or ""
            if st in out:
                out[st].add((r.get("sym"), r.get("dir"),
                             r.get("opened"), r.get("entry")))
    return {t: len(v) for t, v in out.items()}


def _dom_regime():
    """رژیم دامیننس ۱۵د در لحظهٔ نمونه‌گیری — اسنپ‌شات روی پرونده.

    قانون ۱۰ بند ۷: تصویرِ لحظهٔ تصمیم ذخیره می‌شود؛ بازسازیِ بعدی،
    نتیجه را به شرایطِ بعد از تصمیم نسبت می‌دهد."""
    try:
        d = json.loads(DOM.read_text(encoding="utf-8"))
        e = ((d.get("tf_map") or {}).get("15m") or {}).get("usdt") or {}
        return {"regime_15m": e.get("regime"), "delta": e.get("delta")}
    except Exception:                                # noqa: BLE001
        return None


def _arm(s, tag):
    """بازوی آزمایش: همان ستاپ، استاپ در میانهٔ باند هدف، RR حفظ‌شده."""
    lo, hi, mid, _budget = BANDS[tag]
    entry = float(s["entry"])
    native_risk = abs(entry - float(s["sl"]))
    if not entry or not native_risk:
        return None
    rr = abs(float(s.get("tp1") or entry) - entry) / native_risk
    rr = min(max(rr, RR_MIN), RR_MAX) if rr else 1.5
    stop_dist = entry * mid / 100
    return {"symbol": s["sym"], "dir": "SHORT",
            "entry": entry,
            "sl": entry + stop_dist,
            "tp1": entry - stop_dist * rr,
            "tp2": entry - stop_dist * rr * 2,
            "tf": s.get("tf"),
            "stage_tag": tag}


def sample(setups, opener=None):
    """نمونه‌گیری یک چرخه. فقط دفتر می‌نویسد؛ به ستاپ‌ها دست نمی‌زند."""
    if opener is None:
        from hamid import paper
        opener = paper.open_from
    have = counts()
    left = {t: max(0, BANDS[t][3] - have.get(t, 0)) for t in TAGS}
    out = {"opened": 0, "have": have, "left": left}
    if not any(left.values()):
        out["why"] = "بودجهٔ هر دو باند پر است — نمونه‌گیری تمام؛ نوبتِ حکم CI است"
        return out

    cands = [s for s in setups
             if s.get("dir") == "SHORT"
             and s.get("entry") and s.get("sl")
             and (s.get("quality") or 0) >= MIN_QUALITY]
    cands.sort(key=lambda s: s.get("quality") or 0, reverse=True)
    out["candidates"] = len(cands)
    if not cands:
        out["why"] = "این چرخه ستاپ شورتِ باکیفیتی نداشت — نمونهٔ ساختگی گرفته نمی‌شود"
        return out

    ctx = {"experiment": "short-band-fill",
           "ordered": "دستور حمید ۳۰ اوت — پرکردن باندهای ۰.۵–۰.۸ و ۰.۸–۱.۵",
           "sampled_at": int(time.time() * 1000),
           "dominance": _dom_regime()}
    rows = []
    for tag in TAGS:
        n = min(left[tag], PER_CYCLE)
        for s in cands[:n]:
            arm = _arm(s, tag)
            if arm:
                rows.append(arm)
    if rows:
        try:
            added = opener(rows, ctx)
        except Exception as e:                       # noqa: BLE001
            out["why"] = f"ثبت دفتر شکست خورد: {type(e).__name__}"
            return out
        out["opened"] = added if isinstance(added, int) else len(rows)
    return out


def main(argv=()):
    have = counts()
    print("وضعیت بودجهٔ نمونه‌گیری شورت:")
    for t in TAGS:
        lo, hi, mid, budget = BANDS[t]
        print(f"  {t} (استاپ {lo:g}–{hi:g}٪): {have.get(t, 0)} از {budget}")
    print("نمونه‌گیری در خودِ اسکن انجام می‌شود (scan.py) — این فقط وضعیت است")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
