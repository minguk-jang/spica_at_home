from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


CORE_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = CORE_DIR.parent
OUTPUTS_DIR = CORE_DIR / "outputs"


@dataclass(frozen=True)
class Suite:
    name: str
    script: Path
    output_dir: Path
    results_file: Path
    summary_file: Path
    env: dict[str, str]


SUITES = {
    "baseline": Suite(
        name="baseline",
        script=OUTPUTS_DIR / "ablation_study_20260610" / "run_ablation.py",
        output_dir=OUTPUTS_DIR / "ablation_study_20260610",
        results_file=OUTPUTS_DIR / "ablation_study_20260610" / "results.json",
        summary_file=OUTPUTS_DIR / "ablation_study_20260610" / "summary.md",
        env={"WEBMCP_ABLATION_REPEATS": "3"},
    ),
    "harder": Suite(
        name="harder",
        script=OUTPUTS_DIR / "ablation_harder_20260610" / "run_harder_ablation.py",
        output_dir=OUTPUTS_DIR / "ablation_harder_20260610",
        results_file=OUTPUTS_DIR / "ablation_harder_20260610" / "results.json",
        summary_file=OUTPUTS_DIR / "ablation_harder_20260610" / "summary.md",
        env={"WEBMCP_HARDER_ABLATION_REPEATS": "2"},
    ),
    "memory": Suite(
        name="memory",
        script=OUTPUTS_DIR / "ablation_memory_20260610" / "run_memory_ablation.py",
        output_dir=OUTPUTS_DIR / "ablation_memory_20260610",
        results_file=OUTPUTS_DIR / "ablation_memory_20260610" / "results.json",
        summary_file=OUTPUTS_DIR / "ablation_memory_20260610" / "summary.md",
        env={},
    ),
}


def main() -> None:
    args = parse_args()
    suites = select_suites(args.suite)
    python = resolve_python(args.python)
    run_id = time.strftime("%Y%m%d_%H%M%S")
    aggregate_dir = Path(args.aggregate_dir).expanduser() if args.aggregate_dir else OUTPUTS_DIR / "ablation_latest"
    aggregate_dir.mkdir(parents=True, exist_ok=True)

    suite_results: list[dict[str, Any]] = []
    for suite in suites:
        started = time.perf_counter()
        status = "skipped"
        error = ""
        if args.skip_run:
            print(f"[ablation] summarizing existing {suite.name} results")
        else:
            print(f"[ablation] running {suite.name}: {suite.script}")
            try:
                ensure_suite_exists(suite)
                run_suite(suite, python=python, quick=args.quick)
                status = "succeeded"
            except Exception as exc:
                status = "failed"
                error = f"{type(exc).__name__}: {exc}"
                print(f"[ablation] {suite.name} failed: {error}", file=sys.stderr)
                if not args.continue_on_error:
                    suite_results.append(suite_record(suite, status, error, elapsed_ms(started), aggregate_dir))
                    write_aggregate(suite_results, aggregate_dir=aggregate_dir, run_id=run_id, suites=suites)
                    raise SystemExit(1)
        if args.skip_run:
            status = "succeeded" if suite.results_file.exists() else "failed"
            error = "" if suite.results_file.exists() else f"missing results file: {suite.results_file}"
        suite_results.append(suite_record(suite, status, error, elapsed_ms(started), aggregate_dir))

    write_aggregate(suite_results, aggregate_dir=aggregate_dir, run_id=run_id, suites=suites)
    print(f"[ablation] aggregate summary: {aggregate_dir / 'consolidated_summary.md'}")
    print(f"[ablation] aggregate json: {aggregate_dir / 'consolidated_results.json'}")

    if any(result["status"] != "succeeded" for result in suite_results):
        raise SystemExit(1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the fixed WebMCP ablation study suites and build one consolidated summary.",
    )
    parser.add_argument(
        "--suite",
        choices=("all", "fast", "baseline", "harder", "memory"),
        default="all",
        help="all=baseline+harder+memory, fast=harder+memory.",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Use lower repeat counts where the underlying suite supports it.",
    )
    parser.add_argument(
        "--skip-run",
        action="store_true",
        help="Do not execute suites; only consolidate existing results.",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue to later suites if one suite fails.",
    )
    parser.add_argument(
        "--aggregate-dir",
        help="Directory for consolidated summary artifacts. Defaults to core/outputs/ablation_latest.",
    )
    parser.add_argument(
        "--python",
        help="Python interpreter to use. Defaults to core/reference/webwright/.venv/bin/python when present.",
    )
    return parser.parse_args()


def select_suites(name: str) -> list[Suite]:
    if name == "all":
        return [SUITES["baseline"], SUITES["harder"], SUITES["memory"]]
    if name == "fast":
        return [SUITES["harder"], SUITES["memory"]]
    return [SUITES[name]]


def resolve_python(raw: str | None) -> Path:
    if raw:
        return Path(raw).expanduser()
    candidate = CORE_DIR / "reference" / "webwright" / ".venv" / ("Scripts" if os.name == "nt" else "bin") / (
        "python.exe" if os.name == "nt" else "python"
    )
    return candidate if candidate.exists() else Path(sys.executable)


def ensure_suite_exists(suite: Suite) -> None:
    if not suite.script.exists():
        raise FileNotFoundError(
            f"{suite.script} is missing. Recreate the ablation harness under {suite.output_dir} before running."
        )


def run_suite(suite: Suite, *, python: Path, quick: bool) -> None:
    env = os.environ.copy()
    env.update(suite.env)
    if quick:
        if suite.name == "baseline":
            env["WEBMCP_ABLATION_REPEATS"] = "1"
        elif suite.name == "harder":
            env["WEBMCP_HARDER_ABLATION_REPEATS"] = "1"

    completed = subprocess.run(
        [str(python), str(suite.script)],
        cwd=str(REPO_DIR),
        env=env,
        text=True,
        capture_output=True,
    )
    if completed.stdout:
        print(completed.stdout.rstrip())
    if completed.stderr:
        print(completed.stderr.rstrip(), file=sys.stderr)
    if completed.returncode != 0:
        raise RuntimeError(f"{suite.name} exited with {completed.returncode}")
    if not suite.results_file.exists():
        raise FileNotFoundError(f"{suite.name} did not write {suite.results_file}")


def suite_record(
    suite: Suite,
    status: str,
    error: str,
    duration_ms: int,
    aggregate_dir: Path,
) -> dict[str, Any]:
    copied: dict[str, str] = {}
    if suite.results_file.exists():
        target = aggregate_dir / f"{suite.name}_results.json"
        shutil.copy2(suite.results_file, target)
        copied["results"] = str(target)
    if suite.summary_file.exists():
        target = aggregate_dir / f"{suite.name}_summary.md"
        shutil.copy2(suite.summary_file, target)
        copied["summary"] = str(target)

    payload = load_json(suite.results_file) if suite.results_file.exists() else {}
    return {
        "suite": suite.name,
        "status": status,
        "error": error,
        "duration_ms": duration_ms,
        "script": str(suite.script),
        "source_results": str(suite.results_file),
        "copied": copied,
        "groups": normalize_groups(suite.name, payload),
    }


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_groups(suite_name: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for group in payload.get("groups", []):
        condition = str(group.get("mode") or group.get("memory_mode") or "")
        row = {
            "suite": suite_name,
            "example": group.get("example"),
            "condition": condition,
            "workflow_kind": group.get("workflow_kind", ""),
            "n": group.get("n"),
            "successes": group.get("successes"),
            "success_rate": group.get("success_rate"),
            "wall_ms_mean": group.get("wall_ms_mean"),
            "wall_ms_median": group.get("wall_ms_median"),
            "core_duration_ms_mean": group.get("core_duration_ms_mean"),
        }
        rows.append(row)
    return rows


def write_aggregate(
    suite_results: list[dict[str, Any]],
    *,
    aggregate_dir: Path,
    run_id: str,
    suites: list[Suite],
) -> None:
    all_groups = [group for result in suite_results for group in result.get("groups", [])]
    payload = {
        "run_id": run_id,
        "repo": str(REPO_DIR),
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S %z"),
        "suite_order": [suite.name for suite in suites],
        "suite_results": suite_results,
        "groups": all_groups,
    }
    (aggregate_dir / "consolidated_results.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (aggregate_dir / "consolidated_summary.md").write_text(render_markdown(payload), encoding="utf-8")


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# WebMCP Ablation Studies Consolidated Summary",
        "",
        f"- Run ID: `{payload['run_id']}`",
        f"- Generated at: {payload['generated_at']}",
        f"- Repo: `{payload['repo']}`",
        "",
        "## Suite Status",
        "",
        "| Suite | Status | Duration ms | Results |",
        "|---|---|---:|---|",
    ]
    for result in payload["suite_results"]:
        copied = result.get("copied", {})
        result_path = copied.get("results", result.get("source_results", ""))
        lines.append(f"| {result['suite']} | {result['status']} | {result['duration_ms']} | `{result_path}` |")
        if result.get("error"):
            lines.append(f"| {result['suite']} error | `{result['error']}` |  |  |")

    lines.extend(
        [
            "",
            "## Groups",
            "",
            "| Suite | Example | Condition | Workflow kind | n | Success | Wall mean ms | Wall median ms |",
            "|---|---|---|---|---:|---:|---:|---:|",
        ]
    )
    for group in payload["groups"]:
        success = f"{group.get('successes')}/{group.get('n')} ({float(group.get('success_rate') or 0):.0%})"
        lines.append(
            f"| {group.get('suite')} | {group.get('example')} | {group.get('condition')} | "
            f"{group.get('workflow_kind', '')} | {group.get('n')} | {success} | "
            f"{group.get('wall_ms_mean')} | {group.get('wall_ms_median')} |"
        )
    lines.append("")
    return "\n".join(lines)


def elapsed_ms(started: float) -> int:
    return max(0, int(round((time.perf_counter() - started) * 1000)))


if __name__ == "__main__":
    main()
