from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from webworkflows.step_guide import StepGuideSuggester, heuristic_step_guide


class FakeCodexAppServerClient:
    def __init__(self, response_text: str):
        self.response_text = response_text
        self.calls: list[dict] = []
        self.closed = False

    def run_turn(self, *, prompt: str, output_schema: dict, image_paths: list[Path], model: str):
        self.calls.append(
            {
                "prompt": prompt,
                "output_schema": output_schema,
                "image_paths": list(image_paths),
                "model": model,
            }
        )
        return {"text": self.response_text, "thread_id": "thread_step", "turn_id": "turn_step"}

    def close(self) -> None:
        self.closed = True


class StepGuideSuggestionTests(unittest.TestCase):
    def test_codex_suggester_uses_app_server_context_and_normalizes_steps(self) -> None:
        app_server = FakeCodexAppServerClient(
            json.dumps(
                {
                    "steps": [
                        {"name": " open_flights ", "description": " Open Google Flights. ", "step_type": " goto "},
                        {"name": "", "description": "", "step_type": "click"},
                        {
                            "name": "wait_results",
                            "description": "Wait for SEA to JFK results.",
                            "step_type": "wait_for_text",
                        },
                    ]
                }
            )
        )

        suggester = StepGuideSuggester(app_server=app_server, model="gpt-test")
        result = suggester.suggest(
            start_url="https://www.google.com/flights",
            task="Search flights from SEA to JFK",
            final_state="SEA to JFK results are visible.",
            page_analysis_context={
                "analysis": {
                    "stable_markers": ["Google Flights", "SEA to JFK"],
                    "selector_strategy": "Prefer role selectors.",
                }
            },
            knowledge_context=[{"summary": "Wait for Best departing flights before rendering."}],
        )
        suggester.close()

        self.assertEqual("codex_app_server", result.provider)
        self.assertEqual("gpt-test", app_server.calls[0]["model"])
        self.assertEqual([], app_server.calls[0]["image_paths"])
        self.assertEqual("object", app_server.calls[0]["output_schema"]["type"])
        self.assertIn("Human task", app_server.calls[0]["prompt"])
        self.assertIn("Reusable page analysis context JSON", app_server.calls[0]["prompt"])
        self.assertIn("Best departing flights", app_server.calls[0]["prompt"])
        self.assertTrue(app_server.closed)
        self.assertEqual(
            [
                {"name": "open_flights", "description": "Open Google Flights.", "step_type": "goto"},
                {"name": "wait_results", "description": "Wait for SEA to JFK results.", "step_type": "wait_for_text"},
            ],
            result.step_guide,
        )

    def test_step_guide_module_does_not_spawn_nested_codex_exec(self) -> None:
        source = Path(__file__).resolve().parents[1].joinpath("webworkflows", "step_guide.py").read_text(
            encoding="utf-8"
        )

        self.assertNotIn("CodexCliSynthesisBackend", source)
        self.assertNotIn("codex exec", source.lower())

    def test_heuristic_step_guide_builds_a_useful_scaffold(self) -> None:
        guide = heuristic_step_guide(
            start_url="https://example.com/search",
            task="Search for SEA to JFK flights.",
            final_state="SEA to JFK flight results are visible.",
        )

        self.assertEqual("open_start_url", guide[0]["name"])
        self.assertEqual("goto", guide[0]["step_type"])
        self.assertIn("llm_browser_action", [step["step_type"] for step in guide])
        self.assertEqual("wait_for_text", guide[-2]["step_type"])
        self.assertEqual("render_report", guide[-1]["step_type"])

    def test_cli_suggest_step_guide_outputs_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "workflow_tools.sqlite"
            sqlite3.connect(db_path).close()

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "webworkflows.cli",
                    "suggest-step-guide",
                    "--db",
                    str(db_path),
                    "--start-url",
                    "https://www.google.com/flights",
                    "--task",
                    "Search flights from SEA to JFK",
                    "--final-state",
                    "SEA to JFK results are visible.",
                    "--suggester",
                    "heuristic",
                ],
                cwd=Path(__file__).resolve().parents[1],
                text=True,
                capture_output=True,
                check=True,
            )

            payload = json.loads(completed.stdout)
            self.assertEqual("succeeded", payload["status"])
            self.assertEqual("heuristic", payload["provider"])
            self.assertEqual("open_start_url", payload["step_guide"][0]["name"])
            self.assertTrue(payload["step_guide"])


if __name__ == "__main__":
    unittest.main()
