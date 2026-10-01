"""WP-P1: exercise documentation checks against deliberately broken copies."""

import json
import tempfile
import unittest
from pathlib import Path

from scripts.roadwatch.check_docs import check
from scripts.roadwatch.export_schemas import render


class DocumentationTest(unittest.TestCase):
    def test_checker_rejects_broken_documents_and_dependencies(self):
        files = {
            "docs/specs/roadwatch-architecture.md": (
                '---\ndoc_id: "ARCH"\ndoc_type: "specification"\nstatus: "approved"\n'
                'version: "1.1"\napproved_by: "PO"\napproved_on: "2026-09-29"\n'
                'approval_ref: "../plan/review.md"\nauthority_for: ["architecture"]\n---\n'
                "# Spec\n| OQ-B1 | **Đã trả lời 29/09** | PO |\n"
                "| 13 | Web UI | PO duyệt 29/09 |\n"
            ),
            "docs/plan/README.md": (
                '---\ndoc_id: "PLAN"\ndoc_type: "plan"\nstatus: "active"\n'
                'authority_for: ["tasks"]\n---\n# Plan\n'
                "### 4.1 Tuần 1\n"
                "| WP-P1 | Docs | An | Binh | — | N0 | 🟡 |\n"
                "| WP-P2 | Check | Binh | An | WP-P1 | N1 | ⬜ |\n"
                "### 4.2 Tuần 2–4\n### 4.3 Tiến độ\n"
            ),
            "docs/plan/review.md": "# Review\nBằng chứng đã duyệt.\n",
            "docs/plan/phan-viec/an.md": (
                "# Tasks\n### WP-P1 · Docs\n**Xong khi:** có docs\n"
                "**Kiểm chứng:** chạy check\n- Bàn giao\n- [ ] File\n"
                "- Kiểm thử và kiểm chứng\n- [ ] Check\n- Review và nghiệm thu\n- [ ] Review\n"
            ),
        }
        files["docs/plan/phan-viec/binh.md"] = files["docs/plan/phan-viec/an.md"].replace("WP-P1", "WP-P2")
        mutations = [
            ("docs/plan/review.md", "# Review\n[missing](missing.md)\n", "link"),
            ("docs/plan/review.md", "# Review\nWP-P999\n", "ID"),
            ("docs/plan/README.md", files["docs/plan/README.md"].replace("| — |", "| WP-P2 |"), "cycle"),
            ("docs/plan/README.md", files["docs/plan/README.md"].replace("| — |", "| WP-P1 |"), "cycle"),
            ("docs/plan/README.md", files["docs/plan/README.md"].replace("| An | Binh |", "| An | An |"), "reviewer"),
            ("docs/plan/phan-viec/an.md", "# Tasks\n### WP-P1 · Docs\n", "task fields"),
            ("docs/plan/review.md", "# Review\n[v1.1, chờ OQ-B1]\n", "resolved"),
            ("docs/plan/review.md", "# Review\n(ADR-13, chờ duyệt)\n", "resolved"),
            (
                "docs/specs/roadwatch-architecture.md",
                files["docs/specs/roadwatch-architecture.md"].replace('approved_on: "2026-09-29"\n', ""),
                "metadata",
            ),
            (
                "docs/specs/roadwatch-architecture.md",
                files["docs/specs/roadwatch-architecture.md"].replace("../plan/review.md", "https://example.com/review"),
                "relative local path",
            ),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, content in files.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
            self.assertEqual(check(root), [])
            for name, content, expected in mutations:
                with self.subTest(expected=expected, file=name):
                    (root / name).write_text(content, encoding="utf-8")
                    self.assertTrue(any(expected in error for error in check(root)), check(root))
                    (root / name).write_text(files[name], encoding="utf-8")
            # Historical decisions and links inside code examples are not active instructions.
            (root / "docs/plan/review.md").write_text(
                '---\ndoc_id: "OLD"\ndoc_type: "archive"\nstatus: "archived"\n'
                "authority_for: []\n---\n# History\nchờ OQ-B1\n```text\n[x](missing.md)\n```\n",
                encoding="utf-8",
            )
            self.assertEqual(check(root), [])

    def test_export_preserves_json_aliases_required_and_nullable(self):
        schema = json.loads(render())
        defs = schema["$defs"]
        self.assertEqual(defs["AlertDecision"]["properties"]["class"]["enum"], ["hazard", "status"])
        self.assertNotIn("cls", defs["AlertDecision"]["properties"])
        self.assertIn("frame_idx", defs["Measurement"]["required"])
        self.assertIn({"type": "null"}, defs["Measurement"]["properties"]["frame_idx"]["anyOf"])
        self.assertEqual(schema["x-roadwatch"]["status"], "implementation_snapshot")
        self.assertEqual(render(), render())


if __name__ == "__main__":
    unittest.main()
