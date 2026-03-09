from __future__ import annotations

import unittest

from src.mofa_monitor.models import ChangeEvent, MonitorItem
from src.mofa_monitor.telegram import _build_message


class TelegramMessageTests(unittest.TestCase):
    def test_travel_alarm_message_prioritizes_level_and_link(self) -> None:
        item = MonitorItem(
            source="travel_alarm",
            country_code="EG",
            country_name="이집트",
            item_id="1",
            title="이집트 travel_alarm",
            published_at="2026-03-09",
            url="https://example.com/alert",
            content="이집트 travel_alarm 3 일부 중북부 시나이 반도",
            content_hash="hash",
            matched_reason=("country:이집트", "api:travel_alarm"),
            level="3",
            region_type="일부",
            remark="중북부 시나이 반도",
        )
        message = _build_message(ChangeEvent(kind="new", item=item, summary="신규 항목 감지"))
        self.assertIn("게시: 2026-03-09", message)
        self.assertIn("단계: 3", message)
        self.assertIn("구역: 일부", message)
        self.assertIn("핵심: 중북부 시나이 반도", message)
        self.assertIn("링크: https://example.com/alert", message)
        self.assertNotIn("매칭사유", message)

    def test_level_change_message_shows_transition(self) -> None:
        item = MonitorItem(
            source="travel_alarm",
            country_code="IR",
            country_name="이란",
            item_id="1",
            title="이란 travel_alarm",
            published_at="2026-03-09",
            url="https://example.com/iran",
            content="전 지역",
            content_hash="hash",
            matched_reason=("country:이란", "api:travel_alarm"),
            level="4",
            remark="전 지역",
        )
        message = _build_message(
            ChangeEvent(
                kind="alert-level-changed",
                item=item,
                previous_level="3",
                summary="경보단계 변경: 3 -> 4",
            )
        )
        self.assertIn("단계: 3 -> 4", message)


if __name__ == "__main__":
    unittest.main()
