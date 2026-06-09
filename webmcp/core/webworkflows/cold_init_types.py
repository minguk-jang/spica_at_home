from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ArtifactTrace:
    provider: str
    user_request: str
    arguments: dict[str, Any]
    page_text: str
    title: str | None = None
    final_url: str | None = None
    screenshots: list[str] | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "user_request": self.user_request,
            "arguments": self.arguments,
            "page_text": self.page_text,
            "title": self.title,
            "final_url": self.final_url,
            "screenshots": self.screenshots or [],
        }
