from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from webworkflows.cold_init import WorkflowMaterializer, discovery_from_workflow_json
from webworkflows.js_tool import JsToolExporter, eval_js_tool, run_js_tool
from webworkflows.seeds import seed_naver_stock_report
from webworkflows.storage import WorkflowSkillStore
from webworkflows.synthesis import naver_map_transit_route_workflow_json


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


NAVER_MAP_TEXT = """
네이버 지도 길찾기
양재역 출발
사당역 도착
대중교통
지하철
22분
3호선 양재역 승차 후 교대역 환승, 2호선 사당역 하차
"""


GENERIC_PAGE_TEXT = """
Example Product Page
Checkout ready
Order total
42,000원
"""


class JavaScriptToolConversionTest(unittest.TestCase):
    def test_initialize_uses_workflow_tool_tables_as_canonical_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "tools.sqlite"
            store = WorkflowSkillStore(db_path)
            store.initialize()

            with store.connect() as conn:
                tables = {
                    row["name"]
                    for row in conn.execute(
                        "select name from sqlite_master where type = 'table' order by name"
                    )
                }

            self.assertIn("workflow_tools", tables)
            self.assertIn("workflow_tool_versions", tables)
            self.assertIn("workflow_tool_arguments", tables)
            self.assertIn("workflow_tool_steps", tables)
            self.assertIn("workflow_tool_resources", tables)
            self.assertIn("workflow_tool_examples", tables)
            self.assertNotIn("workflow_skills", tables)
            self.assertNotIn("workflow_skill_versions", tables)

    def test_initialize_migrates_legacy_workflow_skill_tables_to_tool_tables(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "legacy.sqlite"
            with sqlite3.connect(db_path) as conn:
                conn.executescript(
                    """
                    create table workflow_skills (
                        id integer primary key autoincrement,
                        name text not null unique,
                        slug text not null unique,
                        description text not null,
                        domain text not null,
                        task_type text not null,
                        status text not null,
                        latest_version_id integer,
                        created_at text not null default current_timestamp,
                        updated_at text not null default current_timestamp
                    );
                    create table workflow_skill_versions (
                        id integer primary key autoincrement,
                        skill_id integer not null references workflow_skills(id) on delete cascade,
                        version integer not null,
                        summary text not null,
                        input_schema_json text not null,
                        output_schema_json text not null,
                        body_md text not null,
                        load_policy_json text not null,
                        status text not null,
                        created_from_run_id integer,
                        created_at text not null default current_timestamp,
                        unique(skill_id, version)
                    );
                    insert into workflow_skills
                      (id, name, slug, description, domain, task_type, status, latest_version_id)
                    values (1, 'legacy_tool', 'legacy-tool', 'Legacy tool', 'example.test', 'demo', 'stable', 1);
                    insert into workflow_skill_versions
                      (id, skill_id, version, summary, input_schema_json, output_schema_json,
                       body_md, load_policy_json, status)
                    values (1, 1, 1, 'Legacy version', '{}', '{}', 'Body', '{}', 'stable');
                    """
                )

            store = WorkflowSkillStore(db_path)
            store.initialize()

            with store.connect() as conn:
                tables = {
                    row["name"]
                    for row in conn.execute(
                        "select name from sqlite_master where type = 'table' order by name"
                    )
                }
                tool = conn.execute("select name from workflow_tools where id = 1").fetchone()
                version = conn.execute(
                    "select version from workflow_tool_versions where skill_id = 1"
                ).fetchone()

            self.assertIn("workflow_tools", tables)
            self.assertIn("workflow_tool_versions", tables)
            self.assertNotIn("workflow_skills", tables)
            self.assertNotIn("workflow_skill_versions", tables)
            self.assertEqual("legacy_tool", tool["name"])
            self.assertEqual(1, version["version"])

    def test_exports_naver_stock_workflow_as_javascript_tool(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = _seed_store(Path(tmp) / "tools.sqlite")
            export_dir = Path(tmp) / "js-tools"

            exported = JsToolExporter(store).export(
                workflow_name="naver_stock_report",
                version=1,
                output_dir=export_dir,
            )

            self.assertEqual("naver_stock_report", exported.manifest["name"])
            self.assertEqual(1, exported.manifest["version"])
            self.assertTrue((exported.tool_dir / "manifest.json").exists())
            self.assertTrue((exported.tool_dir / "tool.cjs").exists())
            self.assertTrue((exported.tool_dir / "workflow.json").exists())

    def test_runs_three_exported_javascript_tool_examples(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = _seed_store(Path(tmp) / "tools.sqlite")
            export_root = Path(tmp) / "js-tools"

            stock_dir = JsToolExporter(store).export(
                workflow_name="naver_stock_report",
                version=1,
                output_dir=export_root,
            ).tool_dir
            stock = run_js_tool(
                stock_dir,
                {
                    "company_name": "삼성전자",
                    "ticker": "005930",
                    "news_limit": 3,
                    "page_text": NAVER_STOCK_TEXT,
                },
            )
            self.assertEqual("succeeded", stock["status"])
            self.assertEqual("삼성전자", stock["output"]["company_name"])
            self.assertEqual(295500, stock["output"]["current_price"])
            self.assertIn("삼성전자 주가 리포트", stock["output"]["report_text"])

            map_dir = JsToolExporter(store).export(
                workflow_name="naver_map_transit_route",
                version=1,
                output_dir=export_root,
            ).tool_dir
            route = run_js_tool(
                map_dir,
                {
                    "start_station": "양재역",
                    "end_station": "사당역",
                    "start_url": "https://www.naver.com",
                    "page_text": NAVER_MAP_TEXT,
                },
            )
            self.assertEqual("succeeded", route["status"])
            self.assertEqual("22분", route["output"]["duration_text"])
            self.assertEqual(22, route["output"]["duration_minutes"])

            generic_dir = JsToolExporter(store).export(
                workflow_name="generic_checkout_summary",
                version=1,
                output_dir=export_root,
            ).tool_dir
            generic = run_js_tool(
                generic_dir,
                {
                    "start_url": "https://example.test/checkout",
                    "page_text": GENERIC_PAGE_TEXT,
                },
            )
            self.assertEqual("succeeded", generic["status"])
            self.assertIn("Checkout ready", generic["output"]["report_text"])

    def test_evaluates_javascript_tool_output_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = _seed_store(Path(tmp) / "tools.sqlite")
            tool_dir = JsToolExporter(store).export(
                workflow_name="naver_stock_report",
                version=1,
                output_dir=Path(tmp) / "js-tools",
            ).tool_dir

            report = eval_js_tool(
                tool_dir,
                {
                    "company_name": "삼성전자",
                    "ticker": "005930",
                    "news_limit": 3,
                    "page_text": NAVER_STOCK_TEXT,
                },
                required_output=["company_name", "ticker", "current_price", "report_text"],
            )

            self.assertTrue(report["passed"])
            self.assertEqual("succeeded", report["run"]["status"])
            self.assertEqual([], report["missing_output"])

    def test_cli_exports_runs_and_evaluates_javascript_tool(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "tools.sqlite"
            store = _seed_store(db_path)
            self.assertIsNotNone(store)
            export_root = Path(tmp) / "js-tools"
            args_path = Path(tmp) / "args.json"
            args_path.write_text(
                json.dumps(
                    {
                        "company_name": "삼성전자",
                        "ticker": "005930",
                        "news_limit": 3,
                        "page_text": NAVER_STOCK_TEXT,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            export_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "webworkflows.cli",
                    "export-js-tool",
                    "--db",
                    str(db_path),
                    "--workflow-name",
                    "naver_stock_report",
                    "--version",
                    "1",
                    "--output-dir",
                    str(export_root),
                ],
                text=True,
                capture_output=True,
                check=True,
            )
            exported = json.loads(export_completed.stdout)

            run_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "webworkflows.cli",
                    "run-js-tool",
                    "--tool-dir",
                    exported["tool_dir"],
                    "--arguments-file",
                    str(args_path),
                ],
                text=True,
                capture_output=True,
                check=True,
            )
            run_payload = json.loads(run_completed.stdout)
            self.assertEqual("succeeded", run_payload["status"])

            eval_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "webworkflows.cli",
                    "eval-js-tool",
                    "--tool-dir",
                    exported["tool_dir"],
                    "--arguments-file",
                    str(args_path),
                    "--required-output",
                    "company_name",
                    "--required-output",
                    "ticker",
                    "--required-output",
                    "current_price",
                    "--required-output",
                    "report_text",
                ],
                text=True,
                capture_output=True,
                check=True,
            )
            eval_payload = json.loads(eval_completed.stdout)
            self.assertTrue(eval_payload["passed"])


def _seed_store(db_path: Path) -> WorkflowSkillStore:
    store = WorkflowSkillStore(db_path)
    store.initialize()
    seed_naver_stock_report(store)
    WorkflowMaterializer(store).materialize(
        discovery_from_workflow_json(
            naver_map_transit_route_workflow_json(
                start_station="양재역",
                end_station="사당역",
                start_url="https://www.naver.com",
            ),
            provider="test",
            page_text=NAVER_MAP_TEXT,
        )
    )
    WorkflowMaterializer(store).materialize(
        discovery_from_workflow_json(
            _generic_checkout_workflow_json(),
            provider="test",
            page_text=GENERIC_PAGE_TEXT,
        )
    )
    return store


def _generic_checkout_workflow_json() -> dict:
    return {
        "skill_name": "generic_checkout_summary",
        "slug": "generic-checkout-summary",
        "description": "Summarize a generic checkout page from page text.",
        "domain": "example.test",
        "task_type": "checkout_summary",
        "body_md": "Generic text-first checkout summary workflow.",
        "input_schema": {
            "start_url": {"type": "string", "required": True},
            "page_text": {"type": "string", "required": True},
        },
        "output_schema": {"url": "string", "report_text": "string"},
        "arguments": [
            {
                "name": "start_url",
                "description": "Start URL",
                "type": "string",
                "required": True,
                "default_value": None,
                "validation": {},
                "examples": ["https://example.test/checkout"],
                "is_dynamic": True,
                "order_index": 0,
            },
            {
                "name": "page_text",
                "description": "Page text",
                "type": "string",
                "required": True,
                "default_value": None,
                "validation": {},
                "examples": [],
                "is_dynamic": True,
                "order_index": 1,
            },
        ],
        "steps": [
            {
                "name": "open_checkout",
                "description": "Open checkout URL.",
                "step_type": "goto",
                "handler_ref": None,
                "action": {"url_template": "{{start_url}}"},
                "argument_bindings": {},
                "assertions": {},
                "fallback_policy": {},
                "update_policy": {},
            },
            {
                "name": "wait_checkout_ready",
                "description": "Wait for checkout text.",
                "step_type": "wait_for_text",
                "handler_ref": None,
                "action": {},
                "argument_bindings": {},
                "assertions": {"contains_any": ["Checkout ready", "Order total"]},
                "fallback_policy": {},
                "update_policy": {},
            },
            {
                "name": "render_checkout_report",
                "description": "Render checkout report.",
                "step_type": "render_report",
                "handler_ref": None,
                "action": {"template_resource": "checkout_report_markdown"},
                "argument_bindings": {},
                "assertions": {},
                "fallback_policy": {},
                "update_policy": {},
            },
        ],
        "resources": [
            {
                "resource_type": "template",
                "name": "checkout_report_markdown",
                "description": "Checkout report template.",
                "content_json": None,
                "content_text": "# Checkout Summary\n\n{{page_text}}\n",
                "load_when": {},
            }
        ],
        "handlers": [],
    }


if __name__ == "__main__":
    unittest.main()
