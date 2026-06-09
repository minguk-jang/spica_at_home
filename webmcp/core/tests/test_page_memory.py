from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from webworkflows.cold_init_types import ArtifactTrace
from webworkflows.page_memory import (
    PageAnalysisStore,
    WorkflowKnowledgeStore,
    build_script_generation_knowledge,
    normalize_url_key,
)
from webworkflows.storage import WorkflowSkillStore, default_studio_db_path
from webworkflows.synthesis import build_synthesis_prompt


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


class PageMemoryTest(unittest.TestCase):
    def test_default_studio_db_path_uses_home_dot_webmcp_studio_db(self) -> None:
        self.assertEqual(
            Path("/Users/alice/.webmcp-studio/db/workflows.sqlite"),
            default_studio_db_path(home_dir=Path("/Users/alice"), env={}),
        )
        self.assertEqual(
            Path("/tmp/custom-workflows.sqlite"),
            default_studio_db_path(
                home_dir=Path("/Users/alice"),
                env={"WEBMCP_STUDIO_DB_PATH": "/tmp/custom-workflows.sqlite"},
            ),
        )
        self.assertEqual(
            Path("/Users/alice/custom/workflows.sqlite"),
            default_studio_db_path(
                home_dir=Path("/Users/alice"),
                env={"WEBMCP_STUDIO_DB_PATH": "~/custom/workflows.sqlite"},
            ),
        )

    def test_normalize_url_key_removes_query_fragment_and_kebab_cases_path(self) -> None:
        self.assertEqual(
            "example-com-search-results",
            normalize_url_key("HTTPS://Example.COM:443/search/results/?q=삼성전자&utm=ad#section"),
        )
        self.assertEqual(
            "example-com-search-results",
            normalize_url_key("https://example.com/search/results?query=other"),
        )
        self.assertEqual(
            "localhost-5173-admin-tools",
            normalize_url_key("http://localhost:5173/admin_tools?debug=true"),
        )

    def test_page_analysis_store_upserts_and_finds_by_query_variant(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = WorkflowSkillStore(Path(tmp) / "workflows.sqlite")
            store.initialize()
            page_store = PageAnalysisStore(store)

            first = page_store.upsert_from_trace(
                ArtifactTrace(
                    provider="static",
                    user_request="Analyze iframe page",
                    arguments={},
                    page_text="ExampleReady iframe src='/checkout' frame navigation requires frame_locator",
                    title="Checkout",
                    final_url="https://example.com/checkout?cart=123&utm=campaign",
                ),
                source="test",
            )
            second = page_store.upsert_from_trace(
                ArtifactTrace(
                    provider="static",
                    user_request="Analyze iframe page again",
                    arguments={},
                    page_text="ExampleReady iframe src='/checkout' frame navigation requires frame_locator updated",
                    title="Checkout Updated",
                    final_url="https://example.com/checkout?cart=999",
                ),
                source="test",
            )
            found = page_store.lookup("https://example.com/checkout?cart=different")

        self.assertEqual("example-com-checkout", first.url_key)
        self.assertEqual(first.id, second.id)
        self.assertIsNotNone(found)
        self.assertEqual(2, found.observation_count)
        self.assertEqual("Checkout Updated", found.title)
        self.assertIn("iframe", found.frame_hints)
        self.assertIn("frame_locator", found.locator_hints)

    def test_naver_stock_page_analysis_contains_actionable_script_tips(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = WorkflowSkillStore(Path(tmp) / "workflows.sqlite")
            store.initialize()
            record = PageAnalysisStore(store).upsert_from_trace(
                ArtifactTrace(
                    provider="naver_browser_trace",
                    user_request="네이버에서 삼성전자 주가 리포트",
                    arguments={"company_name": "삼성전자", "ticker": "005930"},
                    page_text=NAVER_STOCK_TEXT,
                    title="삼성전자 주가 : 네이버 검색",
                    final_url="https://search.naver.com/search.naver?query=삼성전자%20주가",
                ),
                source="test",
            )

        self.assertEqual("naver_stock_search_result", record.analysis["page_type"])
        self.assertIn("증권정보", record.analysis["stable_markers"])
        self.assertIn("현재가", record.analysis["stable_markers"])
        self.assertIn("005930", record.analysis["detected_tickers"])
        self.assertTrue(
            any("direct search URL" in tip for tip in record.analysis["actionable_tips"]),
            record.analysis["actionable_tips"],
        )
        self.assertTrue(
            any("naver_stock.extract_stock_card" in tip for tip in record.analysis["extraction_tips"]),
            record.analysis["extraction_tips"],
        )

    def test_generic_page_analysis_extracts_stable_visible_text_markers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = WorkflowSkillStore(Path(tmp) / "workflows.sqlite")
            store.initialize()
            record = PageAnalysisStore(store).upsert_from_trace(
                ArtifactTrace(
                    provider="generic_browser_trace",
                    user_request="Remove and restore a dynamic checkbox",
                    arguments={},
                    page_text=(
                        "Dynamic Controls\n\n"
                        "This example demonstrates when elements are changed asynchronously.\n\n"
                        "Remove/add\n\n"
                        "A checkbox\n"
                        "Remove\n\n"
                        "Enable/disable\n\n"
                        "Enable\n"
                        "Powered by Elemental Selenium"
                    ),
                    title="The Internet",
                    final_url="https://the-internet.herokuapp.com/dynamic_controls",
                ),
                source="test",
            )

        self.assertEqual("generic_page", record.analysis["page_type"])
        self.assertIn("Dynamic Controls", record.analysis["stable_markers"])
        self.assertIn("Remove/add", record.analysis["stable_markers"])
        self.assertNotIn(
            "This example demonstrates when elements are changed asynchronously.",
            record.analysis["stable_markers"],
        )
        self.assertTrue(
            any("stable text markers" in tip for tip in record.analysis["actionable_tips"]),
            record.analysis["actionable_tips"],
        )
        self.assertIn("Dynamic Controls", record.analysis["assertion_strategy"])
        self.assertIn("markers=Dynamic Controls", record.analysis["summary"])

    def test_script_generation_knowledge_is_actionable_not_just_status(self) -> None:
        page_analysis = {
            "page_type": "naver_stock_search_result",
            "stable_markers": ["증권정보", "현재가", "005930"],
            "actionable_tips": [
                "Use the direct search URL https://search.naver.com/search.naver?query={{company_name}} 주가.",
                "Wait for 증권정보/current price markers before extracting body text.",
            ],
            "extraction_tips": ["Use naver_stock.extract_stock_card with page_text, company_name, ticker."],
            "risk_notes": ["Market status text changes between 장중 and 장마감."],
        }

        knowledge = build_script_generation_knowledge(
            status="succeeded",
            workflow_name="naver_stock_report",
            workflow_version=1,
            start_url="https://search.naver.com/search.naver?query=삼성전자%20주가",
            user_task="네이버에서 삼성전자 주가 리포트",
            final_state="삼성전자 현재가와 종목코드가 보인다.",
            output_keys=["company_name", "current_price", "report_text", "ticker"],
            page_analysis=page_analysis,
            error=None,
        )

        self.assertIn("Naver stock", knowledge["summary"])
        self.assertIn("actionable_tips", knowledge["content"])
        self.assertGreaterEqual(len(knowledge["content"]["actionable_tips"]), 3)
        self.assertIn("selector_strategy", knowledge["content"])
        self.assertIn("assertion_strategy", knowledge["content"])
        self.assertNotEqual("Workflow creation succeeded", knowledge["summary"])

    def test_workflow_knowledge_store_appends_jsonl_style_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = WorkflowSkillStore(Path(tmp) / "workflows.sqlite")
            store.initialize()
            knowledge_store = WorkflowKnowledgeStore(store)

            knowledge_store.append(
                category="script_generation",
                summary="Prefer role selectors for login forms",
                content={"selector_strategy": "get_by_role before css"},
                source="test",
                confidence=0.9,
                tags=["selectors", "forms"],
            )
            knowledge_store.append(
                category="page_analysis",
                summary="Iframe pages need frame_locator context",
                content={"hint": "detect iframe before click synthesis"},
                source="test",
                confidence=0.8,
                tags=["iframe"],
            )

            script_entries = knowledge_store.recent(category="script_generation", limit=5)
            all_entries = knowledge_store.recent(limit=5)

        self.assertEqual(1, len(script_entries))
        self.assertEqual("Prefer role selectors for login forms", script_entries[0].summary)
        self.assertEqual(2, len(all_entries))
        self.assertEqual("Iframe pages need frame_locator context", all_entries[0].summary)

    def test_synthesis_prompt_includes_page_analysis_and_knowledge_context(self) -> None:
        trace = ArtifactTrace(
            provider="static",
            user_request="Create dashboard script",
            arguments={"start_url": "https://app.example.com/dashboard"},
            page_text="ExampleReady React dashboard",
            title="Dashboard",
            final_url="https://app.example.com/dashboard",
            page_analysis_context={
                "url_key": "app-example-com-dashboard",
                "framework_hints": ["react", "nextjs"],
                "frame_hints": [],
                "locator_hints": ["prefer_role_selectors"],
            },
            knowledge_context=[
                {
                    "category": "script_generation",
                    "summary": "Prefer stable accessible names before CSS selectors",
                    "content": {"selector_order": ["role", "label", "testid", "css"]},
                }
            ],
        )

        prompt = build_synthesis_prompt(trace)

        self.assertIn("Reusable page analysis context JSON", prompt)
        self.assertIn("app-example-com-dashboard", prompt)
        self.assertIn("Reusable script generation knowledge JSON", prompt)
        self.assertIn("stable accessible names", prompt)


if __name__ == "__main__":
    unittest.main()
