#!/usr/bin/env python3
"""گزارش ساعتی اتاق دامیننس — دستور صریح حمید (۲۶ اوت شب).

«هر یک ساعت نظریهٔ ایجنت و انجین دامیننس‌ها رو برام بفرسته با چارت یک
ساعته.» هر ساعت یک پیام: چارت کندلی ۱ساعتهٔ USDT.D و BTC.D از سری
واقعی اتاق دامیننس + نظریهٔ ساختاری (روند ۱س/۴س، سطح‌های معتبر،
سناریوی هر دو جهت — قانون ۱۱: همیشه درخت سناریو) + کارنامهٔ
پیش‌بینی‌های نمره‌خورده.

صداقت: اگر سری کافی نیست، همان را می‌گوید و حکم نمی‌سازد (قانون ۱).
ضدتکرار: حافظهٔ خودش (signals/dominance-report.json) — زیر ۵۰ دقیقه از
گزارش قبلی دوباره نمی‌فرستد مگر --force.
"""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
ROOT = PY.parents[1]
sys.path.insert(0, str(PY))

SERIES = ROOT / "brain" / "dominance-series.json"
DOM = ROOT / "signals" / "dominance.json"
STATE = ROOT / "signals" / "dominance-report.json"
MIN_GAP_MIN = 50
BARS_SHOWN = 72          # سه روزِ ۱ساعته روی چارت


def _tehran(ts_ms):
    t = time.gmtime(ts_ms / 1000 + 3.5 * 3600)
    return time.strftime("%H:%M", t)


def _bars_1h(key, n=BARS_SHOWN):
    from hamid import dominance as D
    try:
        pts = json.loads(SERIES.read_text()).get("points") or []
    except Exception:                                # noqa: BLE001
        return []
    return D._bars(pts, key)[-n:]


def render(path):
    """چارت ۱ساعتهٔ دو پنلی — کندل واقعی هر سطل، سطح‌های معتبر، واترمارک."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    bu = _bars_1h("u")
    bb = _bars_1h("b")
    if len(bu) < 12 or len(bb) < 12:
        return None
    try:
        dom = json.loads(DOM.read_text())
    except Exception:                                # noqa: BLE001
        dom = {}
    mt = (dom.get("multi_tf") or {})

    fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=False)
    fig.patch.set_facecolor("#101418")
    for ax, bars, name, key in ((axes[0], bu, "USDT.D", "usdt"),
                                (axes[1], bb, "BTC.D", "btc_d")):
        ax.set_facecolor("#101418")
        for i, k in enumerate(bars):
            up = k["c"] >= k["o"]
            col = "#26a69a" if up else "#ef5350"
            ax.plot([i, i], [k["l"], k["h"]], color=col, linewidth=0.8)
            ax.plot([i, i], [k["o"], k["c"]], color=col, linewidth=3.2,
                    solid_capstyle="butt")
        st1 = ((mt.get(key) or {}).get("1h") or {})
        for lv in (st1.get("levels_above") or [])[:2]:
            ax.axhline(lv, color="#ffb74d", linewidth=0.7, linestyle="--", alpha=0.7)
        for lv in (st1.get("levels_below") or [])[:2]:
            ax.axhline(lv, color="#4fc3f7", linewidth=0.7, linestyle="--", alpha=0.7)
        ax.set_title(f"{name} · 1h", color="#e0e0e0", fontsize=11, loc="left")
        ax.tick_params(colors="#9e9e9e", labelsize=8)
        for sp in ax.spines.values():
            sp.set_color("#37474f")
        ticks = list(range(0, len(bars), 12))
        ax.set_xticks(ticks)
        ax.set_xticklabels([_tehran(bars[i]["t"]) for i in ticks])
        ax.text(0.5, 0.5, "Trade_osuli", transform=ax.transAxes,
                fontsize=26, color="#ffffff", alpha=0.06,
                ha="center", va="center")
    fig.suptitle(f"اتاق دامیننس — {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}",
                 color="#e0e0e0", fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=110, facecolor=fig.get_facecolor())
    plt.close(fig)
    return path


def _scenario(name, st1):
    """درخت سناریوی دو جهت — قانون ۱۱: هر دو جهت با مقصد بعدی."""
    if not st1 or st1.get("note"):
        return f"{name}: دادهٔ ساختاری کافی نیست — حکم نمی‌سازیم"
    up = (st1.get("levels_above") or [None])[0]
    dn = (st1.get("levels_below") or [None])[0]
    px = st1.get("px")
    lines = []
    if up:
        lines.append(f"بالا برود: اول واکنش در {up}")
    if dn:
        lines.append(f"پایین بیاید: اول واکنش در {dn}")
    return f"{name} ({px}): " + " · ".join(lines) if lines else f"{name}: سطح معتبری ثبت نشده"


def _calendar_lines(dom):
    """تقویم رویدادهای پیش رو — همهٔ رویدادها با ساعت تهران (دستور ۲۷ اوت:
    «خبرای مهم فردا رو دقیق بدونی کی هست»). درس همان شب: سخنرانی رئیس فد
    در داده بود ولی گزارش فقط نزدیک‌ترین رویداد را چاپ می‌کرد."""
    mac = dom.get("macro") or []
    if not mac:
        return []
    gen = dom.get("generated") or time.time() * 1000
    rows = []
    for e in sorted(mac, key=lambda x: x.get("in_hours") or 99)[:5]:
        hrs = e.get("in_hours")
        when = _tehran(gen + hrs * 3600 * 1000) if isinstance(hrs, (int, float)) else "؟"
        rows.append(f"{e.get('title')} ({e.get('country', '?')}) ساعت {when}")
    out = ["📅 پیش رو: " + " · ".join(rows)]
    # آنلاک‌های توکن — فقط اگر منبع راستی‌آزمایی‌شده جواب داده باشد
    try:
        from hamid import intel
        ul = intel.unlocks()
        if ul.get("status") == "OK" and ul["events"]:
            toks = " · ".join(x["token"] for x in ul["events"][:4])
            out.append(f"🔓 آنلاک هفتهٔ پیش رو: {toks}")
    except Exception:                                # noqa: BLE001
        pass
    return out


def build():
    try:
        dom = json.loads(DOM.read_text())
    except Exception:                                # noqa: BLE001
        return None
    age_min = (time.time() * 1000 - (dom.get("generated") or 0)) / 60000
    mt = dom.get("multi_tf") or {}
    u1 = (mt.get("usdt") or {}).get("1h") or {}
    u4 = (mt.get("usdt") or {}).get("4h") or {}
    b1 = (mt.get("btc_d") or {}).get("1h") or {}
    b4 = (mt.get("btc_d") or {}).get("4h") or {}
    sb = ((dom.get("forecast") or {}).get("scoreboard") or {})
    # کارنامه با بنچمارک — نه فقط درصدِ کل (اندازه‌گیری ۲۹ اوت: ۸۷.۶٪
    # پیش‌بینی‌ها FLAT بودند، پس «۷۳.۵٪ اصابت» عمدتاً پاداشِ گفتنِ
    # «تکان نمی‌خورد» بود نه تشخیص مسیر). عددی که بنچمارک ندارد،
    # اعتبارنامه نیست — و روی گزارشِ حمید نباید مثل اعتبارنامه چاپ شود.
    graded = []
    for k in sorted(sb):
        r = sb[k]
        if not (isinstance(r, dict) and r.get("n")):
            continue
        line = f"{k}: {r.get('hit', r.get('hits', 0))}/{r['n']}"
        if r.get("skill") is not None:
            line += f" (مهارت {r['skill']:+g} در برابر «همیشه FLAT»)"
        if r.get("dir_n"):
            line += f" · جهت‌دار {r['dir_n']} نوبت {r.get('dir_hit_pct')}٪"
        graded.append(line)
    cap = ["🏷 <b>لیام تریدر ۹</b> · 🧭 <b>نظریهٔ ساعتی دامیننس</b>"]
    if age_min > 90:
        cap.append(f"⚠️ دادهٔ اتاق {age_min:.0f} دقیقه کهنه است — نظریهٔ تازه صادر نمی‌شود (قانون ۱)")
    else:
        cap.append(f"USDT.D <code>{dom.get('usdt_dominance')}</code> · "
                   f"۱س {u1.get('trend','?')} · ۴س {u4.get('trend','?')}")
        cap.append(f"BTC.D <code>{dom.get('btc_dominance')}</code> · "
                   f"۱س {b1.get('trend','?')} · ۴س {b4.get('trend','?')}")
        if dom.get("verdict"):
            cap.append(f"💬 {dom['verdict']}")
        cap += _calendar_lines(dom)
        cap.append("📐 " + _scenario("USDT.D", u1))
        cap.append("📐 " + _scenario("BTC.D", b1))
        if graded:
            cap.append("🎯 کارنامهٔ پیش‌بینی (با بنچمارک):")
            cap += [f"   • {g}" for g in graded[:4]]
        inv = (dom.get("structure") or {}).get("invalidation")
        if inv:
            cap.append(f"⛔ {inv}")
        # بستهٔ شواهد (قانون ۱۲): منابع + مرز صادقانه، روی هر گزارش
        cap.append("🔗 منابع: سری خود اتاق · تقویم ForexFactory/TradingView")
        cap.append("⚖️ مرز صادقانه: سناریو شاهد است نه دروازه — تصمیم فقط از دروازه‌های سخت")
    cap.append(f"🕐 <code>{_tehran(time.time()*1000)}</code> به وقت ایران")
    return "\n".join(cap)


def already_sent_recently():
    try:
        last = json.loads(STATE.read_text()).get("last_sent") or 0
    except Exception:                                # noqa: BLE001
        last = 0
    return (time.time() * 1000 - last) < MIN_GAP_MIN * 60 * 1000


def mark_sent():
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps({"last_sent": int(time.time() * 1000)}))


def main(argv):
    force = "--force" in argv
    send = "--send" in argv
    cap = build()
    if cap is None:
        print("dominance_report: signals/dominance.json در دسترس نیست")
        return 1
    if send and already_sent_recently() and not force:
        print("dominance_report: زیر ۵۰ دقیقه از گزارش قبلی — نمی‌فرستم")
        return 0
    png = None
    try:
        png = render(str(ROOT / "signals" / "dominance-report.png"))
    except Exception as e:                           # noqa: BLE001
        print(f"dominance_report: چارت کشیده نشد ({type(e).__name__})")
    print(cap)
    if not send:
        return 0
    import telegram as tg
    token, chat = tg.creds()
    if not token:
        print("dominance_report: بدون کلید تلگرام — نرفت")
        return 1
    try:
        # کپشن بلندتر از سقف ۱۰۲۴ تلگرام دو تکه می‌شود: سر با عکس، دنباله
        # ریپلای همان پیام — همان الگوی سیگنال‌ها (درس SOL/CRCLB)
        head, tail = tg._split_caption(cap)
        if png:
            with open(png, "rb") as f:
                r = tg._post(token, "sendPhoto",
                             {"chat_id": chat, "parse_mode": "HTML",
                              "caption": head},
                             {"photo": ("dominance.png", f.read())})
        else:
            r = tg._post(token, "sendMessage",
                         {"chat_id": chat, "parse_mode": "HTML", "text": head})
        if r and tail:
            mid = ((r.get("result") or {}).get("message_id")
                   if isinstance(r, dict) else None)
            try:
                tg._post(token, "sendMessage",
                         {"chat_id": chat, "parse_mode": "HTML", "text": tail,
                          **({"reply_to_message_id": mid,
                              "allow_sending_without_reply": True} if mid else {})})
            except Exception:                        # noqa: BLE001 - دنباله گزارش را نمی‌کشد
                pass
        if r:
            mark_sent()
            tg.record_out("dom_report", "نظریهٔ ساعتی دامیننس",
                          {"chart": bool(png)})
            print("dominance_report: رفت ✓")
            return 0
    except Exception as e:                           # noqa: BLE001
        print(f"dominance_report: ارسال نشد ({tg.scrub(e)})")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
