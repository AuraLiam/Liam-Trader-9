"""نقشهٔ کامل انجین‌ها: هر کدام چه پایش می‌کند، از کجا، و به که می‌دهد.

دستور حمید (۳۱ اوت): «می‌خواهم نقشهٔ کامل را بدانم چه‌جوری است و کدام
انجین چه‌جوری اطلاعاتش را پایش می‌کند و در اختیار چه انجین‌هایی
می‌گذارد؟»

## چرا مولد، نه سند دستی

سندِ دست‌نویس روزِ بعد کهنه می‌شود و کسی نمی‌فهمد. این نقشه از **خودِ
کد** ساخته می‌شود:

- `config/state_registry.json` — مالک، تولیدکننده، مصرف‌کننده، لایه،
  سقف کهنگی (قرارداد قانون ۱۳)
- سورسِ هر تولیدکننده — میزبان‌های بیرونی با regex از خودِ فایل
- `signals/` — سنِ واقعی هر فایل همین الان

پس اگر انجینی منبعش عوض شود، نقشه خودش عوض می‌شود. اگر انجینی فایل
وضعیت نداشته باشد، این‌جا صریح «بی‌ردپا» علامت می‌خورد — نه اینکه از
نقشه بیفتد.

اجرا: `python3 -m hamid.engine_map [--json]`
"""
import collections
import json
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = HERE.parent
ROOT = PY.parent.parent
REG = ROOT / "config" / "state_registry.json"
LIST = ROOT / "claude-liam-signal" / "ENGINE-LIST.json"
SIG = ROOT / "signals"

HOST_RE = re.compile(r"https?://([a-z0-9.\-]+)")
SKIP_HOST = ("github", "anthropic", "schema", "json-schema", "localhost")

# آنچه هر انجین «پایش» می‌کند — یک جمله، از منشور/قوانین، نه حدس
WATCHES = {
    "E00": "کلِ گذرگاه وضعیت و حلقهٔ بسته: هر سیگنالِ رفته ردپای پنل/یادگیری دارد؟",
    "E01": "جهانِ نمادها: گینر/لوزر/حجم چند صرافی، نوسان، طبقه‌بندی",
    "E02": "سلامت داده: عمق، اسپرد، تازگی، ناسازگاری منابع",
    "E03": "دامیننس تتر — مهم‌ترین بستر: سطح، کانال، رژیم، پیش‌بینی",
    "E04": "دامیننس بیت‌کوین (داخل موتور دامیننس، فایل جدا ندارد)",
    "E05": "رژیم کلان: تقویم اقتصادی، ریسک‌آن/آف",
    "E06": "بیت‌کوین: الگوها و بسترِ اجباریِ هر آلت",
    "E07": "ساختار: سوینگ، BOS/CHoCH، خط روند، سطح (داخل موتور، فایل جدا ندارد)",
    "E08": "اردر بلاک و FVG: کشف، اعتبار، مصرف‌شدگی، رادار نزدیک‌شدن",
    "E09": "هندسهٔ کندل: بدنه/ویک، IBS، دیسپلیسمنت (داخل موتور)",
    "E10": "نقدینگی و مشتقه: نقشهٔ استاپ، خوشهٔ لیکویید، تقویم",
    "E11": "مسیریاب استراتژی: کدام استراتژی روی این نماد، با چه هندسه‌ای",
    "E12": "لید-لگ و پامپ: چه ارزی قبل/بعد حرکت می‌کند، حساسیت به BTC",
    "E13": "قیاسِ تاریخی: همین الگو قبلاً چه شد (داخل موتور)",
    "E14": "خبر و کاتالیزور: RSS، آنلاک توکن، بازار پیش‌بینی",
    "E15": "دیده‌بان و آلارم: نقاط علامت‌خورده (داخل موتور)",
    "E16": "ریسک: سایز، کارمزد، محافظ لیکویید، سقف پوزیشن",
    "E17": "کمیتهٔ سیگنال: جمعِ همهٔ شواهد، دروازه‌ها، تصمیم نهایی",
    "E18": "پیپر/ریپلی/بک‌تست: هر ادعا را روی کندل واقعی می‌سنجد",
    "E19": "مدیریت معامله: نردبان تریل، انقضا، پاسبان پوزیشن",
    "E20": "بازبینی پس از معامله: علت‌یابی، درس، گزارش کار",
    "E21": "متولی حافظه: چه چیزی وارد حافظهٔ دائمی می‌شود",
    "E22": "بهبود و تحقیق: قفسهٔ لبه، بندیت، تخصیص آزمایش",
    "E23": "ناظر/SRE: سلامت زنجیره، انطباق، تشدید",
    "E24": "قرارداد پنل و QA رابط (داخل ساخت پنل)",
    "E25": "تحویل تلگرام: ضدتکرار، رسید، آرشیو شماره‌دار",
    "E26": "ناظر کل: دستور تمرکز از کارنامهٔ همهٔ اتاق‌ها",
    # E27 با اتاق توزیع اطلاعات آمد (دستور ۳ سپتامبر): اول دسته‌بندی، بعد توزیع.
    "E27": "توزیع اطلاعات: تاکسونومی ارز و مسیر رویداد→اتاق، با دلیلِ هر حذف",
}


def _hosts(producer):
    out = set()
    for p in re.split(r"[,\s]+", producer or ""):
        p = p.strip()
        if not p or p.startswith("external:"):
            continue
        for cand in (PY / p, ROOT / p, Path(p)):
            if cand.exists() and cand.is_file():
                try:
                    txt = cand.read_text(encoding="utf-8", errors="ignore")
                except Exception:                    # noqa: BLE001
                    continue
                out |= {h for h in HOST_RE.findall(txt)
                        if not any(s in h for s in SKIP_HOST)}
                break
    return sorted(out)


def build(now_ms=None):
    now = now_ms or int(time.time() * 1000)
    reg = json.loads(REG.read_text(encoding="utf-8"))
    files = reg.get("files", reg)
    try:
        listed = json.loads(LIST.read_text(encoding="utf-8"))
        names = {e["id"]: e["name"] for e in listed}
    except Exception:                                # noqa: BLE001
        names = {}

    by = collections.defaultdict(list)
    for fn, v in files.items():
        by[v.get("owner") or "?"].append((fn, v))

    engines = []
    for eid in sorted(set(list(by) + list(WATCHES)) - {"?"}):
        rows = by.get(eid, [])
        prods, hosts, cons, layers, out_files = set(), set(), set(), set(), []
        for fn, v in rows:
            p = v.get("producer") or ""
            prods.add(p)
            hosts |= set(_hosts(p))
            if v.get("consumer"):
                cons.add(v["consumer"])
            if v.get("layer"):
                layers.add(v["layer"])
            f = SIG / fn
            age = None
            if f.exists():
                try:
                    g = json.loads(f.read_text(encoding="utf-8")).get("generated")
                    age = round((now - g) / 60000) if g else None
                except Exception:                    # noqa: BLE001
                    age = None
            out_files.append({"file": fn, "kind": v.get("kind"),
                              "max_age_min": v.get("max_age_min"),
                              "age_min": age, "critical": bool(v.get("critical"))})
        engines.append({
            "id": eid, "name": names.get(eid, "—"),
            "watches": WATCHES.get(eid, "—"),
            "layers": sorted(layers),
            "producers": sorted(p for p in prods if p),
            "sources": sorted(hosts) or ["داخلی — از خروجی انجین‌های دیگر"],
            "consumers": sorted(cons) or ["—"],
            "files": out_files,
            "traceless": not rows,
        })
    return {"generated": now, "engines": engines,
            "n_files": len(files),
            "n_traceless": sum(1 for e in engines if e["traceless"])}


def main(argv=()):
    m = build()
    if "--json" in argv:
        print(json.dumps(m, ensure_ascii=False, indent=1))
        return 0
    print(f"### نقشهٔ انجین‌ها — {len(m['engines'])} انجین · "
          f"{m['n_files']} فایل وضعیت · {m['n_traceless']} بی‌ردپا\n")
    for e in m["engines"]:
        mark = "⚪ بی‌ردپا" if e["traceless"] else "🟢"
        print(f"{mark} {e['id']} — {e['name']}")
        print(f"    پایش: {e['watches']}")
        print(f"    منبع: {'، '.join(e['sources'])[:110]}")
        if not e["traceless"]:
            print(f"    می‌دهد به: {'، '.join(e['consumers'])}")
            for f in e["files"]:
                age = f"{f['age_min']}د" if f["age_min"] is not None else "—"
                cap = f"/{f['max_age_min']}د" if f["max_age_min"] else ""
                print(f"      · {f['file']} ({f['kind']}) سن {age}{cap}"
                      + ("  ⚠️حیاتی" if f["critical"] else ""))
        print()
    print("⚪ «بی‌ردپا» یعنی انجین داخل موتور کار می‌کند ولی فایل وضعیت")
    print("   مستقل ندارد — پس کارنامه‌اش جدا سنجیده نمی‌شود. عیب نیست،")
    print("   ولی شکافِ اندازه‌گیری است و همین‌جا صریح علامت می‌خورد.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
