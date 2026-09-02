"""اتاق فومو — شاهدِ نرم‌افزار fomo + شاخص داغیِ جمعیت (دستور حمید، ۲ سپتامبر).

حمید: «ایدهٔ جدید چی داری برای بهبود پنل؟ از نرم‌افزار فومو هم استفاده کن.»
و بعد از پرسش: «دقیقاً نرم‌افزار fomo».

## مرز صادقانه، پیش از هر چیز

نرم‌افزار fomo (fomo.family) اپ موبایلِ معاملهٔ میم‌کوین/آلت با لایهٔ
اجتماعی است: توکن ترند، تریدرهای برتر، هشدار خرید، کپی‌ترید. **API عمومی
ندارد.** پس هیچ چیزی از آن «کشیده» نمی‌شود؛ دو مسیر واقعی می‌ماند:

۱. **شاهدِ دستی**: آنچه حمید در فومو می‌بیند را با یک پیام کوتاه به همان
   بات می‌فرستد (`fomo TRUMP buy 3 …`). این ماژول آن را از getUpdates
   می‌خواند، فقط از چتِ خودِ حمید می‌پذیرد، در دفتر append-only ثبت
   می‌کند و بعداً با کندل واقعی نمره می‌دهد (MFE/MAE در ۱س/۴س/۲۴س).
۲. **داغیِ جمعیت (crowd heat)**: همان چیزی که فومو می‌فروشد، از داده‌ای
   که خودمان داریم بازسازی می‌شود: ترس/طمع + فاندینگ + رتبهٔ ترند
   کوین‌گکو. عددی ۰–۱۰۰ که روی هر سیگنال ثبت می‌شود تا ماشین بونفرونی
   شبانه بپرسد: «ورود وقتی جمعیت داغ است بدتر جواب می‌دهد؟»

هیچ‌کدام دروازه نیست، هیچ امتیازی بالا نمی‌برد (قانون ۱۱ لایهٔ اجتماعی:
سقف ۵٪ رأی، هرگز منبع عدد). فقط ثبت می‌شود و نمره می‌گیرد؛ ورودش به
تصمیم فقط از مسیر قانون ۰۳ (CI بالای صفر + تأیید حمید).

## دستور زبان پیام (سخت‌گیر — چیزی که پارس نشود، نادیده گرفته می‌شود)

    fomo <نماد> <buy|sell|trend|alert|top> [رتبه] [یادداشت آزاد]
    فومو <نماد> <خرید|فروش|ترند|هشدار|برتر> [رتبه] [یادداشت]

نماد بدون USDT هم قبول است (TRUMP → TRUMPUSDT). فقط پیام‌هایی که از
`TELEGRAM_CHAT_ID` آمده‌اند پذیرفته می‌شوند؛ هر فرستندهٔ دیگری رد.
"""
import json
import math
import os
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BRAIN = ROOT / "brain" / "fomo"
WITNESS = BRAIN / "witness.jsonl"          # append-only، کلید یکتا = update_id
OUTCOMES = BRAIN / "outcomes.jsonl"        # append-only، کلید = (update_id, horizon)
OFFSET = BRAIN / "offset-state.json"       # آخرین update_id مصرف‌شده — پسوند -state.json یعنی
                                           # حل‌کنندهٔ انتشار «مرز جلوتر برنده» را رویش اعمال می‌کند
OUT = ROOT / "signals" / "fomo.json"
PANEL = "لیام تریدر ۹"
ENGINE = "E15"

API = "https://api.telegram.org"
KINDS = {"buy": "buy", "sell": "sell", "trend": "trend", "alert": "alert", "top": "top",
         "خرید": "buy", "فروش": "sell", "ترند": "trend", "هشدار": "alert", "برتر": "top"}
HORIZONS = (("1h", 3600), ("4h", 14400), ("24h", 86400))
HEAT_HOT = 70          # آستانهٔ «داغ» برای شرط شبانه — عدد فرضیه است، نه قانون
MIN_N_TRACK = 20       # زیر این نمونه، کارنامه گزارش نمی‌شود (عدد بی‌پشتوانه چاپ نمی‌شود)

_WORD = re.compile(r"^(fomo|فومو)\s+([A-Za-z0-9]{2,15})\s+(\S+)(?:\s+(\d{1,3}))?(?:\s+(.*))?$",
                   re.IGNORECASE | re.DOTALL)


# ── ۱. پارس پیام ──────────────────────────────────────────────────────────
def norm_symbol(s):
    s = (s or "").strip().upper()
    if not s:
        return None
    if not s.endswith("USDT"):
        s += "USDT"
    return s


def parse(text):
    """dict یا None. فقط دستور زبان بالا؛ حدس نمی‌زند."""
    if not isinstance(text, str):
        return None
    m = _WORD.match(text.strip())
    if not m:
        return None
    kind = KINDS.get(m.group(3).lower())
    if not kind:
        return None
    rank = int(m.group(4)) if m.group(4) else None
    note = (m.group(5) or "").strip()[:200]
    return {"sym": norm_symbol(m.group(2)), "kind": kind, "rank": rank, "note": note}


# ── ۲. خواندن از تلگرام (فقط چت حمید) ───────────────────────────────────
def _fetch_updates(token, offset):
    q = urllib.parse.urlencode({"offset": offset, "timeout": 0, "allowed_updates": '["message"]'})
    req = urllib.request.Request(f"{API}/bot{token}/getUpdates?{q}")
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r).get("result") or []


def _load_offset():
    try:
        return int(json.loads(OFFSET.read_text()).get("offset") or 0)
    except Exception:                                # noqa: BLE001
        return 0


def _known_ids():
    ids = set()
    if WITNESS.exists():
        for line in WITNESS.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
                if isinstance(r, dict) and r.get("update_id") is not None:
                    ids.add(int(r["update_id"]))
            except Exception:                        # noqa: BLE001
                continue
    return ids


def ingest(fetch=None, token=None, chat_id=None, now_ms=None):
    """پیام‌های تازهٔ حمید → دفتر شاهد. برمی‌گرداند: فهرست ردیف‌های تازه.

    - فرستنده باید همان TELEGRAM_CHAT_ID باشد؛ غیر آن رد (و شمرده) می‌شود.
    - update_id تکراری هرگز دوباره ثبت نمی‌شود (append-only با هویت).
    - offset فقط بعد از نوشتنِ موفق جلو می‌رود."""
    token = token if token is not None else os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = str(chat_id if chat_id is not None else os.environ.get("TELEGRAM_CHAT_ID", "")).strip()
    fetch = fetch or (lambda off: _fetch_updates(token, off))
    if not token or not chat_id:
        return {"rows": [], "rejected": 0, "why": "بدون توکن/چت — چیزی خوانده نشد"}
    offset = _load_offset()
    try:
        ups = fetch(offset + 1 if offset else 0)
    except Exception as e:                           # noqa: BLE001 - شبکه نبود، دفعهٔ بعد
        return {"rows": [], "rejected": 0, "why": f"getUpdates نشد ({type(e).__name__})"}
    known = _known_ids()
    rows, rejected, max_id = [], 0, offset
    now_ms = now_ms or int(time.time() * 1000)
    for up in ups:
        if not isinstance(up, dict):
            continue
        uid = up.get("update_id")
        m = up.get("message") or {}
        if uid is None:
            continue
        max_id = max(max_id, int(uid))
        chat = str((m.get("chat") or {}).get("id", ""))
        if chat != chat_id:
            rejected += 1
            continue
        p = parse(m.get("text") or "")
        if not p or int(uid) in known:
            continue
        at = int((m.get("date") or now_ms / 1000) * 1000)
        rows.append({"update_id": int(uid), "at": at, "seen": now_ms,
                     "sym": p["sym"], "kind": p["kind"], "rank": p["rank"],
                     "note": p["note"], "source": "fomo-app/hamid"})
    if rows:
        BRAIN.mkdir(parents=True, exist_ok=True)
        with WITNESS.open("a", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    if max_id > offset:
        BRAIN.mkdir(parents=True, exist_ok=True)
        OFFSET.write_text(json.dumps({"offset": max_id, "at": now_ms}))
    return {"rows": rows, "rejected": rejected, "why": ""}


def witnesses():
    out = []
    if not WITNESS.exists():
        return out
    for line in WITNESS.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(line)
        except Exception:                            # noqa: BLE001
            continue
        if isinstance(r, dict) and r.get("sym") and r.get("at"):
            out.append(r)
    return out


# ── ۳. نمره‌دهی شاهد با کندل واقعی ──────────────────────────────────────
def _scored_keys():
    keys = set()
    if OUTCOMES.exists():
        for line in OUTCOMES.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
                keys.add((int(r["update_id"]), r["horizon"]))
            except Exception:                        # noqa: BLE001
                continue
    return keys


def forward_stats(candles, at_ms, secs):
    """بازده جلو + MFE/MAE از اولین کندلِ بعد از شاهد تا افق. کندل: [t,o,h,l,c,v]."""
    after = [c for c in candles if c[0] >= at_ms]
    if not after:
        return None
    start = after[0]
    end_t = at_ms + secs * 1000
    bar_ms = (after[1][0] - after[0][0]) if len(after) > 1 else 300000
    win = [c for c in after if c[0] <= end_t]
    if not win or win[-1][0] < end_t - bar_ms:
        return None                                  # افق هنوز کامل نشده — نمرهٔ نیمه‌کاره نمی‌دهیم
    p0 = float(start[1])
    if p0 <= 0:
        return None
    hi = max(float(c[2]) for c in win)
    lo = min(float(c[3]) for c in win)
    return {"ret": round(float(win[-1][4]) / p0 - 1, 5),
            "mfe": round(hi / p0 - 1, 5), "mae": round(lo / p0 - 1, 5), "bars": len(win)}


def score_outcomes(klines=None, now_ms=None):
    """هر شاهدِ رسیده به افق، یک ردیف نتیجه می‌گیرد. برمی‌گرداند شمار ردیف‌های تازه."""
    now_ms = now_ms or int(time.time() * 1000)
    if klines is None:
        import sources                                # noqa: WPS433 - فقط وقتی شبکه لازم است
        klines = lambda sym: sources.klines(sym, "5m", 300)   # noqa: E731
    done = _scored_keys()
    new = []
    cache = {}
    for w in witnesses():
        for hname, secs in HORIZONS:
            if (int(w["update_id"]), hname) in done or now_ms < w["at"] + secs * 1000:
                continue
            if w["sym"] not in cache:
                try:
                    cache[w["sym"]] = klines(w["sym"]) or []
                except Exception:                    # noqa: BLE001 - نماد بی‌کندل = بی‌نمره، نه صفر
                    cache[w["sym"]] = []
            st = forward_stats(cache[w["sym"]], w["at"], secs)
            if not st:
                continue
            new.append({"update_id": int(w["update_id"]), "sym": w["sym"], "kind": w["kind"],
                        "horizon": hname, "scored_at": now_ms, **st})
    if new:
        BRAIN.mkdir(parents=True, exist_ok=True)
        with OUTCOMES.open("a", encoding="utf-8") as fh:
            for r in new:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    return len(new)


def _wilson(k, n, z=1.96):
    if n <= 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(c - h, 3), round(c + h, 3)]


def track_record():
    """کارنامهٔ شاهدهای فومو به تفکیک افق: نرخ اصابتِ جهت (buy/trend/top/alert → بالا،
    sell → پایین). زیر MIN_N_TRACK نمونه، عدد گزارش نمی‌شود."""
    rows = []
    if OUTCOMES.exists():
        for line in OUTCOMES.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(line))
            except Exception:                        # noqa: BLE001
                continue
    out = {}
    for hname, _ in HORIZONS:
        hs = [r for r in rows if isinstance(r, dict) and r.get("horizon") == hname and r.get("ret") is not None]
        n = len(hs)
        if n < MIN_N_TRACK:
            out[hname] = {"n": n, "hit": None, "ci": None, "mean_ret": None,
                          "why": f"n={n} < {MIN_N_TRACK} — کارنامه هنوز عدد ندارد"}
            continue
        hits = sum(1 for r in hs if (r["ret"] < 0) == (r.get("kind") == "sell"))
        out[hname] = {"n": n, "hit": round(hits / n, 3), "ci": _wilson(hits, n),
                      "mean_ret": round(sum(r["ret"] for r in hs) / n, 5), "why": ""}
    return out


# ── ۴. داغیِ جمعیت ────────────────────────────────────────────────────────
def _clip(x, lo=0.0, hi=100.0):
    return max(lo, min(hi, x))


def crowd_heat(fear=None, funding_pct=None, trend_rank=None):
    """۰–۱۰۰. سه جزء با وزن صریح؛ جزء غایب از مخرج حذف می‌شود، جعل نمی‌شود.

    - ترس/طمع (۰–۱۰۰) همان‌طور که هست — وزن ۰.۴
    - فاندینگ میانگین (٪ در هر ۸ ساعت): −۰.۰۵ → ۰ · ۰ → ۵۰ · +۰.۰۵ → ۱۰۰ — وزن ۰.۴
    - رتبهٔ ترند کوین‌گکو برای همان نماد: رتبهٔ ۱ → ۱۰۰ … رتبهٔ ۱۰ → ۱۰، خارج از فهرست → ۰ — وزن ۰.۲
    """
    parts, wsum, total = {}, 0.0, 0.0
    if fear is not None:
        parts["fear_greed"] = _clip(float(fear)); wsum += 0.4; total += 0.4 * parts["fear_greed"]
    if funding_pct is not None:
        parts["funding"] = _clip(50 + float(funding_pct) * 1000); wsum += 0.4; total += 0.4 * parts["funding"]
    if trend_rank is not None:
        parts["trending"] = _clip(110 - 10 * int(trend_rank)) if 1 <= int(trend_rank) <= 10 else 0.0
        wsum += 0.2; total += 0.2 * parts["trending"]
    if wsum == 0:
        return {"heat": None, "label": "بی‌داده", "components": {}, "why": "هیچ جزئی در دسترس نبود"}
    heat = round(total / wsum, 1)
    label = "داغ" if heat >= HEAT_HOT else "سرد" if heat <= 30 else "معمولی"
    return {"heat": heat, "label": label, "components": parts, "why": ""}


def market_inputs(intel=None):
    """ورودی‌های بازار از intel (شبکه) — هر منبع جدا، شکستش جدا ثبت می‌شود."""
    if intel is None:
        from hamid import intel as _intel            # noqa: WPS433
        intel = _intel
    out = {"fear": None, "funding_avg": None, "trending": [], "errors": {}}
    try:
        out["fear"] = float(intel.fear_greed()["value"])
    except Exception as e:                           # noqa: BLE001
        out["errors"]["fear_greed"] = type(e).__name__
    try:
        f = intel.funding()
        vals = [v for k, v in f.items() if isinstance(v, (int, float))]
        out["funding_avg"] = round(sum(vals) / len(vals), 5) if vals else None
    except Exception as e:                           # noqa: BLE001
        out["errors"]["funding"] = type(e).__name__
    try:
        out["trending"] = [{"sym": norm_symbol(t["symbol"]), "rank": i + 1, "name": t.get("name")}
                           for i, t in enumerate(intel.trending() or [])]
    except Exception as e:                           # noqa: BLE001
        out["errors"]["trending"] = type(e).__name__
    return out


def heat_for(sym, market):
    rank = next((t["rank"] for t in (market.get("trending") or []) if t["sym"] == sym), None)
    return crowd_heat(market.get("fear"), market.get("funding_avg"), rank)


# ── ۵. عکس‌فوری برای پنل + ردپا روی سیگنال ───────────────────────────────
def snapshot_for(sym, snap=None):
    """آنچه روی هر سیگنال ثبت می‌شود (بدون شبکه؛ از signals/fomo.json).

    fomo_heat: داغی همان نماد در آخرین عکس‌فوری (یا بازار اگر نماد ترند نبود)
    fomo_witness: آیا در ۲۴ ساعت اخیر شاهدِ فومو برای همین نماد ثبت شده؟"""
    try:
        snap = snap if snap is not None else json.loads(OUT.read_text(encoding="utf-8"))
    except Exception:                                # noqa: BLE001
        return {"fomo_heat": None, "fomo_witness": None}
    if not isinstance(snap, dict):
        return {"fomo_heat": None, "fomo_witness": None}
    per = (snap.get("heat_by_symbol") or {}).get(sym)
    heat = per if isinstance(per, (int, float)) else (snap.get("market") or {}).get("heat")
    recent = {w.get("sym") for w in (snap.get("witness_recent") or [])
              if isinstance(w, dict) and (snap.get("generated") or 0) - (w.get("at") or 0) <= 86400000}
    return {"fomo_heat": heat, "fomo_witness": sym in recent}


def build_snapshot(market, tradable=None, now_ms=None):
    from hamid import evidence_packet as EP           # noqa: WPS433
    now_ms = now_ms or int(time.time() * 1000)
    ws = witnesses()
    recent = [w for w in ws if now_ms - w["at"] <= 86400000][-20:]
    mk = crowd_heat(market.get("fear"), market.get("funding_avg"), None)
    by_sym = {}
    trend_rows = []
    for t in market.get("trending") or []:
        ok, why = (tradable(t["sym"]) if tradable else (None, "بدون فهرست صرافی"))
        h = heat_for(t["sym"], market)
        by_sym[t["sym"]] = h["heat"]
        trend_rows.append({**t, "heat": h["heat"], "tradable": ok, "why": why})
    for w in recent:
        by_sym.setdefault(w["sym"], heat_for(w["sym"], market)["heat"])
    tr = track_record()
    best = next(((h, v) for h, v in tr.items() if v.get("hit") is not None), None)
    numbers = {"شاهدهای ۲۴ ساعت": len(recent), "کل شاهدها": len(ws),
               "داغی بازار": mk["heat"] if mk["heat"] is not None else "بی‌داده",
               "ترند قابل‌معامله": sum(1 for r in trend_rows if r["tradable"])}
    packet = EP.build(
        claim=(f"داغی جمعیت {mk['label']} ({mk['heat']})" if mk["heat"] is not None
               else "داغی جمعیت بی‌داده — هیچ عددی ساخته نشد"),
        numbers=numbers,
        track_record=(f"شاهد فومو در {best[0]}: اصابت {best[1]['hit']} CI {best[1]['ci']} n={best[1]['n']}"
                      if best else f"کارنامه: n هنوز کافی نیست ({tr['4h']['n']} از {MIN_N_TRACK})"),
        scenario_up="داغی بالا + شاهد buy: انتظارِ ادامهٔ کوتاه ولی ریسک تلهٔ خریدِ دیرهنگام — فقط ثبت، بدون امتیاز",
        scenario_down="داغی پایین/ترس + شاهد sell: انتظار فشار ادامه‌دار — فقط ثبت، بدون امتیاز",
        invalidator="CI کارنامهٔ شاهد در ۴س زیر یا شامل صفر با n≥۲۰۰ = شاهد بی‌ارزش؛ داغیِ بی‌اثر در ماشین شبانه = حذف فیلد",
        sources=["fomo-app (دستی، حمید)", "alternative.me fear&greed", "OKX funding", "CoinGecko trending"],
        limit="fomo API ندارد؛ شاهد فقط از پیام حمید. داغی از سه منبع عمومی؛ هیچ‌کدام دروازه یا امتیاز نیست (قانون ۱۱، سقف ۵٪)")
    return {"generated": now_ms, "panel": PANEL, "engine": ENGINE,
            "market": {**mk, "fear": market.get("fear"), "funding_avg": market.get("funding_avg"),
                       "errors": market.get("errors") or {}},
            "trending": trend_rows, "heat_by_symbol": by_sym,
            "witness_recent": recent, "witness_n": len(ws), "track_record": tr,
            "packet": packet, "packet_faults": EP.validate(packet),
            "note": ("اتاق فومو: شاهدِ دستی از اپ fomo + داغی جمعیت از دادهٔ عمومی. "
                     "ثبت و نمره؛ نه دروازه، نه امتیاز (قانون ۰۳/۱۱).")}


def run(quiet=False):
    # پوشهٔ دفتر همیشه وجود دارد (با .gitkeep) تا مسیر انتشار «brain/fomo»
    # پیش از اولین شاهد هم معتبر باشد — اجرای ۱ ورک‌فلو (۱۵:۲۵): مسیرِ
    # ناموجود کل git add را می‌کشت و fomo.json منتشر نمی‌شد.
    BRAIN.mkdir(parents=True, exist_ok=True)
    keep = BRAIN / ".gitkeep"
    if not keep.exists():
        keep.write_text("")
    ing = ingest()
    scored = score_outcomes()
    market = market_inputs()
    try:
        from hamid import venues                      # noqa: WPS433
        idx = venues.index()
        tradable = (lambda s: venues.tradable(s, idx)) if idx else None
    except Exception:                                # noqa: BLE001
        tradable = None
    snap = build_snapshot(market, tradable)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(snap, ensure_ascii=False, indent=1), encoding="utf-8")
    if not quiet:
        print(f"فومو: {len(ing['rows'])} شاهد تازه (رد {ing['rejected']}{' — ' + ing['why'] if ing['why'] else ''}) "
              f"· {scored} نمرهٔ تازه · داغی بازار {snap['market']['heat']} "
              f"· ترند {len(snap['trending'])} · خطاهای منبع {snap['market']['errors']}")
    return snap


if __name__ == "__main__":
    run()
