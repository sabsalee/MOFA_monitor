from __future__ import annotations

import re
from urllib.parse import urljoin

from .config import CountrySpec, MONITORED_COUNTRIES
from .models import MonitorItem
from .utils import compute_hash, normalize_date, normalize_text, strip_tags


EMBASSY_LIST_URL = "https://www.0404.go.kr/bbs/embsyNtc/list"
TRAVEL_LIST_URL = "https://www.0404.go.kr/bbs/travelAlertAjmt/list"
BASE_URL = "https://www.0404.go.kr"


ROW_RE = re.compile(r"<tr[^>]*>(?P<body>.*?)</tr>", re.IGNORECASE | re.DOTALL)
CELL_RE = re.compile(r"<t[dh][^>]*>(?P<body>.*?)</t[dh]>", re.IGNORECASE | re.DOTALL)


def parse_notice_list(html: str) -> list[dict[str, str]]:
    return _parse_table_rows(html, "/bbs/embsyNtc/")


def parse_travel_alert_list(html: str) -> list[dict[str, str]]:
    return _parse_table_rows(html, "/bbs/travelAlertAjmt/")


def _parse_table_rows(html: str, href_prefix: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in ROW_RE.findall(html):
        link_match = re.search(
            rf'href="(?P<href>{re.escape(href_prefix)}[^"]+)"[^>]*>(?P<title>.*?)</a>',
            row,
            re.IGNORECASE | re.DOTALL,
        )
        if not link_match:
            continue
        cells = [strip_tags(cell) for cell in CELL_RE.findall(row)]
        if not cells:
            continue
        title = strip_tags(link_match.group("title"))
        rows.append(
            {
                "title": normalize_text(title),
                "url": urljoin(BASE_URL, link_match.group("href")),
                "country": cells[1] if len(cells) > 1 else "",
                "published_at": normalize_date(cells[-1]),
            }
        )
    return rows


def fallback_notice_items(rows: list[dict[str, str]], countries: tuple[CountrySpec, ...] = MONITORED_COUNTRIES) -> list[MonitorItem]:
    items: list[MonitorItem] = []
    country_map = {country.name_ko: country for country in countries}
    for row in rows:
        country = country_map.get(row["country"])
        if not country:
            continue
        content = row["title"]
        items.append(
            MonitorItem(
                source="country_notice",
                country_code=country.iso2,
                country_name=country.name_ko,
                item_id=row["url"].rstrip("/").split("/")[-2],
                title=row["title"],
                published_at=row["published_at"],
                url=row["url"],
                content=content,
                content_hash=compute_hash(row["title"], content, row["published_at"]),
                matched_reason=(f"country:{country.name_ko}", "fallback:web"),
                remark=row["country"],
            )
        )
    return items


def fallback_travel_items(rows: list[dict[str, str]], countries: tuple[CountrySpec, ...] = MONITORED_COUNTRIES) -> list[MonitorItem]:
    items: list[MonitorItem] = []
    country_map = {country.name_ko: country for country in countries}
    for row in rows:
        country = country_map.get(row["country"])
        if not country:
            continue
        content = row["title"]
        items.append(
            MonitorItem(
                source="travel_alarm",
                country_code=country.iso2,
                country_name=country.name_ko,
                item_id=row["url"].rstrip("/").split("/")[-2],
                title=row["title"],
                published_at=row["published_at"],
                url=row["url"],
                content=content,
                content_hash=compute_hash(row["title"], content, row["published_at"]),
                matched_reason=(f"country:{country.name_ko}", "fallback:web"),
                remark=row["country"],
            )
        )
    return items
