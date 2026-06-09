from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from webworkflows.seeds import seed_naver_stock_report
from webworkflows.services.workflow_runtime import PageTextEvidence, WorkflowRuntime
from webworkflows.storage import WorkflowSkillStore


NAVER_STOCK_TEXT = """
삼성전자 주가 검색 결과
증권정보
삼성전자
005930 KOSPI
현재가
295,500원
전일대비 하락 33,500 (-10.18%)
KRX 06.08. 16:10 장마감
관련 뉴스
삼성전자와 SK하이닉스가 반도체 업황 변동으로 하락했다.
"""


class WorkflowRuntimeServiceTest(unittest.TestCase):
    def test_run_version_returns_cli_compatible_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "workflow_tools.sqlite"
            output_dir = Path(tmp) / "runs"
            store = WorkflowSkillStore(db_path)
            store.initialize()
            seed_naver_stock_report(store)
            runtime = WorkflowRuntime(store, output_dir=output_dir)

            payload = runtime.run_version(
                workflow_name="naver_stock_report",
                version=1,
                user_request="네이버에서 삼성전자 주가 리포트",
                arguments={
                    "company_name": "삼성전자",
                    "ticker": "005930",
                    "page_text": NAVER_STOCK_TEXT,
                    "news_limit": 3,
                },
                page_text_evidence=PageTextEvidence(
                    source="page_text_file",
                    details={"path": "fixture"},
                ),
            )

            self.assertEqual(
                {
                    "workflow",
                    "workflow_version",
                    "run_id",
                    "status",
                    "llm_used",
                    "page_text_evidence",
                    "output",
                    "report_path",
                },
                set(payload),
            )
            self.assertEqual("naver_stock_report", payload["workflow"])
            self.assertEqual(1, payload["workflow_version"])
            self.assertEqual("succeeded", payload["status"])
            self.assertFalse(payload["llm_used"])
            self.assertEqual({"source": "page_text_file", "path": "fixture"}, payload["page_text_evidence"])
            self.assertEqual(295500, payload["output"]["current_price"])
            self.assertTrue(Path(payload["report_path"]).exists())

    def test_run_latest_searches_workflow_and_returns_latest_version_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "workflow_tools.sqlite"
            output_dir = Path(tmp) / "runs"
            store = WorkflowSkillStore(db_path)
            store.initialize()
            seed_naver_stock_report(store)
            runtime = WorkflowRuntime(store, output_dir=output_dir)

            payload = runtime.run_latest(
                user_request="네이버에서 삼성전자 주가 리포트",
                arguments={
                    "company_name": "삼성전자",
                    "ticker": "005930",
                    "page_text": NAVER_STOCK_TEXT,
                    "news_limit": 3,
                },
                page_text_evidence=PageTextEvidence(source="page_text_file"),
            )

            self.assertEqual("naver_stock_report", payload["workflow"])
            self.assertEqual(1, payload["workflow_version"])
            self.assertEqual("succeeded", payload["status"])


if __name__ == "__main__":
    unittest.main()
