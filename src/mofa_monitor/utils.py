from __future__ import annotations

import hashlib
import html
import re
from typing import Any


TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")


def strip_tags(value: str) -> str:
    return html.unescape(WS_RE.sub(" ", TAG_RE.sub(" ", value or "")).strip())


def normalize_text(value: str) -> str:
    cleaned = strip_tags(value)
    cleaned = cleaned.replace("\u200b", " ")
    cleaned = cleaned.replace("\xa0", " ")
    cleaned = cleaned.replace("•", " ")
    return WS_RE.sub(" ", cleaned).strip()


def compute_hash(*parts: str) -> str:
    raw = "\n".join(normalize_text(part) for part in parts if part)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def pick(data: dict[str, Any], *keys: str, default: str = "") -> str:
    for key in keys:
        value = data.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return default


def normalize_date(value: str) -> str:
    text = normalize_text(value)
    return text.replace(".", "-").replace("/", "-")


def truncate(value: str, limit: int = 220) -> str:
    text = normalize_text(value)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"
