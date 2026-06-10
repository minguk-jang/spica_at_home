"""Codex app-server model backend using the user's local Codex OAuth login."""

from __future__ import annotations

import base64
import json
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from webwright.models.base import (
    BaseModel,
    BaseModelConfig,
    OptStr,
    _request_metrics_from_serialized_input,
    parse_json_output,
)

__all__ = ["CodexAppServerModel", "CodexAppServerModelConfig"]


class CodexAppServerModelConfig(BaseModelConfig):
    model_name: OptStr = "gpt-5.5"
    codex_bin: OptStr = "codex"
    codex_sandbox: OptStr = "read-only"
    codex_workdir: OptStr = ""


def _text_from_part(part: dict[str, Any]) -> str:
    if part.get("type") in {"text", "input_text", "output_text"}:
        return str(part.get("text", ""))
    return ""


def _image_file_from_data_url(image_url: str, tmpdir: Path, index: int) -> Path | None:
    if not image_url.startswith("data:"):
        return None
    header, _, payload = image_url.partition(",")
    suffix = ".png"
    media_type = header.split(";", 1)[0].removeprefix("data:")
    if media_type == "image/jpeg":
        suffix = ".jpg"
    image_path = tmpdir / f"input_image_{index}{suffix}"
    image_path.write_bytes(base64.b64decode(payload))
    return image_path


def _messages_to_prompt_and_images(
    messages: list[dict[str, Any]],
    tmpdir: Path,
) -> tuple[str, list[Path], list[dict[str, Any]]]:
    chunks: list[str] = []
    images: list[Path] = []
    metrics_input: list[dict[str, Any]] = []
    for message in messages:
        role = message.get("role")
        if role == "exit":
            continue
        content = message.get("content", "")
        parts: list[dict[str, Any]] = []
        if isinstance(content, str):
            parts.append({"type": "input_text", "text": content})
            chunks.append(f"{role}:\n{content}")
            metrics_input.append({"content": parts})
            continue

        text_chunks: list[str] = []
        for part in content:
            if not isinstance(part, dict):
                continue
            if part.get("type") == "input_image":
                image_path = _image_file_from_data_url(
                    str(part.get("image_url", "")),
                    tmpdir,
                    len(images) + 1,
                )
                if image_path is not None:
                    images.append(image_path)
                    text_chunks.append(f"[image: {image_path.name}]")
                    parts.append({"type": "input_image"})
                continue
            text = _text_from_part(part)
            if text:
                text_chunks.append(text)
                parts.append({"type": "input_text", "text": text})
        chunks.append(f"{role}:\n" + "\n".join(text_chunks))
        metrics_input.append({"content": parts})
    return "\n\n".join(chunks), images, metrics_input


def _app_server_user_input(*, prompt: str, image_paths: list[Path]) -> list[dict[str, Any]]:
    user_input: list[dict[str, Any]] = [{"type": "text", "text": prompt, "text_elements": []}]
    for image_path in image_paths:
        user_input.append({"type": "localImage", "path": str(image_path), "detail": "auto"})
    return user_input


class _CodexAppServerJsonRpcClient:
    def __init__(self, *, codex_bin: str, cwd: Path, timeout_seconds: int):
        self.codex_bin = codex_bin
        self.cwd = cwd
        self.timeout_seconds = timeout_seconds
        self.process: subprocess.Popen[str] | None = None
        self._next_id = 1

    def run_turn(
        self,
        *,
        prompt: str,
        image_paths: list[Path],
        model: str,
        sandbox: str,
        output_schema: dict[str, Any] | None,
    ) -> str:
        self._ensure_started()
        thread_id = self._start_thread(model=model, sandbox=sandbox)
        params: dict[str, Any] = {
            "threadId": thread_id,
            "input": _app_server_user_input(prompt=prompt, image_paths=image_paths),
            "model": model,
            "approvalPolicy": "never",
            "sandboxPolicy": {"type": "readOnly", "networkAccess": False},
        }
        if output_schema is not None:
            params["outputSchema"] = output_schema
        turn_response_id = self._send_request("turn/start", params)
        turn_result, events = self._read_response(turn_response_id, timeout_seconds=30)
        turn_id = str(((turn_result.get("turn") or {}).get("id")) or "")
        final_text = _agent_message_text(events, thread_id=thread_id, turn_id=turn_id)
        if _turn_completed(events, thread_id=thread_id, turn_id=turn_id):
            return final_text

        deadline = time.time() + self.timeout_seconds
        while time.time() < deadline:
            message = self._read_message(deadline)
            if _is_request(message):
                self._send_error(
                    str(message["id"]),
                    code=-32601,
                    message="Webwright Codex app-server model does not handle requests",
                )
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
                        raise RuntimeError(f"Codex app-server turn failed: {json.dumps(turn)[:1000]}")
                    if not final_text.strip():
                        raise RuntimeError("Codex app-server turn completed without an agent message.")
                    return final_text
        raise TimeoutError("Timed out waiting for Codex app-server turn to complete.")

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
                    "name": "webwright-codex-app-server",
                    "title": "Webwright Codex App Server",
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

    def _start_thread(self, *, model: str, sandbox: str) -> str:
        response_id = self._send_request(
            "thread/start",
            {
                "model": model,
                "cwd": str(self.cwd),
                "approvalPolicy": "never",
                "sandbox": sandbox,
                "ephemeral": True,
                "baseInstructions": (
                    "You are only Webwright's JSON model backend. Do not use tools, shell commands, "
                    "file edits, web browsing, or repo context yourself."
                ),
                "developerInstructions": (
                    "Return only the requested model response. The outer Webwright harness executes actions."
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


class CodexAppServerModel(BaseModel):
    _API_KEY_FIELD = ""
    _ENV_VAR = ""
    _LOG_SOURCE = "codex_app_server"
    _DEFAULT_CONFIG_CLASS = CodexAppServerModelConfig

    def __init__(self, *, config_class: type | None = None, **kwargs):
        super().__init__(config_class=config_class, **kwargs)
        cwd = Path(self.config.codex_workdir) if self.config.codex_workdir else Path.cwd()
        self._app_server = _CodexAppServerJsonRpcClient(
            codex_bin=self.config.codex_bin,
            cwd=cwd,
            timeout_seconds=self.config.request_timeout_seconds,
        )

    def close(self) -> None:
        self._app_server.close()

    def _request_headers(self) -> dict[str, str]:
        return {}

    def _post_url(self) -> str:
        return "codex app-server"

    def _build_payload(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        return {"messages": messages}

    def _request_metrics_input(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        return payload.get("metrics_input") or []

    def _extract_text(self, payload: dict[str, Any]) -> str:
        return str(payload.get("text", ""))

    def _usage_metrics_from_payload(self, payload: dict[str, Any]) -> dict[str, int]:
        return {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "cached_input_tokens": 0,
            "reasoning_output_tokens": 0,
        }

    def _run_codex(self, prompt: str, *, schema: dict[str, Any] | None, images: list[Path]) -> str:
        return self._app_server.run_turn(
            prompt=prompt,
            image_paths=images,
            model=self.config.model_name,
            sandbox=self.config.codex_sandbox,
            output_schema=schema,
        )

    def query(self, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        with tempfile.TemporaryDirectory(prefix="webwright-codex-app-server-images-") as tmp:
            prompt, images, metrics_input = _messages_to_prompt_and_images(messages, Path(tmp))
            prompt = (
                f"{prompt}\n\nYou are acting only as Webwright's model backend. "
                f"Do not run shell commands, edit files, browse, or use tools yourself; "
                f"the outer Webwright harness will execute the returned command. "
                f"Respond with a single strict JSON object and no prose. "
                f"The JSON schema is the provided output schema."
            )
            request_metrics = _request_metrics_from_serialized_input(metrics_input)
            self._last_request_metrics = dict(request_metrics)
            for key, value in request_metrics.items():
                self._cumulative_request_metrics[key] += value
            raw_text = self._run_codex(prompt, schema=self._response_schema(), images=images)
        parsed = parse_json_output(raw_text, action_field=self.config.action_field)
        action_text = str(parsed.get(self.config.action_field, "") or "").strip()
        actions: list[dict[str, Any]] = []
        if action_text:
            actions.append(
                {
                    self.config.action_field: action_text,
                    "command": action_text,
                    "bash_command": action_text,
                }
            )
        return self.format_message(
            role="assistant",
            content=parsed.get("thought", ""),
            extra={
                "actions": actions,
                "done": bool(parsed.get("done", False)),
                "final_response": parsed.get("final_response", ""),
                "raw_response": parsed,
                "usage": self._usage_snapshot(),
            },
        )

    def __call__(self, messages: list[dict[str, Any]], **kwargs: Any) -> str:
        with tempfile.TemporaryDirectory(prefix="webwright-codex-app-server-images-") as tmp:
            prompt, images, metrics_input = _messages_to_prompt_and_images(messages, Path(tmp))
            request_metrics = _request_metrics_from_serialized_input(metrics_input)
            self._last_request_metrics = dict(request_metrics)
            for key, value in request_metrics.items():
                self._cumulative_request_metrics[key] += value
            return self._run_codex(prompt, schema=None, images=images)


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
                raise RuntimeError(f"Codex app-server turn failed: {json.dumps(turn)[:1000]}")
            return True
    return False


def _is_request(message: dict[str, Any]) -> bool:
    return "id" in message and "method" in message and "result" not in message and "error" not in message
