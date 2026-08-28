"""بستهٔ شواهد — مدل رسمی پاسخگویی همهٔ انجین‌ها (دستور حمید، ۲۷ اوت).

حمید: «همین مدل رو در همه انجین‌ها کدنویسی کن که دلیل و منطق با اعداد
ارقام و بررسی سوابق باشه.» الگو همان پاسخ ۲۷ اوت است که پسندید:

    ادعا → اعداد → کارنامه/سوابق → سناریوی هر دو جهت → باطل‌کننده →
    منابع → مرز صادقانه

هیچ فیلدی اختیاری نیست. انجینی که یکی را ندارد باید صادقانه بنویسد
چرا ندارد («کارنامه: هنوز n کافی نیست»)، نه این‌که فیلد را حذف کند.
قانون مرجع: `.claude/rules/12-evidence-packet.md`.
"""

REQUIRED = ("claim", "numbers", "track_record", "scenario_up",
            "scenario_down", "invalidator", "sources", "limit")

# نگاشت فیلد → برچسب فارسی روی خروجی
_LABEL = {
    "claim": "💬",
    "numbers": "🔢",
    "track_record": "🎯 کارنامه",
    "scenario_up": "📐 بالا برود",
    "scenario_down": "📐 پایین بیاید",
    "invalidator": "⛔ باطل‌کننده",
    "sources": "🔗 منابع",
    "limit": "⚖️ مرز صادقانه",
}


def build(claim, numbers, track_record, scenario_up, scenario_down,
          invalidator, sources, limit):
    """ساخت بستهٔ کامل. numbers: dict برچسب→مقدار؛ sources: list نام منبع."""
    return {"claim": claim, "numbers": numbers, "track_record": track_record,
            "scenario_up": scenario_up, "scenario_down": scenario_down,
            "invalidator": invalidator, "sources": sources, "limit": limit}


def validate(p):
    """فهرست عیب‌ها؛ خالی یعنی بسته کامل است."""
    faults = []
    if not isinstance(p, dict):
        return ["packet is not a dict"]
    for k in REQUIRED:
        v = p.get(k)
        if v in (None, "", [], {}):
            faults.append(f"missing:{k}")
    if isinstance(p.get("numbers"), dict):
        for lbl, val in p["numbers"].items():
            if val is None:
                faults.append(f"empty_number:{lbl}")
    if p.get("sources") and not isinstance(p["sources"], (list, tuple)):
        faults.append("sources_not_list")
    return faults


def render(p):
    """متن فارسی بسته — همان ترتیب همیشگی، برای تلگرام/گزارش/لاگ."""
    lines = []
    lines.append(f"{_LABEL['claim']} {p['claim']}")
    nums = p.get("numbers") or {}
    if isinstance(nums, dict) and nums:
        lines.append(f"{_LABEL['numbers']} " + " · ".join(
            f"{k} <code>{v}</code>" for k, v in nums.items()))
    lines.append(f"{_LABEL['track_record']}: {p['track_record']}")
    lines.append(f"{_LABEL['scenario_up']}: {p['scenario_up']}")
    lines.append(f"{_LABEL['scenario_down']}: {p['scenario_down']}")
    lines.append(f"{_LABEL['invalidator']}: {p['invalidator']}")
    srcs = p.get("sources") or []
    if srcs:
        lines.append(f"{_LABEL['sources']}: " + " · ".join(str(s) for s in srcs))
    lines.append(f"{_LABEL['limit']}: {p['limit']}")
    return "\n".join(lines)
