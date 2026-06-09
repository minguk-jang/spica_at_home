from __future__ import annotations

import base64
import json
import mimetypes
import os
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

from webworkflows.eval_loop import EvaluationSnapshot, StepEvaluation


CODEX_VLM_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "status",
        "summary",
        "problems",
        "suggested_update",
        "failure_kind",
        "expected_state",
        "observed_state",
        "repair_focus",
        "evidence_artifacts",
    ],
    "properties": {
        "status": {"type": "string", "enum": ["passed", "failed"]},
        "summary": {"type": "string"},
        "problems": {"type": "array", "items": {"type": "string"}},
        "suggested_update": {"type": "string"},
        "failure_kind": {"type": "string"},
        "expected_state": {"type": "string"},
        "observed_state": {"type": "string"},
        "repair_focus": {"type": "string"},
        "evidence_artifacts": {"type": "array", "items": {"type": "string"}},
    },
}


class CodexAppServerVisionLanguageEvaluator:
    name = "codex_app_server"

    def __init__(
        self,
        *,
        model: str = "gpt-5.5",
        cwd: str | Path | None = None,
        timeout_seconds: int = 180,
        app_server: Any | None = None,
    ):
        self.model = model
        self.cwd = Path(cwd) if cwd else None
        self.timeout_seconds = timeout_seconds
        self.app_server = app_server or CodexAppServerJsonRpcClient(
            cwd=self.cwd,
            timeout_seconds=timeout_seconds,
        )

    def evaluate(self, snapshot: EvaluationSnapshot, criteria: dict[str, Any]) -> StepEvaluation:
        image_paths = _snapshot_image_paths(snapshot.screenshot_path, cwd=self.cwd)
        result = self.app_server.run_turn(
            prompt=_build_codex_vlm_prompt(snapshot, criteria),
            output_schema=CODEX_VLM_RESPONSE_SCHEMA,
            image_paths=image_paths,
            model=self.model,
        )
        parsed = json.loads(_extract_json(str(result.get("text") or "")))
        return _step_evaluation_from_model_json(
            parsed,
            snapshot,
            criteria,
            evaluator_name=self.name,
            model=self.model,
            evidence_extra={
                "codex_thread_id": result.get("thread_id", ""),
                "codex_turn_id": result.get("turn_id", ""),
            },
        )

    def close(self) -> None:
        close = getattr(self.app_server, "close", None)
        if callable(close):
            close()


class CodexAppServerJsonRpcClient:
    def __init__(
        self,
        *,
        codex_bin: str = "codex",
        cwd: str | Path | None = None,
        timeout_seconds: int = 180,
    ):
        self.codex_bin = codex_bin
        self.cwd = Path(cwd) if cwd else Path(tempfile.gettempdir())
        self.timeout_seconds = timeout_seconds
        self.process: subprocess.Popen[str] | None = None
        self._next_id = 1

    def run_turn(
        self,
        *,
        prompt: str,
        output_schema: dict[str, Any],
        image_paths: list[Path],
        model: str,
    ) -> dict[str, str]:
        self._ensure_started()
        thread_id = self._start_thread(model=model)
        turn_response_id = self._send_request(
            "turn/start",
            {
                "threadId": thread_id,
                "input": _app_server_user_input(prompt=prompt, image_paths=image_paths),
                "model": model,
                "approvalPolicy": "never",
                "sandboxPolicy": {"type": "readOnly", "networkAccess": False},
                "outputSchema": output_schema,
            },
        )
        turn_result, events = self._read_response(turn_response_id, timeout_seconds=30)
        turn_id = str(((turn_result.get("turn") or {}).get("id")) or "")
        final_text = _agent_message_text(events, thread_id=thread_id, turn_id=turn_id)
        completed = _turn_completed(events, thread_id=thread_id, turn_id=turn_id)
        if completed:
            return {"text": final_text, "thread_id": thread_id, "turn_id": turn_id}

        deadline = time.time() + self.timeout_seconds
        while time.time() < deadline:
            message = self._read_message(deadline)
            if _is_request(message):
                self._send_error(str(message["id"]), code=-32601, message="WebMCP VLM evaluator does not handle requests")
                continue
            if message.get("method") == "item/completed":
                text = _agent_message_text([message], thread_id=thread_id, turn_id=turn_id)
                if text:
                    final_text = text
            if message.get("method") == "turn/completed":
                params = message.get("params") or {}
                turn = params.get("turn") or {}
                if params.get("threadId") == thread_id and turn.get("id") == turn_id:
                    if turn.get("status") != "completed":
                        raise RuntimeError(f"Codex app-server VLM turn failed: {json.dumps(turn)[:1000]}")
                    if not final_text.strip():
                        raise RuntimeError("Codex app-server VLM turn completed without an agent message.")
                    return {"text": final_text, "thread_id": thread_id, "turn_id": turn_id}
        raise TimeoutError("Timed out waiting for Codex app-server VLM turn to complete.")

    def close(self) -> None:
        process = self.process
        self.process = None
        if not process:
            return
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)

    def _ensure_started(self) -> None:
        if self.process and self.process.poll() is None:
            return
        self.process = subprocess.Popen(
            [self.codex_bin, "app-server", "--stdio"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
            cwd=str(self.cwd),
        )
        initialize_id = self._send_request(
            "initialize",
            {
                "clientInfo": {
                    "name": "webmcp-core-vlm",
                    "title": "WebMCP Core VLM",
                    "version": "0.1.0",
                },
                "capabilities": {
                    "experimentalApi": True,
                    "requestAttestation": False,
                    "optOutNotificationMethods": [
                        "item/agentMessage/delta",
                        "item/plan/delta",
                        "item/reasoning/textDelta",
                        "item/reasoning/summaryTextDelta",
                    ],
                },
            },
        )
        self._read_response(initialize_id, timeout_seconds=20)
        self._send_notification("initialized")

    def _start_thread(self, *, model: str) -> str:
        response_id = self._send_request(
            "thread/start",
            {
                "model": model,
                "cwd": str(self.cwd),
                "approvalPolicy": "never",
                "sandbox": "read-only",
                "ephemeral": True,
                "baseInstructions": (
                    "You are only a JSON evaluator for browser workflow evidence. "
                    "Do not use tools, shell commands, file reads, skills, web, or repo context."
                ),
                "developerInstructions": (
                    "Evaluate only the user-provided text and image inputs. "
                    "Return only JSON matching the provided schema."
                ),
                "config": {
                    "model_verbosity": "low",
                    "model_reasoning_summary": "none",
                },
            },
        )
        result, _events = self._read_response(response_id, timeout_seconds=30)
        thread_id = str(((result.get("thread") or {}).get("id")) or "")
        if not thread_id:
            raise RuntimeError(f"Codex app-server did not return a thread id: {json.dumps(result)[:1000]}")
        return thread_id

    def _send_request(self, method: str, params: dict[str, Any]) -> str:
        request_id = str(self._next_id)
        self._next_id += 1
        self._write_message({"id": request_id, "method": method, "params": params})
        return request_id

    def _send_notification(self, method: str, params: dict[str, Any] | None = None) -> None:
        message: dict[str, Any] = {"method": method}
        if params is not None:
            message["params"] = params
        self._write_message(message)

    def _send_error(self, request_id: str, *, code: int, message: str) -> None:
        self._write_message({"id": request_id, "error": {"code": code, "message": message}})

    def _write_message(self, message: dict[str, Any]) -> None:
        if not self.process or not self.process.stdin:
            raise RuntimeError("Codex app-server process is not running.")
        self.process.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
        self.process.stdin.flush()

    def _read_response(self, request_id: str, *, timeout_seconds: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        deadline = time.time() + timeout_seconds
        events: list[dict[str, Any]] = []
        while time.time() < deadline:
            message = self._read_message(deadline)
            if message.get("id") == request_id:
                if "error" in message:
                    raise RuntimeError(f"Codex app-server request failed: {json.dumps(message['error'])[:1000]}")
                return message.get("result") or {}, events
            events.append(message)
        raise TimeoutError(f"Timed out waiting for Codex app-server response to {request_id}.")

    def _read_message(self, deadline: float) -> dict[str, Any]:
        if not self.process or not self.process.stdout:
            raise RuntimeError("Codex app-server process is not running.")
        if time.time() >= deadline:
            raise TimeoutError("Timed out waiting for Codex app-server message.")
        line = self.process.stdout.readline()
        if not line:
            raise RuntimeError("Codex app-server closed stdout.")
        return json.loads(line)


class CodexResponsesVisionLanguageEvaluator:
    name = "codex_responses"

    def __init__(
        self,
        *,
        model: str = "gpt-5.5",
        api_key: str | None = None,
        endpoint: str = "https://api.openai.com/v1/responses",
        timeout_seconds: int = 180,
        http_post: Callable[[str, dict[str, Any], dict[str, str], int], dict[str, Any]] | None = None,
    ):
        self.model = model
        self.api_key = os.environ.get("OPENAI_API_KEY") if api_key is None else api_key
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds
        self.http_post = http_post or _default_responses_post

    def evaluate(self, snapshot: EvaluationSnapshot, criteria: dict[str, Any]) -> StepEvaluation:
        if not self.api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is required for Codex Responses VLM evaluation. "
                "This path uses the OpenAI Responses API directly instead of spawning `codex exec`."
            )
        response = self.http_post(
            self.endpoint,
            _responses_payload(snapshot, criteria, model=self.model),
            {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            self.timeout_seconds,
        )
        parsed = json.loads(_extract_json(_response_output_text(response)))
        return _step_evaluation_from_model_json(
            parsed,
            snapshot,
            criteria,
            evaluator_name=self.name,
            model=self.model,
            evidence_extra={"openai_response_id": response.get("id", "")},
        )


class CodexCliVisionLanguageEvaluator:
    name = "codex_cli"

    def __init__(
        self,
        *,
        model: str = "gpt-5.5",
        cwd: str | Path | None = None,
        timeout_seconds: int = 180,
        run_command: Callable[..., subprocess.CompletedProcess[str]] | None = None,
    ):
        self.model = model
        self.cwd = Path(cwd) if cwd else None
        self.timeout_seconds = timeout_seconds
        self.run_command = run_command or subprocess.run

    def evaluate(self, snapshot: EvaluationSnapshot, criteria: dict[str, Any]) -> StepEvaluation:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            schema_path = tmp_path / "vlm_response_schema.json"
            output_path = tmp_path / "vlm_response.json"
            schema_path.write_text(json.dumps(CODEX_VLM_RESPONSE_SCHEMA, ensure_ascii=False), encoding="utf-8")
            command = [
                "codex",
                "exec",
                "--model",
                self.model,
                "--ephemeral",
                "--ignore-rules",
                "--ignore-user-config",
                "--sandbox",
                "read-only",
                "--output-schema",
                str(schema_path),
                "--output-last-message",
                str(output_path),
            ]
            screenshot_path = Path(snapshot.screenshot_path) if snapshot.screenshot_path else None
            if screenshot_path and screenshot_path.is_file():
                command.extend(["--image", str(screenshot_path)])
            prompt = _build_codex_vlm_prompt(snapshot, criteria)

            try:
                completed = self.run_command(
                    command,
                    input=prompt,
                    cwd=str(self.cwd) if self.cwd else None,
                    text=True,
                    capture_output=True,
                    timeout=self.timeout_seconds,
                    check=True,
                )
            except subprocess.CalledProcessError as exc:
                raise RuntimeError(
                    "codex VLM evaluation failed "
                    f"(exit={exc.returncode}, model={self.model}).\n"
                    f"STDERR:\n{exc.stderr}\nSTDOUT:\n{exc.stdout}"
                ) from exc

            raw_output = output_path.read_text(encoding="utf-8") if output_path.exists() else completed.stdout

        parsed = json.loads(_extract_json(raw_output))
        return _step_evaluation_from_model_json(
            parsed,
            snapshot,
            criteria,
            evaluator_name=self.name,
            model=self.model,
            evidence_extra={
                "codex_stdout": completed.stdout[-2000:],
                "codex_stderr": completed.stderr[-2000:],
            },
        )


def _step_evaluation_from_model_json(
    parsed: dict[str, Any],
    snapshot: EvaluationSnapshot,
    criteria: dict[str, Any],
    *,
    evaluator_name: str,
    model: str,
    evidence_extra: dict[str, Any],
) -> StepEvaluation:
    status = _status(parsed.get("status"))
    problems = _string_list(parsed.get("problems"))
    if snapshot.assertion_error:
        status = "failed"
        problems = [*problems, snapshot.assertion_error]
    evidence_artifacts = _string_list(parsed.get("evidence_artifacts"))
    if snapshot.screenshot_path and snapshot.screenshot_path not in evidence_artifacts:
        evidence_artifacts.append(snapshot.screenshot_path)
    return StepEvaluation(
        step_name=snapshot.step_name,
        step_type=snapshot.step_type,
        status=status,
        summary=str(parsed.get("summary") or snapshot.assertion_error or "Codex VLM returned no summary."),
        evidence={
            **snapshot.as_dict(),
            "criteria": criteria,
            "vlm_evaluator": evaluator_name,
            "codex_model": model,
            **evidence_extra,
        },
        problems=problems,
        suggested_update=str(parsed.get("suggested_update") or ""),
        failure_kind=str(parsed.get("failure_kind") or ""),
        expected_state=str(parsed.get("expected_state") or ""),
        observed_state=str(parsed.get("observed_state") or ""),
        repair_focus=str(parsed.get("repair_focus") or ""),
        evidence_artifacts=evidence_artifacts,
    )


def _responses_payload(snapshot: EvaluationSnapshot, criteria: dict[str, Any], *, model: str) -> dict[str, Any]:
    content: list[dict[str, Any]] = [{"type": "input_text", "text": _build_codex_vlm_prompt(snapshot, criteria)}]
    screenshot_path = Path(snapshot.screenshot_path) if snapshot.screenshot_path else None
    if screenshot_path and screenshot_path.is_file():
        content.append(
            {
                "type": "input_image",
                "image_url": _image_data_url(screenshot_path),
                "detail": "auto",
            }
        )
    return {
        "model": model,
        "input": [{"role": "user", "content": content}],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "webmcp_vlm_evaluation",
                "schema": CODEX_VLM_RESPONSE_SCHEMA,
                "strict": True,
            }
        },
        "store": False,
    }


def _app_server_user_input(*, prompt: str, image_paths: list[Path]) -> list[dict[str, Any]]:
    user_input: list[dict[str, Any]] = [{"type": "text", "text": prompt, "text_elements": []}]
    for image_path in image_paths:
        user_input.append({"type": "localImage", "path": str(image_path), "detail": "auto"})
    return user_input


def _snapshot_image_paths(screenshot_path: str, *, cwd: Path | None) -> list[Path]:
    if not screenshot_path:
        return []
    path = Path(screenshot_path)
    if not path.is_absolute() and cwd is not None:
        path = cwd / path
    path = path.resolve()
    return [path] if path.is_file() else []


def _agent_message_text(events: list[dict[str, Any]], *, thread_id: str, turn_id: str) -> str:
    for event in events:
        if event.get("method") != "item/completed":
            continue
        params = event.get("params") or {}
        if params.get("threadId") != thread_id or params.get("turnId") != turn_id:
            continue
        item = params.get("item") or {}
        if item.get("type") == "agentMessage" and item.get("phase") == "final_answer":
            return str(item.get("text") or "")
    return ""


def _turn_completed(events: list[dict[str, Any]], *, thread_id: str, turn_id: str) -> bool:
    for event in events:
        if event.get("method") != "turn/completed":
            continue
        params = event.get("params") or {}
        turn = params.get("turn") or {}
        if params.get("threadId") == thread_id and turn.get("id") == turn_id:
            if turn.get("status") != "completed":
                raise RuntimeError(f"Codex app-server VLM turn failed: {json.dumps(turn)[:1000]}")
            return True
    return False


def _is_request(message: dict[str, Any]) -> bool:
    return "id" in message and "method" in message and "result" not in message and "error" not in message


def _default_responses_post(
    endpoint: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    timeout_seconds: int,
) -> dict[str, Any]:
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI Responses API request failed (status={exc.code}).\n{error_body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"OpenAI Responses API request failed: {exc}") from exc
    return json.loads(body)


def _response_output_text(response: dict[str, Any]) -> str:
    output_text = response.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text
    chunks: list[str] = []
    for item in response.get("output", []):
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []):
            if not isinstance(content, dict):
                continue
            if content.get("type") == "output_text" and isinstance(content.get("text"), str):
                chunks.append(content["text"])
    joined = "\n".join(chunks).strip()
    if not joined:
        raise ValueError(f"OpenAI Responses API returned no output text: {json.dumps(response)[:500]}")
    return joined


def _image_data_url(path: Path) -> str:
    media_type = mimetypes.guess_type(path.name)[0] or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{media_type};base64,{encoded}"


def _build_codex_vlm_prompt(snapshot: EvaluationSnapshot, criteria: dict[str, Any]) -> str:
    payload = {
        "snapshot": snapshot.as_dict(),
        "criteria": criteria,
        "evaluation_rules": [
            "Evaluate the attached screenshot together with URL, title, page text, output, and assertions.",
            "Return passed only when the current browser state satisfies the criteria and there is no assertion_error.",
            "Do not use generic summaries such as 'passed with browser evidence'.",
            "The summary, expected_state, and observed_state must cite concrete visible or textual evidence.",
            "Write user-facing explanations in Korean unless the evidence is an English literal.",
        ],
    }
    return (
        "You are the VLM evaluator for a WebMCP Playwright workflow step.\n"
        "Inspect the browser evidence and return only JSON matching the provided schema.\n\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def _status(value: Any) -> str:
    return value if value in {"passed", "failed"} else "failed"


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _extract_json(raw: str) -> str:
    stripped = raw.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end > start:
        return stripped[start : end + 1]
    raise ValueError(f"Codex VLM evaluator did not return JSON: {raw[:500]}")
