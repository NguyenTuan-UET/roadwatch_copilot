"""WP-P1: check the repository's Markdown conventions without modifying files."""

import argparse
import json
import re
from datetime import date
from graphlib import CycleError, TopologicalSorter
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[2]
SPEC = "docs/specs/roadwatch-architecture.md"
PLAN = "docs/plan/README.md"
IDENTIFIER = re.compile(r"\b(?:WP-[PABCD]\d+|OQ-[BMAE]\d+|AC-[MF]\d+|ADR-\d+|[ID]-\d+|F\d+[ab]?|KS-\d+)\b")
# ponytail: repo uses inline Markdown links; use a CommonMark parser if reference links need checking.
LINK = re.compile(r"!?\[[^\]\n]*\]\((?:<([^>]+)>|([^\s)]+))(?:\s+\"[^\"]*\")?\)")


def prose(text: str) -> list[tuple[int, str]]:
    """Ignore fenced examples; keep original line numbers for diagnostics."""
    lines = []
    fence = ""
    for number, line in enumerate(text.splitlines(), 1):
        match = re.match(r"^\s*(`{3,}|~{3,})", line)
        if match:
            marker = match[1]
            if not fence:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence):
                fence = ""
        elif not fence:
            lines.append((number, line))
    return lines


def check(root: Path) -> list[str]:
    paths = sorted(
        path for path in (root / "docs").rglob("*.md")
    )
    paths += [root / name for name in ("AGENTS.md", "README.md", "ARCHITECTURE.md") if (root / name).exists()]
    documents = {path.relative_to(root).as_posix(): path.read_text(encoding="utf-8") for path in paths}
    errors = []

    def fail(name: str, number: int, message: str) -> None:
        errors.append(f"{name}:{number}: {message}")

    def link(name: str, number: int, target: str) -> None:
        url = urlsplit(target)
        if not url.scheme and not url.netloc and url.path:
            if not (root / name).parent.joinpath(unquote(url.path)).exists():
                fail(name, number, f"link target missing: {target}")

    for name in (SPEC,):  # PLAN (task table) was removed on 09/10/2026: checked if present, WP IDs unchecked if not
        if name not in documents:
            fail(name, 1, "required document missing")
    defined = set()
    resolved = set()
    # Definitions come from authoritative tables, never arbitrary mentions or examples.
    sources = [SPEC, PLAN] + [name for name in documents if name.startswith("docs/requirements/")]
    for name in sources:
        for _, line in prose(documents.get(name, "")):
            cells = [cell.strip().strip("*") for cell in re.split(r"(?<!\\)\|", line)[1:-1]]
            if cells and IDENTIFIER.fullmatch(cells[0]):
                defined.add(cells[0])
                if "Đã trả lời" in line:
                    resolved.add(cells[0])
            if name == SPEC and cells and re.fullmatch(r"\d{2}", cells[0]):
                identifier = f"ADR-{cells[0]}"
                defined.add(identifier)
                if "PO duyệt" in line or "PO chốt" in line:
                    resolved.add(identifier)
            if name == PLAN and line.startswith("**ID đã bỏ:"):
                defined.update(IDENTIFIER.findall(line))

    doc_ids = set()
    for name, text in documents.items():
        meta = {}
        if text.startswith("---\n"):
            try:
                block, _ = text[4:].split("\n---\n", 1)
                for line in block.splitlines():
                    key, value = line.split(":", 1)
                    if key in meta:
                        raise ValueError(f"duplicate key {key}")
                    meta[key] = json.loads(value)
                for key in ("doc_id", "doc_type", "status"):
                    if not isinstance(meta.get(key), str) or not meta[key]:
                        raise ValueError(f"missing/invalid {key}")
                if meta["doc_type"] not in {"specification", "plan", "view", "archive"}:
                    raise ValueError("invalid doc_type")
                if meta["status"] not in {"draft", "proposed", "approved", "active", "archived"}:
                    raise ValueError("invalid status")
                authority = meta.get("authority_for")
                if not isinstance(authority, list) or any(not isinstance(item, str) or not item for item in authority):
                    raise ValueError("authority_for must be an array of strings")
                if meta["doc_type"] in {"view", "archive"} and authority:
                    raise ValueError("derived/history documents cannot own authority")
                if (meta["doc_type"] == "archive") != (meta["status"] == "archived"):
                    raise ValueError("archive type and status must agree")
                if meta["status"] == "approved":
                    for key in ("version", "approved_by", "approved_on", "approval_ref"):
                        if not isinstance(meta.get(key), str) or not meta[key]:
                            raise ValueError(f"approved metadata needs {key}")
                    date.fromisoformat(meta["approved_on"])
                    if urlsplit(meta["approval_ref"]).scheme or Path(meta["approval_ref"]).is_absolute():
                        raise ValueError("approval_ref must be a relative local path")
                    link(name, 1, meta["approval_ref"])
                if meta["doc_id"] in doc_ids:
                    raise ValueError("duplicate doc_id")
                doc_ids.add(meta["doc_id"])
            except (ValueError, TypeError) as exc:
                fail(name, 1, f"metadata: {exc}")
        elif name in (SPEC, PLAN, "docs/architecture.md"):
            fail(name, 1, "metadata missing")

        for number, line in prose(text):
            for match in LINK.finditer(line):
                link(name, number, match[1] or match[2])
            if meta.get("status") == "archived":
                continue
            for identifier in IDENTIFIER.findall(line):
                if identifier not in defined and not (identifier.startswith("WP-") and PLAN not in documents):
                    fail(name, number, f"undefined ID: {identifier}")
                if identifier in resolved and (
                    re.search(rf"chờ\s+{re.escape(identifier)}\b", line, re.IGNORECASE)
                    or re.search(rf"{re.escape(identifier)}\s*,\s*chờ duyệt", line, re.IGNORECASE)
                ):
                    # Checklist evidence is a dated historical record, not an active decision.
                    if not re.match(r"\s*- \[x\].*→.*\d{2}/\d{2}/\d{4}", line):
                        fail(name, number, f"resolved decision still marked pending: {identifier}")

    tasks = {}
    phase = None
    for number, line in prose(documents.get(PLAN, "")):
        if line.startswith("### 4."):
            phase = line.split()[1]
        if phase not in {"4.1", "4.2"} or not line.startswith("| WP-"):
            continue
        cells = [cell.strip() for cell in re.split(r"(?<!\\)\|", line)[1:-1]]
        if len(cells) != (7 if phase == "4.1" else 6) or not all(cells):
            fail(
                PLAN,
                number,
                "task fields missing: ID, work, owner, reviewer, dependencies, status (and deadline in week 1)",
            )
            continue
        identifier, _, owner, reviewer, dependencies = cells[:5]
        if identifier in tasks:
            fail(PLAN, number, f"duplicate task ID: {identifier}")
        if owner.split(" (")[0] in reviewer:
            fail(PLAN, number, f"reviewer must differ from owner: {identifier}")
        tasks[identifier] = (set(re.findall(r"WP-[PABCD]\d+", dependencies)), phase, number)
        if dependencies != "—" and not IDENTIFIER.search(dependencies):
            fail(PLAN, number, f"task dependencies need explicit IDs: {identifier}")
        if not cells[-1].startswith(("⬜", "🟡", "✅", "⛔")):
            fail(PLAN, number, f"invalid task status: {identifier}")
    for identifier, (dependencies, phase, number) in tasks.items():
        for dependency in dependencies:
            if dependency not in tasks:
                fail(PLAN, number, f"unknown task dependency: {dependency}")
            elif phase == "4.1" and tasks[dependency][1] == "4.2":
                fail(PLAN, number, f"week 1 depends on extension: {identifier} -> {dependency}")
    try:
        list(TopologicalSorter({key: value[0] for key, value in tasks.items()}).static_order())
    except CycleError as exc:
        fail(PLAN, 1, f"dependency cycle: {' -> '.join(exc.args[1])}")

    details = {}
    for name, text in documents.items():
        if not name.startswith("docs/plan/phan-viec/"):
            continue
        for match in re.finditer(r"^### (WP-[PABCD]\d+)\b(.*?)(?=^#{1,3} |\Z)", text, re.MULTILINE | re.DOTALL):
            identifier, body = match.groups()
            number = text[: match.start()].count("\n") + 1
            if identifier in details:
                fail(name, number, f"duplicate task detail: {identifier}")
            details[identifier] = name
            required = (
                "**Xong khi:**",
                "**Kiểm chứng:**",
                "Bàn giao",
                "Kiểm thử và kiểm chứng",
                "Review và nghiệm thu",
                "- [",
            )
            if any(field not in body for field in required):
                fail(name, number, f"task fields incomplete: {identifier}")
    for identifier in tasks.keys() ^ details.keys():
        fail(PLAN, 1, f"task table/detail mismatch: {identifier}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    errors = check(args.root.resolve())
    print("\n".join(errors) if errors else "Documentation checks passed.")
    return bool(errors)


if __name__ == "__main__":
    raise SystemExit(main())
