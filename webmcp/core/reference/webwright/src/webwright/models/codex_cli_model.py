"""Compatibility aliases for the previous Codex CLI model backend name."""

from __future__ import annotations

from webwright.models.codex_app_server_model import CodexAppServerModel, CodexAppServerModelConfig

CodexCliModelConfig = CodexAppServerModelConfig


class CodexCliModel(CodexAppServerModel):
    """Backward-compatible class name; runtime uses Codex app-server."""


__all__ = ["CodexCliModel", "CodexCliModelConfig"]
