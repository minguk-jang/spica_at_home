from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import unquote, urlsplit, urlunsplit

from webworkflows.storage import WorkflowSkillStore, dumps, loads


@dataclass(frozen=True)
class PageAnalysisRecord:
    id: int
    url_key: str
    canonical_url: str
    original_url: str
    title: str
    framework_hints: list[str]
    frame_hints: list[str]
    locator_hints: list[str]
    analysis: dict[str, Any]
    evidence: dict[str, Any]
    source: str
    observation_count: int

    def as_context(self) -> dict[str, Any]:
        return {
            "url_key": self.url_key,
            "canonical_url": self.canonical_url,
            "title": self.title,
            "framework_hints": self.framework_hints,
            "frame_hints": self.frame_hints,
            "locator_hints": self.locator_hints,
            "analysis": self.analysis,
            "observation_count": self.observation_count,
        }


@dataclass(frozen=True)
class WorkflowKnowledgeEntry:
    id: int
    category: str
    summary: str
    content: dict[str, Any]
    source: str
    confidence: float
    tags: list[str]

    def as_context(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "summary": self.summary,
            "content": self.content,
            "source": self.source,
            "confidence": self.confidence,
            "tags": self.tags,
        }


def normalize_url_key(raw_url: str) -> str:
    parts = _split_url(raw_url)
    host = (parts.hostname or "").lower()
    port = _normalized_port(parts)
    path = unquote(parts.path or "").strip("/")
    pieces = [host]
    if port:
        pieces.append(str(port))
    if path:
        pieces.append(path)
    return _kebab_case("-".join(piece for piece in pieces if piece)) or "unknown-url"


def canonical_url_without_query(raw_url: str) -> str:
    parts = _split_url(raw_url)
    scheme = (parts.scheme or "https").lower()
    host = (parts.hostname or "").lower()
    port = _normalized_port(parts)
    netloc = f"{host}:{port}" if port else host
    path = unquote(parts.path or "").rstrip("/")
    return urlunsplit((scheme, netloc, path or "/", "", ""))


class PageAnalysisStore:
    def __init__(self, store: WorkflowSkillStore):
        self.store = store

    def upsert_from_trace(self, trace: Any, *, source: str) -> PageAnalysisRecord:
        target_url = _trace_url(trace)
        page_text = str(getattr(trace, "page_text", "") or "")
        title = str(getattr(trace, "title", "") or "")
        analysis = analyze_page_text(page_text=page_text, url=target_url, title=title)
        framework_hints = list(analysis["framework_hints"])
        frame_hints = list(analysis["frame_hints"])
        locator_hints = list(analysis["locator_hints"])
        evidence = {
            "provider": str(getattr(trace, "provider", "") or ""),
            "final_url": str(getattr(trace, "final_url", "") or ""),
            "title": title,
            "page_text_excerpt": page_text[:1000],
        }
        return self.upsert(
            original_url=target_url,
            title=title,
            framework_hints=framework_hints,
            frame_hints=frame_hints,
            locator_hints=locator_hints,
            analysis=analysis,
            evidence=evidence,
            source=source,
        )

    def upsert(
        self,
        *,
        original_url: str,
        title: str = "",
        framework_hints: list[str] | None = None,
        frame_hints: list[str] | None = None,
        locator_hints: list[str] | None = None,
        analysis: dict[str, Any] | None = None,
        evidence: dict[str, Any] | None = None,
        source: str = "manual",
    ) -> PageAnalysisRecord:
        url_key = normalize_url_key(original_url)
        canonical_url = canonical_url_without_query(original_url)
        with self.store.connect() as conn:
            existing = conn.execute(
                "select id, observation_count from page_analyses where url_key = ?",
                (url_key,),
            ).fetchone()
            if existing:
                record_id = int(existing["id"])
                conn.execute(
                    """
                    update page_analyses
                    set canonical_url = ?, original_url = ?, title = ?,
                        framework_hints_json = ?, frame_hints_json = ?, locator_hints_json = ?,
                        analysis_json = ?, evidence_json = ?, source = ?,
                        observation_count = observation_count + 1,
                        updated_at = current_timestamp,
                        last_seen_at = current_timestamp
                    where id = ?
                    """,
                    (
                        canonical_url,
                        original_url,
                        title,
                        dumps(framework_hints or []),
                        dumps(frame_hints or []),
                        dumps(locator_hints or []),
                        dumps(analysis or {}),
                        dumps(evidence or {}),
                        source,
                        record_id,
                    ),
                )
            else:
                record_id = int(
                    conn.execute(
                        """
                        insert into page_analyses
                          (url_key, canonical_url, original_url, title,
                           framework_hints_json, frame_hints_json, locator_hints_json,
                           analysis_json, evidence_json, source)
                        values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            url_key,
                            canonical_url,
                            original_url,
                            title,
                            dumps(framework_hints or []),
                            dumps(frame_hints or []),
                            dumps(locator_hints or []),
                            dumps(analysis or {}),
                            dumps(evidence or {}),
                            source,
                        ),
                    ).lastrowid
                )
        return self._load_by_id(record_id)

    def lookup(self, url: str) -> PageAnalysisRecord | None:
        url_key = normalize_url_key(url)
        with self.store.connect() as conn:
            row = conn.execute("select * from page_analyses where url_key = ?", (url_key,)).fetchone()
        return _page_analysis_from_row(row) if row else None

    def _load_by_id(self, record_id: int) -> PageAnalysisRecord:
        with self.store.connect() as conn:
            row = conn.execute("select * from page_analyses where id = ?", (record_id,)).fetchone()
        if not row:
            raise KeyError(f"page analysis not found: {record_id}")
        return _page_analysis_from_row(row)


class WorkflowKnowledgeStore:
    def __init__(self, store: WorkflowSkillStore):
        self.store = store

    def append(
        self,
        *,
        category: str,
        summary: str,
        content: dict[str, Any] | None = None,
        source: str,
        confidence: float = 0.5,
        tags: list[str] | None = None,
    ) -> WorkflowKnowledgeEntry:
        with self.store.connect() as conn:
            entry_id = int(
                conn.execute(
                    """
                    insert into workflow_knowledge_entries
                      (category, summary, content_json, source, confidence, tags_json)
                    values (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        category,
                        summary,
                        dumps(content or {}),
                        source,
                        float(confidence),
                        dumps(tags or []),
                    ),
                ).lastrowid
            )
            row = conn.execute("select * from workflow_knowledge_entries where id = ?", (entry_id,)).fetchone()
        return _knowledge_from_row(row)

    def recent(self, *, category: str | None = None, limit: int = 5) -> list[WorkflowKnowledgeEntry]:
        if limit < 1:
            return []
        with self.store.connect() as conn:
            if category:
                rows = conn.execute(
                    """
                    select * from workflow_knowledge_entries
                    where category = ?
                    order by id desc
                    limit ?
                    """,
                    (category, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    select * from workflow_knowledge_entries
                    order by id desc
                    limit ?
                    """,
                    (limit,),
                ).fetchall()
        return [_knowledge_from_row(row) for row in rows]


def analyze_page_text(*, page_text: str, url: str, title: str = "") -> dict[str, Any]:
    framework_hints = _framework_hints(page_text)
    frame_hints = _frame_hints(page_text)
    locator_hints = _locator_hints(page_text, frame_hints)
    page_type = _page_type(page_text=page_text, url=url, title=title)
    stable_markers = _stable_markers(page_text, page_type)
    detected_tickers = _detected_tickers(page_text)
    actionable_tips = _actionable_page_tips(
        page_type=page_type,
        framework_hints=framework_hints,
        frame_hints=frame_hints,
        locator_hints=locator_hints,
        stable_markers=stable_markers,
        detected_tickers=detected_tickers,
    )
    extraction_tips = _extraction_tips(page_type, detected_tickers)
    risk_notes = _risk_notes(page_type, framework_hints, frame_hints)
    return {
        "summary": _analysis_summary(
            page_type=page_type,
            framework_hints=framework_hints,
            frame_hints=frame_hints,
            locator_hints=locator_hints,
            stable_markers=stable_markers,
        ),
        "page_type": page_type,
        "text_length": len(page_text),
        "has_iframe": bool(frame_hints),
        "framework_count": len(framework_hints),
        "framework_hints": framework_hints,
        "frame_hints": frame_hints,
        "locator_hints": locator_hints,
        "stable_markers": stable_markers,
        "detected_tickers": detected_tickers,
        "actionable_tips": actionable_tips,
        "extraction_tips": extraction_tips,
        "risk_notes": risk_notes,
        "selector_strategy": _selector_strategy(locator_hints, frame_hints),
        "assertion_strategy": _assertion_strategy(page_type, stable_markers),
    }


def build_script_generation_knowledge(
    *,
    status: str,
    workflow_name: str,
    workflow_version: int | None,
    start_url: str,
    user_task: str,
    final_state: str,
    output_keys: list[str],
    page_analysis: dict[str, Any] | None,
    error: dict[str, Any] | None,
) -> dict[str, Any]:
    analysis = page_analysis or {}
    page_type = str(analysis.get("page_type") or "generic_page")
    action = "succeeded" if status == "succeeded" else "failed"
    if page_type == "naver_stock_search_result":
        summary = f"Naver stock workflow {action}: direct search URL + text-handler extraction"
    elif analysis.get("frame_hints"):
        summary = f"Iframe workflow {action}: frame-aware locator strategy"
    elif analysis.get("framework_hints"):
        summary = f"Framework page workflow {action}: role/text assertions before brittle selectors"
    else:
        summary = f"Workflow generation {action}: text-first deterministic skeleton"

    actionable_tips = list(analysis.get("actionable_tips") or [])
    extraction_tips = list(analysis.get("extraction_tips") or [])
    if not actionable_tips:
        actionable_tips.append("Prefer role selectors and visible text assertions before CSS selectors.")
    if status == "succeeded":
        actionable_tips.append("Reuse the verified workflow shape and keep assertions tied to observed page markers.")
    else:
        actionable_tips.append("Record the failure evidence and repair the smallest unstable step first.")
    if output_keys:
        actionable_tips.append(f"Assert downstream output keys after extraction/rendering: {', '.join(output_keys)}.")

    return {
        "category": "script_generation",
        "summary": summary,
        "content": {
            "status": status,
            "workflow_name": workflow_name,
            "workflow_version": workflow_version,
            "start_url": start_url,
            "user_task": user_task,
            "final_state": final_state,
            "page_type": page_type,
            "stable_markers": list(analysis.get("stable_markers") or []),
            "actionable_tips": _unique(actionable_tips),
            "extraction_tips": _unique(extraction_tips),
            "selector_strategy": analysis.get("selector_strategy") or _selector_strategy(
                list(analysis.get("locator_hints") or []),
                list(analysis.get("frame_hints") or []),
            ),
            "assertion_strategy": analysis.get("assertion_strategy")
            or _assertion_strategy(page_type, list(analysis.get("stable_markers") or [])),
            "risk_notes": list(analysis.get("risk_notes") or []),
            "output_keys": sorted(output_keys),
            "error": error,
        },
        "source": "workflow_creation",
        "confidence": 0.86 if status == "succeeded" else 0.46,
        "tags": _unique(["workflow_creation", status, page_type, *_tag_hints(analysis)]),
    }


def _split_url(raw_url: str):
    cleaned = (raw_url or "").strip()
    if not cleaned:
        cleaned = "unknown-url"
    if "://" not in cleaned and not cleaned.startswith("//"):
        cleaned = f"https://{cleaned}"
    return urlsplit(cleaned)


def _normalized_port(parts: Any) -> int | None:
    try:
        port = parts.port
    except ValueError:
        return None
    if port is None:
        return None
    scheme = (parts.scheme or "").lower()
    if (scheme == "http" and port == 80) or (scheme == "https" and port == 443):
        return None
    return int(port)


def _kebab_case(value: str) -> str:
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", value)
    value = re.sub(r"[^A-Za-z0-9]+", "-", value)
    value = re.sub(r"-+", "-", value)
    return value.strip("-").lower()


def _trace_url(trace: Any) -> str:
    final_url = str(getattr(trace, "final_url", "") or "")
    if final_url:
        return final_url
    arguments = getattr(trace, "arguments", {}) or {}
    return str(arguments.get("start_url") or "unknown-url")


def _framework_hints(page_text: str) -> list[str]:
    lower = page_text.lower()
    hints: list[str] = []
    if "react" in lower or "data-reactroot" in lower:
        hints.append("react")
    if "__next_data__" in lower or "next.js" in lower or "nextjs" in lower:
        hints.append("nextjs")
    if "vue" in lower or "createapp" in lower:
        hints.append("vue")
    if "angular" in lower or "ng-version" in lower:
        hints.append("angular")
    if "svelte" in lower:
        hints.append("svelte")
    return hints


def _frame_hints(page_text: str) -> list[str]:
    lower = page_text.lower()
    hints: list[str] = []
    if "iframe" in lower or "<frame" in lower:
        hints.append("iframe")
    return hints


def _locator_hints(page_text: str, frame_hints: list[str]) -> list[str]:
    lower = page_text.lower()
    hints = ["prefer_role_selectors"]
    if frame_hints or "frame_locator" in lower:
        hints.append("frame_locator")
    if "shadowroot" in lower or "shadow dom" in lower:
        hints.append("shadow_dom")
    if "data-testid" in lower or "data-test" in lower:
        hints.append("test_id")
    return hints


def _page_type(*, page_text: str, url: str, title: str) -> str:
    lower_url = url.lower()
    combined = f"{title}\n{page_text}".lower()
    if "search.naver.com/search.naver" in lower_url and (
        "증권정보" in page_text or "현재가" in page_text or "kospi" in combined or "kosdaq" in combined
    ):
        return "naver_stock_search_result"
    if "map.naver.com" in lower_url or ("네이버지도" in page_text and "길찾기" in page_text):
        return "naver_map_route"
    if "iframe" in combined:
        return "iframe_page"
    if _framework_hints(page_text):
        return "framework_app"
    return "generic_page"


def _stable_markers(page_text: str, page_type: str) -> list[str]:
    markers: list[str] = []
    if page_type == "naver_stock_search_result":
        for marker in ["증권정보", "현재가", "전일대비", "KRX", "장마감", "관련 뉴스"]:
            if marker in page_text:
                markers.append(marker)
        markers.extend(_detected_tickers(page_text))
        return _unique(markers)
    if page_type == "naver_map_route":
        for marker in ["길찾기", "대중교통", "최적 경로순", "도착"]:
            if marker in page_text:
                markers.append(marker)
    if "ExampleReady" in page_text:
        markers.append("ExampleReady")
    markers.extend(_visible_text_markers(page_text))
    return _unique(markers)[:8]


def _visible_text_markers(page_text: str) -> list[str]:
    markers: list[str] = []
    for raw_line in re.split(r"[\r\n]+", page_text):
        marker = re.sub(r"\s+", " ", raw_line).strip(" \t-•*")
        if not _is_stable_visible_text_marker(marker):
            continue
        markers.append(marker)
        if len(markers) >= 6:
            break
    return _unique(markers)


def _is_stable_visible_text_marker(marker: str) -> bool:
    if len(marker) < 4 or len(marker) > 64:
        return False
    lower = marker.lower()
    if lower.startswith(("http://", "https://")):
        return False
    if lower.startswith(("powered by", "copyright", "all rights reserved")):
        return False
    if not re.search(r"[A-Za-z가-힣]", marker):
        return False
    if re.search(r"[£$₩]\s*\d|\b\d+[,.]\d+\b|\b\d{1,2}:\d{2}\b", marker):
        return False
    digits = sum(1 for char in marker if char.isdigit())
    if digits and digits / max(len(marker), 1) > 0.25:
        return False
    return True


def _detected_tickers(page_text: str) -> list[str]:
    return _unique(re.findall(r"\b\d{6}\b", page_text))


def _actionable_page_tips(
    *,
    page_type: str,
    framework_hints: list[str],
    frame_hints: list[str],
    locator_hints: list[str],
    stable_markers: list[str],
    detected_tickers: list[str],
) -> list[str]:
    tips: list[str] = []
    if page_type == "naver_stock_search_result":
        tips.extend(
            [
                "Use the direct search URL https://search.naver.com/search.naver?query={{company_name}} 주가 instead of driving the Naver home search box.",
                "Wait for stock-card text markers such as 증권정보, 현재가, and the six-digit ticker before extracting body text.",
                "Normalize URL keys without the query so all company searches share the same page-shape memory.",
                "Keep the workflow deterministic: goto -> wait_for_text -> naver_stock.extract_stock_card -> assert_output -> render_report.",
            ]
        )
        if detected_tickers:
            tips.append(f"Treat detected ticker(s) {', '.join(detected_tickers)} as validation anchors, not selector text.")
    if frame_hints:
        tips.append("Prefer frame_locator or frame-aware Playwright steps before querying controls inside embedded content.")
    if framework_hints:
        tips.append(
            f"Framework hints ({', '.join(framework_hints)}) mean DOM timing can shift; wait on user-visible text before click/fill."
        )
    if "test_id" in locator_hints:
        tips.append("Prefer data-testid/data-test selectors after accessible role/name selectors.")
    tips.append("Prefer role selectors and visible text assertions before brittle CSS selectors.")
    if stable_markers:
        tips.append(f"Use stable text markers for wait/assert steps: {', '.join(stable_markers[:5])}.")
    return _unique(tips)


def _extraction_tips(page_type: str, detected_tickers: list[str]) -> list[str]:
    if page_type == "naver_stock_search_result":
        ticker_hint = f" Validate ticker against {', '.join(detected_tickers)} when present." if detected_tickers else ""
        return [
            "Use naver_stock.extract_stock_card with page_text, company_name, and optional ticker instead of scraping individual DOM nodes."
            + ticker_hint,
            "Parse current_price from comma-formatted Korean price text and keep change_text as display text because signs/market wording vary.",
        ]
    if page_type == "naver_map_route":
        return ["Extract duration from route result text after 대중교통 markers are visible."]
    return ["Render reports from observed page_text when no domain handler exists; do not invent new handler modules."]


def _risk_notes(page_type: str, framework_hints: list[str], frame_hints: list[str]) -> list[str]:
    notes: list[str] = []
    if page_type == "naver_stock_search_result":
        notes.extend(
            [
                "Naver stock card text changes between 장중, 장마감, and delayed quote states.",
                "Company news snippets can mention other companies; validate company_name/ticker before using news context.",
                "Do not tie selectors to price numbers because they change every run.",
            ]
        )
    if framework_hints:
        notes.append("Hydrated framework pages may show initial shell text before controls become actionable.")
    if frame_hints:
        notes.append("Iframe content may not be visible to page-level locators; capture frame boundaries in the workflow.")
    return _unique(notes)


def _selector_strategy(locator_hints: list[str], frame_hints: list[str]) -> str:
    if frame_hints or "frame_locator" in locator_hints:
        return "Prefer frame_locator -> role/name -> label/text -> test id -> CSS, with frame boundary recorded explicitly."
    if "test_id" in locator_hints:
        return "Prefer role/name -> label/text -> data-testid/data-test -> CSS."
    return "Prefer role/name and visible text; use CSS only as a last resort."


def _assertion_strategy(page_type: str, stable_markers: list[str]) -> str:
    if page_type == "naver_stock_search_result":
        markers = ", ".join(stable_markers[:5]) or "증권정보, 현재가, ticker"
        return f"Wait for stock markers ({markers}), then assert extracted company_name/current_price/ticker instead of raw DOM shape."
    if stable_markers:
        return f"Wait for stable markers ({', '.join(stable_markers[:5])}) before extracting or rendering."
    return "Assert visible task-specific text first, then validate structured output keys."


def _analysis_summary(
    *,
    page_type: str,
    framework_hints: list[str],
    frame_hints: list[str],
    locator_hints: list[str],
    stable_markers: list[str],
) -> str:
    parts: list[str] = []
    parts.append(f"page_type={page_type}")
    if stable_markers:
        parts.append("markers=" + ",".join(stable_markers[:5]))
    if framework_hints:
        parts.append("frameworks=" + ",".join(framework_hints))
    if frame_hints:
        parts.append("frames=" + ",".join(frame_hints))
    if locator_hints:
        parts.append("locators=" + ",".join(locator_hints))
    return "; ".join(parts) if parts else "No special page-structure hints detected."


def _tag_hints(analysis: dict[str, Any]) -> list[str]:
    tags: list[str] = []
    tags.extend(str(item) for item in analysis.get("framework_hints") or [])
    tags.extend(str(item) for item in analysis.get("frame_hints") or [])
    tags.extend(str(item) for item in analysis.get("locator_hints") or [])
    return tags


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique_values: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        unique_values.append(value)
    return unique_values


def _page_analysis_from_row(row: Any) -> PageAnalysisRecord:
    return PageAnalysisRecord(
        id=int(row["id"]),
        url_key=row["url_key"],
        canonical_url=row["canonical_url"],
        original_url=row["original_url"],
        title=row["title"] or "",
        framework_hints=loads(row["framework_hints_json"], []),
        frame_hints=loads(row["frame_hints_json"], []),
        locator_hints=loads(row["locator_hints_json"], []),
        analysis=loads(row["analysis_json"], {}),
        evidence=loads(row["evidence_json"], {}),
        source=row["source"],
        observation_count=int(row["observation_count"]),
    )


def _knowledge_from_row(row: Any) -> WorkflowKnowledgeEntry:
    return WorkflowKnowledgeEntry(
        id=int(row["id"]),
        category=row["category"],
        summary=row["summary"],
        content=loads(row["content_json"], {}),
        source=row["source"],
        confidence=float(row["confidence"]),
        tags=loads(row["tags_json"], []),
    )
