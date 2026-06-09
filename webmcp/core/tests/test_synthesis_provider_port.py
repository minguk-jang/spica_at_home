from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from webworkflows.providers.synthesis_provider import create_synthesis_backend
from webworkflows.synthesis import naver_stock_workflow_json


class SynthesisProviderPortTest(unittest.TestCase):
    def test_create_agent_json_backend_from_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workflow_path = Path(tmp) / "workflow.json"
            workflow_path.write_text(json.dumps(naver_stock_workflow_json(), ensure_ascii=False), encoding="utf-8")

            backend = create_synthesis_backend("agent-json", workflow_json_file=workflow_path)

            self.assertEqual("agent_json", backend.provider)

    def test_create_codex_backend_keeps_provider_name(self) -> None:
        backend = create_synthesis_backend("codex", cwd=Path.cwd())

        self.assertEqual("codex_cli", backend.provider)

    def test_create_fake_copy_backend_requires_base_workflow(self) -> None:
        backend = create_synthesis_backend("fake-copy", base_workflow_json=naver_stock_workflow_json())

        self.assertEqual("fake", backend.provider)
        self.assertIn("fake-copy", backend.response["body_md"])


if __name__ == "__main__":
    unittest.main()
