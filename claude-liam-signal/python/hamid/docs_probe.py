"""کاوش اسناد فنیِ حمید از رانر — چون نشست به این دامنه‌ها دسترسی ندارد.

دستور حمید (۲۳ اوت): شش سند فنی داد — چهار سند وب‌سوکت بایبیت (kline،
trade، orderbook، all-liquidation) و دو سند TradingView (bar-states،
repainting) — و خواست نکاتشان به انجین‌ها تزریق شود.

مشکل: خروجیِ این نشست به `bybit-exchange.github.io` و `*.tradingview.com`
بسته است (CONNECT 403 در پروکسی). راه درست دور زدنِ سیاست نیست؛ راه درست
این است که کار را جایی ببریم که خروجی باز است — همان قاعدهٔ همیشگی:
**محاسبه و شبکه روی Actions، نه نشست.**

این ماژول صفحه‌ها را می‌گیرد و **متنِ کلیدی را عیناً** بیرون می‌کشد تا
ادعاها از روی متن واقعی راستی‌آزمایی شوند، نه از حافظهٔ مدل. هیچ فیلدی
حدس زده نمی‌شود: اگر صفحه نیامد، وضعیت UNREACHABLE می‌ماند و مدخل
کتابخانه QUEUED می‌ماند (قانون ۰۳).

خروجی: `signals/docs-probe.json`

اجرا:  python3 -m hamid.docs_probe
"""
import argparse
import html
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
ROOT = HERE.parents[2]
OUT = ROOT / "signals" / "docs-probe.json"

UA = {"User-Agent": "Mozilla/5.0 (compatible; liam9-docs/1.0)",
      "Accept": "text/html,application/xhtml+xml,*/*"}

# هر سند: کلیدواژه‌هایی که دنبالشان می‌گردیم. حضورِ کلیدواژه تأیید نیست —
# متنِ اطرافش بیرون کشیده می‌شود تا خوانده و داوری شود.
DOCS = [
    {"id": "bybit-ws-kline", "engine": "E09",
     "url": "https://bybit-exchange.github.io/docs/v5/websocket/public/kline",
     "topic": "candle-close",
     "want": ["confirm", "interval", "timestamp", "start", "end"],
     "question": "معنی confirm و فهرست بازه‌های رسمی (آیا زیر ۱ دقیقه هست؟)"},
    {"id": "bybit-ws-trade", "engine": "E10",
     "url": "https://bybit-exchange.github.io/docs/v5/websocket/public/trade",
     "topic": "raw-trades",
     "want": ["side", "size", "price", "timestamp", "tickDirection"],
     "question": "آیا فیلدها برای ساخت کندل ۳۰ثانیه‌ای کافی است؟"},
    {"id": "bybit-ws-orderbook", "engine": "E10",
     "url": "https://bybit-exchange.github.io/docs/v5/websocket/public/orderbook",
     "topic": "depth",
     "want": ["snapshot", "delta", "seq", "u", "depth", "frequency"],
     "question": "عمق‌ها، نرخ push، و تشخیص از دست رفتن پیام (seq)"},
    {"id": "bybit-ws-liquidation", "engine": "E10",
     "url": "https://bybit-exchange.github.io/docs/v5/websocket/public/all-liquidation",
     "topic": "liquidation",
     "want": ["side", "position", "liquidat"],
     "question": "side یعنی سمتِ پوزیشنِ لیکوییدشده یا سمتِ سفارش؟"},
    {"id": "tv-bar-states", "engine": "E09",
     "url": "https://www.tradingview.com/pine-script-docs/concepts/bar-states/",
     "topic": "candle-close",
     "want": ["barstate.isconfirmed", "barstate.islast", "barstate.isrealtime"],
     "question": "تعریف عین‌به‌عین barstate.isconfirmed"},
    {"id": "tv-repainting", "engine": "E18",
     "url": "https://www.tradingview.com/pine-script-docs/concepts/repainting/",
     "topic": "repaint",
     "want": ["repaint", "lookahead", "realtime", "historical"],
     "question": "سند چه چیزی را عامل بک‌تستِ غیرواقعی می‌داند؟"},
]

_TAG = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.S | re.I)
_ANY = re.compile(r"<[^>]+>")
#   (nbsp) و هم‌خانواده‌هایش فاصلهٔ معمولی نیستند: «Order book»
# با جستجوی «order book» پیدا نمی‌شود و کلیدواژه بی‌صدا گم می‌شود.
_WS = re.compile(r"[ \t\r\f\v   ​]+")


def to_text(raw):
    """HTML → متن ساده. بدون کتابخانهٔ بیرونی (رانر تمیز بماند)."""
    t = _TAG.sub(" ", raw)
    t = re.sub(r"<br\s*/?>|</p>|</li>|</tr>|</h[1-6]>", "\n", t, flags=re.I)
    t = _ANY.sub(" ", t)
    t = html.unescape(t)
    t = _WS.sub(" ", t)
    return "\n".join(ln.strip() for ln in t.split("\n") if ln.strip())


def excerpts(text, words, width=320, cap=4):
    """برای هر کلیدواژه، تا `cap` تکه از متنِ اطرافش — شاهد، نه خلاصه."""
    out = {}
    low = text.lower()
    for w in words:
        hits, start = [], 0
        wl = w.lower()
        while len(hits) < cap:
            i = low.find(wl, start)
            if i < 0:
                break
            a, b = max(0, i - width // 2), min(len(text), i + width // 2)
            hits.append(text[a:b].strip())
            start = i + len(wl)
        if hits:
            out[w] = hits
    return out


def fetch(url, timeout=25):
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", "replace"), r.status, None
    except urllib.error.HTTPError as e:
        return None, e.code, f"HTTPError {e.code}"
    except Exception as e:                              # noqa: BLE001
        return None, None, f"{type(e).__name__}: {e}"


def probe(docs=None, quiet=False):
    rows = []
    for d in (docs or DOCS):
        raw, code, err = fetch(d["url"])
        rec = {"id": d["id"], "url": d["url"], "engine": d["engine"],
               "topic": d["topic"], "question": d["question"],
               "http": code, "at": int(time.time() * 1000)}
        if raw is None:
            rec.update({"status": "UNREACHABLE", "error": err,
                        "note": "ادعا UNVERIFIED می‌ماند — از حافظه نوشته نمی‌شود"})
        else:
            text = to_text(raw)
            ex = excerpts(text, d["want"])
            rec.update({"status": "FETCHED", "chars": len(text),
                        "found": sorted(ex), "missing": [w for w in d["want"]
                                                         if w not in ex],
                        "excerpts": ex})
            # صفحهٔ کوتاه یعنی احتمالاً پوستهٔ جاوااسکریپتی، نه محتوا.
            if len(text) < 1200:
                rec["status"] = "THIN"
                rec["note"] = ("صفحه محتوای متنی کافی نداشت (احتمالاً "
                               "رندر سمت کلاینت) — راستی‌آزمایی نشد")
            elif not ex:
                # درسِ ۲۳ اوت: صفحهٔ TradingView ۱۱ هزار کاراکتر برگرداند و
                # هیچ‌کدام از کلیدواژه‌ها را نداشت — یعنی منو و پانوشت آمده
                # بود و متنِ اصلی سمت کلاینت رندر می‌شود. حجمِ بایت دلیل
                # محتوا نیست؛ صفحه‌ای که هیچ شاهدی ندارد نباید «دریافت شد»
                # حساب شود، وگرنه دقیقاً همان موفقیتِ خاموشی است که این
                # ماژول برای جلوگیری از آن نوشته شد.
                rec["status"] = "NO_EVIDENCE"
                rec["note"] = ("صفحه آمد ولی هیچ کلیدواژه‌ای در متنش نبود "
                               "(محتوا سمت کلاینت رندر می‌شود) — ادعا "
                               "UNVERIFIED می‌ماند")
        rows.append(rec)
        if not quiet:
            print(f"  [{rec['status']:11}] {rec['id']:22} http={rec['http']} "
                  f"{'یافت: ' + ','.join(rec.get('found', [])) if rec.get('found') else rec.get('error', '')}")
    res = {"generated": int(time.time() * 1000), "panel": "لیام تریدر ۹",
           "docs": rows,
           "ok": sum(1 for r in rows if r["status"] == "FETCHED"),
           "no_evidence": [r["id"] for r in rows if r["status"] == "NO_EVIDENCE"],
           "total": len(rows),
           "note": ("اسناد حمید (۲۳ اوت). نشستِ کلود به این دامنه‌ها دسترسی "
                    "ندارد، پس کاوش روی رانر انجام می‌شود. تکهٔ متن شاهد است؛ "
                    "ورود به قفسه فقط بعد از خواندنِ همین شواهد (قانون ۰۳).")}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    if not quiet:
        print(f"\n{res['ok']} از {res['total']} سند دریافت شد → {OUT}")
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--quiet", action="store_true")
    r = probe(quiet=ap.parse_args().quiet)
    # نبودِ سند خطا نیست؛ سکوتِ بی‌گزارش خطاست.
    sys.exit(0)
