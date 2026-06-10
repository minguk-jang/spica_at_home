from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = ROOT / "plugins" / "webwright-text-vision"


class TextDefaultVisionFallbackTest(unittest.TestCase):
    def test_plugin_manifest_exposes_text_default_vision_fallback(self) -> None:
        manifest_path = PLUGIN_ROOT / ".codex-plugin" / "plugin.json"

        manifest = json.loads(manifest_path.read_text())

        self.assertEqual("webwright-text-vision", manifest["name"])
        self.assertEqual("./skills/", manifest["skills"])
        self.assertIn("defaultPrompt", manifest["interface"])
        default_prompt = manifest["interface"]["defaultPrompt"].lower()
        self.assertIn("text default", default_prompt)
        self.assertIn("vision fallback", default_prompt)

    def test_skill_requires_dom_first_and_vision_fallback_only_when_needed(self) -> None:
        skill_path = PLUGIN_ROOT / "skills" / "webwright" / "SKILL.md"

        skill = skill_path.read_text()

        self.assertIn("Text-default mode", skill)
        self.assertIn("gpt-5.5", skill)
        self.assertNotIn("gpt-5.3-codex-spark", skill)
        self.assertIn("aria_snapshot", skill)
        self.assertIn("Vision fallback", skill)
        self.assertIn("Do not send screenshots to the default text model", skill)
        self.assertIn("No nested Codex", skill)
        self.assertIn("Do not launch the standalone Python harness as the default path", skill)
        self.assertIn("WebMCP Workflow Optimization", skill)
        self.assertIn("--synthesizer agent-json", skill)
        self.assertIn("--workflow-json-file", skill)
        self.assertIn("Use Codex app-server for Core-managed Codex synthesis", skill)

    def test_dual_model_config_disables_default_screenshot_attachment(self) -> None:
        config_path = PLUGIN_ROOT / "config" / "model_codex_oauth_text_vision.yaml"

        config = config_path.read_text()

        self.assertIn("Codex app-server", config)
        self.assertNotIn("Current mode", config)
        self.assertNotIn("default agent", config.lower())
        self.assertNotIn("model_class: codex_cli", config)
        self.assertIn("model_class: codex_app_server", config)
        self.assertIn("model_name: gpt-5.5", config)
        self.assertNotIn("model_name: gpt-5.3-codex-spark", config)
        self.assertIn("attach_observation_screenshot: false", config)
        self.assertIn("vision_model:", config)
        self.assertIn("attach_observation_screenshot: true", config)

    def test_text_default_alias_is_documented_as_fallback_only(self) -> None:
        config_path = PLUGIN_ROOT / "config" / "model_text_default_vision_fallback.yaml"

        config = config_path.read_text()

        self.assertIn("Codex app-server", config)
        self.assertNotIn("current Codex OAuth mode", config)
        self.assertNotIn("model_class: codex_cli", config)
        self.assertIn("model_class: codex_app_server", config)

    def test_openai_compatible_config_is_packaged_for_later_switch(self) -> None:
        config_path = PLUGIN_ROOT / "config" / "model_openai_compatible_text_vision.yaml"

        config = config_path.read_text()

        self.assertIn("model_class: openai", config)
        self.assertIn("openai_endpoint:", config)
        self.assertIn("openai_api_key:", config)
        self.assertIn("vision_model:", config)

    def test_run_script_requires_explicit_harness_config_to_avoid_nested_codex(self) -> None:
        script_path = PLUGIN_ROOT / "scripts" / "run_text_vision_demo.sh"

        script = script_path.read_text()

        self.assertIn("WEBWRIGHT_MODEL_CONFIG must be set", script)
        self.assertIn("model_codex_oauth_text_vision.yaml", script)
        self.assertNotIn("WEBWRIGHT_MODEL_CONFIG:-model_codex_oauth_text_vision.yaml", script)
        self.assertNotIn("codex_cli", script)
        self.assertIn("python -m webwright.run.cli main", script)

    def test_plugin_commands_document_webmcp_workflow_agent_json_path(self) -> None:
        for command_name in ["run", "craft"]:
            command_path = PLUGIN_ROOT / "skills" / "webwright" / "commands" / f"{command_name}.md"

            command = command_path.read_text()

            self.assertIn("WebMCP workflow", command)
            self.assertIn("--synthesizer agent-json", command)
            self.assertIn("--workflow-json-file", command)
            self.assertIn("Codex app-server JSON-RPC", command)

    def test_local_marketplace_points_at_current_plugin(self) -> None:
        marketplace_path = ROOT / ".agents" / "plugins" / "marketplace.json"

        marketplace = json.loads(marketplace_path.read_text())

        self.assertEqual("webwright-text-vision", marketplace["name"])
        self.assertEqual("webwright-text-vision", marketplace["plugins"][0]["name"])
        self.assertEqual(
            "./plugins/webwright-text-vision",
            marketplace["plugins"][0]["source"]["path"],
        )


if __name__ == "__main__":
    unittest.main()
