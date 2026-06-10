from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from webworkflows.providers.synthesis_provider import create_synthesis_backend
from webworkflows.synthesis import CodexAppServerSynthesisBackend, LLMWorkflowSynthesizer, naver_stock_workflow_json


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
        return {"text": self.response_text, "thread_id": "thread_synth", "turn_id": "turn_synth"}

    def close(self) -> None:
        self.closed = True


class SynthesisProviderPortTest(unittest.TestCase):
    def test_create_agent_json_backend_from_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workflow_path = Path(tmp) / "workflow.json"
            workflow_path.write_text(json.dumps(naver_stock_workflow_json(), ensure_ascii=False), encoding="utf-8")

            backend = create_synthesis_backend("agent-json", workflow_json_file=workflow_path)

            self.assertEqual("agent_json", backend.provider)

    def test_create_codex_backend_uses_app_server_instead_of_nested_cli_exec(self) -> None:
        backend = create_synthesis_backend("codex", cwd=Path.cwd())

        self.assertEqual("codex_app_server", backend.provider)

    def test_codex_app_server_synthesis_backend_uses_json_rpc_schema(self) -> None:
        workflow = naver_stock_workflow_json()
        fake_client = FakeCodexAppServerClient(json.dumps(workflow, ensure_ascii=False))
        backend = CodexAppServerSynthesisBackend(app_server=fake_client)

        result = backend.synthesize(
            prompt="Build a Naver stock workflow.",
            schema={"type": "object", "properties": {"skill_name": {"type": "string"}}},
            model="gpt-test",
        )
        backend.close()

        self.assertEqual(workflow["skill_name"], result["skill_name"])
        self.assertEqual("gpt-test", fake_client.calls[0]["model"])
        self.assertEqual([], fake_client.calls[0]["image_paths"])
        self.assertIn("Build a Naver stock workflow.", fake_client.calls[0]["prompt"])
        self.assertIn("JSON Schema", fake_client.calls[0]["prompt"])
        self.assertTrue(fake_client.closed)

    def test_llm_workflow_synthesizer_default_backend_uses_app_server(self) -> None:
        synthesizer = LLMWorkflowSynthesizer()

        self.assertEqual("llm_codex_app_server", synthesizer.provider)

    def test_create_fake_copy_backend_requires_base_workflow(self) -> None:
        backend = create_synthesis_backend("fake-copy", base_workflow_json=naver_stock_workflow_json())

        self.assertEqual("fake", backend.provider)
        self.assertIn("fake-copy", backend.response["body_md"])


if __name__ == "__main__":
    unittest.main()
