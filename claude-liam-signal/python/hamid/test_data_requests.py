"""آزمون آفلاین قانون ۱۹ — درخواست داده + مأموریت وفق‌پذیری.

  ۱. قرارداد زنده معتبر است؛ خطاهای کلاس گرفته می‌شوند (نوع/مالک/خوراک/فایل/n).
  ۲. برآورده‌سازی بی‌جعل: کندل تازه → ok با روند؛ کهنه → why_not؛ خوراک
     ناموفق/کهنه → why_not؛ فایل بی‌ردیف → why_not؛ استثنا → why_not.
  ۳. هر (نماد،تایم) فقط یک بار کشیده می‌شود.
  ۴. --add: درخواست نامعتبر رد و فایل دست‌نخورده می‌ماند.
  ۵. هر ایجنت و هر متخصص نشانگر مأموریت و کلید درست دارد؛ تزریق idempotent.
  ۶. ردیف قرارداد، زنجیره، سرویس محلی، قانون ۱۹.

    python3 -m hamid.test_data_requests
"""
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from hamid import data_requests as DQ                # noqa: E402

ROOT = DQ.ROOT
FAIL = []
OK = 0


def check(name, cond, extra=""):
    global OK
    if cond:
        OK += 1
        print(f"  ✓ {name}")
    else:
        FAIL.append(name)
        print(f"  ✗ {name} {extra}")


# ۱) قرارداد زنده
reqs, errs = DQ.load_contract()
errs += DQ.validate(reqs)
check("قرارداد زنده معتبر است", not errs, str(errs[:3]))
check("قوس (E14) خبر و تقویم را سفارش دارد",
      {r["id"] for r in reqs.get("E14", [])} >= {"news", "calendar"})
bad = {"E03": [{"id": "x", "kind": "magic", "why": "?", "max_age_min": 5}],
       "E99": [{"id": "y", "kind": "feed", "feed": "news", "why": "?", "max_age_min": 5}],
       "E05": [{"id": "z", "kind": "kline", "symbol": "BTC", "tf": "3m", "n": 5,
                "why": "?", "max_age_min": 5},
               {"id": "w", "kind": "state", "file": "nope.json", "why": "?", "max_age_min": 5},
               {"id": "w", "kind": "feed", "feed": "tiktok", "why": "", "max_age_min": 0}]}
e = DQ.validate(bad)
check("کلاس خطاها گرفته می‌شود (نوع/مالک/نماد/tf/n/فایل/خوراک/why/تکرار)",
      len(e) >= 8, f"{len(e)}: {e[:3]}")

# ۲) برآورده‌سازی با دادهٔ قلابی — بدون شبکه
NOW = 1_800_000_000_000
TF = 3_600_000
calls = []


def kget(sym, tf, n):
    calls.append((sym, tf))
    if sym == "DEADUSDT":
        raise RuntimeError("451")
    fresh = sym == "BTCUSDT"
    last = NOW - (10 * 60000 if fresh else 5 * TF)
    # زیگزاگ روی شیب مثبت — سوینگ می‌سازد تا structure.trend «up» را ببیند
    # (پلهٔ یکنواخت هیچ سوینگی ندارد و «range» می‌شود — همان مرزِ خودِ trend)
    def c(i):
        return 100 + i * 0.4 + (1.2 if (i // 5) % 2 == 0 else -1.2)
    return [{"t": last - (n - 1 - i) * TF, "o": c(i) - 0.2, "h": c(i) + 0.8,
             "l": c(i) - 0.8, "c": c(i), "v": 1} for i in range(n)]


intake = {"generated": NOW - 60000, "items": [
    {"id": "ext:news", "family": "external", "ok": True, "age_min": 20,
     "payload": {"count": 7, "hot": [{"source": "s", "title": "t"}]}},   # شکلِ واقعیِ intake
    {"id": "ext:calendar", "family": "external", "ok": False, "age_min": 20, "error": "403"},
    {"id": "state:dominance.json", "family": "state", "ok": True, "age_min": 12, "digest": {"v": 1}},
    {"id": "state:market-stance.json", "family": "state", "ok": True, "age_min": 500, "digest": {}},
]}
R = {"E06": [{"id": "b1", "kind": "kline", "symbol": "BTCUSDT", "tf": "1h", "n": 60, "why": "?", "max_age_min": 30},
             {"id": "b2", "kind": "kline", "symbol": "BTCUSDT", "tf": "1h", "n": 60, "why": "?", "max_age_min": 30},
             {"id": "old", "kind": "kline", "symbol": "ETHUSDT", "tf": "1h", "n": 60, "why": "?", "max_age_min": 30},
             {"id": "dead", "kind": "kline", "symbol": "DEADUSDT", "tf": "1h", "n": 60, "why": "?", "max_age_min": 30}],
     "E14": [{"id": "news", "kind": "feed", "feed": "news", "why": "?", "max_age_min": 60},
             {"id": "cal", "kind": "feed", "feed": "calendar", "why": "?", "max_age_min": 60},
             {"id": "fg", "kind": "feed", "feed": "fear_greed", "why": "?", "max_age_min": 60}],
     "E03": [{"id": "dom", "kind": "state", "file": "dominance.json", "why": "?", "max_age_min": 45},
             {"id": "st", "kind": "state", "file": "market-stance.json", "why": "?", "max_age_min": 120}]}
doc = DQ.fulfill(R, kget=kget, intake=intake, now_ms=NOW)
o6 = {r["id"]: r for r in doc["owners"]["E06"]["items"]}
check("کندل تازه → ok با روند و قیمت", o6["b1"]["ok"] and o6["b1"]["summary"]["trend"] == "up"
      and o6["b1"]["summary"]["close"] > 100 and o6["b1"]["summary"]["chg_pct_20"] > 0)
check("کندل کهنه → برآورده نشد با دلیل", not o6["old"]["ok"] and "کهنه" in o6["old"]["why_not"])
# ۱۵ سپتامبر، اثبات روی Actions: کندل ۴س سالم «۳۴۶د کهنه» خوانده شد چون سن از
# open سنجیده می‌شد. حالا سن = دقیقه از بسته‌شدن آخرین کندل (کندل باز = ۰).
check("سن کندل از بسته‌شدنش شمرده می‌شود، نه از بازشدنش", o6["b1"]["age_min"] == 0.0
      and o6["old"]["age_min"] == 240.0, f"{o6['b1']['age_min']} / {o6['old']['age_min']}")
check("max_age_min کمتر از یک کندل رد می‌شود (همیشه کهنه می‌شد)",
      any("کمتر از یک کندل" in e for e in DQ.validate(
          {"E06": [{"id": "x", "kind": "kline", "symbol": "BTCUSDT", "tf": "4h", "n": 60, "why": "?", "max_age_min": 60}]})))
check("منبع مرده → why_not، نه عدد", not o6["dead"]["ok"] and "451" in o6["dead"]["why_not"]
      and o6["dead"]["summary"] is None)
check("هر (نماد،تایم) یک بار کشیده شد", calls.count(("BTCUSDT", "1h")) == 1, str(calls))
o14 = {r["id"]: r for r in doc["owners"]["E14"]["items"]}
check("خوراک سالم → ok با خلاصهٔ واقعیِ payload (نه خالی)", o14["news"]["ok"] and o14["news"]["summary"].get("count") == 7)
check("خوراک ناموفق → why_not", not o14["cal"]["ok"] and "ناموفق" in o14["cal"]["why_not"])
check("خوراک غایب در intake → why_not", not o14["fg"]["ok"] and "نیست" in o14["fg"]["why_not"])
o3 = {r["id"]: r for r in doc["owners"]["E03"]["items"]}
check("فایل وضعیت تازه → ok؛ کهنه‌تر از سقف → why_not",
      o3["dom"]["ok"] and not o3["st"]["ok"] and "کهنه" in o3["st"]["why_not"])
check("شمارش n_ok درست است", doc["owners"]["E06"]["n_ok"] == 2 and doc["owners"]["E14"]["n_ok"] == 1)

# ۴) --add روی نسخهٔ موقت قرارداد
tmp = Path(tempfile.mkdtemp()) / "c.yaml"
tmp.write_text(DQ.CONTRACT.read_text(encoding="utf-8"), encoding="utf-8")
before = tmp.read_text(encoding="utf-8")
e1 = DQ.add_request("E07", "kline", {"symbol": "ETHUSDT", "tf": "4h", "n": "220",
                                       "why": "ساختار", "max_age_min": "300"}, path=tmp)
e2 = DQ.add_request("E07", "feed", {"feed": "tiktok", "why": "?", "max_age_min": "5"}, path=tmp)
after = tmp.read_text(encoding="utf-8")
check("--add معتبر ثبت شد", not e1 and "ETHUSDT" in after)
check("--add نامعتبر رد شد و فایل دست‌نخورده ماند", e2 and "tiktok" not in after)
check("قرارداد اصلی دست‌نخورده است", DQ.CONTRACT.read_text(encoding="utf-8") == before)

# ۵) مأموریت در هر ایجنت و متخصص
agents = sorted((ROOT / ".claude" / "agents").glob("*.md"))
skills = sorted((ROOT / ".claude" / "skills").glob("liam-e*/SKILL.md"))
MARK = "<!-- adaptive-mandate -->"
miss = [str(p.relative_to(ROOT)) for p in agents + skills if MARK not in p.read_text(encoding="utf-8")]
check(f"هر {len(agents)} ایجنت و {len(skills)} متخصص مأموریت وفق‌پذیری دارد", not miss, str(miss[:4]))
badk = []
for p in agents + skills:
    txt = p.read_text(encoding="utf-8")
    m = re.search(r"data_requests --for (\S+)`", txt)
    key = m.group(1) if m else None
    mm = re.match(r"e(\d\d)-", p.name) or re.match(r"liam-e(\d\d)-", p.parent.name)
    want = f"E{mm.group(1)}" if mm else p.stem
    if key != want:
        badk.append((p.name, key, want))
check("کلیدِ درخواست داده داخل هر فایل با نامش می‌خواند", not badk, str(badk[:4]))
r = subprocess.run([sys.executable, str(ROOT / "scripts" / "inject_adaptive_mandate.py")],
                   capture_output=True, text=True, timeout=60)
check("تزریقِ دوباره چیزی اضافه نمی‌کند", "تزریق شد: 0" in r.stdout, r.stdout[-120:])

# ۶) اتصال‌ها
reg = json.loads((ROOT / "config" / "state_registry.json").read_text(encoding="utf-8"))["files"]
check("data-requests.json ردیف قرارداد دارد", "data-requests.json" in reg and reg["data-requests.json"].get("max_age_min"))
chain = (ROOT / ".github" / "workflows" / "pump-radar.yml").read_text(encoding="utf-8")
check("زنجیرهٔ سیگنال بعد از دسته‌بند، درخواست داده را برآورده می‌کند",
      "hamid.data_requests --write" in chain
      and chain.index("hamid.dispatch --write") < chain.index("hamid.data_requests --write"))
from hamid import liam9d as D                        # noqa: E402
keys = {j["key"]: j for j in D.JOBS}
check("سرویس محلی هر ۵ دقیقه درخواست داده را دارد",
      "data_requests" in keys and keys["data_requests"]["every"] == 300)
check("دروازهٔ چرخه این محافظ را می‌زند",
      "hamid.test_data_requests" in (ROOT / ".github" / "workflows" / "hamid-cycle.yml").read_text(encoding="utf-8"))
rule = ROOT / ".claude" / "rules" / "19-adaptive-agents-data-requests.md"
check("قانون ۱۹ مکتوب است و محافظ را نام می‌برد",
      rule.exists() and "test_data_requests" in rule.read_text(encoding="utf-8"))

print(f"\n{OK} بررسی گذشت" + (f"، {len(FAIL)} افتاد: {FAIL}" if FAIL else ""))
sys.exit(1 if FAIL else 0)
