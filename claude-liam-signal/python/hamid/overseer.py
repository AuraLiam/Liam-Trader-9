"""E26 — ناظر کل مجموعه (ایجنت ۲۷؛ دستور حمید، ۱۷ اوت).

«بسیار سخت‌گیر، ماهر، باسواد و یک تریدر حرفه‌ای که با توجه به شرایط دستور
می‌دهد کدام انجین‌ها فعالیت و دقتشان را بالاتر ببرند.»

این ماژول بخش قطعیِ (Python) ناظر است — قانون ۰۶: عددها را کد می‌سنجد،
ایجنت LLM فقط برای ابهام/پژوهش صدا می‌شود. هر چرخه، وضعیت واقعی مجموعه
را از خروجی‌های ثبت‌شده می‌خواند و دستورهای مستدل صادر می‌کند:

  ورودی‌ها: کارنامهٔ پیپر (برد/باخت)، کارنامهٔ پیش‌بینی دامیننس، دفتر
  جایزهٔ انجین‌ها، تازگی داده‌ها، رژیم/رویداد کلان.
  خروجی: signals/overseer.json — دستورها با انجین هدف، دلیل و شدت؛
  پنل و ایجنت‌ها همین را می‌خوانند. دستور ناظر وتو/وزن معاملاتی ندارد —
  جهت‌دهی تمرکز است؛ تغییر قانون فقط از مسیر CI (قانون ۰۳).
"""
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
SIG = ROOT / "signals"
OUT = SIG / "overseer.json"

STALE_MIN = 30            # دادهٔ کهنه‌تر از این = دستور به E02/E23


def _load(p):
    try:
        return json.loads((SIG / p).read_text())
    except Exception:                                # noqa: BLE001
        return {}


def directives(report=None, now_ms=None):
    now = now_ms or int(time.time() * 1000)
    rep = report or _load("hamid-latest.json")
    dom = _load("dominance.json")
    rw = _load("rewards.json")
    out = []

    def order(engine, text, why, sev="normal"):
        out.append({"engine": engine, "order": text, "reason": why, "sev": sev})

    # ۱) کیفیت سیگنال — فقط از دفترِ سیگنال‌های واقعاً صادرشده.
    # عیب ممیزی ۲۳ اوت: این ماشه از lifetime می‌خواند که تمرین/اسکلپ/شوک/
    # آلارم را با محصول واقعی قاطی می‌کند (۳۱هزار معامله، R منفیِ آلوده) و
    # به E17/E11 دستورِ «دقت را بالا ببر» می‌داد در حالی که دفتر صادرشده
    # +۸۰٪ برد داشت. دستورِ ناظر باید به همان دفتری قلاب باشد که محصول است
    # (همان تفکیک قانون ۰۷)؛ دفترِ آلوده اصلاً مبنای دستور نیست.
    paper = (rep.get("paper") or {})
    sig = paper.get("sent_scan_signals") or {}
    n, wp = sig.get("trades") or 0, sig.get("win_pct")
    mr = sig.get("mean_r")
    if n >= 20 and wp is not None and (wp < 45 or (mr or 0) < 0):
        order("E17,E11", "دقت را بالا ببرید: فقط ستاپ‌های باکیفیت‌تر از میانه عبور کنند",
              f"کارنامهٔ دفتر صادرشده: {n} معامله، برد {wp}٪"
              + (f"، میانگین R={mr}" if mr is not None else ""), "high")

    # ۲) دامیننس — کارنامهٔ پیش‌بینی ضعیف = اعتماد کم، تحلیل عمیق‌تر
    sb = ((dom.get("forecast") or {}).get("scoreboard")) or {}
    tot = sum(v.get("n", 0) for v in sb.values())
    hit = sum(v.get("hit", 0) for v in sb.values())
    if tot >= 20 and hit / tot < 0.5:
        order("E03,E04", "تحلیل دامیننس را عمیق‌تر کنید و به رژیم فعلی کمتر تکیه شود",
              f"کارنامهٔ پیش‌بینی دامیننس {hit}/{tot} ({round(100*hit/tot)}٪) زیر ۵۰٪", "high")

    # ۳) رژیم UNSAFE/رویداد کلان → دقت اجرا
    reg = ((dom.get("structure") or {}).get("regime"))
    if reg == "UNSAFE":
        order("E16,E19", "سایز کوچک و اجرای سخت‌گیرانه تا عبور رویداد کلان",
              (dom.get("structure") or {}).get("unsafe_reason") or "رویداد کلان نزدیک", "high")

    # ۴) انجین با امتیاز منفی در دفتر جایزه → بازبینی همان انجین
    for row in (rw.get("board") or []):
        if row.get("points", 0) <= -3:
            order(row["engine"], "ردپای تأییدهایت بیشتر استاپ خورده — قواعد تأیید را بازبینی کن",
                  f"دفتر جایزه: {row['points']} امتیاز ({row.get('stop', 0)} استاپ)", "high")

    # ۵) تازگی داده — دامیننس کهنه یعنی زنجیرهٔ پایش لنگ می‌زند
    gen = dom.get("generated")
    if gen and now - gen > STALE_MIN * 60000:
        order("E02,E23", "زنجیرهٔ نمونه‌گیری دامیننس را احیا کنید",
              f"dominance.json {round((now-gen)/60000)} دقیقه کهنه است", "high")

    if not out:
        order("*", "وضعیت عادی — همان انضباط همیشگی، بدون تغییر تمرکز",
              "هیچ آستانهٔ هشداری فعال نیست", "info")
    return out


def run(report=None):
    ds = directives(report)
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({
        "generated": int(time.time() * 1000),
        "engine": "E26",
        "note": "ناظر کل — جهت‌دهی تمرکز؛ بدون وتو/وزن معاملاتی (قانون ۰۳)",
        "directives": ds,
    }, ensure_ascii=False, indent=1))
    for d in ds:
        print(f"ناظر کل → {d['engine']}: {d['order']} ({d['reason']})")
    return ds


if __name__ == "__main__":
    run()
