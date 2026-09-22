#!/usr/bin/env python3
"""
Submit .ai-log/session.jsonl to grading server.
Called by git pre-push hook or manually.

All entries remain in .ai-log/session.jsonl (never split into archive files).
A .submitted_count file tracks how many entries have been successfully submitted
so that only new entries are sent on each push.
"""
import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

SERVER_URL = os.environ.get("AI_LOG_SERVER", "")
API_KEY = os.environ.get("AI_LOG_API_KEY", "")
LOG_DIR = Path(os.environ.get("AI_LOG_DIR", ".ai-log"))
LOG_FILE = LOG_DIR / "session.jsonl"
STATE_FILE = LOG_DIR / ".submitted_count"

# Match server-side MAX_BATCH_ENTRIES so we never get a 422.
BATCH_LIMIT = 500


def _get_submitted_count() -> int:
    if STATE_FILE.exists():
        try:
            return int(STATE_FILE.read_text(encoding="utf-8").strip())
        except Exception:
            return 0
    return 0


def _set_submitted_count(count: int) -> None:
    STATE_FILE.write_text(str(count), encoding="utf-8")


def main():
    if not SERVER_URL:
        print("[ai-log] AI_LOG_SERVER not set — skipping submission.", file=sys.stderr)
        sys.exit(0)

    if not LOG_FILE.exists() or LOG_FILE.stat().st_size == 0:
        print("[ai-log] No logs to submit.", file=sys.stderr)
        sys.exit(0)

    submitted_count = _get_submitted_count()

    lines = []
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if stripped:
                lines.append(stripped)

    total_lines = len(lines)
    if submitted_count >= total_lines:
        print("[ai-log] All logs already submitted.", file=sys.stderr)
        sys.exit(0)

    unsubmitted = lines[submitted_count:]
    batch_lines = unsubmitted[:BATCH_LIMIT]

    entries = []
    for line in batch_lines:
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            pass

    if not entries:
        _set_submitted_count(submitted_count + len(batch_lines))
        print("[ai-log] No valid entries to submit.", file=sys.stderr)
        sys.exit(0)

    payload = json.dumps({"entries": entries}, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"
    req = urllib.request.Request(
        SERVER_URL,
        data=payload,
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(f"[ai-log] Submitted {len(entries)} entries → {resp.status}", file=sys.stderr)
            _set_submitted_count(submitted_count + len(batch_lines))
    except urllib.error.URLError as e:
        print(f"[ai-log] Submit failed: {e} — logs kept locally.", file=sys.stderr)
        sys.exit(0)

    if len(unsubmitted) > BATCH_LIMIT:
        print(
            f"[ai-log] {len(unsubmitted) - BATCH_LIMIT} entries deferred to next push.",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
