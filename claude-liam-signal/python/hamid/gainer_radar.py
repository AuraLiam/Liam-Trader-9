"""رادار گینرهای بیت‌یونیکس — همان ریشه‌یابیِ ARB، خودکار و هر ۱۵ دقیقه.

دستور حمید (۱ سپتامبر): «این مدل ریشه‌یابی را اسکیل کن که هر ۱۵ دقیقه در
قسمت گینرز صرافی بیت‌یونیکس چک کنی و بلافاصله متوجه شدی ارزی در حال
تغییر هست سریعاً با توجه به همین اسکیل بررسی می‌کنی و همان‌جا آلارم
می‌دهی و گزارش را از تلگرام ارسال می‌کنی.»

## چرا بیت‌یونیکس و چرا گینرها

گشتِ چندصرافی (`scout.py`) نامزد پیدا می‌کند ولی از صرافی‌هایی که ما
**روی‌شان معامله نمی‌کنیم**. حمید روی بیت‌یونیکس فیوچرز اجرا می‌کند، پس
ارزی که آن‌جا در فهرست گینرها بالا می‌آید همان چیزی است که واقعاً
قابل‌معامله است (قانون ۰۰: سیگنال اجرایی فقط برای نمادِ فعالِ صرافی هدف).

## همان تحلیلِ ARB، ولی قطعی و تکرارپذیر

تحلیلِ دستیِ ARB چهار چیز را کنار هم گذاشت و به همین دلیل درست بود:
حرکتِ قیمت · **جهتِ OI** · فاندینگ · نسبت لانگ/شورت. این فایل همان چهار
را از خودِ بیت‌یونیکس می‌گیرد و همان تفکیک را می‌کند:

| الگو | شرط | معنی |
|---|---|---|
| **پول تازه** | قیمت ↑ و OI ↑ | پوزیشن تازه باز شده — قوی‌ترین حالت |
| **شورت‌اسکوئیز** | قیمت ↑ و OI ↓ | فروشنده مجبور به خرید شده — سوختِ محدود |
| **توزیع** | قیمت ↓ و OI ↑ | شورتِ تازه سوار می‌شود |
| **بستنِ لانگ** | قیمت ↓ و OI ↓ | خروجِ ساده |

این تفکیک همان چیزی است که حمید در ARB دستی انجام داد («OI +۱۸.۶٪ و
ارزش +۳۷٪ ⇒ فقط شورت‌اسکوئیز نیست»). حالا برای هر گینر، هر ۱۵ دقیقه.

## گزارشِ تکراری ممنوع — دستور صریح

«ممکن است چندین ارز چند روز در گینرز باشند؛ وقتی بار اول توضیحات را دادی
و هر بار دیدی همین‌ها هستند، همان گزارش اولیه کافی است.»

پس دفترِ `brain/gainer-seen.json` نگه می‌دارد چه ارزی، با چه **حالتی**،
کِی گزارش شده. ارز دوباره فقط وقتی گزارش می‌شود که:

۱. **تازه** باشد (اصلاً گزارش نشده)، یا
۲. **حالتش عوض شده باشد** (مثلاً از شورت‌اسکوئیز به پول‌تازه) — این خبرِ
   واقعی است نه تکرار، یا
۳. **جهش معنادار** کرده باشد (تغییر ≥ ۱.۵ برابرِ گزارش قبلی).

وگرنه ساکت. ارزی که سه روز در گینرهاست و هیچ‌چیزش عوض نشده، خبر نیست.

## مرز صادقانه — این آلارم است، نه سیگنال

خروجی این فایل **هیچ سیگنالی صادر نمی‌کند** و هیچ دروازه‌ای را دور
نمی‌زند. قانون ۰۷: موفقیتِ توصیفیِ پامپ ≠ ورودِ قابل‌معامله. و اندازه‌گیری
خودمان (۳۱ اوت): چسبندگی پامپ ×۱.۰۴ — یعنی «پامپ کرد» تقریباً هیچ قدرت
پیش‌بینی ندارد. پس این رادار **میدان دید** است: می‌گوید کجا را نگاه کن،
نه اینکه بخر. ورود فقط از مسیر ستاپ ساختاری + همان دروازه‌های همیشگی.

و طبق قانون ۰۱ بند ۱: هر عددی که نیامد `None` می‌ماند و در پیام صریح
«نامعلوم» نوشته می‌شود — هیچ رقمی حدس زده نمی‌شود.

اجرا: `python3 -m hamid.gainer_radar [--write] [--telegram]`
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
sys.path.insert(0, str(PY))
ROOT = PY.parent.parent
OUT = ROOT / "signals" / "gainer-radar.json"
SEEN = ROOT / "brain" / "gainer-seen.json"

BASE = "https://fapi.bitunix.com"
UA = {"User-Agent": "liam9-gainer/1.0", "Accept": "application/json"}

TOP_N = 8                 # چند گینر برتر بررسی شود
MIN_CHG_PCT = 4.0         # زیر این تغییر، «در حال تغییر» نیست
RESURFACE_MULT = 1.5      # جهشِ لازم برای گزارشِ دوبارهٔ همان ارز
SEEN_TTL_H = 48           # بعد از این مدت سکوت، ارز دوباره «تازه» است
MIN_QUOTE_VOL = 200_000   # نقدشوندگیِ حداقلی (دلار در ۲۴ ساعت)


def _get(path, timeout=12):
    """خطا بی‌جزئیات نمی‌ماند — کد و بدنه به پیام می‌چسبند."""
    try:
        req = urllib.request.Request(BASE + path, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8")), None
    except urllib.error.HTTPError as e:              # noqa: PERF203
        return None, f"HTTP {e.code}"
    except Exception as e:                           # noqa: BLE001
        return None, type(e).__name__


def _rows(payload):
    """بدنهٔ بیت‌یونیکس گاهی `data` است گاهی `data.list` — هر دو پذیرفته."""
    if not isinstance(payload, dict):
        return []
    d = payload.get("data")
    if isinstance(d, dict):
        d = d.get("list") or d.get("tickers") or []
    return d if isinstance(d, list) else []


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def tickers():
    """تیکرهای فیوچرز — نام میدان‌ها بین نسخه‌ها فرق می‌کند، پس چندنامی."""
    for p in ("/api/v1/futures/market/tickers",
              "/api/v1/futures/market/ticker"):
        payload, err = _get(p)
        rows = _rows(payload)
        if rows:
            return rows, None
    return [], err or "پاسخ خالی"


def _chg(r):
    for k in ("change", "priceChangePercent", "rose", "chg", "changeRate"):
        v = _f(r.get(k))
        if v is not None:
            # بعضی نسخه‌ها نسبت می‌دهند (۰.۱۸) نه درصد (۱۸)
            return v * 100 if abs(v) < 1.5 else v
    return None


def _sym(r):
    return r.get("symbol") or r.get("s") or r.get("coin")


def _vol(r):
    for k in ("quoteVol", "quoteVolume", "turnover", "amount", "volCcy24h"):
        v = _f(r.get(k))
        if v is not None:
            return v
    return None


def oi_now(sym):
    """اوپن‌اینترست — قلبِ تفکیکِ «پول تازه» از «شورت‌اسکوئیز»."""
    for p in (f"/api/v1/futures/market/open_interest?symbol={sym}",
              f"/api/v1/futures/market/openInterest?symbol={sym}"):
        payload, _ = _get(p, timeout=8)
        d = payload.get("data") if isinstance(payload, dict) else None
        if isinstance(d, dict):
            for k in ("openInterest", "oi", "value", "amount"):
                v = _f(d.get(k))
                if v is not None:
                    return v
        v = _f(d)
        if v is not None:
            return v
    return None


def funding(sym):
    for p in (f"/api/v1/futures/market/funding_rate?symbol={sym}",
              f"/api/v1/futures/market/fundingRate?symbol={sym}"):
        payload, _ = _get(p, timeout=8)
        d = payload.get("data") if isinstance(payload, dict) else None
        if isinstance(d, dict):
            for k in ("fundingRate", "rate", "value"):
                v = _f(d.get(k))
                if v is not None:
                    return v * 100
        v = _f(d)
        if v is not None:
            return v * 100
    return None


def classify(chg, oi_delta_pct):
    """همان چهار حالتِ بالای سند — و «نامعلوم» وقتی OI نیامده.

    این تابع عمداً هیچ حدسی نمی‌زند: بدون OI، تفکیکِ پول‌تازه از
    شورت‌اسکوئیز **ممکن نیست**، و همان را می‌گوید (قانون ۰۱)."""
    if chg is None:
        return "UNKNOWN", "تغییر قیمت نامعلوم"
    if oi_delta_pct is None:
        return "UNKNOWN_OI", ("جهتِ OI نامعلوم — بدون آن، پولِ تازه از "
                              "شورت‌اسکوئیز جدا نمی‌شود")
    up, oi_up = chg > 0, oi_delta_pct > 0
    if up and oi_up:
        return "NEW_MONEY", "قیمت ↑ و OI ↑ — پوزیشن تازه باز شده"
    if up and not oi_up:
        return "SHORT_SQUEEZE", "قیمت ↑ و OI ↓ — شورت‌بستن، سوخت محدود"
    if not up and oi_up:
        return "DISTRIBUTION", "قیمت ↓ و OI ↑ — شورتِ تازه سوار می‌شود"
    return "LONG_UNWIND", "قیمت ↓ و OI ↓ — خروجِ ساده"


def _seen():
    try:
        return json.loads(SEEN.read_text(encoding="utf-8"))
    except Exception:                                # noqa: BLE001
        return {}


def should_report(sym, state, chg, seen, now_ms):
    """گزارشِ تکراری ممنوع — دستور صریح حمید.

    ارزی که چند روز در گینرهاست و هیچ‌چیزش عوض نشده، خبر نیست. فقط سه
    چیز دوباره خبر است: تازه‌بودن، عوض‌شدنِ حالت، جهشِ معنادار."""
    p = seen.get(sym)
    if not p:
        return True, "تازه — اولین بار در رادار"
    if now_ms - (p.get("at") or 0) > SEEN_TTL_H * 3_600_000:
        return True, f"بعد از {SEEN_TTL_H} ساعت سکوت دوباره بالا آمد"
    if p.get("state") != state:
        return True, f"حالت عوض شد: {p.get('state')} → {state}"
    old = abs(p.get("chg") or 0)
    if old and abs(chg or 0) >= old * RESURFACE_MULT:
        return True, f"جهش: {old:.1f}٪ → {abs(chg):.1f}٪"
    return False, "بدون تغییر نسبت به گزارش قبلی — ساکت"


def scan(now_ms=None, fetch=None):
    now = now_ms or int(time.time() * 1000)
    rows, err = (fetch or tickers)()
    if not rows:
        return {"generated": now, "ok": False, "why": f"تیکر نیامد: {err}",
                "candidates": [], "report": []}
    cand = []
    for r in rows:
        s, c, v = _sym(r), _chg(r), _vol(r)
        if not s or c is None or c < MIN_CHG_PCT:
            continue
        if v is not None and v < MIN_QUOTE_VOL:
            continue
        cand.append({"sym": s, "chg_pct": round(c, 2), "quote_vol": v,
                     "last": _f(r.get("last") or r.get("lastPrice"))})
    cand.sort(key=lambda x: -x["chg_pct"])
    cand = cand[:TOP_N]

    seen = _seen()
    prev_oi = {k: (v.get("oi") if isinstance(v, dict) else None)
               for k, v in seen.items()}
    out, report = [], []
    for c in cand:
        oi = oi_now(c["sym"])
        p_oi = prev_oi.get(c["sym"])
        d = (round((oi - p_oi) / p_oi * 100, 2)
             if oi is not None and p_oi else None)
        state, why = classify(c["chg_pct"], d)
        fr = funding(c["sym"])
        row = dict(c, oi=oi, oi_delta_pct=d, funding_pct=fr,
                   state=state, state_why=why)
        ok, reason = should_report(c["sym"], state, c["chg_pct"], seen, now)
        row["report"] = ok
        row["report_reason"] = reason
        out.append(row)
        if ok:
            report.append(row)
    return {"generated": now, "ok": True, "source": "bitunix-futures",
            "n_candidates": len(out), "candidates": out, "report": report,
            "boundary": ("آلارم است نه سیگنال — چسبندگی پامپ در دفتر خودمان "
                         "×۱.۰۴ اندازه‌گیری شده (۳۱ اوت). ورود فقط از مسیر "
                         "ستاپ ساختاری و دروازه‌های همیشگی (قانون ۰۷).")}


def remember(res):
    """دفترِ دیده‌ها — فقط برای همان ارزهایی که **گزارش شدند**.

    اگر برای هر دیدنی به‌روزرسانی می‌کردیم، `chg` مرجع مدام جابه‌جا
    می‌شد و شرطِ «جهش ≥۱.۵×» هرگز فعال نمی‌شد — یعنی ضدتکرار، خودش
    خبرِ واقعی را هم خفه می‌کرد. مرجع باید **آخرین گزارش** بماند.
    فقط OI هر بار تازه می‌شود، چون مبنای دلتای بعدی است."""
    seen = _seen()
    for r in res.get("candidates") or []:
        p = seen.get(r["sym"]) or {}
        if r["report"]:
            p = {"at": res["generated"], "state": r["state"],
                 "chg": r["chg_pct"]}
        if r.get("oi") is not None:
            p["oi"] = r["oi"]
        seen[r["sym"]] = p
    cut = res["generated"] - SEEN_TTL_H * 2 * 3_600_000
    seen = {k: v for k, v in seen.items() if (v.get("at") or cut + 1) > cut}
    SEEN.parent.mkdir(parents=True, exist_ok=True)
    SEEN.write_text(json.dumps(seen, ensure_ascii=False, indent=1),
                    encoding="utf-8")
    return seen


FA = {"NEW_MONEY": "🟢 پول تازه", "SHORT_SQUEEZE": "🟡 شورت‌اسکوئیز",
      "DISTRIBUTION": "🔴 توزیع", "LONG_UNWIND": "⚪ بستنِ لانگ",
      "UNKNOWN_OI": "⚪ OI نامعلوم", "UNKNOWN": "⚪ نامعلوم"}


def caption(res):
    """پیام تلگرام — فقط ارزهای گزارش‌شدنی، با امضای پنل (دستور ۱۶ اوت)."""
    from hamid import telegram as tg
    rep = res.get("report") or []
    if not rep:
        return None
    L = [f"📡 رادار گینرهای بیت‌یونیکس — {len(rep)} ارز تازه", ""]
    for r in rep:
        L.append(f"• {r['sym']}  {r['chg_pct']:+.1f}٪   {FA.get(r['state'])}")
        L.append(f"    {r['state_why']}")
        oi = ("نامعلوم" if r["oi_delta_pct"] is None
              else f"{r['oi_delta_pct']:+.1f}٪")
        fr = "نامعلوم" if r["funding_pct"] is None else f"{r['funding_pct']:+.4f}٪"
        L.append(f"    OI: {oi} · فاندینگ: {fr}")
        L.append(f"    چرا حالا: {r['report_reason']}")
        L.append("")
    L.append("⛔ این آلارم است نه سیگنال — ورود فقط از ستاپ ساختاری.")
    L.append("چسبندگی پامپ در دفتر خودمان ×۱.۰۴ (۳۱ اوت) — «پامپ کرد» "
             "به‌تنهایی دلیل خرید نیست.")
    L.append("")
    L.append(getattr(tg, "PANEL_NAME", "لیام تریدر ۹"))
    return "\n".join(L)


def main(argv=()):
    res = scan()
    if not res.get("ok"):
        print(f"رادار گینر: {res.get('why')}")
        return 1
    print(f"### رادار گینرهای بیت‌یونیکس — {res['n_candidates']} نامزد · "
          f"{len(res['report'])} گزارش‌شدنی\n")
    for r in res["candidates"]:
        mark = "📢" if r["report"] else "🔇"
        print(f"{mark} {r['sym']:14s} {r['chg_pct']:+7.2f}٪  "
              f"{FA.get(r['state'], r['state'])}")
        print(f"      {r['state_why']}")
        print(f"      {r['report_reason']}")
    print(f"\n### مرز\n  {res['boundary']}")
    if "--write" in argv:
        OUT.parent.mkdir(exist_ok=True)
        OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1),
                       encoding="utf-8")
        remember(res)
        print(f"\n  نوشته شد: {OUT.name}")
    if "--telegram" in argv and res.get("report"):
        # از دروازهٔ آلارم رد می‌شود، نه مستقیم — قانون ۰۷ (۲۳ اوت):
        # هر ماژولی که مستقیم به تلگرام بفرستد و در DIRECT_OK نباشد،
        # چرخه را سرخ می‌کند. کلید از (نماد|حالت)های گزارش‌شدنی ساخته
        # می‌شود؛ چون `should_report` از قبل ارزِ بی‌تغییر را حذف کرده،
        # عوض‌شدنِ این کلید یعنی خبرِ واقعی، نه نوسانِ فهرست.
        from hamid import alert_gate
        key = "gainer|" + "|".join(sorted(
            f"{r['sym']}:{r['state']}" for r in res["report"]))
        sent, why = alert_gate.send("رادار گینر", key, caption(res))
        print(f"  تلگرام: {'رفت' if sent else 'نرفت'} ({why})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
