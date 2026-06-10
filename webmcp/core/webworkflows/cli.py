from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from webworkflows.cold_init import (
    ColdInitRunner,
    IntelligentColdInitRunner,
    NaverBrowserDiscoveryRunner,
    NaverBrowserTraceCollector,
    StaticDiscoveryRunner,
    StaticTraceCollector,
)
from webworkflows.dynamic_browser import CodexAppServerDynamicBrowserActionPlanner
from webworkflows.eval_loop import PlaywrightEvalAndEvolveLoop, WorkflowEvaluationError
from webworkflows.cold_init_types import ArtifactTrace
from webworkflows.js_tool import JsToolExporter, JsToolRuntimeError, eval_js_tool, run_js_tool
from webworkflows.page_memory import PageAnalysisStore, WorkflowKnowledgeStore, build_script_generation_knowledge
from webworkflows.seeds import seed_naver_stock_report
from webworkflows.services.update_runtime import WorkflowUpdateRuntime
from webworkflows.services.evolution_runtime import WorkflowEvolutionRuntime
from webworkflows.services.creation_runtime import (
    GenericBrowserTraceCollector,
    StaticCreationTraceCollector,
    WorkflowCreationRuntime,
)
from webworkflows.services.workflow_runtime import WorkflowRuntime
from webworkflows.synthesis import (
    AgentJsonSynthesisBackend,
    CodexAppServerSynthesisBackend,
    DEFAULT_CODEX_SYNTHESIS_MODEL,
    FakeSynthesisBackend,
    LLMWorkflowSynthesizer,
    naver_stock_workflow_json,
)
from webworkflows.storage import WorkflowSkillStore, default_studio_db_path
from webworkflows.step_guide import StepGuideSuggester, heuristic_step_guide
from webworkflows.vlm_codex import (
    CodexAppServerVisionLanguageEvaluator,
    CodexResponsesVisionLanguageEvaluator,
)

BROWSER_RUNTIME_REEXEC_ENV = "WEBMCP_BROWSER_RUNTIME_REEXECED"


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m webworkflows.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run")
    add_db_arg(run_parser)
    run_parser.add_argument("--output-dir", required=True)
    run_parser.add_argument("--request", required=True)
    run_parser.add_argument("--company-name")
    run_parser.add_argument("--ticker")
    run_parser.add_argument("--page-text-file")
    run_parser.add_argument("--news-limit", type=int, default=3)
    run_parser.add_argument("--argument", action="append", default=[])
    run_parser.add_argument("--live-page-text", action="store_true")
    run_parser.add_argument("--headed", action="store_true")
    add_eval_loop_args(run_parser)

    run_version_parser = subparsers.add_parser("run-version")
    add_db_arg(run_version_parser)
    run_version_parser.add_argument("--output-dir", required=True)
    run_version_parser.add_argument("--workflow-name", required=True)
    run_version_parser.add_argument("--version", type=int, required=True)
    run_version_parser.add_argument("--request", required=True)
    run_version_parser.add_argument("--company-name")
    run_version_parser.add_argument("--ticker")
    run_version_parser.add_argument("--page-text-file")
    run_version_parser.add_argument("--news-limit", type=int, default=3)
    run_version_parser.add_argument("--argument", action="append", default=[])
    run_version_parser.add_argument("--live-page-text", action="store_true")
    run_version_parser.add_argument("--headed", action="store_true")
    add_eval_loop_args(run_version_parser)

    propose_update_parser = subparsers.add_parser("propose-update")
    add_db_arg(propose_update_parser)
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
    add_db_arg(apply_proposal_parser)
    apply_proposal_parser.add_argument("--proposal-id", type=int, required=True)
    apply_proposal_parser.add_argument("--approved-by", default="desktop")

    cold_parser = subparsers.add_parser("cold-init")
    add_db_arg(cold_parser)
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
    add_eval_loop_args(cold_parser)

    intelligent_parser = subparsers.add_parser("intelligent-cold-init")
    add_db_arg(intelligent_parser)
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
    add_eval_loop_args(intelligent_parser)

    create_parser = subparsers.add_parser("create-workflow")
    add_db_arg(create_parser)
    create_parser.add_argument("--output-dir", required=True)
    create_parser.add_argument("--start-url", required=True)
    create_parser.add_argument("--task", required=True)
    create_parser.add_argument("--final-state", required=True)
    create_parser.add_argument("--company-name")
    create_parser.add_argument("--ticker")
    create_parser.add_argument("--news-limit", type=int)
    create_parser.add_argument("--argument", action="append", default=[])
    create_parser.add_argument("--step-guide-json")
    create_parser.add_argument("--page-text-file")
    create_parser.add_argument(
        "--discovery-provider",
        choices=("browser", "static"),
        default="browser",
    )
    create_parser.add_argument(
        "--synthesizer",
        choices=("agent-json", "codex", "fake-naver-stock"),
        default="codex",
    )
    create_parser.add_argument("--workflow-json-file")
    create_parser.add_argument("--synthesizer-model", default=DEFAULT_CODEX_SYNTHESIS_MODEL)
    create_parser.add_argument("--max-attempts", type=int, default=3)
    create_parser.add_argument(
        "--repair-synthesizer",
        choices=("codex", "agent-json", "fake-copy"),
        default="codex",
    )
    create_parser.add_argument("--headed", action="store_true")
    add_eval_loop_args(create_parser)

    suggest_steps_parser = subparsers.add_parser("suggest-step-guide")
    add_db_arg(suggest_steps_parser)
    suggest_steps_parser.add_argument("--start-url", required=True)
    suggest_steps_parser.add_argument("--task", required=True)
    suggest_steps_parser.add_argument("--final-state", required=True)
    suggest_steps_parser.add_argument(
        "--suggester",
        choices=("codex", "heuristic"),
        default="codex",
    )
    suggest_steps_parser.add_argument("--synthesizer-model", default=DEFAULT_CODEX_SYNTHESIS_MODEL)

    evolve_parser = subparsers.add_parser("evolve")
    add_db_arg(evolve_parser)
    evolve_parser.add_argument("--output-dir", required=True)
    evolve_parser.add_argument("--workflow-name", required=True)
    evolve_parser.add_argument("--base-version", type=int, required=True)
    evolve_parser.add_argument("--request", required=True)
    evolve_parser.add_argument("--company-name")
    evolve_parser.add_argument("--ticker")
    evolve_parser.add_argument("--page-text-file")
    evolve_parser.add_argument("--news-limit", type=int, default=3)
    evolve_parser.add_argument("--argument", action="append", default=[])
    evolve_parser.add_argument("--max-attempts", type=int, default=3)
    evolve_parser.add_argument(
        "--repair-synthesizer",
        choices=("agent-json", "fake-copy", "codex"),
        default="agent-json",
    )
    evolve_parser.add_argument("--repair-workflow-json-file")
    evolve_parser.add_argument("--synthesizer-model", default=DEFAULT_CODEX_SYNTHESIS_MODEL)
    evolve_parser.add_argument("--headed", action="store_true")
    add_eval_loop_args(evolve_parser)

    export_js_parser = subparsers.add_parser("export-js-tool")
    add_db_arg(export_js_parser)
    export_js_parser.add_argument("--workflow-name", required=True)
    export_js_parser.add_argument("--version", type=int, required=True)
    export_js_parser.add_argument("--output-dir", required=True)

    run_js_parser = subparsers.add_parser("run-js-tool")
    run_js_parser.add_argument("--tool-dir", required=True)
    run_js_parser.add_argument("--arguments-file")
    run_js_parser.add_argument("--argument", action="append", default=[])

    eval_js_parser = subparsers.add_parser("eval-js-tool")
    eval_js_parser.add_argument("--tool-dir", required=True)
    eval_js_parser.add_argument("--arguments-file")
    eval_js_parser.add_argument("--argument", action="append", default=[])
    eval_js_parser.add_argument("--required-output", action="append", default=[])

    args = parser.parse_args()
    maybe_reexec_with_browser_runtime(args)
    try:
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
        elif args.command == "create-workflow":
            create_workflow(args)
        elif args.command == "suggest-step-guide":
            suggest_step_guide(args)
        elif args.command == "evolve":
            evolve(args)
        elif args.command == "export-js-tool":
            export_js_tool(args)
        elif args.command == "run-js-tool":
            run_js_tool_command(args)
        elif args.command == "eval-js-tool":
            eval_js_tool_command(args)
    except WorkflowEvaluationError as exc:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error_type": "workflow_evaluation_failed",
                    "message": str(exc),
                    "evaluation": exc.report.as_dict(),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        raise SystemExit(2)
    except JsToolRuntimeError as exc:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error_type": "javascript_tool_failed",
                    "message": str(exc),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        raise SystemExit(2)


def add_eval_loop_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--eval-and-evolve", action="store_true")
    parser.add_argument(
        "--vlm-evaluator",
        choices=("codex", "openai-responses"),
        default="codex",
        help="Codex VLM evaluator backend for --eval-and-evolve.",
    )
    parser.add_argument("--vlm-model", default=DEFAULT_CODEX_SYNTHESIS_MODEL, help=argparse.SUPPRESS)
    parser.add_argument(
        "--eval-browser",
        choices=("chromium", "firefox", "webkit"),
        default="chromium",
        help="Playwright browser used by --eval-and-evolve.",
    )


def add_db_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--db",
        default=None,
        help="SQLite workflow DB path. Defaults to WEBMCP_STUDIO_DB_PATH or ~/.webmcp-studio/db/workflows.sqlite.",
    )


def resolve_db_arg(args: argparse.Namespace) -> Path:
    return Path(args.db).expanduser() if getattr(args, "db", None) else default_studio_db_path()


def requires_browser_runtime(args: argparse.Namespace) -> bool:
    if getattr(args, "eval_and_evolve", False):
        return True

    command = getattr(args, "command", "")
    if command in {"run", "run-version"}:
        return bool(getattr(args, "live_page_text", False))
    if command in {"cold-init", "intelligent-cold-init"}:
        return getattr(args, "discovery_provider", "static") == "naver-browser"
    if command == "propose-update":
        return getattr(args, "discovery_provider", "none") == "webwright"
    if command == "create-workflow":
        return getattr(args, "discovery_provider", "browser") == "browser"
    if command == "evolve":
        return True
    return False


def browser_runtime_python(core_root: Path | None = None) -> Path | None:
    root = core_root or Path(__file__).resolve().parents[1]
    scripts_dir = "Scripts" if os.name == "nt" else "bin"
    executable = "python.exe" if os.name == "nt" else "python"
    candidate = root / "reference" / "webwright" / ".venv" / scripts_dir / executable
    return candidate if candidate.exists() else None


def maybe_reexec_with_browser_runtime(
    args: argparse.Namespace,
    *,
    argv: list[str] | None = None,
    core_root: Path | None = None,
) -> None:
    if not requires_browser_runtime(args):
        return
    if _has_playwright():
        return
    if os.environ.get(BROWSER_RUNTIME_REEXEC_ENV) == "1":
        return

    python_path = browser_runtime_python(core_root)
    if python_path is None or _same_path(Path(sys.executable), python_path):
        return

    env = os.environ.copy()
    env[BROWSER_RUNTIME_REEXEC_ENV] = "1"
    exec_args = [str(python_path), "-m", "webworkflows.cli", *(argv if argv is not None else sys.argv[1:])]
    os.execve(str(python_path), exec_args, env)
    raise SystemExit(0)


def _has_playwright() -> bool:
    try:
        import playwright.async_api  # noqa: F401
    except ModuleNotFoundError:
        return False
    return True


def _same_path(left: Path, right: Path) -> bool:
    try:
        return left.resolve() == right.resolve()
    except OSError:
        return left == right


def build_evaluation_loop(args: argparse.Namespace):
    if not getattr(args, "eval_and_evolve", False):
        return None
    model = getattr(args, "vlm_model", DEFAULT_CODEX_SYNTHESIS_MODEL)
    evaluator_name = getattr(args, "vlm_evaluator", "codex")
    if evaluator_name == "openai-responses":
        evaluator = CodexResponsesVisionLanguageEvaluator(model=model)
    else:
        evaluator = CodexAppServerVisionLanguageEvaluator(
            model=model,
            cwd=Path(__file__).resolve().parents[1],
        )
    dynamic_action_planner = CodexAppServerDynamicBrowserActionPlanner(
        model=model,
        cwd=Path(__file__).resolve().parents[1],
    )
    return PlaywrightEvalAndEvolveLoop(
        evaluator=evaluator,
        headed=getattr(args, "headed", False),
        browser_name=args.eval_browser,
        dynamic_action_planner=dynamic_action_planner,
    )


def run(args: argparse.Namespace) -> None:
    store = WorkflowSkillStore(resolve_db_arg(args))
    store.initialize()
    seed_naver_stock_report(store)

    evaluation_loop = build_evaluation_loop(args)
    page_text, page_text_evidence = resolve_run_page_text(args, skip_live_browser=bool(evaluation_loop))
    arguments = _workflow_arguments(args, page_text=page_text)
    page_analysis_context = _record_observed_page_analysis(
        store,
        user_request=args.request,
        arguments=arguments,
        page_text=page_text,
        page_text_evidence=page_text_evidence,
        source="workflow_run",
    )
    payload = WorkflowRuntime(store, output_dir=args.output_dir, evaluation_loop=evaluation_loop).run_latest(
        user_request=args.request,
        arguments=arguments,
        page_text_evidence=page_text_evidence,
    )
    _record_run_knowledge(
        store,
        status=str(payload.get("status") or "unknown"),
        workflow_name=str(payload.get("workflow") or ""),
        workflow_version=payload.get("workflow_version"),
        user_request=args.request,
        arguments=arguments,
        page_text_evidence=page_text_evidence,
        payload=payload,
        page_analysis_context=page_analysis_context,
    )
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def run_version(args: argparse.Namespace) -> None:
    store = WorkflowSkillStore(resolve_db_arg(args))
    store.initialize()
    seed_naver_stock_report(store)

    evaluation_loop = build_evaluation_loop(args)
    page_text, page_text_evidence = resolve_run_page_text(args, skip_live_browser=bool(evaluation_loop))
    arguments = _workflow_arguments(args, page_text=page_text)
    page_analysis_context = _record_observed_page_analysis(
        store,
        user_request=args.request,
        arguments=arguments,
        page_text=page_text,
        page_text_evidence=page_text_evidence,
        source="workflow_run_version",
    )
    payload = WorkflowRuntime(store, output_dir=args.output_dir, evaluation_loop=evaluation_loop).run_version(
        workflow_name=args.workflow_name,
        version=args.version,
        user_request=args.request,
        arguments=arguments,
        page_text_evidence=page_text_evidence,
    )
    _record_run_knowledge(
        store,
        status=str(payload.get("status") or "unknown"),
        workflow_name=str(payload.get("workflow") or args.workflow_name),
        workflow_version=payload.get("workflow_version"),
        user_request=args.request,
        arguments=arguments,
        page_text_evidence=page_text_evidence,
        payload=payload,
        page_analysis_context=page_analysis_context,
    )
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def propose_update(args: argparse.Namespace) -> None:
    store = WorkflowSkillStore(resolve_db_arg(args))
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
    payload = WorkflowUpdateRuntime(store, cwd=Path(__file__).resolve().parents[1]).propose_update(
        workflow_name=args.workflow_name,
        base_version=args.base_version,
        instruction=args.instruction,
        page_text=page_text,
        discovery_provider=discovery_provider,
        synthesizer=args.synthesizer,
        workflow_json_file=args.workflow_json_file,
        synthesizer_model=args.synthesizer_model,
    )
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def apply_proposal(args: argparse.Namespace) -> None:
    store = WorkflowSkillStore(resolve_db_arg(args))
    store.initialize()
    payload = WorkflowUpdateRuntime(store).apply_proposal(
        proposal_id=args.proposal_id,
        approved_by=args.approved_by,
    )
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def resolve_run_page_text(args: argparse.Namespace, *, skip_live_browser: bool = False) -> tuple[str, dict]:
    if skip_live_browser:
        if getattr(args, "page_text_file", None):
            return Path(args.page_text_file).read_text(encoding="utf-8"), {
                "source": "page_text_file",
                "path": str(args.page_text_file),
                "eval_and_evolve": True,
            }
        return "", {
            "source": "eval_and_evolve_browser",
            "provider": "playwright_vlm_monitor",
        }
    if getattr(args, "live_page_text", False):
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

    if getattr(args, "page_text_file", None):
        return Path(args.page_text_file).read_text(encoding="utf-8"), {
            "source": "page_text_file",
            "path": str(args.page_text_file),
        }

    return "", {"source": "not_required"}


def cold_init(args: argparse.Namespace) -> None:
    store = WorkflowSkillStore(resolve_db_arg(args))
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
        evaluation_loop=build_evaluation_loop(args),
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
    store = WorkflowSkillStore(resolve_db_arg(args))
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
        backend = CodexAppServerSynthesisBackend(cwd=Path(__file__).resolve().parents[1])
    synthesizer = LLMWorkflowSynthesizer(backend=backend, model=args.synthesizer_model)

    result = IntelligentColdInitRunner(
        store,
        output_dir=args.output_dir,
        trace_collector=trace_collector,
        synthesizer=synthesizer,
        evaluation_loop=build_evaluation_loop(args),
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


def create_workflow(args: argparse.Namespace) -> None:
    store = WorkflowSkillStore(resolve_db_arg(args))
    store.initialize()
    if args.discovery_provider == "static":
        if not args.page_text_file:
            raise SystemExit("--page-text-file is required for static workflow creation")
        trace_collector = StaticCreationTraceCollector(
            page_text=Path(args.page_text_file).read_text(encoding="utf-8"),
            final_url=args.start_url,
        )
    else:
        trace_collector = GenericBrowserTraceCollector(output_dir=args.output_dir, headed=args.headed)

    if args.synthesizer == "fake-naver-stock":
        backend = FakeSynthesisBackend(response=naver_stock_workflow_json())
    elif args.synthesizer == "agent-json":
        if not args.workflow_json_file:
            raise SystemExit("--workflow-json-file is required with --synthesizer agent-json")
        backend = AgentJsonSynthesisBackend(workflow_json_path=args.workflow_json_file)
    else:
        backend = CodexAppServerSynthesisBackend(cwd=Path(__file__).resolve().parents[1])
    synthesizer = LLMWorkflowSynthesizer(backend=backend, model=args.synthesizer_model)
    arguments = _creation_arguments(args)

    payload = WorkflowCreationRuntime(
        store,
        output_dir=args.output_dir,
        trace_collector=trace_collector,
        synthesizer=synthesizer,
        evaluation_loop=build_evaluation_loop(args),
        cwd=Path(__file__).resolve().parents[1],
    ).create(
        start_url=args.start_url,
        user_task=args.task,
        final_state=args.final_state,
        arguments=arguments,
        max_attempts=args.max_attempts,
        repair_synthesizer=args.repair_synthesizer,
        synthesizer_model=args.synthesizer_model,
    )
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def suggest_step_guide(args: argparse.Namespace) -> None:
    store = WorkflowSkillStore(resolve_db_arg(args))
    store.initialize()
    page = PageAnalysisStore(store).lookup(args.start_url)
    page_context = page.as_context() if page else {}
    knowledge_context = [
        entry.as_context()
        for entry in WorkflowKnowledgeStore(store).recent(category="script_generation", limit=5)
    ]
    provider = args.suggester
    model = args.synthesizer_model
    error: dict[str, str] | None = None

    if args.suggester == "heuristic":
        step_guide = heuristic_step_guide(
            start_url=args.start_url,
            task=args.task,
            final_state=args.final_state,
        )
    else:
        suggester: StepGuideSuggester | None = None
        try:
            suggester = StepGuideSuggester(
                cwd=Path(__file__).resolve().parents[1],
                model=model,
            )
            suggestion = suggester.suggest(
                start_url=args.start_url,
                task=args.task,
                final_state=args.final_state,
                page_analysis_context=page_context,
                knowledge_context=knowledge_context,
            )
            provider = suggestion.provider
            step_guide = suggestion.step_guide
        except Exception as exc:
            provider = "heuristic_fallback"
            error = {"type": type(exc).__name__, "message": str(exc)}
            step_guide = heuristic_step_guide(
                start_url=args.start_url,
                task=args.task,
                final_state=args.final_state,
            )
        finally:
            if suggester is not None:
                suggester.close()

    print(
        json.dumps(
            {
                "status": "succeeded",
                "provider": provider,
                "model": model,
                "step_guide": step_guide,
                "page_analysis_used": bool(page_context),
                "knowledge_entries_used": len(knowledge_context),
                **({"error": error} if error else {}),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


def _creation_arguments(args: argparse.Namespace) -> dict[str, object]:
    arguments = _workflow_arguments(args)
    step_guide = _parse_step_guide_json(getattr(args, "step_guide_json", None))
    if step_guide:
        arguments["step_guide"] = step_guide
    return arguments


def _parse_step_guide_json(raw: str | None) -> list[dict[str, str]]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"--step-guide-json must be valid JSON: {exc}") from exc
    if not isinstance(parsed, list):
        raise SystemExit("--step-guide-json must be a JSON array")

    guide: list[dict[str, str]] = []
    for index, item in enumerate(parsed):
        if not isinstance(item, dict):
            raise SystemExit("--step-guide-json items must be objects")
        name = str(item.get("name") or "").strip()
        description = str(item.get("description") or "").strip()
        step_type = str(item.get("step_type") or item.get("stepType") or "").strip()
        if not name and not description:
            continue
        guide.append(
            {
                "name": name or f"step_{index + 1}",
                "description": description,
                "step_type": step_type or "click",
            }
        )
    return guide


def _workflow_arguments(args: argparse.Namespace, *, page_text: str | None = None) -> dict[str, object]:
    arguments: dict[str, object] = {}
    for item in getattr(args, "argument", []):
        if "=" not in item:
            raise SystemExit(f"--argument must be name=value, got: {item}")
        key, value = item.split("=", 1)
        if not key.strip():
            raise SystemExit(f"--argument key is empty: {item}")
        arguments[key.strip()] = value
    if getattr(args, "company_name", None):
        arguments["company_name"] = args.company_name
    if getattr(args, "ticker", None):
        arguments["ticker"] = args.ticker
    if getattr(args, "news_limit", None) is not None:
        arguments["news_limit"] = args.news_limit
    if page_text is not None:
        arguments["page_text"] = page_text
    return arguments


def _record_observed_page_analysis(
    store: WorkflowSkillStore,
    *,
    user_request: str,
    arguments: dict[str, object],
    page_text: str,
    page_text_evidence: dict,
    source: str,
) -> dict[str, object] | None:
    if not page_text:
        return None
    final_url = str(page_text_evidence.get("final_url") or arguments.get("start_url") or "")
    if not final_url:
        return None
    trace = ArtifactTrace(
        provider=str(page_text_evidence.get("provider") or page_text_evidence.get("source") or source),
        user_request=user_request,
        arguments=dict(arguments),
        page_text=page_text,
        title=str(page_text_evidence.get("title") or ""),
        final_url=final_url,
        screenshots=list(page_text_evidence.get("screenshots") or []),
    )
    return PageAnalysisStore(store).upsert_from_trace(trace, source=source).as_context()


def _record_run_knowledge(
    store: WorkflowSkillStore,
    *,
    status: str,
    workflow_name: str,
    workflow_version: object,
    user_request: str,
    arguments: dict[str, object],
    page_text_evidence: dict,
    payload: dict,
    page_analysis_context: dict[str, object] | None,
) -> None:
    if not page_analysis_context:
        return
    output = payload.get("output") if isinstance(payload.get("output"), dict) else {}
    knowledge = build_script_generation_knowledge(
        status=status,
        workflow_name=workflow_name,
        workflow_version=int(workflow_version) if isinstance(workflow_version, int) else None,
        start_url=str(page_text_evidence.get("final_url") or arguments.get("start_url") or ""),
        user_task=user_request,
        final_state="Observed workflow run completed with live/static page text evidence.",
        output_keys=sorted(output.keys()),
        page_analysis=page_analysis_context.get("analysis") if page_analysis_context else None,
        error=output.get("error") if isinstance(output.get("error"), dict) else None,
    )
    knowledge["source"] = "workflow_run"
    knowledge["tags"] = [
        *[tag for tag in knowledge["tags"] if tag != "workflow_creation"],
        "workflow_run",
        "run_memory",
    ]
    WorkflowKnowledgeStore(store).append(**knowledge)


def evolve(args: argparse.Namespace) -> None:
    store = WorkflowSkillStore(resolve_db_arg(args))
    store.initialize()
    seed_naver_stock_report(store)
    page_text = Path(args.page_text_file).read_text(encoding="utf-8") if args.page_text_file else ""
    args.eval_and_evolve = True
    payload = WorkflowEvolutionRuntime(
        store,
        output_dir=args.output_dir,
        evaluation_loop=build_evaluation_loop(args),
        cwd=Path(__file__).resolve().parents[1],
    ).evolve(
        workflow_name=args.workflow_name,
        base_version=args.base_version,
        user_request=args.request,
        arguments=_workflow_arguments(args, page_text=page_text),
        max_attempts=args.max_attempts,
        repair_synthesizer=args.repair_synthesizer,
        repair_workflow_json_file=args.repair_workflow_json_file,
        synthesizer_model=args.synthesizer_model,
    )
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def export_js_tool(args: argparse.Namespace) -> None:
    store = WorkflowSkillStore(resolve_db_arg(args))
    store.initialize()
    exported = JsToolExporter(store).export(
        workflow_name=args.workflow_name,
        version=args.version,
        output_dir=args.output_dir,
    )
    payload = {
        "status": "succeeded",
        "tool_dir": str(exported.tool_dir),
        "manifest": exported.manifest,
        "files": {
            "manifest": str(exported.tool_dir / "manifest.json"),
            "workflow": str(exported.tool_dir / "workflow.json"),
            "entrypoint": str(exported.tool_dir / "tool.cjs"),
        },
    }
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def run_js_tool_command(args: argparse.Namespace) -> None:
    payload = run_js_tool(args.tool_dir, _json_tool_arguments(args))
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def eval_js_tool_command(args: argparse.Namespace) -> None:
    payload = eval_js_tool(
        args.tool_dir,
        _json_tool_arguments(args),
        required_output=list(args.required_output or []),
    )
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _json_tool_arguments(args: argparse.Namespace) -> dict[str, Any]:
    arguments: dict[str, Any] = {}
    if getattr(args, "arguments_file", None):
        arguments.update(json.loads(Path(args.arguments_file).read_text(encoding="utf-8")))
    for item in getattr(args, "argument", []):
        if "=" not in item:
            raise SystemExit(f"--argument must be name=value, got: {item}")
        key, value = item.split("=", 1)
        if not key.strip():
            raise SystemExit(f"--argument key is empty: {item}")
        arguments[key.strip()] = value
    return arguments


if __name__ == "__main__":
    main()
