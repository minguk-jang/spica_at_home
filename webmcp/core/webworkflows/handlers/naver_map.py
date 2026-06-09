from __future__ import annotations

import re
from typing import Any


def extract_subway_duration(*, page_text: str, start_station: str, end_station: str, **_: Any) -> dict[str, Any]:
    text = _normalize(page_text)
    if not text:
        raise ValueError("page_text is required")
    if start_station not in text or end_station not in text:
        raise ValueError(f"route text does not include requested stations: {start_station}, {end_station}")

    segment = _best_subway_segment(text, start_station, end_station)
    duration_text = _duration_from_segment(segment)
    duration_minutes = int(duration_text.replace("분", ""))
    route_summary = _route_summary(segment, start_station, end_station, duration_text)
    return {
        "start_station": start_station,
        "end_station": end_station,
        "duration_text": duration_text,
        "duration_minutes": duration_minutes,
        "route_summary": route_summary,
    }


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _best_subway_segment(text: str, start_station: str, end_station: str) -> str:
    candidates = [
        _route_body(segment.strip())
        for segment in re.split(r"\s*상세보기\s*", text)
        if start_station in segment and end_station in segment and "지하철" in segment
    ]
    if not candidates:
        raise ValueError("no subway route segment found")

    def score(segment: str) -> tuple[int, int, int]:
        is_optimal = segment.startswith("최적 ")
        has_bus = "버스" in segment
        subway_count = segment.count("지하철")
        duration = _duration_number(segment) or 9999
        return (0 if is_optimal else 1, 1 if has_bus else 0, duration - subway_count)

    return sorted(candidates, key=score)[0]


def _route_body(segment: str) -> str:
    match = re.search(r"(?:최적\s+|최소환승\s+)?(?<!\d)\d{1,3}분", segment)
    if not match:
        return segment
    return segment[match.start() :].strip()


def _duration_from_segment(segment: str) -> str:
    match = re.search(r"(?<!\d)(\d{1,3})분", segment)
    if not match:
        raise ValueError("subway route duration was not found")
    return f"{int(match.group(1))}분"


def _duration_number(segment: str) -> int | None:
    match = re.search(r"(?<!\d)(\d{1,3})분", segment)
    return int(match.group(1)) if match else None


def _route_summary(segment: str, start_station: str, end_station: str, duration_text: str) -> str:
    compact = segment[:500].strip()
    return f"{start_station}에서 {end_station}까지 지하철 경로는 약 {duration_text}입니다. {compact}"
