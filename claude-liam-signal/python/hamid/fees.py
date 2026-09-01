"""موتور کارمزد — دستور حمید (۱۶ اوت، آستانهٔ پول واقعی):
«اگر قرار است با ترید زیاد و سودهای کم ترید کنی، کارمزد هر ترید را قبل از
باز کردن پوزیشن حساب کن — بر اساس مبلغ و ضریب؛ میکر/تیکر بودن هم مزیت است.»

اصل ریاضی: کارمزد روی notional گرفته می‌شود و ریسک هم روی notional تعریف
می‌شود، پس «کارمزد بر حسب R» مستقل از اهرم است:
    fee_R = (کارمزد رفت‌وبرگشت ٪) / (فاصلهٔ استاپ ٪)
هرچه استاپ نزدیک‌تر (اسکالپ)، سهم کارمزد از R بزرگ‌تر — دقیقاً همان دام
«ترید زیاد/سود کم» که حمید گفت.

اعداد پیش‌فرض راستی‌آزمایی‌شده (۱۶ اوت ۲۰۲۶، سه منبع هم‌رأی):
Bitunix futures VIP0: maker 0.020% · taker 0.060%
  - tradersunion.com/brokers/crypto/view/bitunix/fees/
  - bitunix.com/hub/blog/bitunix-features/bitunix-fees-spot-futures-vip-trading-discounts
  - mexc.com/news/1135898
لیست ارزهای صفر-کارمزد Bitunix: UNVERIFIED — تا از خود صرافی/API تأیید
نشود خالی می‌ماند؛ هیچ لیستی از حافظه ساخته نمی‌شود (قانون: عدد بی‌منبع
ممنوع). با پرشدنش، اولویت تحلیل به آن‌ها داده می‌شود (config/fees.json).

سازگاری تاریخی: قانون تریل trading-core «ورود + ~۰.۱۵٪ برای کارمزد دو سر
و لغزش» با تیکر دو سر (۰.۱۲٪) + لغزش می‌خواند — این ماژول همان را دقیق
می‌کند، عوضش نمی‌کند.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent
CFG = ROOT / "config" / "fees.json"

# پیش‌فرض‌ها — منبع در سربرگ؛ config/fees.json در صورت وجود حاکم است
DEFAULTS = {
    "exchange": "bitunix",
    "futures_maker_pct": 0.020,
    "futures_taker_pct": 0.060,
    "slippage_pct_per_leg": 0.015,      # لغزش محافظه‌کارانه هر سر
    "zero_fee_symbols": [],             # UNVERIFIED — فقط از منبع رسمی پر شود
    "zero_fee_status": "UNVERIFIED",
    "us_market_hours_symbols": [],      # ارزهای وابسته به بازار امریکا
    "verified_at": "2026-08-16",
    "sources": [
        "https://tradersunion.com/brokers/crypto/view/bitunix/fees/",
        "https://www.bitunix.com/hub/blog/bitunix-features/bitunix-fees-spot-futures-vip-trading-discounts",
        "https://www.mexc.com/news/1135898",
    ],
}


def config():
    cfg = dict(DEFAULTS)
    try:
        cfg.update(json.loads(CFG.read_text()))
    except Exception:                                # noqa: BLE001
        pass
    return cfg


def round_trip_pct(symbol=None, entry_maker=False, exit_maker=False,
                   with_slippage=True):
    """کارمزد رفت‌وبرگشت به درصدِ notional. ارز صفر-کارمزدِ تأییدشده = فقط لغزش."""
    c = config()
    if symbol and symbol in (c.get("zero_fee_symbols") or []) \
            and c.get("zero_fee_status") == "VERIFIED":
        fee = 0.0
    else:
        fee = ((c["futures_maker_pct"] if entry_maker else c["futures_taker_pct"])
               + (c["futures_maker_pct"] if exit_maker else c["futures_taker_pct"]))
    if with_slippage:
        fee += 2 * c["slippage_pct_per_leg"]
    return round(fee, 4)


def cost_in_r(entry, sl, symbol=None, entry_maker=False, exit_maker=False):
    """کارمزد رفت‌وبرگشت بر حسب R (مستقل از اهرم). None = ورودی نامعتبر."""
    if not entry or not sl or entry == sl:
        return None
    risk_pct = abs(entry - sl) / entry * 100
    return round(round_trip_pct(symbol, entry_maker, exit_maker) / risk_pct, 3)


def apply_net(rows):
    """خالصِ هر ردیفِ دفتر را با **منبع واحد** بازمحاسبه کن (درجا).

    چرا لازم است: تا ۳۰ اوت شب، `paper._settle_one` خالص را با ۰.۱٪
    می‌ساخت در حالی که مدل رسمی و اعداد راستی‌آزمایی‌شدهٔ بیت‌یونیکس
    ۰.۱۵٪ است. ردیف‌های گذشته **بازنویسی نمی‌شوند** (دادهٔ runtime
    دست‌نخورده، قانون ضد-merge)، پس دفتر دو تعریفِ «خالص» دارد و هر
    مصرف‌کننده‌ای که `R_net` ذخیره‌شده را مستقیم بخواند، عددِ کهنه
    گزارش می‌کند.

    اندازه‌گیریِ ۱ سپتامبر روی خودِ گزارش کار: در پنجرهٔ ۲۴ ساعته
    اختلاف صفر بود (ردیف‌های تازه همه ۰.۱۵٪‌اند)، ولی در ۷۲ ساعت
    ‎+۰.۰۱۷R و در ۷ روز **‎+۰.۰۶۳R** — یعنی گزارشِ هفتگی خالص را
    آن‌قدر بهتر نشان می‌داد که با اندازهٔ خودِ لبه (~۰.۰۹R) قابل
    مقایسه بود.

    `_R_net_stored` برای مقایسه/ممیزی می‌ماند؛ چیزی روی دیسک عوض
    نمی‌شود. این تابع تنها جای بازمحاسبه است — هر مصرف‌کنندهٔ تازه
    باید همین را صدا بزند، نه فرمولِ خودش را بنویسد.
    """
    for r in rows:
        if r.get("_R_net_stored") is not None:       # قبلاً اعمال شده
            continue
        r["_R_net_stored"] = r.get("R_net")
        fr = None
        try:
            fr = cost_in_r(r.get("entry"), r.get("sl"), r.get("sym"))
        except Exception:                            # noqa: BLE001
            fr = None
        r["_fee_r"] = fr if fr is not None else r.get("fee_r")
        if fr is not None and r.get("R") is not None:
            r["R_net"] = round(r["R"] - fr, 4)
    return rows


def net_rr(entry, sl, tp, symbol=None, entry_maker=False, exit_maker=False):
    """RR خالص بعد از کارمزد. gross_RR - fee_R."""
    if not entry or not sl or not tp or entry == sl:
        return None
    gross = abs(tp - entry) / abs(entry - sl)
    fee_r = cost_in_r(entry, sl, symbol, entry_maker, exit_maker)
    return None if fee_r is None else round(gross - fee_r, 3)


def gate(entry, sl, tp, symbol=None, min_net_rr=1.8,
         entry_maker=False, exit_maker=False):
    """دروازهٔ پیش از پوزیشن: RR باید **خالص از کارمزد** از حد بگذرد.

    خروجی همیشه دلیلِ نوشته دارد — عدد بی‌توضیح برای حمید بی‌ارزش است."""
    fee_r = cost_in_r(entry, sl, symbol, entry_maker, exit_maker)
    nrr = net_rr(entry, sl, tp, symbol, entry_maker, exit_maker)
    if fee_r is None or nrr is None:
        return dict(ok=False, reason="ورودی ناقص (entry/sl/tp)", fee_r=None,
                    net_rr=None)
    ok = nrr >= min_net_rr
    kind = ("میکر/میکر" if entry_maker and exit_maker else
            "تیکر/تیکر" if not entry_maker and not exit_maker else "ترکیبی")
    reason = (f"کارمزد {kind} رفت‌وبرگشت = {fee_r}R؛ RR خالص {nrr} "
              + ("≥" if ok else "<") + f" حد {min_net_rr}"
              + ("" if ok else " — پوزیشن باز نمی‌شود؛ سود اسمی را کارمزد می‌خورد"))
    return dict(ok=ok, fee_r=fee_r, net_rr=nrr, reason=reason)


if __name__ == "__main__":
    import sys
    e, s_, t = (float(x) for x in sys.argv[1:4])
    print(json.dumps(gate(e, s_, t, *(sys.argv[4:5] or [None])),
                     ensure_ascii=False, indent=1))
