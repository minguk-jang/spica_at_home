from __future__ import annotations

import argparse
import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from webworkflows.cli import (
    BROWSER_RUNTIME_REEXEC_ENV,
    browser_runtime_python,
    main,
    maybe_reexec_with_browser_runtime,
    resolve_db_arg,
    requires_browser_runtime,
)


class CliBrowserRuntimeTests(unittest.TestCase):
    def test_browser_create_workflow_requires_browser_runtime(self) -> None:
        args = argparse.Namespace(command="create-workflow", discovery_provider="browser", eval_and_evolve=False)

        self.assertTrue(requires_browser_runtime(args))

    def test_static_create_workflow_without_eval_does_not_require_browser_runtime(self) -> None:
        args = argparse.Namespace(command="create-workflow", discovery_provider="static", eval_and_evolve=False)

        self.assertFalse(requires_browser_runtime(args))

    def test_reexecs_with_bundled_webwright_python_when_playwright_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            core_root = Path(tmp)
            python_path = core_root / "reference" / "webwright" / ".venv" / "bin" / "python"
            python_path.parent.mkdir(parents=True)
            python_path.write_text("#!/bin/sh\n", encoding="utf-8")

            args = argparse.Namespace(command="create-workflow", discovery_provider="browser", eval_and_evolve=True)
            with (
                patch("webworkflows.cli._has_playwright", return_value=False),
                patch("webworkflows.cli.os.execve") as execve,
                patch.dict(os.environ, {}, clear=True),
                self.assertRaises(SystemExit),
            ):
                maybe_reexec_with_browser_runtime(
                    args,
                    argv=["create-workflow", "--db", "workflows.sqlite"],
                    core_root=core_root,
                )

            execve.assert_called_once()
            command, exec_args, env = execve.call_args.args
            self.assertEqual(str(python_path), command)
            self.assertEqual(
                [str(python_path), "-m", "webworkflows.cli", "create-workflow", "--db", "workflows.sqlite"],
                exec_args,
            )
            self.assertEqual("1", env[BROWSER_RUNTIME_REEXEC_ENV])

    def test_bundled_runtime_path_points_to_reference_webwright_venv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            core_root = Path(tmp)
            expected = core_root / "reference" / "webwright" / ".venv" / "bin" / "python"
            expected.parent.mkdir(parents=True)
            expected.write_text("#!/bin/sh\n", encoding="utf-8")

            self.assertEqual(expected, browser_runtime_python(core_root))

    def test_resolve_db_arg_defaults_to_webmcp_studio_db_path(self) -> None:
        args = argparse.Namespace(db=None)

        with patch.dict(os.environ, {"WEBMCP_STUDIO_DB_PATH": "/tmp/studio/workflows.sqlite"}, clear=True):
            self.assertEqual(Path("/tmp/studio/workflows.sqlite"), resolve_db_arg(args))

    def test_run_version_accepts_generic_arguments_without_stock_fields(self) -> None:
        captured: dict[str, object] = {}

        class FakeRuntime:
            def __init__(self, *_args, **_kwargs):
                pass

            def run_version(self, **kwargs):
                captured.update(kwargs)
                return {"status": "succeeded"}

        with tempfile.TemporaryDirectory() as tmp:
            argv = [
                "python",
                "run-version",
                "--db",
                str(Path(tmp) / "workflow_tools.sqlite"),
                "--output-dir",
                str(Path(tmp) / "runs"),
                "--workflow-name",
                "naver_map_transit_route",
                "--version",
                "1",
                "--request",
                "네이버 지도 지하철 소요 시간",
                "--argument",
                "start_station=양재역",
                "--argument",
                "end_station=사당역",
            ]
            with (
                patch.object(sys, "argv", argv),
                patch("webworkflows.cli.WorkflowRuntime", FakeRuntime),
                patch("webworkflows.cli.build_evaluation_loop", return_value=None),
                patch(
                    "webworkflows.cli.NaverBrowserTraceCollector",
                    side_effect=AssertionError("generic run-version should not collect stock page text"),
                ),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                main()

        arguments = captured["arguments"]
        self.assertEqual("양재역", arguments["start_station"])
        self.assertEqual("사당역", arguments["end_station"])
        self.assertNotIn("company_name", arguments)


if __name__ == "__main__":
    unittest.main()
