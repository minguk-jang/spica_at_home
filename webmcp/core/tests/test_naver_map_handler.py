from __future__ import annotations

import unittest
from pathlib import Path

from webworkflows.handlers.naver_map import extract_subway_duration


class NaverMapHandlerTest(unittest.TestCase):
    def test_extract_subway_duration_prefers_top_optimal_subway_route(self) -> None:
        page_text = Path("tests/fixtures/naver_map_route_text.txt").read_text(encoding="utf-8")

        result = extract_subway_duration(
            page_text=page_text,
            start_station="양재역",
            end_station="사당역",
        )

        self.assertEqual("14분", result["duration_text"])
        self.assertEqual(14, result["duration_minutes"])
        self.assertIn("3호선", result["route_summary"])
        self.assertNotIn("신분당", result["route_summary"])


if __name__ == "__main__":
    unittest.main()
