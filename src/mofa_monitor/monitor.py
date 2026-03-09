from __future__ import annotations

import html
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from .config import Config, MONITORED_COUNTRIES
from .models import ChangeEvent, MonitorItem, RunResult
from .sources import MofaSourceClient
from .state import build_state, load_state, mark_alerted, save_state
from .telegram import send_change, send_text
from .utils import truncate


def run_monitor(config: Config) -> RunResult:
    previous = load_state(config.state_path)
    current_items, source_errors = MofaSourceClient(config).fetch_all()
    changes = detect_changes(previous.get("items", {}), current_items)
    is_bootstrap = not previous.get("items")
    if is_bootstrap and not config.alert_on_bootstrap:
        changes = []
    next_state = build_state(previous, current_items, source_errors)

    alerted_items: list[MonitorItem] = []
    for change in changes:
        send_change(config, change)
        alerted_items.append(change.item)

    if _should_send_manual_no_change_notice(config, changes):
        send_text(config, _build_manual_no_change_message(current_items, source_errors), silent=True)

    if source_errors:
        send_text(config, _build_source_error_message(next_state.get("source_failures", {}), source_errors))

    final_state = mark_alerted(next_state, alerted_items)
    save_state(config.state_path, final_state)
    return RunResult(changes=changes, source_errors=source_errors, fetched_items=current_items)


def detect_changes(previous_items: dict[str, dict], current_items: list[MonitorItem]) -> list[ChangeEvent]:
    changes: list[ChangeEvent] = []
    for item in current_items:
        previous = previous_items.get(item.state_key)
        if previous is None:
            changes.append(ChangeEvent(kind="new", item=item, summary="신규 항목 감지"))
            continue

        previous_hash = previous.get("content_hash", "")
        previous_level = previous.get("level", "")
        if item.level and previous_level and item.level != previous_level:
            changes.append(
                ChangeEvent(
                    kind="alert-level-changed",
                    item=item,
                    previous_hash=previous_hash,
                    previous_level=previous_level,
                    summary=f"경보단계 변경: {previous_level} -> {item.level}",
                )
            )
            continue

        if item.content_hash != previous_hash:
            changes.append(
                ChangeEvent(
                    kind="updated",
                    item=item,
                    previous_hash=previous_hash,
                    previous_level=previous_level,
                    summary=f"본문 또는 메타데이터 수정: {truncate(item.content, 100)}",
                )
            )
    return changes


def _build_source_error_message(source_failures: dict[str, int], source_errors: list[str]) -> str:
    degraded = []
    for key, count in source_failures.items():
        if count >= 3:
            degraded.append(f"{key}=source degraded")
    lines = [
        "[MOFA Monitor][SOURCE-ERROR]",
        f"오류 건수: {len(source_errors)}",
        "상세:",
        *[f"- {error}" for error in source_errors[:10]],
    ]
    if degraded:
        lines.append("상태: " + ", ".join(degraded))
    return "\n".join(lines)


def _should_send_manual_no_change_notice(config: Config, changes: list[ChangeEvent]) -> bool:
    return config.github_event_name == "workflow_dispatch" and not changes


def _build_manual_no_change_message(items: list[MonitorItem], source_errors: list[str]) -> str:
    country_names = set()
    source_names = set()
    for item in items:
        country_names.add(item.country_name)
        source_names.add(item.source)
    checked_at = datetime.now(timezone.utc).astimezone(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M:%S KST")
    ordered_country_names = sorted(country_names)
    country_summary = f"{len(ordered_country_names)}개국"
    if ordered_country_names:
        country_summary += f" ({', '.join(ordered_country_names)})"
    source_label = {
        "country_notice": "공관공지",
        "country_safety": "외교부 안전정보",
        "travel_alarm": "여행경보",
        "special_travel_alarm": "특별여행주의보",
    }
    ordered_sources = [
        source_label[key]
        for key in ("country_notice", "country_safety", "travel_alarm", "special_travel_alarm")
        if key in source_names
    ]

    lines = [
        "<b>[MOFA Monitor] 수동 점검 완료</b>",
        "<b>결과</b> 새로운 정보 없음",
        f"<b>점검 국가</b> {html.escape(country_summary)}",
        f"<b>마지막 확인</b> {html.escape(checked_at)}",
    ]
    if source_errors:
        lines.append(f"<b>주의</b> 일부 소스 오류 {len(source_errors)}건")
    else:
        lines.append("<b>상태</b> 전 소스 정상 응답")
    if ordered_sources:
        lines.append("<b>점검 소스</b>")
        for key, label in (
            ("country_notice", "공관공지"),
            ("country_safety", "외교부 안전정보"),
            ("travel_alarm", "여행경보"),
            ("special_travel_alarm", "특별여행주의보"),
        ):
            if key not in source_names and not any(error.startswith(f"{key}:") for error in source_errors):
                continue
            lines.append(f"- {html.escape(label)} {_source_status_label(key, source_errors)}")
    return "\n".join(lines)


def _source_status_label(source_key: str, source_errors: list[str]) -> str:
    source_specific = [error for error in source_errors if error.startswith(f"{source_key}:")]
    if not source_specific:
        return "<b>[CHECKED]</b>"

    failed_countries = set()
    for error in source_specific:
        parts = error.split(":", 2)
        if len(parts) >= 2 and parts[1]:
            failed_countries.add(parts[1])

    total_countries = len(MONITORED_COUNTRIES)
    if len(failed_countries) >= total_countries:
        return f"<b>[FAILED]</b> {len(source_specific)}건 오류"
    return f"<b>[PARTIAL]</b> {len(source_specific)}건 오류"
