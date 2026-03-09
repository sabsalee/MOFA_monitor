from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .models import MonitorItem


def load_state(path: Path) -> dict:
    if not path.exists():
        return {"last_run_at": "", "items": {}, "source_failures": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def build_state(previous: dict, items: list[MonitorItem], source_errors: list[str]) -> dict:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    previous_items = previous.get("items", {})
    previous_failures = previous.get("source_failures", {})
    next_items: dict[str, dict] = {}
    changed = False
    for item in items:
        prior = previous_items.get(item.state_key, {})
        next_entry = {
            "source": item.source,
            "country_code": item.country_code,
            "country_name": item.country_name,
            "item_id": item.item_id,
            "title": item.title,
            "published_at": item.published_at,
            "content_hash": item.content_hash,
            "last_alerted_hash": prior.get("last_alerted_hash", ""),
            "url": item.url,
            "matched_reason": list(item.matched_reason),
            "last_checked_at": prior.get("last_checked_at", now),
            "level": item.level,
            "region_type": item.region_type,
        }
        comparable_prior = {key: prior.get(key) for key in next_entry if key != "last_checked_at"}
        comparable_next = {key: next_entry.get(key) for key in next_entry if key != "last_checked_at"}
        if comparable_prior != comparable_next:
            next_entry["last_checked_at"] = now
            changed = True
        next_items[item.state_key] = next_entry

    if set(previous_items) != set(next_items):
        changed = True

    for key, prior in previous_items.items():
        if key in next_items:
            continue
        if _is_recent(prior.get("last_checked_at", ""), days=14):
            next_items[key] = prior

    source_failures = _merge_failure_counts(previous_failures, source_errors)
    if previous_failures != source_failures:
        changed = True

    return {
        "last_run_at": now if changed else previous.get("last_run_at", ""),
        "items": next_items,
        "source_failures": source_failures,
    }


def mark_alerted(state: dict, alerted_items: list[MonitorItem]) -> dict:
    items = state.get("items", {})
    for item in alerted_items:
        key = item.state_key
        if key in items:
            items[key]["last_alerted_hash"] = item.content_hash
    return state


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _merge_failure_counts(previous_failures: dict[str, int], source_errors: list[str]) -> dict[str, int]:
    next_failures: dict[str, int] = {}
    error_keys = {error.rsplit(":", 1)[0] for error in source_errors}
    for key in error_keys:
        next_failures[key] = int(previous_failures.get(key, 0)) + 1
    return next_failures


def _is_recent(value: str, days: int) -> bool:
    if not value:
        return False
    try:
        checked_at = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return checked_at >= datetime.now(timezone.utc) - timedelta(days=days)
