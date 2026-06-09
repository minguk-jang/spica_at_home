from __future__ import annotations

import argparse
import json
from pathlib import Path

from webworkflows.cold_init import (
    ColdInitRunner,
    IntelligentColdInitRunner,
    NaverBrowserDiscoveryRunner,
    NaverBrowserTraceCollector,
    StaticDiscoveryRunner,
    StaticTraceCollector,
)
from webworkflows.executor import WorkflowExecutor
from webworkflows.loader import WorkflowSkillLoader
from webworkflows.seeds import seed_naver_stock_report
from webworkflows.synthesis import (
    AgentJsonSynthesisBackend,
    DEFAULT_CODEX_SYNTHESIS_MODEL,
    FakeSynthesisBackend,
    LLMWorkflowSynthesizer,
    naver_stock_workflow_json,
)
from webworkflows.storage import WorkflowSkillStore
from webworkflows.update_proposal import (
    WorkflowUpdateProposalService,
    backend_from_name,
    workflow_json_from_skill,
)


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m webworkflows.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--db", required=True)
    run_parser.add_argument("--output-dir", required=True)
    run_parser.add_argument("--request", required=True)
    run_parser.add_argument("--company-name", required=True)
    run_parser.add_argument("--ticker")
    run_parser.add_argument("--page-text-file")
    run_parser.add_argument("--news-limit", type=int, default=3)
    run_parser.add_argument("--live-page-text", action="store_true")
    run_parser.add_argument("--headed", action="store_true")

    run_version_parser = subparsers.add_parser("run-version")
    run_version_parser.add_argument("--db", required=True)
    run_version_parser.add_argument("--output-dir", required=True)
    run_version_parser.add_argument("--workflow-name", required=True)
    run_version_parser.add_argument("--version", type=int, required=True)
    run_version_parser.add_argument("--request", required=True)
    run_version_parser.add_argument("--company-name", required=True)
    run_version_parser.add_argument("--ticker")
    run_version_parser.add_argument("--page-text-file")
    run_version_parser.add_argument("--news-limit", type=int, default=3)
    run_version_parser.add_argument("--live-page-text", action="store_true")
    run_version_parser.add_argument("--headed", action="store_true")

    propose_update_parser = subparsers.add_parser("propose-update")
    propose_update_parser.add_argument("--db", required=True)
    propose_update_parser.add_argument("--output-dir")
    propose_update_parser.add_argument("--workflow-name", required=True)
    propose_update_parser.add_argument("--base-version", type=int, required=True)
    propose_update_parser.add_argument("--instruction", required=True)
    propose_update_parser.add_argument("--company-name")
    propose_update_parser.add_argument("--ticker")
    propose_update_parser.add_argument("--page-text-file")
    propose_update_parser.add_argument(
        "--discovery-provider",
        choices=("none", "static", "webwright"),
        default="none",
    )
    propose_update_parser.add_argument(
        "--synthesizer",
        choices=("codex", "agent-json", "fake-copy"),
        default="codex",
    )
    propose_update_parser.add_argument("--workflow-json-file")
    propose_update_parser.add_argument("--synthesizer-model", default=DEFAULT_CODEX_SYNTHESIS_MODEL)
    propose_update_parser.add_argument("--headed", action="store_true")

    apply_proposal_parser = subparsers.add_parser("apply-proposal")
    apply_proposal_parser.add_argument("--db", required=True)
    apply_proposal_parser.add_argument("--proposal-id", type=int, required=True)
    apply_proposal_parser.add_argument("--approved-by", default="desktop")

    cold_parser = subparsers.add_parser("cold-init")
    cold_parser.add_argument("--db", required=True)
    cold_parser.add_argument("--output-dir", required=True)
    cold_parser.add_argument("--request", required=True)
    cold_parser.add_argument("--company-name", required=True)
    cold_parser.add_argument("--ticker")
    cold_parser.add_argument("--page-text-file")
    cold_parser.add_argument("--news-limit", type=int, default=3)
    cold_parser.add_argument(
        "--discovery-provider",
        choices=("static", "naver-browser"),
        default="static",
    )
    cold_parser.add_argument("--headed", action="store_true")

    intelligent_parser = subparsers.add_parser("intelligent-cold-init")
    intelligent_parser.add_argument("--db", required=True)
    intelligent_parser.add_argument("--output-dir", required=True)
    intelligent_parser.add_argument("--request", required=True)
    intelligent_parser.add_argument("--company-name", required=True)
    intelligent_parser.add_argument("--ticker")
    intelligent_parser.add_argument("--page-text-file")
    intelligent_parser.add_argument("--news-limit", type=int, default=3)
    intelligent_parser.add_argument(
        "--discovery-provider",
        choices=("static", "naver-browser"),
        default="static",
    )
    intelligent_parser.add_argument(
        "--synthesizer",
        choices=("agent-json", "codex", "fake-naver-stock"),
        default="agent-json",
    )
    intelligent_parser.add_argument("--workflow-json-file")
    intelligent_parser.add_argument("--synthesizer-model", default=DEFAULT_CODEX_SYNTHESIS_MODEL)
    intelligent_parser.add_argument("--headed", action="store_true")

    args = parser.parse_args()
    if args.command == "run":
        run(args)
    elif args.command == "run-version":
        run_version(args)
    elif args.command == "propose-update":
        propose_update(args)
    elif args.command == "apply-proposal":
        apply_proposal(args)
    elif args.command == "cold-init":
        cold_init(args)
    elif args.command == "intelligent-cold-init":
        intelligent_cold_init(args)


def run(args: argparse.Namespace) -> None:
    store = WorkflowSkillStore(args.db)
    store.initialize()
    seed_naver_stock_report(store)

    loader = WorkflowSkillLoader(store)
    candidates = loader.search(args.request)
    if not candidates:
        raise SystemExit(f"no WebMCP workflow matched request: {args.request}")

    skill = loader.load_skill(candidates[0]["id"])
    page_text, page_text_evidence = resolve_run_page_text(args)
    executor = WorkflowExecutor(store, output_dir=args.output_dir)
    result = executor.run(
        skill,
        user_request=args.request,
        arguments={
            "company_name": args.company_name,
            "ticker": args.ticker,
            "page_text": page_text,
            "news_limit": args.news_limit,
        },
    )
    print(
        json.dumps(
            {
                "workflow": skill.name,
                "workflow_version": skill.version,
                "run_id": result.run_id,
                "status": result.status,
                "llm_used": result.llm_used,
                "page_text_evidence": page_text_evidence,
                "output": result.output,
                "report_path": result.report_path,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


def run_version(args: argparse.Namespace) -> None:
    store = WorkflowSkillStore(args.db)
    store.initialize()
    seed_naver_stock_report(store)

    loader = WorkflowSkillLoader(store)
    skill = loader.load_skill_version(args.workflow_name, args.version)
    page_text, page_text_evidence = resolve_run_page_text(args)
    executor = WorkflowExecutor(store, output_dir=args.output_dir)
    result = executor.run(
        skill,
        user_request=args.request,
        arguments={
            "company_name": args.company_name,
            "ticker": args.ticker,
            "page_text": page_text,
            "news_limit": args.news_limit,
        },
    )
    print(
        json.dumps(
            {
                "workflow": skill.name,
                "workflow_version": skill.version,
                "run_id": result.run_id,
                "status": result.status,
                "llm_used": result.llm_used,
                "page_text_evidence": page_text_evidence,
                "output": result.output,
                "report_path": result.report_path,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


def propose_update(args: argparse.Namespace) -> None:
    store = WorkflowSkillStore(args.db)
    store.initialize()
    seed_naver_stock_report(store)
    if args.discovery_provider == "webwright":
        if not args.output_dir:
            raise SystemExit("--output-dir is required with --discovery-provider webwright")
        trace = NaverBrowserTraceCollector(output_dir=args.output_dir, headed=args.headed).collect(
            args.instruction,
            {
                "company_name": args.company_name or "삼성전자",
                "ticker": args.ticker,
            },
        )
        page_text = trace.page_text
        discovery_provider = trace.provider
    else:
        page_text = Path(args.page_text_file).read_text(encoding="utf-8") if args.page_text_file else ""
        discovery_provider = args.discovery_provider
    loader = WorkflowSkillLoader(store)
    base_skill = loader.load_skill_version(args.workflow_name, args.base_version)
    base_workflow = workflow_json_from_skill(store, base_skill)
    backend = backend_from_name(
        args.synthesizer,
        workflow_json_file=args.workflow_json_file,
        base_workflow_json=base_workflow,
        cwd=Path(__file__).resolve().parents[1],
    )
    result = WorkflowUpdateProposalService(
        store,
        backend=backend,
        model=args.synthesizer_model,
        cwd=Path(__file__).resolve().parents[1],
    ).propose(
        workflow_name=args.workflow_name,
        base_version=args.base_version,
        instruction=args.instruction,
        page_text=page_text,
        discovery_provider=discovery_provider,
    )
    print(
        json.dumps(
            {
                "proposal_id": result.proposal_id,
                "workflow": result.workflow_name,
                "base_version": result.base_version,
                "proposed_version": result.proposed_version,
                "status": result.status,
                "synthesizer": args.synthesizer,
                "synthesizer_model": args.synthesizer_model,
                "synthesis_duration_ms": result.synthesis_duration_ms,
                "diff": result.diff,
                "proposed_workflow_json": result.proposed_workflow_json,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


def apply_proposal(args: argparse.Namespace) -> None:
    store = WorkflowSkillStore(args.db)
    store.initialize()
    result = WorkflowUpdateProposalService(store).apply(
        proposal_id=args.proposal_id,
        approved_by=args.approved_by,
    )
    print(
        json.dumps(
            {
                "proposal_id": result.proposal_id,
                "workflow": result.workflow_name,
                "status": result.status,
                "applied_version": result.applied_version,
                "applied_version_id": result.applied_version_id,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


def resolve_run_page_text(args: argparse.Namespace) -> tuple[str, dict]:
    if getattr(args, "live_page_text", False) or not getattr(args, "page_text_file", None):
        trace = NaverBrowserTraceCollector(output_dir=args.output_dir, headed=getattr(args, "headed", False)).collect(
            args.request,
            {
                "company_name": args.company_name,
                "ticker": args.ticker,
            },
        )
        return trace.page_text, {
            "source": "live_naver_browser",
            "provider": trace.provider,
            "final_url": trace.final_url,
            "title": trace.title,
            "screenshots": trace.screenshots,
        }

    return Path(args.page_text_file).read_text(encoding="utf-8"), {
        "source": "page_text_file",
        "path": str(args.page_text_file),
    }


def cold_init(args: argparse.Namespace) -> None:
    store = WorkflowSkillStore(args.db)
    store.initialize()
    if args.discovery_provider == "static":
        if not args.page_text_file:
            raise SystemExit("--page-text-file is required for static discovery")
        discovery_runner = StaticDiscoveryRunner(page_text=Path(args.page_text_file).read_text(encoding="utf-8"))
    else:
        discovery_runner = NaverBrowserDiscoveryRunner(output_dir=args.output_dir, headed=args.headed)
    result = ColdInitRunner(
        store,
        output_dir=args.output_dir,
        discovery_runner=discovery_runner,
    ).run(
        user_request=args.request,
        arguments={
            "company_name": args.company_name,
            "ticker": args.ticker,
            "news_limit": args.news_limit,
        },
    )
    print(
        json.dumps(
            {
                "cold_init_run_id": result.cold_init_run_id,
                "workflow": result.skill.name,
                "workflow_version": result.skill.version,
                "workflow_run_id": result.run_result.run_id,
                "status": result.run_result.status,
                "llm_used": result.run_result.llm_used,
                "discovery_duration_ms": result.discovery_duration_ms,
                "materialization_duration_ms": result.materialization_duration_ms,
                "first_run_duration_ms": result.first_run_duration_ms,
                "output": result.run_result.output,
                "report_path": result.run_result.report_path,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


def intelligent_cold_init(args: argparse.Namespace) -> None:
    store = WorkflowSkillStore(args.db)
    store.initialize()
    if args.discovery_provider == "static":
        if not args.page_text_file:
            raise SystemExit("--page-text-file is required for static discovery")
        trace_collector = StaticTraceCollector(page_text=Path(args.page_text_file).read_text(encoding="utf-8"))
    else:
        trace_collector = NaverBrowserTraceCollector(output_dir=args.output_dir, headed=args.headed)

    if args.synthesizer == "fake-naver-stock":
        backend = FakeSynthesisBackend(response=naver_stock_workflow_json())
    elif args.synthesizer == "agent-json":
        if not args.workflow_json_file:
            raise SystemExit("--workflow-json-file is required with --synthesizer agent-json")
        backend = AgentJsonSynthesisBackend(workflow_json_path=args.workflow_json_file)
    else:
        backend = None
    synthesizer = LLMWorkflowSynthesizer(backend=backend, model=args.synthesizer_model)

    result = IntelligentColdInitRunner(
        store,
        output_dir=args.output_dir,
        trace_collector=trace_collector,
        synthesizer=synthesizer,
    ).run(
        user_request=args.request,
        arguments={
            "company_name": args.company_name,
            "ticker": args.ticker,
            "news_limit": args.news_limit,
        },
    )
    print(
        json.dumps(
            {
                "mode": "intelligent_cold_init",
                "cold_init_run_id": result.cold_init_run_id,
                "synthesis_run_id": result.synthesis_run_id,
                "workflow": result.skill.name,
                "workflow_version": result.skill.version,
                "workflow_run_id": result.run_result.run_id,
                "status": result.run_result.status,
                "llm_used": result.run_result.llm_used,
                "synthesizer_provider": synthesizer.provider,
                "synthesizer_model": synthesizer.model,
                "discovery_duration_ms": result.discovery_duration_ms,
                "synthesis_duration_ms": result.synthesis_duration_ms,
                "materialization_duration_ms": result.materialization_duration_ms,
                "first_run_duration_ms": result.first_run_duration_ms,
                "output": result.run_result.output,
                "report_path": result.run_result.report_path,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
