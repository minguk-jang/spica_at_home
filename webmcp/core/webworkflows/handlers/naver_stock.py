from __future__ import annotations

import re
from typing import Any


def extract_stock_card(
    *,
    page_text: str,
    company_name: str,
    ticker: str | None = None,
    news_limit: int = 3,
) -> dict[str, Any]:
    detected_company = company_name if company_name in page_text else _first_company_like_name(page_text)
    detected_ticker = ticker or _first_match(page_text, r"\b[0-9]{6}\b")
    price_text = _first_match(page_text, r"[0-9]{1,3}(?:,[0-9]{3})+원")
    current_price = int(price_text.replace(",", "").replace("원", "")) if price_text else 0
    change_text = _first_match(page_text, r"전일대비[^\n]+") or _first_match(page_text, r"[▲▼+-]?\s?[0-9,]+\s?\([+-]?[0-9.]+%\)")
    market_status = _first_match(page_text, r"KRX[^\n]+") or "확인 필요"
    news_context = _news_context(page_text, news_limit)

    return {
        "company_name": detected_company,
        "ticker": detected_ticker or "",
        "current_price": current_price,
        "change_text": change_text or "확인 필요",
        "market_status": market_status,
        "news_context": news_context,
    }


def _first_match(text: str, pattern: str) -> str:
    match = re.search(pattern, text)
    return match.group(0).strip() if match else ""


def _first_company_like_name(text: str) -> str:
    for line in (line.strip() for line in text.splitlines()):
        if line and "주가" not in line and not line.startswith("증권"):
            return line
    return ""


def _news_context(text: str, limit: int) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    news_start = 0
    for index, line in enumerate(lines):
        if "뉴스" in line:
            news_start = index + 1
            break
    selected = lines[news_start : news_start + max(limit, 0)]
    return "\n".join(f"- {line}" for line in selected) if selected else "- 관련 뉴스 없음"
