from pathlib import Path
import re
import unittest


def repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / ".git").exists():
            return parent
    raise AssertionError("Could not find repository root")


def prose_only(markdown: str) -> str:
    without_fences = re.sub(r"```.*?```", "", markdown, flags=re.DOTALL)
    return re.sub(r"`[^`]+`", "", without_fences)


PROJECT_DOCS = [
    "webmcp/README.md",
    "webmcp/core/README.md",
    "webmcp/apps/desktop/README.md",
    "webmcp/apps/desktop/src/script-preview/README.md",
    "webmcp/core/plugins/webwright-text-vision/skills/webwright/SKILL.md",
    "webmcp/core/plugins/webwright-text-vision/skills/webwright/commands/craft.md",
    "webmcp/core/plugins/webwright-text-vision/skills/webwright/commands/run.md",
    "webmcp/core/plugins/webwright-text-vision/skills/webwright/reference/cli_tool_mode.md",
    "webmcp/core/plugins/webwright-text-vision/skills/webwright/reference/playwright_patterns.md",
    "webmcp/core/plugins/webwright-text-vision/skills/webwright/reference/workflow.md",
    "webmcp/docs/ARCHITECTURE.md",
    "webmcp/docs/DEVELOPMENT.md",
    "webmcp/docs/DESKTOP_APP.md",
    "webmcp/docs/RUNBOOK.md",
    "webmcp/docs/WORKFLOWS.md",
    "webmcp/docs/plans/2026-06-09-feature-slice-restructure-design.md",
    "webmcp/docs/plans/2026-06-09-feature-slice-restructure.md",
    "webmcp/docs/plans/2026-06-09-webmcp-desktop-design.md",
    "webmcp/docs/plans/2026-06-09-webmcp-desktop-implementation.md",
    "webmcp/docs/plans/2026-06-09-webmcp-update-studio.md",
    "webmcp/docs/plans/2026-06-09-workflow-skills-mvp.md",
]


class WebMcpFeatureSliceStructureTest(unittest.TestCase):
    def test_webmcp_feature_slice_contains_core_and_desktop_app(self) -> None:
        root = repo_root()

        self.assertTrue((root / "webmcp" / "core" / "webworkflows" / "cli.py").is_file())
        self.assertTrue((root / "webmcp" / "core" / "tests").is_dir())
        self.assertTrue((root / "webmcp" / "apps" / "desktop" / "package.json").is_file())
        self.assertTrue((root / "webmcp" / "apps" / "desktop" / "electron" / "main.cjs").is_file())

    def test_webmcp_docs_are_the_entry_point(self) -> None:
        root = repo_root()

        expected_docs = [
            root / "webmcp" / "README.md",
            root / "webmcp" / "docs" / "ARCHITECTURE.md",
            root / "webmcp" / "docs" / "DEVELOPMENT.md",
            root / "webmcp" / "docs" / "DESKTOP_APP.md",
            root / "webmcp" / "docs" / "RUNBOOK.md",
            root / "webmcp" / "docs" / "WORKFLOWS.md",
        ]

        for path in expected_docs:
            with self.subTest(path=path):
                self.assertTrue(path.is_file(), f"Missing {path}")

    def test_project_docs_are_korean_first(self) -> None:
        root = repo_root()

        for relative_path in PROJECT_DOCS:
            path = root / relative_path
            text = prose_only(path.read_text(encoding="utf-8"))
            hangul_count = len(re.findall(r"[가-힣]", text))
            latin_word_count = len(re.findall(r"\b[A-Za-z]{4,}\b", text))

            with self.subTest(path=relative_path):
                self.assertGreater(hangul_count, 120, f"{relative_path} needs Korean prose")
                self.assertGreater(
                    hangul_count,
                    latin_word_count,
                    f"{relative_path} should be Korean-first, not English-first",
                )

    def test_main_docs_include_diagrams(self) -> None:
        root = repo_root()
        main_docs = [
            root / "webmcp" / "README.md",
            root / "webmcp" / "docs" / "ARCHITECTURE.md",
            root / "webmcp" / "docs" / "DEVELOPMENT.md",
            root / "webmcp" / "docs" / "DESKTOP_APP.md",
            root / "webmcp" / "docs" / "RUNBOOK.md",
            root / "webmcp" / "docs" / "WORKFLOWS.md",
        ]

        diagram_count = 0
        for path in main_docs:
            text = path.read_text(encoding="utf-8")
            diagram_count += text.count("```mermaid")

        self.assertGreaterEqual(diagram_count, 8)


if __name__ == "__main__":
    unittest.main()
