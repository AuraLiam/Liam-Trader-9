"""اثر تجربه روی نتیجه — سنجهٔ بازتولیدپذیر (دستور حمید، ۲۳ اوت).

حمید پرسید «یادگیری و تجربه چقدر در نتیجهٔ سیگنال‌های موفق تأثیر داشت؟»
و همان لحظه معلوم شد جوابش را فقط دستی می‌شد حساب کرد. عددی که راه
بازتولید ندارد گزارش نمی‌شود (قانون گزارش)، پس این فایل همان محاسبه است.

## چرا این‌قدر روی «کدام نمونه» تأکید دارد

اندازه‌گیری ۲۳ اوت دو جوابِ متفاوت داد و **هر دو درست بودند**:

- دفتر چندروزه: «با تجربه صادر شد» +۰.۴۴۳R با CI [+۰.۰۳۷, +۰.۸۳۹]
- فقط همان یک روز: −۰.۰۷۰R با CI [−۰.۳۷۴, +۰.۲۵۱] — بازه صفر را در بر
  می‌گیرد، یعنی از نویز جدا نیست.

فرق در اندازهٔ نمونه است، نه در واقعیت. پس این ابزار همیشه CI را کنار
اختلاف چاپ می‌کند و وقتی بازه صفر را در بر بگیرد، صریح می‌گوید
«جدا از نویز نیست» — تا گزارشِ یک‌روزه به ادعای یادگیری تبدیل نشود.

## مرز صادقانه

این سنجه **علیت را ثابت نمی‌کند**. `exp_used` یعنی کارنامهٔ آن (ارز،
جهت) موجود بود و در تصمیم دخالت کرد — نه اینکه ستاپ‌های دو گروه از هر
نظر مثل هم بودند. تجربه ضمناً ستاپ‌های بدِ شناخته‌شده را **وتو** می‌کند،
پس آنچه با برچسب تجربه عبور می‌کند می‌تواند سیستماتیک سخت‌تر باشد. برای
حکم علّی، ماشین بونفرونی روی نمونهٔ بزرگ‌تر مرجع است.

    python3 -m hamid.experience_effect            # امروز + کل دفتر سیگنال
    python3 -m hamid.experience_effect --days 7
"""
import argparse
import json
import random
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
ROOT = HERE.parents[2]
CLOSED = ROOT / "brain" / "paper" / "closed.jsonl"
OUT = ROOT / "signals" / "experience-effect.json"

N_BOOT = 3000
SEED = 7
MIN_N = 8                    # زیر این، بوت‌استرپ عدد بی‌معنا می‌دهد


def load(since_ms=0, sent_only=True):
    """معامله‌های نمره‌خورده. sent_only = فقط دفتر سیگنالِ واقعاً ارسال‌شده."""
    out = []
    if not CLOSED.exists():
        return out
    for line in CLOSED.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            t = json.loads(line)
        except Exception:                            # noqa: BLE001
            continue
        if t.get("R") is None or (t.get("closed") or 0) < since_ms:
            continue
        stage = str((t.get("why") or {}).get("stage") or "")
        if sent_only and not stage.startswith("sig-"):
            continue
        out.append(t)
    return out


def boot_diff(a, b, n_boot=N_BOOT, seed=SEED):
    """CI۹۵ اختلاف میانگین (a − b). None وقتی نمونه برای ادعا کم است."""
    if len(a) < MIN_N or len(b) < MIN_N:
        return None
    rnd = random.Random(seed)
    d = []
    for _ in range(n_boot):
        ma = sum(rnd.choice(a) for _ in a) / len(a)
        mb = sum(rnd.choice(b) for _ in b) / len(b)
        d.append(ma - mb)
    d.sort()
    return d[int(0.025 * n_boot)], d[int(0.975 * n_boot)]


def _side(rows, flag):
    return [t["R"] for t in rows
            if bool((t.get("why") or {}).get("exp_used")) is flag]


def measure(rows, label):
    """→ dict با اختلاف، CI و حکمِ صادقانه."""
    a, b = _side(rows, True), _side(rows, False)
    res = {"label": label, "n_with": len(a), "n_without": len(b)}
    if not a or not b:
        res["verdict"] = "یک طرف خالی است — قابل مقایسه نیست"
        return res
    res["mean_with"] = round(sum(a) / len(a), 4)
    res["mean_without"] = round(sum(b) / len(b), 4)
    res["win_with"] = round(100 * sum(1 for r in a if r > 0) / len(a), 1)
    res["win_without"] = round(100 * sum(1 for r in b if r > 0) / len(b), 1)
    res["diff"] = round(res["mean_with"] - res["mean_without"], 4)
    ci = boot_diff(a, b)
    if ci is None:
        res["ci95"] = None
        res["verdict"] = (f"نمونه کم است (کف {MIN_N} در هر طرف) — "
                          "اختلاف گزارش می‌شود، حکم نه")
        return res
    res["ci95"] = [round(ci[0], 4), round(ci[1], 4)]
    if ci[0] > 0:
        res["verdict"] = "تجربه اثر مثبتِ معنادار دارد (CI بالای صفر)"
    elif ci[1] < 0:
        res["verdict"] = "تجربه اثر منفیِ معنادار دارد (CI زیر صفر)"
    else:
        res["verdict"] = ("بازه صفر را در بر می‌گیرد — اختلاف از نویز "
                          "جدا نیست؛ نه اثبات، نه رد")
    return res


def outcome_split(rows):
    c = {}
    for t in rows:
        c[t.get("outcome") or "?"] = c.get(t.get("outcome") or "?", 0) + 1
    return c


def run(days=1, quiet=False):
    now = int(time.time() * 1000)
    today0 = now - (now % 86_400_000)
    reports = [
        measure(load(since_ms=today0), "امروز (از ۰۰:۰۰ UTC)"),
        measure(load(since_ms=now - days * 86_400_000),
                f"{days} روز اخیر" if days > 1 else "۲۴ ساعت اخیر"),
        measure(load(since_ms=0), "کل دفتر سیگنال"),
    ]
    today = load(since_ms=today0)
    won = sum(1 for t in today if t["R"] > 0)
    res = {"generated": now, "panel": "لیام تریدر ۹",
           "today": {"n": len(today), "won": won, "lost": len(today) - won,
                     "mean_r": round(sum(t["R"] for t in today) / len(today), 4)
                     if today else None,
                     "outcomes": outcome_split(today)},
           "experience_effect": reports,
           "note": ("exp_used علیت را ثابت نمی‌کند — تجربه ستاپ بد را وتو هم "
                    "می‌کند، پس دو گروه لزوماً هم‌شکل نیستند. حکم علّی با "
                    "ماشین بونفرونی روی نمونهٔ بزرگ‌تر.")}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    if not quiet:
        t = res["today"]
        print(f"سیگنال واقعی امروز: {t['n']} نمره‌خورده — "
              f"{t['won']} برد / {t['lost']} باخت · میانگین {t['mean_r']}R")
        print(f"تفکیک: {t['outcomes']}\n")
        for r in reports:
            if "diff" not in r:
                print(f"  {r['label']}: {r['verdict']}")
                continue
            print(f"  {r['label']}: با={r['n_with']} ({r['mean_with']:+.3f}R) "
                  f"بدون={r['n_without']} ({r['mean_without']:+.3f}R) "
                  f"→ {r['diff']:+.3f}R "
                  f"CI{r['ci95'] if r['ci95'] else '—'}")
            print(f"      {r['verdict']}")
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=1)
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    run(days=a.days, quiet=a.quiet)
