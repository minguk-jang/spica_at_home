from __future__ import annotations

from typing import Any

from webworkflows.storage import WorkflowSkillStore, dumps, loads


NAVER_STOCK_REPORT_EXAMPLES = [
    (
        "네이버에서 삼성전자 주가 리포트",
        {"company_name": "삼성전자", "ticker": "005930", "news_limit": 3},
    ),
    (
        "네이버에서 SK하이닉스 주가 리포트",
        {"company_name": "SK하이닉스", "ticker": "000660", "news_limit": 3},
    ),
    (
        "네이버에서 NAVER 주가 리포트",
        {"company_name": "NAVER", "ticker": "035420", "news_limit": 3},
    ),
]


def seed_naver_stock_report(store: WorkflowSkillStore) -> None:
    with store.connect() as conn:
        existing = conn.execute(
            "select id from workflow_skills where name = ?",
            ("naver_stock_report",),
        ).fetchone()
        if existing:
            _ensure_naver_stock_report_examples(conn, int(existing["id"]))
            return

        skill_id = conn.execute(
            """
            insert into workflow_skills
              (name, slug, description, domain, task_type, status)
            values (?, ?, ?, ?, ?, ?)
            """,
            (
                "naver_stock_report",
                "naver-stock-report",
                "네이버에서 기업 주가를 검색하고 현재가, 등락률, 종목코드, 관련 뉴스 기반 리포트를 작성한다.",
                "naver.com",
                "stock_report",
                "stable",
            ),
        ).lastrowid

        version_id = conn.execute(
            """
            insert into workflow_skill_versions
              (skill_id, version, summary, input_schema_json, output_schema_json, body_md, load_policy_json, status)
            values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                skill_id,
                1,
                "Naver stock report WebMCP workflow with deterministic text extraction.",
                dumps(
                    {
                        "company_name": {"type": "string", "required": True},
                        "ticker": {"type": "string", "required": False},
                        "page_text": {"type": "string", "required": False},
                        "news_limit": {"type": "integer", "required": False, "default": 3},
                    }
                ),
                dumps(
                    {
                        "company_name": "string",
                        "ticker": "string",
                        "current_price": "integer",
                        "change_text": "string",
                        "report_text": "string",
                    }
                ),
                "Load this workflow when a user asks to search Naver for a company stock price and write a report.",
                dumps({"metadata_first": True, "lazy_load_steps": True}),
                "stable",
            ),
        ).lastrowid

        conn.execute(
            "update workflow_skills set latest_version_id = ? where id = ?",
            (version_id, skill_id),
        )

        _ensure_naver_stock_report_examples(conn, int(skill_id))

        arguments = [
            ("company_name", "검색할 기업명", "string", True, None, {"min_length": 1}, ["삼성전자"], True),
            ("ticker", "종목코드", "string", False, None, {"pattern": "^[0-9]{6}$"}, ["005930"], True),
            ("page_text", "테스트 또는 캐시 실행에 사용할 페이지 전체 텍스트", "string", False, None, {}, [], True),
            ("news_limit", "리포트에 포함할 뉴스 수", "integer", False, 3, {"minimum": 0, "maximum": 10}, [3], True),
        ]
        for index, arg in enumerate(arguments):
            name, description, typ, required, default_value, validation, examples_json, is_dynamic = arg
            conn.execute(
                """
                insert into workflow_skill_arguments
                  (version_id, name, description, type, required, default_value_json,
                   validation_json, examples_json, is_dynamic, order_index)
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    version_id,
                    name,
                    description,
                    typ,
                    int(required),
                    dumps(default_value) if default_value is not None else None,
                    dumps(validation),
                    dumps(examples_json),
                    int(is_dynamic),
                    index,
                ),
            )

        steps = [
            (
                "open_naver_stock_search",
                "Build the Naver search URL for the company stock query.",
                "goto",
                None,
                {"url_template": "https://search.naver.com/search.naver?query={{company_name}} 주가"},
                {},
                {"url_contains": "search.naver.com"},
            ),
            (
                "wait_stock_card",
                "Require stock result text to be present.",
                "wait_for_text",
                None,
                {"source": "page_text"},
                {},
                {"contains_any": ["증권정보", "현재가", "{{company_name}}"]},
            ),
            (
                "extract_stock_card",
                "Extract company, ticker, current price, change text, and news context.",
                "run_handler",
                "naver_stock.extract_stock_card",
                {"input_key": "page_text"},
                {},
                {"required_output": ["company_name", "current_price"]},
            ),
            (
                "validate_stock_output",
                "Validate extracted stock output against requested arguments.",
                "assert_output",
                None,
                {},
                {},
                {"equals": {"company_name": "{{company_name}}"}, "optional_equals": {"ticker": "{{ticker}}"}},
            ),
            (
                "render_stock_report",
                "Render a deterministic Markdown report from extracted fields.",
                "render_report",
                None,
                {"template_resource": "stock_report_markdown"},
                {},
                {"required_output": ["report_text"]},
            ),
        ]
        for index, step in enumerate(steps):
            name, description, step_type, handler_ref, action, bindings, assertions = step
            conn.execute(
                """
                insert into workflow_skill_steps
                  (version_id, order_index, name, description, step_type, handler_ref,
                   action_json, argument_bindings_json, assertions_json,
                   fallback_policy_json, update_policy_json)
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    version_id,
                    index,
                    name,
                    description,
                    step_type,
                    handler_ref,
                    dumps(action),
                    dumps(bindings),
                    dumps(assertions),
                    dumps({"retry": 0}),
                    dumps({"record_update_event": True}),
                ),
            )

        conn.execute(
            """
            insert into workflow_skill_resources
              (version_id, resource_type, name, description, content_json, content_text, load_when_json)
            values (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                version_id,
                "report_template",
                "stock_report_markdown",
                "Markdown template for a Naver stock report.",
                None,
                (
                    "# {{company_name}} 주가 리포트\n\n"
                    "- 종목코드: {{ticker}}\n"
                    "- 현재가: {{current_price_formatted}}원\n"
                    "- 등락 정보: {{change_text}}\n"
                    "- 시장 상태: {{market_status}}\n\n"
                    "## 관련 맥락\n"
                    "{{news_context}}\n"
                ),
                dumps({"step": "render_stock_report"}),
            ),
        )

        conn.execute(
            """
            insert into handler_registry
              (name, description, module, function, input_schema_json, output_schema_json, allowed_domains_json)
            values (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "naver_stock.extract_stock_card",
                "Extract stock quote fields from Naver stock search text.",
                "webworkflows.handlers.naver_stock",
                "extract_stock_card",
                dumps({"page_text": "string", "company_name": "string", "ticker": "string optional"}),
                dumps({"company_name": "string", "current_price": "integer"}),
                dumps(["naver.com"]),
            ),
        )


def _ensure_naver_stock_report_examples(conn, skill_id: int) -> None:
    existing_keys = set()
    for row in conn.execute(
        """
        select normalized_arguments_json
        from workflow_skill_examples
        where skill_id = ?
        """,
        (skill_id,),
    ):
        args = loads(row["normalized_arguments_json"], {})
        if isinstance(args, dict):
            existing_keys.add(_stock_example_key(args))

    for request, args in NAVER_STOCK_REPORT_EXAMPLES:
        key = _stock_example_key(args)
        if key in existing_keys:
            continue
        conn.execute(
            """
            insert into workflow_skill_examples
              (skill_id, user_request, normalized_arguments_json, expected_output_summary)
            values (?, ?, ?, ?)
            """,
            (skill_id, request, dumps(args), "Markdown stock report"),
        )
        existing_keys.add(key)


def _stock_example_key(args: dict[str, Any]) -> str:
    company_name = args.get("company_name") or args.get("companyName") or ""
    ticker = args.get("ticker") or ""
    if company_name or ticker:
        return f"{company_name}\0{ticker}"
    return dumps(args)
