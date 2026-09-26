from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

EXPECTED_IDS = [f"E{i:02d}" for i in range(27)]


def frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"missing frontmatter: {path}")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise ValueError(f"unclosed frontmatter: {path}")
    return yaml.safe_load(text[4:end]) or {}


# مهارت‌هایی که ایجنت اصلی خودش صدا می‌زند (user-invocable) — زیرایجنت لازم ندارند.
LEAD_ONLY_SKILLS = {"signal-work", "work-report"}


def _skill_wiring(root: Path, rows) -> list:
    """هر مهارت باید دست‌کم یک ایجنت داشته باشد که بارش کند (۲۶ سپتامبر).

    عیبِ اندازه‌گیری‌شده: ۱۰ مهارت (از جمله قواعد ورود کندلی قانون ۱۰ و
    برنامهٔ ۵نوبتهٔ پامپ) هیچ ایجنتی نداشتند؛ پس «تزریق به مهارت» هرگز به
    استدلالِ ایجنت نمی‌رسید. ۹ ایجنت عملیاتی اصلاً ابزار Skill نداشتند.
    """
    errs = []
    agents = sorted((root / ".claude/agents").glob("*.md"))
    skills = {p.parent.name for p in (root / ".claude/skills").glob("*/SKILL.md")}
    used = set()
    by_id = {f"{r['id'].lower()}-{r['slug']}.md": r["claude_skill"] for r in rows}
    for a in agents:
        fm = frontmatter(a)
        lst = fm.get("skills") or []
        used.update(lst)
        for sk in lst:
            if sk not in skills:
                errs.append(f"agent {a.name} references missing skill {sk}")
        if not lst:
            errs.append(f"agent {a.name} loads no skill")
        elif "Skill" not in str(fm.get("tools", "")):
            errs.append(f"agent {a.name} lists skills but lacks the Skill tool")
        own = by_id.get(a.name)
        if own and own not in lst:
            errs.append(f"agent {a.name} does not load its own skill {own}")
    for sk in sorted(skills - used - LEAD_ONLY_SKILLS):
        errs.append(f"skill {sk} is loaded by no agent")
    return errs


def _tracked(root: Path):
    """فقط فایل‌هایی که گیت واقعاً می‌شناسد.

    خاصیتی که این بررسی محافظش است «هیچ سکرتی داخل گیت نیست» (قانون ۰۵).
    اسکنِ کلِ پوشه، چیزِ دیگری را می‌سنجد: یک `.venv` محلیِ ignore-شده
    چرخه را بی‌دلیل قرمز می‌کند. آزمون باید خاصیت را بسنجد نه شکل را
    (درسِ ۶ سپتامبر). اگر گیت در دسترس نبود، به اسکنِ کامل برمی‌گردیم.
    """
    import subprocess
    try:
        r = subprocess.run(["git", "-C", str(root), "ls-files", "-z"],
                           capture_output=True, timeout=60)
        if r.returncode == 0:
            return [root / p for p in r.stdout.decode("utf8", "replace").split("\0") if p]
    except Exception:                                    # noqa: BLE001
        pass
    return list(root.rglob("*"))


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    registry_path = root / "config/engine_registry.yaml"
    if not registry_path.exists():
        return ["missing config/engine_registry.yaml"]
    registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    if registry.get("live_execution") is not False:
        errors.append("live_execution must be false")
    if registry.get("scan_heartbeat_seconds") != 30:
        errors.append("scan_heartbeat_seconds must be 30")

    rows = registry.get("engines") or []
    ids = [r.get("id") for r in rows]
    if ids != EXPECTED_IDS:
        errors.append(f"engine IDs mismatch: {ids}")

    seen_skill_names: set[str] = set()
    seen_agent_names: set[str] = set()
    for row in rows:
        eid = row["id"]
        skill_path = root / ".claude/skills" / row["claude_skill"] / "SKILL.md"
        agent_rel = f"{eid.lower()}-{row['slug']}.md"
        agent_path = root / ".claude/agents" / agent_rel
        runtime_path = root / row["runtime_skill_file"]
        for path in (skill_path, agent_path, runtime_path):
            if not path.exists():
                errors.append(f"missing {path.relative_to(root)}")
        if skill_path.exists():
            fm = frontmatter(skill_path)
            if fm.get("name") != row["claude_skill"]:
                errors.append(f"skill name mismatch: {skill_path}")
            if fm.get("name") in seen_skill_names:
                errors.append(f"duplicate skill name: {fm.get('name')}")
            seen_skill_names.add(fm.get("name"))
        if agent_path.exists():
            fm = frontmatter(agent_path)
            if fm.get("name") != row["claude_agent"]:
                errors.append(f"agent name mismatch: {agent_path}")
            if fm.get("name") in seen_agent_names:
                errors.append(f"duplicate agent name: {fm.get('name')}")
            seen_agent_names.add(fm.get("name"))
            if fm.get("memory") != "project":
                errors.append(f"agent memory must be project: {agent_path}")
        if runtime_path.exists():
            runtime = yaml.safe_load(runtime_path.read_text(encoding="utf-8"))
            if runtime.get("engine_id") != eid:
                errors.append(f"runtime skill ID mismatch: {runtime_path}")

    errors += _skill_wiring(root, rows)

    signal = yaml.safe_load((root / "config/signal_policy.yaml").read_text(encoding="utf-8"))
    if signal.get("release_mode") != "immediate_per_symbol_no_batch_barrier":
        errors.append("signal release mode must be immediate per symbol")
    if signal.get("live_execution") is not False:
        errors.append("signal policy live_execution must be false")

    secret_patterns = [re.compile(r"(?i)(api[_-]?key|secret|token)\s*[=:]\s*['\"][A-Za-z0-9_\-]{16,}")]
    for path in _tracked(root):
        if path.is_file() and path.suffix.lower() in {".md", ".txt", ".yaml", ".yml", ".json", ".py"}:
            text = path.read_text(encoding="utf-8", errors="ignore")
            for pat in secret_patterns:
                if pat.search(text):
                    errors.append(f"possible hard-coded secret in {path.relative_to(root)}")
    errors += _generated_drift(root)
    return errors


def _generated_drift(root: Path) -> list:
    """فایلِ تولیدشده از منبعش عقب نمانده باشد — همان‌جایی که ساخته می‌شود.

    ریشه (۱۷ سپتامبر): `liam9_strategy.py` عوض شد و `ghoghnoos.py`
    بازساخته نشد. دروازهٔ چرخه این را می‌گیرد — ولی **۴۰ دقیقه بعد، روی
    رانر، و با خواباندنِ کلِ زنجیرهٔ سیگنال**. اندازه‌گیری‌شده: ~۸ ساعت
    بی‌سیگنال. خودِ بررسی درست بود؛ جایش غلط بود.

    کلاسِ عیب: هر فایلِ تولیدشده یک «قدمِ دستی» دارد که آدم باید یادش
    بماند — همان کلاسی که قانون «علت پیش از حادثه» می‌گوید با مشتق‌کردن
    از منبع بسته می‌شود، نه با یادآوری. این بررسی نشستِ سازنده را قبل از
    پایان متوقف می‌کند، پس رانر هرگز نوبتش نمی‌رسد.

    عمداً فقط **گزارش** می‌دهد و خودش بازنمی‌سازد: بازسازیِ خودکار،
    واگرایی را پنهان می‌کند و سازنده هرگز نمی‌فهمد چیزی جا مانده بود.
    """
    py = root / "claude-liam-signal" / "python"
    src_p, out_p = py / "liam9_strategy.py", py / "ghoghnoos.py"
    if not (src_p.exists() and out_p.exists()):
        return []
    sys.path.insert(0, str(py))
    try:
        from hamid import build_dashboard as B          # noqa: PLC0415
        src = src_p.read_text(encoding="utf-8")
        body_now = "\n".join(B.banner(src, B.strip(src)).splitlines()[13:])
        body_out = "\n".join(out_p.read_text(encoding="utf-8").splitlines()[13:])
        if body_now != body_out:
            return ["ghoghnoos.py از liam9_strategy.py عقب مانده — "
                    "بدوان: python3 -m hamid.build_dashboard"]
    except Exception:                                    # noqa: BLE001
        # نبودنِ ابزارِ ساخت نباید هوک را بشکند؛ دروازهٔ چرخه پشتیبانِ
        # همین بررسی است و آن‌جا وابستگی‌ها حتماً نصب‌اند.
        return []
    finally:
        if sys.path and sys.path[0] == str(py):
            sys.path.pop(0)
    return []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    errors = validate(root)
    if errors:
        print("LIAM package validation FAILED", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    if not args.quiet:
        print("LIAM package validation OK: 27 engines, 36 agents (27 specialist + 9 operational), every skill wired, immediate 30s/event-driven policy, live execution disabled.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
