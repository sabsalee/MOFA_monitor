from __future__ import annotations

import unittest

from src.mofa_monitor.config import Config
from src.mofa_monitor.models import MonitorItem
from src.mofa_monitor.monitor import (
    _build_manual_no_change_message,
    _source_status_label,
    detect_changes,
    run_monitor,
)
from src.mofa_monitor.state import build_state


def make_item(*, content_hash: str, level: str = "", source: str = "country_safety") -> MonitorItem:
    return MonitorItem(
        source=source,
        country_code="IR",
        country_name="이란",
        item_id="13",
        title="테헤란 안전공지",
        published_at="2026-03-09",
        url="https://example.com",
        content="본문",
        content_hash=content_hash,
        matched_reason=("country:이란", "api:test"),
        level=level,
    )


class ChangeDetectionTests(unittest.TestCase):
    def test_detect_new_item(self) -> None:
        changes = detect_changes({}, [make_item(content_hash="hash-1")])
        self.assertEqual(changes[0].kind, "new")

    def test_detect_updated_item(self) -> None:
        previous = {
            "country_safety:IR:13": {
                "content_hash": "old",
                "level": "",
            }
        }
        changes = detect_changes(previous, [make_item(content_hash="new")])
        self.assertEqual(changes[0].kind, "updated")

    def test_detect_alert_level_change(self) -> None:
        previous = {
            "travel_alarm:IR:13": {
                "content_hash": "same",
                "level": "2단계",
            }
        }
        item = make_item(content_hash="same", level="3단계", source="travel_alarm")
        changes = detect_changes(previous, [item])
        self.assertEqual(changes[0].kind, "alert-level-changed")

    def test_ignore_same_content(self) -> None:
        previous = {
            "country_safety:IR:13": {
                "content_hash": "same",
                "level": "",
            }
        }
        changes = detect_changes(previous, [make_item(content_hash="same")])
        self.assertEqual(changes, [])

    def test_build_state_keeps_last_checked_for_unchanged_item(self) -> None:
        previous = {
            "last_run_at": "2026-03-09T00:00:00+00:00",
            "source_failures": {},
            "items": {
                "country_safety:IR:13": {
                    "source": "country_safety",
                    "country_code": "IR",
                    "country_name": "이란",
                    "item_id": "13",
                    "title": "테헤란 안전공지",
                    "published_at": "2026-03-09",
                    "content_hash": "same",
                    "last_alerted_hash": "",
                    "url": "https://example.com",
                    "matched_reason": ["country:이란", "api:test"],
                    "last_checked_at": "2026-03-09T00:00:00+00:00",
                    "level": "",
                    "region_type": "",
                }
            },
        }
        state = build_state(previous, [make_item(content_hash="same")], [])
        entry = state["items"]["country_safety:IR:13"]
        self.assertEqual(entry["last_checked_at"], "2026-03-09T00:00:00+00:00")
        self.assertEqual(state["last_run_at"], "2026-03-09T00:00:00+00:00")

    def test_build_state_tracks_failure_counts(self) -> None:
        previous = {"last_run_at": "", "items": {}, "source_failures": {"travel_alarm:IR": 2}}
        state = build_state(previous, [], ["travel_alarm:IR:timeout"])
        self.assertEqual(state["source_failures"]["travel_alarm:IR"], 3)

    def test_bootstrap_run_suppresses_alerts(self) -> None:
        from unittest.mock import patch
        from pathlib import Path

        item = make_item(content_hash="hash-1")
        config = Config(
            data_go_kr_service_key="x",
            telegram_bot_token="",
            telegram_chat_id="",
            state_path=Path("test-state.json"),
            dry_run=True,
        )
        with patch("src.mofa_monitor.monitor.load_state", return_value={"last_run_at": "", "items": {}, "source_failures": {}}), \
             patch("src.mofa_monitor.monitor.build_state", return_value={"last_run_at": "", "items": {}, "source_failures": {}}), \
             patch("src.mofa_monitor.monitor.save_state"), \
             patch("src.mofa_monitor.monitor.mark_alerted", return_value={"last_run_at": "", "items": {}, "source_failures": {}}), \
             patch("src.mofa_monitor.monitor.send_change") as send_change, \
             patch("src.mofa_monitor.monitor.MofaSourceClient") as client:
            client.return_value.fetch_all.return_value = ([item], [])
            result = run_monitor(config)
        self.assertEqual(result.changes, [])
        send_change.assert_not_called()

    def test_manual_run_without_changes_sends_silent_summary(self) -> None:
        from unittest.mock import patch
        from pathlib import Path

        item = make_item(content_hash="same")
        config = Config(
            data_go_kr_service_key="x",
            telegram_bot_token="",
            telegram_chat_id="",
            state_path=Path("test-state.json"),
            dry_run=True,
            github_event_name="workflow_dispatch",
        )
        previous = {
            "last_run_at": "2026-03-09T00:00:00+00:00",
            "items": {
                item.state_key: {
                    "content_hash": "same",
                    "level": "",
                }
            },
            "source_failures": {},
        }
        with patch("src.mofa_monitor.monitor.load_state", return_value=previous), \
             patch("src.mofa_monitor.monitor.build_state", return_value={"last_run_at": "", "items": {}, "source_failures": {}}), \
             patch("src.mofa_monitor.monitor.save_state"), \
             patch("src.mofa_monitor.monitor.mark_alerted", return_value={"last_run_at": "", "items": {}, "source_failures": {}}), \
             patch("src.mofa_monitor.monitor.send_change") as send_change, \
             patch("src.mofa_monitor.monitor.send_text") as send_text, \
             patch("src.mofa_monitor.monitor.MofaSourceClient") as client:
            client.return_value.fetch_all.return_value = ([item], [])
            run_monitor(config)
        send_change.assert_not_called()
        send_text.assert_called_once()
        self.assertEqual(send_text.call_args.kwargs.get("silent"), True)

    def test_manual_no_change_message_format(self) -> None:
        message = _build_manual_no_change_message(
            [
                make_item(content_hash="x", source="country_safety"),
                MonitorItem(
                    source="travel_alarm",
                    country_code="EG",
                    country_name="이집트",
                    item_id="14",
                    title="이집트 여행경보",
                    published_at="2026-03-09",
                    url="https://example.com",
                    content="본문",
                    content_hash="y",
                    matched_reason=("country:이집트", "api:test"),
                    level="3",
                ),
            ],
            [],
        )
        self.assertIn("수동 점검 완료", message)
        self.assertIn("새로운 정보 없음", message)
        self.assertIn("마지막 확인", message)
        self.assertIn("2개국 (이란, 이집트)", message)
        self.assertIn("- 외교부 안전정보 <b>[CHECKED]</b>", message)
        self.assertIn("- 여행경보 <b>[CHECKED]</b>", message)
        self.assertIn("전 소스 정상 응답", message)

    def test_source_status_label_partial_and_failed(self) -> None:
        self.assertEqual(_source_status_label("country_notice", []), "<b>[CHECKED]</b>")
        self.assertIn("[PARTIAL]", _source_status_label("country_notice", ["country_notice:IR:timeout"]))
        all_failed = [f"travel_alarm:{country.iso2}:timeout" for country in __import__("src.mofa_monitor.config", fromlist=["MONITORED_COUNTRIES"]).MONITORED_COUNTRIES]
        self.assertIn("[FAILED]", _source_status_label("travel_alarm", all_failed))


if __name__ == "__main__":
    unittest.main()
