from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from webworkflows.seeds import seed_naver_stock_report
from webworkflows.services.update_runtime import WorkflowUpdateRuntime
from webworkflows.storage import WorkflowSkillStore
from webworkflows.synthesis import DEFAULT_CODEX_SYNTHESIS_MODEL, naver_stock_workflow_json


NAVER_STOCK_TEXT = """
삼성전자 주가 검색 결과
증권정보
삼성전자
005930 KOSPI
현재가
295,500원
전일대비 하락 33,500 (-10.18%)
"""


class WorkflowUpdateRuntimeServiceTest(unittest.TestCase):
    def test_propose_and_apply_return_cli_compatible_payloads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "workflow_tools.sqlite"
            workflow_json_path = Path(tmp) / "proposal.json"
            proposed = naver_stock_workflow_json()
            proposed["body_md"] = proposed["body_md"] + "\n\nInclude valuation metrics in the report."
            proposed["output_schema"]["valuation_summary"] = "string"
            workflow_json_path.write_text(json.dumps(proposed, ensure_ascii=False), encoding="utf-8")

            store = WorkflowSkillStore(db_path)
            store.initialize()
            seed_naver_stock_report(store)
            runtime = WorkflowUpdateRuntime(store, cwd=Path.cwd())

            proposal_payload = runtime.propose_update(
                workflow_name="naver_stock_report",
                base_version=1,
                instruction="리포트에 PER/PBR 같은 밸류에이션 섹션을 추가해줘",
                page_text=NAVER_STOCK_TEXT,
                discovery_provider="static",
                synthesizer="agent-json",
                workflow_json_file=workflow_json_path,
                synthesizer_model=DEFAULT_CODEX_SYNTHESIS_MODEL,
            )

            self.assertEqual(
                {
                    "proposal_id",
                    "workflow",
                    "base_version",
                    "proposed_version",
                    "status",
                    "synthesizer",
                    "synthesizer_model",
                    "synthesis_duration_ms",
                    "diff",
                    "proposed_workflow_json",
                },
                set(proposal_payload),
            )
            self.assertEqual("draft", proposal_payload["status"])
            self.assertEqual("agent-json", proposal_payload["synthesizer"])
            self.assertEqual(2, proposal_payload["proposed_version"])

            apply_payload = runtime.apply_proposal(
                proposal_id=proposal_payload["proposal_id"],
                approved_by="desktop-test",
            )

            self.assertEqual(
                {"proposal_id", "workflow", "status", "applied_version", "applied_version_id"},
                set(apply_payload),
            )
            self.assertEqual("applied", apply_payload["status"])
            self.assertEqual(2, apply_payload["applied_version"])


if __name__ == "__main__":
    unittest.main()
