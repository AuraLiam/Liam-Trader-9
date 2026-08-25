"""دانلود پوشهٔ اشتراکیِ گوگل‌درایو روی رانر Actions — بدون احراز هویت.

چرا این‌جا: کانتینر ابری کلود و WebFetch هر دو به drive.google.com
بسته‌اند؛ رانر گیت‌هاب شبکهٔ آزاد دارد (دستور حمید ۲۶ اوت: دادهٔ ۳ سالهٔ
ارزها در پوشهٔ اشتراکی). فقط پوشه‌ای که «هر کس با لینک» باشد باز می‌شود؛
غیر آن، با پیام روشن ACCESS_DENIED می‌میرد — حدس و دورزدن ممنوع.

روش: فهرست از embeddedfolderview (HTML عمومی گوگل برای پوشهٔ اشتراکی)،
بازگشتی برای زیرپوشه‌ها؛ دانلود هر فایل از uc?export=download با مدیریت
توکن تأیید فایل‌های بزرگ. ساختار درختی عیناً بازسازی می‌شود.

اجرا:  python3 scripts/gdrive_fetch.py <FOLDER_ID> <DEST_DIR>
"""
import html
import re
import sys
import time
import urllib.request
from pathlib import Path

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) liam9-history/1"}
ENTRY_RE = re.compile(
    r'href="https://drive\.google\.com/(file/d/|drive/folders/)'
    r'([-\w]{10,})[^"]*"[^>]*>.*?flip-entry-title">([^<]+)<',
    re.S)


def parse_listing(page_html):
    """→ [(kind, id, name)] از HTML فهرست پوشه؛ kind یکی از file/folder."""
    out = []
    for kind, fid, name in ENTRY_RE.findall(page_html or ""):
        out.append(("folder" if "folders" in kind else "file",
                    fid, html.unescape(name).strip()))
    return out


def _get(url, timeout=60):
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=timeout)


def list_folder(folder_id, tries=6):
    """فهرست پوشه؛ ۵xxِ گوگل روی این endpoint قدیمی گذراست — با فاصله
    دوباره تلاش می‌کنیم (اجرای ۲۶ اوت: بعد از باز شدن اشتراک، 500 داد).
    401/403 یعنی واقعاً بسته است — آن retry نمی‌خورد."""
    last = None
    for attempt in range(tries):
        try:
            with _get("https://drive.google.com/embeddedfolderview?id="
                      + folder_id) as r:
                body = r.read().decode("utf-8", "replace")
            if "ServiceLogin" in body or "You need access" in body:
                raise PermissionError("ACCESS_DENIED")
            return parse_listing(body)
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise PermissionError("ACCESS_DENIED") from e
            last = e
            print(f"  فهرست {folder_id[:8]}…: HTTP {e.code} — "
                  f"تلاش {attempt + 1}/{tries}", flush=True)
        except PermissionError:
            raise
        except Exception as e:                       # noqa: BLE001
            last = e
        time.sleep(8 * (attempt + 1))
    raise last


def download_file(file_id, dest, tries=3):
    """uc?export=download + عبور از صفحهٔ «فایل بزرگ، اسکن ویروس نشده»."""
    url = f"https://drive.google.com/uc?export=download&id={file_id}"
    for attempt in range(tries):
        try:
            with _get(url, timeout=300) as r:
                data = r.read()
            if data[:6] != b"<html>" and b"<!DOCTYPE html>" not in data[:200]:
                dest.write_bytes(data)
                return len(data)
            body = data.decode("utf-8", "replace")
            m = re.search(r'action="([^"]*usercontent[^"]*)"', body)
            token = dict(re.findall(r'name="(\w+)" value="([^"]*)"', body))
            if m:
                q = "&".join(f"{k}={v}" for k, v in token.items())
                with _get(html.unescape(m.group(1)) + "?" + q, timeout=600) as r:
                    dest.write_bytes(r.read())
                return dest.stat().st_size
            raise RuntimeError("confirm-page بدون فرم")
        except PermissionError:
            raise
        except Exception:                            # noqa: BLE001
            if attempt == tries - 1:
                raise
            time.sleep(3 * (attempt + 1))
    return 0


def fetch_tree(folder_id, dest, depth=0, stats=None):
    stats = stats if stats is not None else {"files": 0, "bytes": 0, "errors": []}
    if depth > 6:
        return stats
    dest.mkdir(parents=True, exist_ok=True)
    for kind, fid, name in list_folder(folder_id):
        safe = name.replace("/", "_")
        if kind == "folder":
            fetch_tree(fid, dest / safe, depth + 1, stats)
        else:
            try:
                n = download_file(fid, dest / safe)
                stats["files"] += 1
                stats["bytes"] += n
                if stats["files"] % 25 == 0:
                    print(f"  {stats['files']} فایل، "
                          f"{stats['bytes'] // 1_000_000}MB", flush=True)
            except Exception as e:                   # noqa: BLE001
                stats["errors"].append(f"{name}: {type(e).__name__}")
    return stats


def main():
    folder_id, dest = sys.argv[1], Path(sys.argv[2])
    try:
        stats = fetch_tree(folder_id, dest)
    except PermissionError:
        print("ACCESS_DENIED: پوشه برای «هر کس با لینک» باز نیست — "
              "در درایو: راست‌کلیک → Share → Anyone with the link")
        sys.exit(2)
    print(f"تمام: {stats['files']} فایل، {stats['bytes'] // 1_000_000}MB، "
          f"{len(stats['errors'])} خطا")
    for e in stats["errors"][:10]:
        print("  خطا:", e)
    if not stats["files"]:
        print("هیچ فایلی دیده نشد — یا پوشه خالی است یا فهرست عمومی نیست")
        sys.exit(3)


if __name__ == "__main__":
    main()
