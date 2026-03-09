from __future__ import annotations

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
    }
    data = urllib.parse.urlencode(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(request, timeout=config.request_timeout_seconds) as response:
        result = json.loads(response.read().decode("utf-8"))
    if not result.get("ok"):
        raise RuntimeError(f"Telegram send failed: {result}")


def _build_message(event: ChangeEvent) -> str:
    item = event.item
    header = {
        "new": "NEW",
        "updated": "UPDATED",
        "alert-level-changed": "ALERT-LEVEL-CHANGED",
    }[event.kind]
    source_label = {
        "country_notice": "공관공지",
        "country_safety": "외교부 안전정보",
        "travel_alarm": "여행경보",
        "special_travel_alarm": "특별여행주의보",
    }.get(item.source, item.source)
    lines = [f"[MOFA Monitor][{header}] {source_label} | {item.country_name}"]
    lines.append(f"제목: {item.title}")
    lines.append(f"게시: {item.published_at or '-'}")
    if event.kind == "alert-level-changed":
        lines.append(f"단계: {event.previous_level or '?'} -> {item.level or '?'}")
    elif item.level:
        lines.append(f"단계: {item.level}")
    if item.region_type:
        lines.append(f"구역: {item.region_type}")
    detail = item.remark or ""
    if detail:
        lines.append(f"핵심: {truncate(detail, 180)}")
    elif item.content:
        lines.append(f"핵심: {truncate(item.content, 180)}")
    lines.append(f"변경: {event.summary or '-'}")
    lines.append(f"링크: {item.url or '-'}")
    return "\n".join(lines)
