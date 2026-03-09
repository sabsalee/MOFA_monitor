from __future__ import annotations

import html
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from .config import Config
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
    countries = set()
    for item in items:
        countries.add(item.country_code)
    checked_at = datetime.now(timezone.utc).astimezone(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M:%S KST")

    lines = [
        "<b>[MOFA Monitor] 수동 점검 완료</b>",
        "<b>결과</b> 새로운 정보 없음",
        f"<b>점검 국가</b> {len(countries)}개국",
        f"<b>마지막 확인</b> {html.escape(checked_at)}",
    ]
    if source_errors:
        lines.append(f"<b>주의</b> 일부 소스 오류 {len(source_errors)}건")
    else:
        lines.append("<b>상태</b> 전 소스 정상 응답")
    return "\n".join(lines)
