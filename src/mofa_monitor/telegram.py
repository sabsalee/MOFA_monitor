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
        "new": "[MOFA Monitor][NEW]",
        "updated": "[MOFA Monitor][UPDATED]",
        "alert-level-changed": "[MOFA Monitor][ALERT-LEVEL-CHANGED]",
    }[event.kind]
    lines = [
        header,
        f"국가: {item.country_name} ({item.country_code})",
        f"소스: {item.source}",
        f"제목: {item.title}",
        f"작성일: {item.published_at or '-'}",
        f"변화: {event.summary or '-'}",
        f"매칭사유: {', '.join(item.matched_reason) or '-'}",
        f"링크: {item.url or '-'}",
    ]
    snippet = truncate(item.content, 240)
    if snippet:
        lines.append(f"요약: {snippet}")
    return "\n".join(lines)
