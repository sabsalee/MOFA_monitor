from __future__ import annotations

import html
import json
import urllib.parse
import urllib.request

from .config import Config
from .models import ChangeEvent
from .utils import truncate


def send_change(config: Config, event: ChangeEvent) -> None:
    send_text(config, _build_message(event))


def send_text(config: Config, message: str) -> None:
    if config.dry_run:
        print(message)
        return

    url = f"https://api.telegram.org/bot{config.telegram_bot_token}/sendMessage"
    payload = {
        "chat_id": config.telegram_chat_id,
        "text": message,
        "disable_web_page_preview": True,
        "parse_mode": "HTML",
    }
    data = urllib.parse.urlencode(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(request, timeout=config.request_timeout_seconds) as response:
        result = json.loads(response.read().decode("utf-8"))
    if not result.get("ok"):
        raise RuntimeError(f"Telegram send failed: {result}")


def _build_message(event: ChangeEvent) -> str:
    item = event.item
    header = _event_label(event.kind, item.source)
    source_label = {
        "country_notice": "공관공지",
        "country_safety": "외교부 안전정보",
        "travel_alarm": "여행경보",
        "special_travel_alarm": "특별여행주의보",
    }.get(item.source, item.source)
    meta_parts = [f"게시 {html.escape(item.published_at or '-')}"]
    if event.kind == "alert-level-changed":
        meta_parts.append(f"단계 {html.escape(event.previous_level or '?')} → {html.escape(item.level or '?')}")
    elif item.level:
        meta_parts.append(f"단계 {html.escape(item.level)}")
    if item.region_type:
        meta_parts.append(f"구역 {html.escape(item.region_type)}")

    detail = item.remark or item.content or ""
    lines = [
        f"<b>[MOFA Monitor] {html.escape(header)}</b>",
        f"<b>{html.escape(item.country_name)} | {html.escape(source_label)}</b>",
        f"<b>제목</b> {html.escape(item.title)}",
        f"<b>정보</b> {' | '.join(meta_parts)}",
    ]
    if detail:
        lines.append(f"<b>요지</b> {html.escape(truncate(detail, 220))}")
    if event.kind != "new":
        lines.append(f"<b>변경</b> {html.escape(event.summary or '-')}")
    if item.url:
        lines.append(f"<b>원문</b> <a href=\"{html.escape(item.url, quote=True)}\">링크 열기</a>")
    else:
        lines.append("<b>원문</b> 링크 없음")
    return "\n".join(lines)


def _event_label(kind: str, source: str) -> str:
    if source == "country_notice":
        return {
            "new": "공관공지 신규",
            "updated": "공관공지 수정",
            "alert-level-changed": "공관공지 단계변경",
        }[kind]
    if source == "country_safety":
        return {
            "new": "외교부 안전정보 신규",
            "updated": "외교부 안전정보 수정",
            "alert-level-changed": "외교부 안전정보 단계변경",
        }[kind]
    if source == "travel_alarm":
        return {
            "new": "여행경보 신규",
            "updated": "여행경보 수정",
            "alert-level-changed": "여행경보 단계변경",
        }[kind]
    if source == "special_travel_alarm":
        return {
            "new": "특별여행주의보 신규",
            "updated": "특별여행주의보 수정",
            "alert-level-changed": "특별여행주의보 단계변경",
        }[kind]
    return kind
