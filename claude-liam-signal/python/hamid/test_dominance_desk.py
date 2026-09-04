"""پاسبان اتاق دامیننس (۴ سپتامبر) — آفلاین، بدون شبکه، قطعی.

قفل می‌کند دستور حمید: «دامیننس مهم‌ترین بخش پیش از ترید» · «ریزش
دامیننس = بالا رفتن بازار» · هم‌ترازی تایم با ارزِ در دستِ تحلیل **ولی
روند کلی مهم‌تر از ریزتایم** · نقشهٔ ۴س و ۱س و جای دامیننس در کانال ·
**USDC.D** («موردی که باید خودت پیدا می‌کردی») · و چرخهٔ پول.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from hamid import dominance_desk as DD               # noqa: E402

OK = 0
FAIL = []
T0 = 1_800_000_000_000
MIN = 60_000


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


def series(n=3000, du=0.0, dc=0.0, db=0.0, step_min=5, with_usdc=True):
    """سری مصنوعی با شیب‌های کنترل‌شده — هر نقطه ۵ دقیقه."""
    pts = []
    for i in range(n):
        p = {"t": T0 + i * step_min * MIN,
             "u": round(5.0 + du * i, 6),
             "b": round(56.0 + db * i, 6)}
        if with_usdc:
            p["c"] = round(1.0 + dc * i, 6)
        pts.append(p)
    return pts


# ── ۱. قاعدهٔ پایه — جملهٔ خود حمید ─────────────────────────────────────
check("USDT.D پایین = بازار بالا", DD.base_rule(-0.1)["market"] == "UP")
check("USDT.D بالا = بازار پایین", DD.base_rule(+0.1)["market"] == "DOWN")
check("بی‌تغییر = خنثی", DD.base_rule(0.0)["market"] == "FLAT")
check("بی‌داده = UNKNOWN با دلیل، نه فرضِ خنثی",
      DD.base_rule(None)["market"] == "UNKNOWN"
      and "قانون ۱" in DD.base_rule(None)["why"])
check("دلیل هر حکم، عدد را نام می‌برد", "+0.1" in DD.base_rule(0.1)["why"])

# ── ۲. وزن تایم‌فریم — روند کلی مهم‌تر از ریزتایم ───────────────────────
check("۴س سنگین‌ترین وزن را دارد",
      DD.TF_WEIGHT["4h"] == max(DD.TF_WEIGHT.values()))
check("۵د سبک‌ترین", DD.TF_WEIGHT["5m"] == min(DD.TF_WEIGHT.values()))
check("و ترتیب وزن‌ها یک‌نواخت نزولی است",
      DD.TF_WEIGHT["4h"] > DD.TF_WEIGHT["1h"] > DD.TF_WEIGHT["15m"] > DD.TF_WEIGHT["5m"])
w = DD.weighted_regime({"4h": {"regime": "BULLISH"}, "1h": {"regime": "BULLISH"},
                        "15m": {"regime": "BEARISH"}, "5m": {"regime": "BEARISH"}})
check("۴س و ۱س صعودی در برابر ۱۵د و ۵د نزولی → حکم با تایم بالاست",
      w["regime"] == "BULLISH" and w["score"] > 0, str(w))
w2 = DD.weighted_regime({"4h": {"regime": "BEARISH"}, "5m": {"regime": "BULLISH"}})
check("و برعکسش هم — یک نوسان ۵دقیقه‌ای بسترِ ۴س را برنمی‌گرداند",
      w2["regime"] == "BEARISH", str(w2))
w3 = DD.weighted_regime({"4h": {"regime": "LOW_RESOLUTION", "note": "رزولوشن کم"},
                         "1h": {"regime": "BULLISH"}})
check("تایمِ بی‌رزولوشن رأی ندارد ولی صفر هم نمی‌شود — کنار گذاشته می‌شود",
      len(w3["skipped"]) == 1 and len(w3["used"]) == 1, str(w3))
check("و دلیل کنارگذاشتنش نوشته می‌شود", w3["skipped"][0]["why"])
w4 = DD.weighted_regime({"4h": {"regime": "INSUFFICIENT"}})
check("بی‌هیچ تایمِ معتبر، حکم اعلام نمی‌شود",
      w4["regime"] == "INSUFFICIENT" and w4["score"] is None)
check("جملهٔ دستور حمید روی خروجی نوشته شده", "ریزتایم" in w["why"])

# ── ۳. هم‌ترازی با تایمِ ارز (بند H4.2) ────────────────────────────────
r = DD.for_symbol_tf({"5m": {"tf": "5m", "regime": "BEARISH"}}, "5m")
check("خوانشِ همان تایمِ ارز برگردانده می‌شود", r["regime"] == "BEARISH")
check("و وزنش همراهش می‌آید", r["weight"] == DD.TF_WEIGHT["5m"])
check("با یادآوریِ صریح که ریزتایم بالادست را نقض نمی‌کند",
      "قانون ۲" in r["reminder"])
check("تایمِ نخوانده، رژیم جعلی نمی‌گیرد",
      DD.for_symbol_tf({}, "5m")["regime"] == "UNKNOWN")

# ── ۴. USDC.D — موردی که حمید گفت باید خودم پیدا می‌کردم ────────────────
u = DD.usdc_line(series(n=600, du=0.0005, dc=0.0002), minutes=240)
check("هر دو استیبل بالا = پول واقعاً از بازار بیرون رفته",
      u["ok"] and u["state"] == "TO_STABLE", str(u))
u = DD.usdc_line(series(n=600, du=-0.0005, dc=-0.0002), minutes=240)
check("هر دو استیبل پایین = پول واقعاً وارد بازار شده", u["state"] == "TO_RISK")
u = DD.usdc_line(series(n=600, du=0.0008, dc=-0.0008), minutes=240)
check("یکی بالا و دیگری پایین = چرخش بین دو استیبل، نه فرار از بازار",
      u["state"] == "STABLE_ROTATION", str(u))
check("و صریح هشدار می‌دهد جهت بازار را از این حرکت نتیجه نگیر",
      "نتیجه نگیر" in u["why"], u["why"])
u = DD.usdc_line(series(n=600, du=0.000001, dc=-0.000001), minutes=240)
check("حرکت زیر آستانه، حکم قاطع نمی‌گیرد", u["state"] == "MIXED")
u = DD.usdc_line(series(n=600, du=0.0005, with_usdc=False), minutes=240)
check("بدون USDC.D در سری، عدد جعل نمی‌شود",
      u["ok"] is False and "جعل نمی‌شود" in u["why"], str(u))
u = DD.usdc_line(series(n=600, du=0.0005, dc=0.0002), minutes=240)
check("سهم مجموع استیبل‌ها هم گزارش می‌شود", u["stable_total"] > 0)
check("و دلیلِ اهمیت USDC روی خروجی نوشته شده", "اروپا" in u["note"])

# ── ۵. چرخهٔ پول ────────────────────────────────────────────────────────
m = DD.money_cycle(series(n=600, du=0.0006, dc=0.0002, db=-0.0002), minutes=240)
check("وقتی استیبل‌ها بالا و بیت‌کوین پایین است، پول به استیبل می‌رود",
      m["ok"] and m["state"].endswith("استیبل"), str(m))
m = DD.money_cycle(series(n=600, du=-0.0006, dc=-0.0002, db=0.001), minutes=240)
check("وقتی استیبل‌ها پایین و بیت‌کوین بالا، پول به بیت‌کوین می‌رود",
      m["state"].endswith("بیت‌کوین"), str(m))
m = DD.money_cycle(series(n=600, du=0.0, dc=0.0, db=0.0), minutes=240)
check("بی‌حرکت = QUIET، نه حکمِ ساختگی", m["state"] == "QUIET", str(m))
check("سه پایهٔ چرخه جدا گزارش می‌شوند",
      set(m["legs"]) == {"stable", "btc", "alt"})
check("و صریح گفته می‌شود سهم آلت باقی‌ماندهٔ حسابی است نه اندازه‌گیری",
      "باقی‌ماندهٔ حسابی" in m["note"])
m2 = DD.money_cycle(series(n=600, du=0.0006, db=-0.0002, with_usdc=False), minutes=240)
check("بی USDC هم چرخه شمرده می‌شود ولی غیبتش نوشته می‌شود",
      m2["ok"] and "USDC.D" in m2["missing"], str(m2.get("missing")))
check("بی USDT.D یا BTC.D اصلاً حکم نمی‌دهد",
      DD.money_cycle([{"t": T0, "u": 5.0}], 240)["ok"] is False)

# ── ۶. نقشهٔ ۴س و ۱س ────────────────────────────────────────────────────
pts = series(n=3000, du=0.00002, db=-0.00001, dc=0.00001)
ch = DD.channel_place(pts)
check("نقشهٔ کانال روی ۴س و ۱س ساخته می‌شود",
      ch["ok"] and set(ch["frames"]) <= {"4h", "1h"} and ch["frames"], str(ch.get("why")))
for tf, row in (ch.get("frames") or {}).items():
    check(f"[{tf}] قیمت و جای دامیننس گزارش می‌شود",
          row["px"] is not None and row.get("where"))
check("کانالِ نبوده، جای زوری اعلام نمی‌کند",
      all("زوری" in r["where"] or r.get("pos_pct") is not None
          for r in (ch.get("frames") or {}).values()))
check("سریِ کوتاه نقشه نمی‌سازد و دلیلش را می‌گوید",
      DD.channel_place(series(n=10))["ok"] is False)

# ── ۷. تابلوی کامل ──────────────────────────────────────────────────────
b = DD.build(pts, tf="5m")
for k in ("base_rule", "by_tf", "btc_d_by_tf", "weighted", "tf_weights",
          "symbol_tf", "channel", "usdc", "money_cycle", "chg_1h", "boundary"):
    check(f"تابلو بخش «{k}» را دارد", k in b)
check("مالک اتاق E03 است", b["engine"] == "E03")
check("سری خیلی کوتاه، اتاق را ساکت می‌کند نه پرگو",
      DD.build([{"t": T0, "u": 5.0}])["ok"] is False)
check("مرز روی تابلو نوشته می‌شود",
      "بستر می‌دهد نه دستور" in b["boundary"] and "قانون ۰۳" in b["boundary"])
src = (HERE / "dominance_desk.py").read_text(encoding="utf-8")
for bad in ("sendMessage", "requests.post", "urlopen"):
    check(f"اتاق «{bad}» ندارد — چیزی نمی‌فرستد", bad not in src)

# ── ۸. سیم‌کشی ──────────────────────────────────────────────────────────
ROOT = HERE.parents[2]
reg = json.loads((ROOT / "config" / "state_registry.json").read_text(encoding="utf-8"))["files"]
check("dominance-desk.json ردیف قرارداد دارد (قانون ۱۳)",
      "dominance-desk.json" in reg
      and reg["dominance-desk.json"]["producer"] == "hamid/dominance_desk.py",
      str(reg.get("dominance-desk.json")))
wf = (ROOT / ".github" / "workflows" / "pump-radar.yml").read_text(encoding="utf-8")
check("زنجیرهٔ سیگنال اتاق دامیننس را می‌سازد", "hamid.dominance_desk --write" in wf)

print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
sys.exit(1 if FAIL else 0)
