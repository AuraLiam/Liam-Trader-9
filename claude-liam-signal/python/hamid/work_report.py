"""گزارش کار — موتورِ قابل‌بازتولیدِ «نتایج را با جزئیات و خلاصه و دقیق بگو».

دستور حمید (۲۴ اوت): «همین مورد را تبدیل به یک اسکیل بکن که نخواهم هر بار
بگویم؛ تا گفتم گزارش کار را بده، نتایج را با جزئیات و خلاصه و دقیق بهم
بگو.» این فایل همان چیز است — نه یک متنِ دست‌نویس، که هر بار جور دیگری
درمی‌آید، بلکه یک اندازه‌گیری با ورودی و خروجی مشخص.

چه چیزی می‌سنجد (همهٔ برش‌ها روی همان پنجرهٔ زمانی):
  · هر دفتر جدا (سیگنالِ ارسال‌شده، اسکلپ، شوک، تمرین، آزمایش‌ها)
  · تایم‌فریم‌ها — «موفقیت در کدام تایم بیشتر بوده؟»
  · استاپ و تارگت: چند تا استاپ، چند تا تارگت، چند تا تریل، MFE/MAE،
    و مهم‌ترینشان: **معامله‌های در-سود که برگشتند و استاپ خوردند**
  · اثر تجربه (از hamid.experience_effect — با بازهٔ اطمینان)
  · جایزهٔ انجین‌ها (brain/rewards.json)

سه قیدِ صادقانه که این‌جا کد شده‌اند، نه توصیه:

۱. **هر عددِ اثر با CI می‌آید.** نمونهٔ کوچک حکم نمی‌گیرد. یک روزِ خوب
   «یادگیری» را اثبات نمی‌کند (قانون ۰۳، جدول ۲۳ اوت).
۲. **دفترها قاطی نمی‌شوند.** پیپر/تمرین/آزمایش سقف خوش‌بینانه‌اند
   (فیل کامل، بی‌لغزش)؛ عددِ سیگنالِ واقعاً ارسال‌شده جداست.
۳. **پوششِ ناقص گزارش می‌شود، پنهان نمی‌شود.** مثلاً `tf` روی همهٔ
   ردیف‌ها نیست؛ گزارشِ تایم‌فریم می‌گوید روی چند درصدِ نمونه حساب شده.

اجرا:
    python3 -m hamid.work_report                 # از ۰۰:۰۰ UTC امروز
    python3 -m hamid.work_report --hours 18      # پنجرهٔ دلخواه
    python3 -m hamid.work_report --json          # برای پنل/ورک‌فلو
"""
import argparse
import json
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
ROOT = HERE.parents[2]
CLOSED = ROOT / "brain" / "paper" / "closed.jsonl"
REWARDS = ROOT / "brain" / "rewards.json"
OUT = ROOT / "signals" / "work-report.json"

# دفترِ سیگنالِ واقعاً ارسال‌شده — همان تعریفی که experience_effect دارد.
SENT_STAGES = ("sig-ibs", "sig-smc")
# دفترهای دیگر، هر کدام با نامِ فارسیِ خودش. ناشناخته حذف نمی‌شود؛
# زیر «سایر» می‌آید تا ردیفی از قلم نیفتد.
BOOKS = {
    "sig-ibs": "سیگنال ارسالی — IBS+پولبک",
    "sig-smc": "سیگنال ارسالی — کانال/اردر بلاک",
    "scalp": "میز اسکلپ ۱د",
    "shock": "میز شوک بیت‌کوین",
    "practice": "تمرین (مربی)",
    "alarm": "دفتر آلارم",
    "v2": "موتور v2",
    "first": "آزمایش پولبک اول",
    "second": "پولبک دوم",
    "inducement": "آزمایش ایندوسمنت/ویک",
    "vetoed": "وتوشده (ضدواقع — اگر می‌رفت چه می‌شد)",
}
# دفترهایی که ادعای عملکرد نیستند: یا فرضیهٔ آزمایشی‌اند یا ضدواقع.
NOT_PERFORMANCE = {"first", "second", "inducement", "vetoed", "alarm"}


def load(since_ms=None, path=None):
    """ردیف‌های بستهٔ داخل پنجره. ردیفِ بی‌نمره (R=None) وارد آمار نمی‌شود."""
    p = Path(path) if path else CLOSED
    if not p.exists():
        return []
    out = []
    with p.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("R") is None:
                continue
            if since_ms and (r.get("closed") or 0) < since_ms:
                continue
            out.append(r)
    return out


def _tf_of(r):
    return r.get("tf") or (r.get("why") or {}).get("tf")


def _stage_of(r):
    return (r.get("why") or {}).get("stage") or "?"


def summarize(rows, label=""):
    """آمار پایهٔ یک گروه. n<8 حکمِ اثر نمی‌گیرد ولی عددش چاپ می‌شود."""
    rs = [float(r["R"]) for r in rows]
    if not rs:
        return {"label": label, "n": 0}
    won = sum(1 for x in rs if x > 0)
    oc = Counter(r.get("outcome") for r in rows)
    net = [float(r["R_net"]) for r in rows if r.get("R_net") is not None]
    return {
        "label": label, "n": len(rs), "won": won, "lost": len(rs) - won,
        "win_pct": round(won / len(rs) * 100, 1),
        "mean_r": round(statistics.fmean(rs), 4),
        "median_r": round(statistics.median(rs), 4),
        "sum_r": round(sum(rs), 2),
        "mean_r_net": round(statistics.fmean(net), 4) if net else None,
        "best_r": round(max(rs), 2), "worst_r": round(min(rs), 2),
        "outcomes": dict(oc.most_common()),
    }


def by_timeframe(rows):
    """«موفقیت در کدام تایم‌فریم بیشتر بوده؟» — با پوششِ صریح.

    `tf` روی همهٔ ردیف‌ها نیست. اگر پوشش را نگوییم، جدولِ تایم‌فریم
    شبیه یک تصویرِ کامل به‌نظر می‌رسد در حالی که بخشی از دفتر را اصلاً
    ندیده. پس هم پوشش چاپ می‌شود، هم ردیف‌های بی‌تایم زیر «نامشخص».
    """
    g = defaultdict(list)
    for r in rows:
        g[_tf_of(r) or "نامشخص"].append(r)
    known = sum(len(v) for k, v in g.items() if k != "نامشخص")
    tfs = [summarize(v, k) for k, v in g.items()]
    # مرتب بر انتظار، ولی فقط نمونهٔ کافی حق «بهترین» بودن دارد.
    ranked = sorted([t for t in tfs if t["n"] >= 8],
                    key=lambda t: -t["mean_r"])
    return {
        "coverage_pct": round(known / len(rows) * 100, 1) if rows else 0.0,
        "n_with_tf": known, "n_total": len(rows),
        "rows": sorted(tfs, key=lambda t: -t["n"]),
        "best": ranked[0]["label"] if ranked else None,
        "note": ("تایم‌فریمی که نمونه‌اش زیر ۸ باشد «بهترین» اعلام نمی‌شود؛ "
                 "با نمونهٔ کم هر تایمی می‌تواند اول شود."),
    }


def stops_and_targets(rows):
    """بازبینی استاپ و تارگت — همان چیزی که حمید جدا خواست.

    عددِ کلیدی `in_profit_stopped` است: معامله‌ای که MFE مثبت داشته و
    آخرش استاپ خورده. زیادشدنش یعنی یا تارگت دور است یا تریل دیر مسلح
    می‌شود — نه بدشانسی.
    """
    stops = [r for r in rows if r.get("outcome") == "stop"]
    tgts = [r for r in rows if r.get("outcome") == "target"]
    trails = [r for r in rows if r.get("outcome") == "trail"]
    mfe = [float(r["mfe_r"]) for r in rows if r.get("mfe_r") is not None]
    mae = [float(r["mae_r"]) for r in rows if r.get("mae_r") is not None]
    # استاپ‌هایی که قبلش در سود بوده‌اند، و چقدر در سود بوده‌اند
    ip = [float(r["mfe_r"]) for r in stops
          if r.get("mfe_r") is not None and float(r["mfe_r"]) > 0]
    # تارگت‌هایی که تا کجا رفتند (آیا تارگت خیلی نزدیک بوده؟)
    over = [float(r["mfe_r"]) for r in tgts if r.get("mfe_r") is not None]
    held = [float(r["held_h"]) for r in rows if r.get("held_h") is not None]
    fees = [float(r["fee_r"]) for r in rows if r.get("fee_r") is not None]
    out = {
        "n": len(rows), "stop": len(stops), "target": len(tgts),
        "trail": len(trails),
        "stop_pct": round(len(stops) / len(rows) * 100, 1) if rows else 0.0,
        "mean_mfe_r": round(statistics.fmean(mfe), 3) if mfe else None,
        "mean_mae_r": round(statistics.fmean(mae), 3) if mae else None,
        "in_profit_stopped": len(ip),
        "in_profit_stopped_pct": (round(len(ip) / len(stops) * 100, 1)
                                  if stops else None),
        "mean_mfe_of_stopped": round(statistics.fmean(ip), 3) if ip else None,
        "mean_mfe_of_targets": round(statistics.fmean(over), 3) if over else None,
        "mean_hold_h": round(statistics.fmean(held), 2) if held else None,
        "mean_fee_r": round(statistics.fmean(fees), 3) if fees else None,
    }
    hints = []
    if out["in_profit_stopped_pct"] and out["in_profit_stopped_pct"] >= 50:
        hints.append(f"{out['in_profit_stopped_pct']}٪ از استاپ‌ها قبلاً در "
                     f"سود بوده‌اند (میانگین {out['mean_mfe_of_stopped']}R) — "
                     "تریل دیر مسلح می‌شود یا استاپ داخل نویز است.")
    if out["mean_mfe_of_targets"] and out["mean_mfe_of_targets"] > 2.0:
        hints.append(f"تارگت‌ها به‌طور میانگین تا {out['mean_mfe_of_targets']}R "
                     "رفته‌اند — تارگت۱ احتمالاً نزدیک بسته می‌شود.")
    if out["mean_fee_r"] and out["mean_fee_r"] > 0.2:
        hints.append(f"کارمزد به‌طور میانگین {out['mean_fee_r']}R از هر معامله "
                     "می‌برد — استاپ‌ها تنگ‌اند (دام اسکالپ).")
    out["hints"] = hints or ["الگوی مشکل‌دار آشکاری در استاپ/تارگت دیده نشد."]
    return out


def rewards(top=8):
    """کارنامهٔ انجین‌ها. جایزه انگیزشی/عیب‌یابانه است — وتو و وزن ندارد."""
    if not REWARDS.exists():
        return {"available": False}
    try:
        d = json.loads(REWARDS.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"available": False}
    eng = []
    for k, v in (d.get("engines") or {}).items():
        n = (v.get("target", 0) + v.get("trail", 0) + v.get("stop", 0))
        eng.append({"engine": k, "points": v.get("points", 0),
                    "target": v.get("target", 0), "trail": v.get("trail", 0),
                    "stop": v.get("stop", 0), "n": n,
                    "pts_per_trade": round(v.get("points", 0) / n, 2) if n else None})
    eng.sort(key=lambda e: -(e["pts_per_trade"] or -99))
    return {"available": True, "engines": eng[:top],
            "note": "جایزه اثرِ علّی نیست؛ ردپای تأیید است. وتو/وزن ندارد."}


# ── میز استراتژی‌های جدید (دستور حمید ۲۶ اوت: «استراتژی‌های جدید رو بگو») ──
# فقط از فایل‌های حکمِ از-قبل-تولیدشده می‌خوانَد؛ خودش چیزی نمی‌سنجد.
_EXP_FILES = [
    ("موتور v2.8 روی ۳ سال", "brain/research/history/backtest3y.json"),
    ("هندسهٔ گشاد (استاپ ۲×، rr3)", "brain/research/history/backtest3y_rr3wide.json"),
    ("شکست سقف/کف ۴س (RR3، اهرم ۱۵)", "brain/research/history/strategy_break4h.json"),
    ("اردر بلاک (RR3، اهرم ۱۵)", "brain/research/history/strategy_ob3.json"),
]


def experiments():
    out = []
    for name, rel in _EXP_FILES:
        try:
            j = json.loads((ROOT / rel).read_text(encoding="utf-8"))
        except Exception:                            # noqa: BLE001
            continue
        o = j.get("overall") or {}
        oos = j.get("oos_2026") or {}
        if not o.get("n"):
            continue
        ci = o.get("ci95") or [None, None]
        verdict = ("CI بالای صفر" if ci[0] is not None and ci[0] > 0 else
                   "CI زیر صفر" if ci[1] is not None and ci[1] < 0 else
                   "CI شامل صفر")
        row = {"name": name, "n": o["n"], "mean_r_net": o.get("mean_r_net"),
               "ci95": ci, "verdict": verdict}
        if oos.get("n"):
            row["oos_2026"] = {"n": oos["n"],
                               "mean_r_net": oos.get("mean_r_net"),
                               "ci95": oos.get("ci95")}
        out.append(row)
    return out


def build(hours=None, since_ms=None, now_ms=None, path=None):
    now = now_ms or int(time.time() * 1000)
    if since_ms is None:
        if hours:
            since_ms = now - int(hours * 3600_000)
        else:                       # پیش‌فرض: از ۰۰:۰۰ UTC امروز
            t = time.gmtime(now / 1000)
            since_ms = int((now / 1000 - (t.tm_hour * 3600 + t.tm_min * 60
                                          + t.tm_sec)) * 1000)
    rows = load(since_ms, path=path)
    sent = [r for r in rows if _stage_of(r) in SENT_STAGES]
    live_books = [r for r in rows if _stage_of(r) not in NOT_PERFORMANCE]

    per_book, others = [], []
    g = defaultdict(list)
    for r in rows:
        g[_stage_of(r)].append(r)
    for stage, rs in sorted(g.items(), key=lambda kv: -len(kv[1])):
        s = summarize(rs, BOOKS.get(stage, f"سایر — {stage}"))
        s["stage"] = stage
        s["is_performance"] = stage not in NOT_PERFORMANCE
        (per_book if stage in BOOKS else others).append(s)

    rep = {
        "generated": now,
        "panel": "لیام تریدر ۹",
        "window": {
            "since": time.strftime("%Y-%m-%d %H:%M UTC",
                                   time.gmtime(since_ms / 1000)),
            "until": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(now / 1000)),
            "hours": round((now - since_ms) / 3600_000, 2),
        },
        "headline": summarize(sent, "سیگنالِ ارسال‌شده"),
        "all_live_books": summarize(live_books, "همهٔ دفترهای عملکردی"),
        "per_book": per_book + others,
        "timeframe": by_timeframe(live_books),
        "timeframe_sent_only": by_timeframe(sent),
        "stops_targets": stops_and_targets(live_books),
        "stops_targets_sent_only": stops_and_targets(sent),
        "rewards": rewards(),
        "boundary": ("دفترهای آزمایشی/وتوشده ادعای عملکرد نیستند و در سرخط "
                     "نمی‌آیند. عددِ پیپر سقف خوش‌بینانه است (فیل کامل، "
                     "بی‌لغزش). هر ادعای اثر فقط با CI ردشده از صفر."),
    }
    # اثر تجربه از ماژول خودش می‌آید، نه از حسابِ دوبارهٔ این‌جا — تا
    # تعریف «با تجربه» و روش بوت‌استرپ یک‌جا بماند (seed ثابت، بازتولیدپذیر).
    try:
        from hamid import experience_effect as EE
        rep["experience"] = [
            EE.measure(EE.load(since_ms=since_ms), "پنجرهٔ همین گزارش"),
            EE.measure(EE.load(since_ms=now - 7 * 86_400_000), "۷ روز اخیر"),
            EE.measure(EE.load(since_ms=0), "کل دفتر سیگنال"),
        ]
    except Exception as e:                          # noqa: BLE001
        rep["experience"] = []
        rep["experience_error"] = str(e)
    return rep


def _fa(x, suffix=""):
    return "—" if x is None else f"{x}{suffix}"


def text(rep):
    """خلاصهٔ فارسی — همان «خلاصه و دقیق» که حمید خواست، بالای جزئیات."""
    h, w = rep["headline"], rep["window"]
    L = [f"📊 گزارش کار — {w['since']} تا {w['until']}  ({w['hours']} ساعت)"]
    if h["n"]:
        L.append(f"سیگنالِ ارسال‌شده: {h['n']} بسته · {h['won']} برد / "
                 f"{h['lost']} باخت ({h['win_pct']}٪) · انتظار {h['mean_r']}R"
                 + (f" (خالص از کارمزد {h['mean_r_net']}R)"
                    if h.get("mean_r_net") is not None else ""))
        L.append(f"  نتیجه‌ها: {h['outcomes']}")
    else:
        L.append("سیگنالِ ارسال‌شده: هیچ معامله‌ای در این پنجره بسته نشد.")
    a = rep["all_live_books"]
    if a["n"]:
        L.append(f"همهٔ دفترهای عملکردی: {a['n']} بسته · {a['win_pct']}٪ برد "
                 f"· انتظار {a['mean_r']}R · جمع {a['sum_r']}R")

    tf = rep["timeframe"]
    L.append(f"\n⏱ تایم‌فریم (پوشش {tf['coverage_pct']}٪ از {tf['n_total']} ردیف):")
    for t in tf["rows"][:6]:
        if t["n"]:
            L.append(f"  {t['label']}: n={t['n']} · برد {t['win_pct']}٪ · "
                     f"انتظار {t['mean_r']}R")
    L.append(f"  ← بهترین با نمونهٔ کافی: {tf['best'] or 'هیچ‌کدام نمونهٔ کافی ندارد'}")

    st = rep["stops_targets"]
    L.append(f"\n🎯 استاپ و تارگت (n={st['n']}): استاپ {st['stop']} · "
             f"تارگت {st['target']} · تریل {st['trail']}")
    L.append(f"  MFE میانگین {_fa(st['mean_mfe_r'], 'R')} · "
             f"MAE میانگین {_fa(st['mean_mae_r'], 'R')} · "
             f"نگهداری {_fa(st['mean_hold_h'], ' ساعت')}")
    L.append(f"  در-سود ولی استاپ‌خورده: {st['in_profit_stopped']} "
             f"({_fa(st['in_profit_stopped_pct'], '٪')} از استاپ‌ها)")
    for hnt in st["hints"]:
        L.append(f"  ⚠️ {hnt}")

    if rep.get("experience"):
        L.append("\n🧠 اثر تجربه (هر خط با بازهٔ اطمینان):")
        for e in rep["experience"]:
            if e.get("ci95"):
                L.append(f"  {e['label']}: {e['n_with']} با / "
                         f"{e['n_without']} بدون · اختلاف {e['diff']:+}R · "
                         f"CI [{e['ci95'][0]:+}, {e['ci95'][1]:+}] → {e['verdict']}")
            else:
                L.append(f"  {e['label']}: {e['verdict']}")

    rw = rep.get("rewards") or {}
    if rw.get("available"):
        L.append("\n🏅 کارنامهٔ انجین‌ها (امتیاز بر معامله):")
        for e in rw["engines"][:5]:
            L.append(f"  {e['engine']}: {_fa(e['pts_per_trade'])} "
                     f"(n={e['n']} · تارگت {e['target']} / استاپ {e['stop']})")
        L.append(f"  {rw['note']}")

    ex = rep.get("experiments") or []
    if ex:
        L.append("\n🧪 میز استراتژی‌های جدید (حکم فقط با CI):")
        for e in ex:
            line = (f"  {e['name']}: n={e['n']} · خالص {_fa(e['mean_r_net'], 'R')} "
                    f"· {e['verdict']}")
            oos = e.get("oos_2026")
            if oos:
                line += (f" · برون‌نمونهٔ ۲۰۲۶: {_fa(oos['mean_r_net'], 'R')} "
                         f"{oos.get('ci95')}")
            L.append(line)
        L.append("  هیچ‌کدام هنوز مجوز تولید ندارند مگر CI بالای صفر + تأیید حمید.")

    L.append(f"\n{rep['boundary']}")
    return "\n".join(L)


def run(hours=None, as_json=False, quiet=False, write=True):
    rep = build(hours=hours)
    rep["experiments"] = experiments()
    if write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(rep, ensure_ascii=False, indent=1),
                       encoding="utf-8")
    if not quiet:
        print(json.dumps(rep, ensure_ascii=False, indent=1) if as_json
              else text(rep))
    return rep


def send_telegram(rep):
    """گزارش نوبت‌دار به تلگرام — دستور صریح حمید (۲۶ اوت): «دائم ترید کن
    و نتیجه و استراتژی‌های جدید را بگو». محصولِ خواسته‌شده است؛ هر نوبت
    محتوای تازه دارد، پس دروازهٔ ضدتکرار لازم ندارد (ثبت در DIRECT_OK)."""
    import telegram as tg
    token, chat = tg.creds()
    if not token:
        print("تلگرام: توکن نیست — گزارش فقط چاپ شد")
        return False
    body = text(rep)
    tg._post(token, "sendMessage",
             {"chat_id": chat, "text": body[:4000],
              "disable_web_page_preview": "true"})
    print("گزارش کار به تلگرام رفت")
    return True


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=float, default=None)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--send", action="store_true",
                    help="ارسال گزارش به تلگرام (کادنس مصوب حمید)")
    a = ap.parse_args()
    rep = run(hours=a.hours, as_json=a.json, quiet=a.send)
    if a.send:
        send_telegram(rep)
