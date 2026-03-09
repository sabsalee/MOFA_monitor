from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class MonitorItem:
    source: str
    country_code: str
    country_name: str
    item_id: str
    title: str
    published_at: str
    url: str
    content: str
    content_hash: str
    matched_reason: tuple[str, ...]
    level: str = ""
    region_type: str = ""

    @property
    def state_key(self) -> str:
        return f"{self.source}:{self.country_code}:{self.item_id}"


@dataclass(frozen=True)
class ChangeEvent:
    kind: str
    item: MonitorItem
    previous_hash: str = ""
    previous_level: str = ""
    summary: str = ""


@dataclass
class RunResult:
    changes: list[ChangeEvent] = field(default_factory=list)
    source_errors: list[str] = field(default_factory=list)
    fetched_items: list[MonitorItem] = field(default_factory=list)

