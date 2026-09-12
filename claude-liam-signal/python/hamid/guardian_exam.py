#!/usr/bin/env python3
"""تستِ مهارت و استفاده از تجربه — ققنوس از ۱۲ متخصص و انجین‌ها امتحان می‌گیرد.

دستور حمید (۱۲ سپتامبر): «هر ۱۲ متخصص باید بر اساس استراتژیشون نظر بدن و
هیچ استثنایی وجود نداره… و تو به عنوان ققنوس و نفر اصلی این پنل باید از
همه انجین‌ها و ایجنت‌ها و به خصوص ۱۲ متخصص تست مهارت و استفاده از تجربه
بگیری که مطمئن بشی از همه داده‌ها استفاده می‌کنند.»

═══════════════════════════════════════════════════════════════════════
  چرا این فایل لازم شد — یک عیبِ واقعی که بدون امتحان دیده نمی‌شد
═══════════════════════════════════════════════════════════════════════

در اجرای بازپخشِ ۱۲ سپتامبر، چهار مراقب (ثور، حمل، میزان، سنبله) **دقیقاً
یک عدد** دادند: n=۳۰۵۳، خالص +۰.۰۱۰۸R، صفر امتناع، صفر ردِ زیرآستانه.
علتش این بود که میدانِ ورودی‌شان روی هر ستاپ پر بود و رأیشان همیشه از
آستانه رد می‌شد — یعنی عملاً غربال نمی‌کردند. کارنامه‌شان «خوب» به نظر
می‌رسید در حالی که اصلاً تصمیمی نگرفته بودند.

هیچ سنجهٔ سود/زیانی این را لو نمی‌دهد. فقط امتحانی که بپرسد «آیا اصلاً
رأیت تغییر می‌کند؟» آن را می‌گیرد. سه پرسشِ این امتحان از همان‌جا آمد:

  ۱. **مشارکت** — چند درصد ستاپ‌ها را اصلاً رأی دادی؟ (ممتنعِ دائمی = کور)
  ۲. **تمایز** — رأیت بین ستاپ‌ها فرق می‌کند یا همیشه یک عدد است؟
  ۳. **کارنامه** — وقتی رأی دادی، بازار تأییدت کرد؟ (با بازهٔ اطمینان)

و برای «استفاده از همهٔ داده‌ها»: دلیلِ امتناع‌ها دسته‌بندی می‌شود، چون
خودِ موتور موقع امتناع می‌نویسد **کدام داده نبود**. پس فهرستِ داده‌های
گمشده از خروجیِ خودِ کد درمی‌آید، نه از حدسِ من.

═══════════════════════════════════════════════════════════════════════
  مرزِ صادقانه — از پیش نوشته
═══════════════════════════════════════════════════════════════════════

۱. این امتحان **نمره‌ای به سود و زیان نمی‌دهد** و هیچ وزنی را عوض
   نمی‌کند. فقط می‌گوید هر مراقب چقدر از داده‌اش استفاده کرده و رأیش
   چقدر معنا داشته. تغییر وزن فقط از مسیر کارنامهٔ قانون ۱۶.
۲. «کور» یعنی دادهٔ تخصصش نرسیده، **نه** این‌که تخصصش بی‌ارزش است. این
   دو را قاطی کردن همان اشتباهی است که شبِ ۱۱ سپتامبر نزدیک بود بکنم.
۳. کارنامه روی معامله‌های بسته‌ای است که رأی مراقبان رویشان ثبت شده؛
   n کم = بی‌حکم، نه «ضعیف».
۴. امتحانِ انجین‌ها از گذرگاه وضعیت نقل می‌شود، نه سنجهٔ دوم — دو تعریف
   از «سالم» در یک مخزن، همان بی‌نظمی‌ای است که قانون ۱۳ بست.

    python3 -m hamid.guardian_exam --selftest
    python3 -m hamid.guardian_exam --write
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
ROOT = HERE.parents[2]
OUT = ROOT / "signals" / "guardian-exam.json"
VERDICTS = ROOT / "brain" / "phoenix" / "verdicts.jsonl"
CLOSED = ROOT / "brain" / "paper" / "closed.jsonl"
REGISTRY = ROOT / "config" / "state_registry.json"

from hamid import phoenix as PH                              # noqa: E402

# قاعده‌های امتحان — **قبل از دیدن نتیجه** ثبت شده‌اند.
MIN_SEEN = 30          # زیر این، دربارهٔ مشارکت/تمایز حکم نمی‌دهیم
MIN_SCORED = 25        # زیر این، کارنامه عدد نمی‌گیرد
BLIND_PCT = 80.0       # امتناع ≥ این ⇒ «کورِ داده»
FLAT_DISTINCT = 1      # رأی‌های متمایز ≤ این ⇒ «رأی بی‌تمایز»

GIDS = [g["id"] for g in PH.GUARDIANS]
FA = {g["id"]: f'{g["sign"]} {g["name"]}' for g in PH.GUARDIANS}
SPEC = {g["id"]: g["specialty"] for g in PH.GUARDIANS}
ENGINE = {g["id"]: g.get("engine") for g in PH.GUARDIANS}


def _rows(path, limit=None):
    """خواندنِ بردبارِ دفترِ append-only — خطِ خراب کلِ امتحان را نمی‌خواباند."""
    if not Path(path).exists():
        return []
    out = []
    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:                                    # noqa: BLE001
            continue
    return out[-limit:] if limit else out


def _wilson(k, n, z=1.96):
    """بازهٔ ویلسون — روی نسبت، نه میانگین. با n کم صادق‌تر از نرمال است."""
    if not n:
        return None, None, None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return round(p, 4), round(c - h, 4), round(c + h, 4)


def _bucket(why):
    """دلیلِ امتناع را به یک سطلِ کوتاه می‌برد.

    متنِ دلیل را خودِ رأی‌دهنده نوشته؛ پس فهرستِ «کدام داده نبود» از
    خروجیِ کد درمی‌آید نه از حدس. سطل‌ها درشت‌اند تا یک جمله‌بندیِ تازه
    سطلِ جدید نسازد.
    """
    t = (why or "").strip()
    if not t:
        return "بی‌دلیل"
    for key, name in (("دامیننس", "دادهٔ دامیننس نبود"),
                      ("BTC", "شاهد بستر بیت‌کوین نبود"),
                      ("نقدینگی", "شاهد نقدینگی نبود"),
                      ("کارنامه", "کارنامهٔ تاریخی کافی نبود"),
                      ("خبر", "اجماع خبری نبود"),
                      ("جمعیت", "شاهد جمعیت نبود"),
                      ("فومو", "شاهد جمعیت نبود"),
                      ("اردر بلاک", "دادهٔ اردر بلاک نبود"),
                      ("کیفیت", "کیفیت/کندل ثبت نشده بود"),
                      ("روند", "دادهٔ روند نبود"),
                      ("خطای مراقب", "خطای اجرای مراقب")):
        if key in t:
            return name
    return t[:40]


def participation(verdicts):
    """مشارکت و تمایزِ رأی — از دفترِ رأی، نه از نتیجهٔ معامله."""
    seen = {g: 0 for g in GIDS}
    voted = {g: [] for g in GIDS}
    abst = {g: {} for g in GIDS}
    for v in verdicts:
        votes = v.get("votes") or {}
        for gid, d in votes.items():
            if gid not in seen:
                continue
            seen[gid] += 1
            val = d.get("v")
            if val is None:
                b = _bucket(d.get("why"))
                abst[gid][b] = abst[gid].get(b, 0) + 1
            else:
                voted[gid].append(float(val))
    out = {}
    for gid in GIDS:
        vs = voted[gid]
        n = seen[gid]
        distinct = len(set(round(x, 3) for x in vs))
        out[gid] = {
            "n_seen": n,
            "n_voted": len(vs),
            "abstain_pct": round((n - len(vs)) / n * 100, 1) if n else None,
            "distinct_votes": distinct,
            "vote_sd": round(statistics.pstdev(vs), 4) if len(vs) > 1 else 0.0,
            "vote_mean": round(statistics.fmean(vs), 4) if vs else None,
            "abstain_reasons": dict(sorted(abst[gid].items(),
                                           key=lambda kv: -kv[1])[:3]),
        }
    return out


def scored(closed):
    """کارنامه — و چرا «نرخ درستی» به‌تنهایی دروغ می‌گوید.

    اولین نسخهٔ همین تابع فقط می‌پرسید «علامتِ رأی با علامتِ نتیجه یکی
    بود؟» و هشت مراقب «مهارت اثبات‌شده» گرفتند. بعد پایه را شمردم:
    **۷۴.۸٪ از همین معامله‌ها برنده‌اند**. یعنی مراقبی که ۹۶٪ مواقع مثبت
    رأی می‌دهد، بی‌هیچ مهارتی ~۷۵٪ «درست» می‌شود — و سنبله با ۶۹٪ عملاً
    *بدتر از پایه* بود، نه بهتر. عددِ خوش‌ظاهری که جهتش هم غلط بود.

    پس دو سنجه کنار هم می‌آید:

      · **برتری نسبت به پایه** (`edge_pp`): نرخ درستی منهای همان چیزی که
        با همین سهمِ رأی مثبت و همین پایه، شانسی به دست می‌آمد.
      · **جداسازیِ R** (`sep`): میانگین خالصِ «وقتی موافق بود» منهای
        «وقتی مخالف بود» — با بوت‌استرپِ خوشه‌ای روی نماد، چون معامله‌های
        یک نماد مستقل نیستند.

    حکم روی **جداسازی** بنا می‌شود نه نرخ درستی: پرسشِ واقعی این نیست که
    «چند بار درست گفت» بلکه «آیا حرفش پول را جابه‌جا کرد».
    """
    from hamid.ob_lab import _cluster_boot
    hit = {g: [0, 0] for g in GIDS}          # [درست, کل]
    pos = {g: 0 for g in GIDS}               # شمارِ رأی مثبت
    r_for = {g: {} for g in GIDS}            # نماد → فهرست R خالص
    r_against = {g: {} for g in GIDS}
    base_r = []
    for t in closed:
        w = t.get("why") or {}
        pv = w.get("phoenix_votes") or {}
        if not pv:
            continue
        r = t.get("R_net")
        if r is None:
            r = t.get("R")
        if r is None:
            continue
        r = float(r)
        if r == 0:
            continue
        sym = t.get("sym") or "?"
        base_r.append(r)
        for gid, val in pv.items():
            if gid not in hit or val is None:
                continue
            val = float(val)
            if val == 0:
                continue
            hit[gid][1] += 1
            if (val > 0) == (r > 0):
                hit[gid][0] += 1
            if val > 0:
                pos[gid] += 1
                r_for[gid].setdefault(sym, []).append(r)
            else:
                r_against[gid].setdefault(sym, []).append(r)
    base = (sum(1 for r in base_r if r > 0) / len(base_r)) if base_r else None
    alpha = 1 - (1 - 0.05) ** (1 / len(GIDS))       # Šidák روی ۱۲ مقایسه
    out = {"_base_win_rate": round(base, 4) if base is not None else None,
           "_n_population": len(base_r),
           "_alpha_sidak": round(alpha, 5)}
    for gid in GIDS:
        k, n = hit[gid]
        p, lo, hi = _wilson(k, n)
        share = (pos[gid] / n) if n else None
        # آنچه با همین سهمِ رأی مثبت و همین پایه، **شانسی** به دست می‌آمد
        exp = (share * base + (1 - share) * (1 - base)) \
            if (share is not None and base is not None) else None
        fv = [x for v in r_for[gid].values() for x in v]
        av = [x for v in r_against[gid].values() for x in v]
        ci = None
        if fv and av:
            ci = _cluster_boot(r_for[gid], r_against[gid], alpha)
        out[gid] = {
            "n_scored": n, "hit": k, "hit_rate": p, "hit_ci": [lo, hi],
            "pos_share": round(share, 4) if share is not None else None,
            "expected_hit": round(exp, 4) if exp is not None else None,
            "edge_pp": round((p - exp) * 100, 2)
            if (p is not None and exp is not None) else None,
            "mean_r_when_for": round(statistics.fmean(fv), 4) if fv else None,
            "n_for": len(fv),
            "mean_r_when_against": round(statistics.fmean(av), 4) if av else None,
            "n_against": len(av),
            "sep": round(statistics.fmean(fv) - statistics.fmean(av), 4)
            if (fv and av) else None,
            "sep_ci": [round(ci[0], 4), round(ci[1], 4)] if ci else None,
        }
    return out


def verdict(part, sc):
    """حکمِ امتحان — ترتیبش مهم است: کور و بی‌تمایز **قبل از** کارنامه.

    چون کارنامهٔ یک رأی‌دهندهٔ بی‌تمایز بی‌معناست: او تصمیمی نگرفته که
    درست یا غلط باشد.
    """
    if (part["n_seen"] or 0) < MIN_SEEN:
        return "بی‌حکم — هنوز کم دیده"
    if part["abstain_pct"] is not None and part["abstain_pct"] >= BLIND_PCT:
        return "کورِ داده — دادهٔ تخصصش نمی‌رسد"
    if part["n_voted"] and part["distinct_votes"] <= FLAT_DISTINCT:
        return "رأی بی‌تمایز — همیشه یک عدد"
    n = sc["n_scored"]
    if n < MIN_SCORED:
        return "فعال — کارنامه هنوز نمونهٔ کافی ندارد"
    # حکم روی **جداسازیِ R** است نه نرخ درستی: با پایهٔ برد ۷۵٪، نرخ
    # درستیِ بالا را هر رأیِ همیشه-مثبتی رایگان می‌گیرد.
    if not sc.get("n_against") or not sc.get("n_for"):
        return "فعال — یک‌طرفه رأی می‌دهد، مقایسه‌ای ممکن نیست"
    ci = sc.get("sep_ci")
    if not ci or ci[0] is None:
        return "فعال — بازهٔ جداسازی هنوز ساخته نشد"
    if ci[0] > 0:
        return "مهارت اثبات‌شده (جداسازیِ R بالای صفر)"
    if ci[1] < 0:
        return "ضدِ مهارت (جداسازیِ R زیر صفر)"
    return "فعال — هنوز از تصادف جدا نشده"


def engines():
    """امتحانِ انجین‌ها: از گذرگاه وضعیت نقل می‌شود، سنجهٔ دوم ساخته نمی‌شود."""
    try:
        from hamid import state_bus
        st = state_bus.scan()
    except Exception as e:                                   # noqa: BLE001
        return {"status": "UNAVAILABLE", "why": type(e).__name__}
    if not isinstance(st, dict) or "rows" not in st:
        return {"status": "UNAVAILABLE", "why": "گذرگاه ردیفی نداد"}
    by_owner = {}
    for r in st["rows"]:
        o = r.get("owner") or "?"
        d = by_owner.setdefault(o, {"ok": 0, "bad": 0})
        d["ok" if r.get("status") in ("ok", "absent_ok") else "bad"] += 1
    bad = sorted((o for o, d in by_owner.items() if d["bad"]),
                 key=lambda o: -by_owner[o]["bad"])
    return {"status": st.get("verdict"), "n_files": st.get("n_files"),
            "n_faults": st.get("n_faults"),
            "owners_with_faults": {o: by_owner[o] for o in bad},
            "n_owners": len(by_owner), "by_owner": by_owner}


def build(n_recent=None):
    v = _rows(VERDICTS, n_recent)
    c = _rows(CLOSED)
    part = participation(v)
    sc = scored(c)
    rows = {}
    for gid in GIDS:
        rows[gid] = {"fa": FA[gid], "specialty": SPEC[gid], "engine": ENGINE[gid],
                     **part[gid], **sc[gid],
                     "verdict": verdict(part[gid], sc[gid])}
    tally = {}
    for r in rows.values():
        k = r["verdict"].split(" —")[0].split(" (")[0]
        tally[k] = tally.get(k, 0) + 1
    blind = [r["fa"] for r in rows.values() if r["verdict"].startswith("کور")]
    flat = [r["fa"] for r in rows.values() if r["verdict"].startswith("رأی بی‌تمایز")]
    return {
        "generated": int(time.time() * 1000),
        "panel": "لیام تریدر ۹",
        "owner": "E00",
        "advisory": True,
        "n_verdicts": len(v),
        "base_win_rate": sc.get("_base_win_rate"),
        "n_population": sc.get("_n_population"),
        "alpha_sidak": sc.get("_alpha_sidak"),
        "n_closed_with_votes": sum(1 for t in c if (t.get("why") or {}).get("phoenix_votes")),
        "rules": {"min_seen": MIN_SEEN, "min_scored": MIN_SCORED,
                  "blind_pct": BLIND_PCT, "flat_distinct": FLAT_DISTINCT,
                  "hit_ci": "ویلسون ۹۵٪"},
        "guardians": rows,
        "tally": tally,
        "blind": blind,
        "flat": flat,
        "engines": engines(),
        "boundary": ("این امتحان مشاوره‌ای است: هیچ وزنی، آستانه‌ای یا "
                     "سیگنالی را عوض نمی‌کند. «کور» یعنی دادهٔ تخصص نرسیده، "
                     "نه این‌که تخصص بی‌ارزش است. کارنامه فقط روی "
                     "معامله‌های بسته‌ای است که رأی مراقبان رویشان ثبت شده؛ "
                     "n کم = بی‌حکم. امتحانِ انجین‌ها از گذرگاه وضعیت نقل "
                     "می‌شود و سنجهٔ دومی ساخته نشده (قانون ۱۳)."),
    }


def render(d):
    b = d.get("base_win_rate")
    L = [f"🔥 امتحانِ ققنوس — {d['n_verdicts']} رأی · "
         f"{d['n_closed_with_votes']} معاملهٔ بسته با رأی · "
         f"پایهٔ برد {('%.1f%%' % (b*100)) if b else '—'}"]
    for gid in GIDS:
        r = d["guardians"][gid]
        hit = "—" if r["hit_rate"] is None else f"{r['hit_rate']*100:.0f}%"
        edge = "—" if r.get("edge_pp") is None else f"{r['edge_pp']:+.1f}pp"
        sep = "—" if r.get("sep") is None else f"{r['sep']:+.3f}R {r.get('sep_ci')}"
        L.append(f"{r['fa']:<14} دیده={r['n_seen']:<4} رأی={r['n_voted']:<4} "
                 f"ممتنع={r['abstain_pct']}% تمایز={r['distinct_votes']:<3} "
                 f"مثبت={('%.0f%%' % (r['pos_share']*100)) if r.get('pos_share') is not None else '—':<5} "
                 f"درستی={hit} برتری={edge}")
        L.append(f"{'':<14} جداسازی={sep} (n={r['n_scored']}) → {r['verdict']}")
        if r["abstain_reasons"]:
            L.append(f"{'':<14} چرا ممتنع: " +
                     " · ".join(f"{k}×{v}" for k, v in r["abstain_reasons"].items()))
    return "\n".join(L)


def _selftest():
    ok = fails = 0

    def chk(c, m):
        nonlocal ok, fails
        if c:
            ok += 1
        else:
            fails += 1
            print(f"  ✗ {m}")

    chk(len(GIDS) == 12, f"شمار مراقبان {len(GIDS)}")

    # ── مشارکت و تمایز ────────────────────────────────────────────────
    def vrow(votes):
        return {"votes": {g: votes.get(g, {"v": None, "why": "نبود"})
                          for g in GIDS}}
    # A: همیشه یک عدد (بی‌تمایز) · B: متغیر · C: همیشه ممتنع
    A, B, C = GIDS[0], GIDS[1], GIDS[2]
    vs = []
    for i in range(40):
        vs.append(vrow({A: {"v": 0.5, "why": ""},
                        B: {"v": (i % 7) / 10 - 0.3, "why": ""},
                        C: {"v": None, "why": "دامیننس تازه در دسترس نیست"}}))
    p = participation(vs)
    chk(p[A]["distinct_votes"] == 1, f"تمایزِ رأی ثابت: {p[A]['distinct_votes']}")
    chk(p[B]["distinct_votes"] > 3, f"تمایزِ رأی متغیر: {p[B]['distinct_votes']}")
    chk(p[C]["abstain_pct"] == 100.0, f"امتناع کامل: {p[C]['abstain_pct']}")
    chk(p[A]["abstain_pct"] == 0.0, "رأی‌دهندهٔ دائمی امتناع نشان داد")
    chk("دادهٔ دامیننس نبود" in p[C]["abstain_reasons"],
        f"دلیلِ امتناع سطل نشد: {p[C]['abstain_reasons']}")
    chk(p[A]["vote_sd"] == 0.0, "انحرافِ رأی ثابت صفر نشد")

    # ── کارنامه ──────────────────────────────────────────────────────
    #
    # جمعیتِ ساختگی عمداً **پایهٔ برد ۷۵٪** دارد و روی ۸ نماد پخش است:
    # پایهٔ بالا همان تله‌ای است که این تابع برای گرفتنش نوشته شد، و
    # چند-نماد بودن شرطِ بوت‌استرپِ خوشه‌ای است (نسخهٔ اولِ همین آزمون
    # یک نماد داشت و مسیرِ جداسازی اصلاً اجرا نمی‌شد).
    D, E = GIDS[3], GIDS[4]                    # D با مهارت · E ضدِ مهارت
    closed = []
    for i in range(80):
        good = i % 4 != 0                      # ۷۵٪ برنده
        r = 1.0 if good else -1.0
        closed.append({"sym": f"S{i % 8}USDT", "R_net": r,
                       "why": {"phoenix_votes": {
                           A: 0.5,                       # همیشه موافق
                           B: -0.5,                      # همیشه مخالف
                           C: None,                      # ممتنع
                           D: 0.6 if good else -0.6,     # موافقِ برنده‌ها
                           E: -0.6 if good else 0.6}}})  # قرینه
    s = scored(closed)
    chk(s[A]["n_scored"] == 80, f"شمارِ کارنامه: {s[A]['n_scored']}")
    chk(abs((s[A]["hit_rate"] or 0) - 0.75) < 1e-9, f"نرخ درستی: {s[A]['hit_rate']}")
    chk(s[C]["n_scored"] == 0, "ممتنع وارد کارنامه شد")
    chk(abs((s["_base_win_rate"] or 0) - 0.75) < 1e-9,
        f"پایهٔ برد غلط: {s['_base_win_rate']}")
    # قلبِ ماجرا: رأیِ همیشه-مثبت با ۷۵٪ درستی باید **برتریِ صفر** بگیرد
    chk(abs(s[A]["edge_pp"]) < 1e-6,
        f"رأی همیشه-مثبت برتری گرفت: {s[A]['edge_pp']}pp")
    chk(s[D]["edge_pp"] > 20, f"مهارتِ واقعی برتری نگرفت: {s[D]['edge_pp']}")
    chk(s[D]["sep"] is not None and s[D]["sep"] > 1.5, f"جداسازی D: {s[D]['sep']}")
    chk(s[E]["sep"] is not None and s[E]["sep"] < -1.5, f"جداسازی E: {s[E]['sep']}")
    chk(s[D]["sep_ci"] and s[D]["sep_ci"][0] > 0, f"بازهٔ D: {s[D]['sep_ci']}")
    # معاملهٔ دقیقاً صفر نباید شمرده شود
    z = scored([{"R_net": 0.0, "why": {"phoenix_votes": {A: 0.5}}}])
    chk(z[A]["n_scored"] == 0, "معاملهٔ صفر شمرده شد")

    # ── ترتیبِ حکم: کور و بی‌تمایز قبل از کارنامه ─────────────────────
    chk(verdict(p[C], s[C]).startswith("کورِ داده"), f"حکم کور: {verdict(p[C], s[C])}")
    chk(verdict(p[A], s[A]).startswith("رأی بی‌تمایز"),
        f"رأیِ ثابت با کارنامهٔ خوب «مهارت» گرفت: {verdict(p[A], s[A])}")
    # یک‌طرفه = غیرقابل‌مقایسه، نه «ضد مهارت»
    chk(verdict(p[B], s[B]).startswith("فعال — یک‌طرفه"),
        f"رأیِ یک‌طرفه حکمِ قطعی گرفت: {verdict(p[B], s[B])}")
    pd_ = {"n_seen": 140, "abstain_pct": 0.0, "n_voted": 140, "distinct_votes": 5}
    chk(verdict(pd_, s[D]).startswith("مهارت اثبات‌شده"), f"حکم D: {verdict(pd_, s[D])}")
    chk(verdict(pd_, s[E]).startswith("ضدِ مهارت"), f"حکم E: {verdict(pd_, s[E])}")
    chk(verdict({"n_seen": 3, "abstain_pct": 0, "n_voted": 3, "distinct_votes": 3},
                s[D]).startswith("بی‌حکم"), "با n کم حکم داد")
    chk(verdict(pd_, {"n_scored": 5}).startswith("فعال"),
        "کارنامهٔ کم‌نمونه حکمِ قطعی گرفت")

    # ── امتحانِ انجین‌ها واقعاً وصل است ────────────────────────────────
    #
    # نسخهٔ اولِ همین بخش `state_bus.build()` را صدا می‌زد — تابعی که وجود
    # ندارد — و چون داخل try بود، بی‌صدا «UNAVAILABLE» می‌داد. یعنی بخشی
    # از امتحان که حمید خواسته («از همه انجین‌ها») عملاً خالی بود و هیچ
    # قرمزی هم نمی‌ساخت. این بررسی همان کلاس را می‌بندد.
    e = engines()
    chk(e.get("status") != "UNAVAILABLE", f"امتحانِ انجین‌ها وصل نیست: {e}")
    chk((e.get("n_owners") or 0) >= 10, f"شمارِ مالکان کم است: {e.get('n_owners')}")
    chk(isinstance(e.get("by_owner"), dict) and e["by_owner"],
        "تفکیکِ مالکان خالی است")

    # ── نگهبان: امتحان هیچ دفترِ تولیدی را نمی‌نویسد (قانون ۰۵) ───────
    src = (HERE / "guardian_exam.py").read_text(encoding="utf-8")
    body = src.split("def _selftest(")[0]
    for bad in ("paper._append", "telegram.", "VERDICTS.open", "CLOSED.open",
                "digest_closed"):
        chk(bad not in body, f"امتحان به دفترِ تولید دست زد: {bad}")
    chk("OUT.write_text" in src, "امتحان خروجیِ خودش را نمی‌نویسد")

    print(f"guardian_exam: {ok} بررسی سبز" + (f" · {fails} قرمز" if fails else ""))
    return 1 if fails else 0


def main(argv=()):
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--recent", type=int, default=None,
                    help="فقط N رأیِ آخر (پیش‌فرض: همه)")
    a = ap.parse_args(list(argv))
    if a.selftest:
        return _selftest()
    d = build(a.recent)
    print(render(d))
    if a.write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\nنوشته شد: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
