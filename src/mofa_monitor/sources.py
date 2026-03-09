from __future__ import annotations

import json
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Iterable

from .config import Config, CountrySpec, MONITORED_COUNTRIES
from .fallback import (
    EMBASSY_LIST_URL,
    TRAVEL_LIST_URL,
    fallback_notice_items,
    fallback_travel_items,
    parse_notice_list,
    parse_travel_alert_list,
)
from .models import MonitorItem
from .utils import compute_hash, normalize_date, normalize_text, pick


class SourceFetchError(RuntimeError):
    pass


class MofaSourceClient:
    def __init__(self, config: Config):
        self.config = config

    def fetch_all(self) -> tuple[list[MonitorItem], list[str]]:
        items: list[MonitorItem] = []
        errors: list[str] = []

        for country in MONITORED_COUNTRIES:
            try:
                items.extend(self.fetch_country_notice(country))
            except SourceFetchError as exc:
                errors.append(f"country_notice:{country.iso2}:{exc}")
            try:
                items.extend(self.fetch_country_safety(country))
            except SourceFetchError as exc:
                errors.append(f"country_safety:{country.iso2}:{exc}")
            try:
                items.extend(self.fetch_travel_alarm(country))
            except SourceFetchError as exc:
                errors.append(f"travel_alarm:{country.iso2}:{exc}")
            try:
                items.extend(self.fetch_special_travel_alarm(country))
            except SourceFetchError as exc:
                errors.append(f"special_travel_alarm:{country.iso2}:{exc}")

        deduped = {item.state_key: item for item in items}
        return list(deduped.values()), errors

    def fetch_country_notice(self, country: CountrySpec) -> list[MonitorItem]:
        params = {"isoCode1": country.iso3}
        endpoint = "https://apis.data.go.kr/1262000/CountryNoticeService/getCountryNoticeList"
        items: list[MonitorItem] = []
        try:
            rows = self._fetch_paginated_xml(endpoint, params, self.config.notice_max_pages)
        except SourceFetchError:
            rows = []

        for row in rows:
            item_id = pick(row, "id")
            title = pick(row, "title")
            if not item_id or not title:
                continue
            published_at = normalize_date(pick(row, "wrtDt"))
            url = pick(row, "fileUrl") or f"https://www.0404.go.kr/bbs/embsyNtc/{item_id}/detail"
            content = "\n".join(part for part in (title, pick(row, "fileUrl")) if part)
            items.append(
                MonitorItem(
                    source="country_notice",
                    country_code=country.iso2,
                    country_name=country.name_ko,
                    item_id=item_id,
                    title=title,
                    published_at=published_at,
                    url=url,
                    content=content,
                    content_hash=compute_hash(title, content, published_at),
                    matched_reason=(f"country:{country.name_ko}", "api:country_notice"),
                )
            )

        for item in self._fallback_notice_items(country):
            items.append(item)

        deduped = {item.state_key: item for item in items}
        return list(deduped.values())

    def fetch_country_safety(self, country: CountrySpec) -> list[MonitorItem]:
        endpoint = "https://apis.data.go.kr/1262000/CountrySafetyService/getCountrySafetyList"
        try:
            rows = self._fetch_paginated_xml(endpoint, {"title": country.name_ko}, self.config.safety_max_pages)
        except SourceFetchError:
            raise

        items: list[MonitorItem] = []
        for row in rows:
            if normalize_text(pick(row, "countryName")) != country.name_ko:
                continue
            item_id = pick(row, "id")
            title = pick(row, "title")
            content = pick(row, "content")
            if not item_id or not title:
                continue
            published_at = normalize_date(pick(row, "wrtDt"))
            items.append(
                MonitorItem(
                    source="country_safety",
                    country_code=country.iso2,
                    country_name=country.name_ko,
                    item_id=item_id,
                    title=title,
                    published_at=published_at,
                    url=pick(row, "fileUrl"),
                    content=content,
                    content_hash=compute_hash(title, content, published_at),
                    matched_reason=(f"country:{country.name_ko}", "api:country_safety"),
                )
            )
        return items

    def fetch_travel_alarm(self, country: CountrySpec) -> list[MonitorItem]:
        primary_endpoint = "https://apis.data.go.kr/1262000/TravelAlarmService0404/getTravelAlarm0404List"
        fallback_endpoint = "https://apis.data.go.kr/1262000/CountryHistoryService2/getCountryHistoryList2"
        params = {"cond[country_iso_alp2::EQ]": country.iso2}

        try:
            rows = self._fetch_paginated_json(primary_endpoint, params, self.config.alert_max_pages)
        except SourceFetchError:
            try:
                rows = self._fetch_paginated_json(fallback_endpoint, params, self.config.alert_max_pages)
            except SourceFetchError:
                return self._fallback_travel_items(country)

        return self._build_travel_items(rows, country, source="travel_alarm", api_reason="api:travel_alarm")

    def fetch_special_travel_alarm(self, country: CountrySpec) -> list[MonitorItem]:
        endpoint = "https://apis.data.go.kr/1262000/CountrySptravelAlarmService2/getCountrySptravelAlarmList2"
        params = {"cond[country_iso_alp2::EQ]": country.iso2}
        rows = self._fetch_paginated_json(endpoint, params, self.config.alert_max_pages)

        return self._build_travel_items(
            rows,
            country,
            source="special_travel_alarm",
            api_reason="api:special_travel_alarm",
        )

    def _build_travel_items(
        self,
        rows: Iterable[dict[str, object]],
        country: CountrySpec,
        *,
        source: str,
        api_reason: str,
    ) -> list[MonitorItem]:
        items: list[MonitorItem] = []
        for row in rows:
            country_name = pick(row, "country_nm", "countryName")
            if country_name and country_name != country.name_ko:
                continue
            title = pick(row, "title")
            published_at = normalize_date(pick(row, "wrt_dt", "wrtDt"))
            region_type = pick(row, "region_ty", "regionType", "region_ty_nm")
            level = pick(row, "alarm_lvl", "alarmLvl", "warning_lvl", "warningLvl")
            remark = pick(row, "txt_origin_cn", "alarm_cn", "remark", "content", "withdrawal_rcmd_remark")
            url = pick(row, "file_download_url", "fileUrl")
            item_id = pick(row, "id")
            if not item_id:
                seed = "|".join(
                    [country.iso2, source, title, published_at, region_type, level, remark, url]
                )
                item_id = compute_hash(seed)[:16]
            if not title:
                title = f"{country.name_ko} {source}"
            content = "\n".join(part for part in (title, level, region_type, remark) if part)
            items.append(
                MonitorItem(
                    source=source,
                    country_code=country.iso2,
                    country_name=country.name_ko,
                    item_id=item_id,
                    title=title,
                    published_at=published_at,
                    url=url,
                    content=content,
                    content_hash=compute_hash(title, level, region_type, remark, published_at),
                    matched_reason=(f"country:{country.name_ko}", api_reason),
                    level=level,
                    region_type=region_type,
                    remark=remark,
                )
            )
        return items

    def _fallback_notice_items(self, country: CountrySpec) -> list[MonitorItem]:
        rows: list[dict[str, str]] = []
        for page_index in range(1, self.config.notice_web_max_pages + 1):
            html_text = self._fetch_text(EMBASSY_LIST_URL, {"pageIndex": str(page_index)})
            page_rows = parse_notice_list(html_text)
            if not page_rows:
                break
            rows.extend(page_rows)
        return [item for item in fallback_notice_items(rows) if item.country_code == country.iso2]

    def _fallback_travel_items(self, country: CountrySpec) -> list[MonitorItem]:
        rows: list[dict[str, str]] = []
        for page_index in range(1, self.config.travel_web_max_pages + 1):
            html_text = self._fetch_text(TRAVEL_LIST_URL, {"pageIndex": str(page_index)})
            page_rows = parse_travel_alert_list(html_text)
            if not page_rows:
                break
            rows.extend(page_rows)
        return [item for item in fallback_travel_items(rows) if item.country_code == country.iso2]

    def _fetch_paginated_xml(self, endpoint: str, params: dict[str, str], max_pages: int) -> list[dict[str, str]]:
        all_rows: list[dict[str, str]] = []
        for page in range(1, max_pages + 1):
            page_params = {"serviceKey": self.config.data_go_kr_service_key, "pageNo": str(page), "numOfRows": "50"}
            page_params.update(params)
            root = ET.fromstring(self._fetch_text(endpoint, page_params))
            self._raise_if_xml_error(root)
            rows = self._extract_xml_rows(root)
            if not rows:
                break
            all_rows.extend(rows)
            if len(rows) < 50:
                break
        return all_rows

    def _fetch_paginated_json(self, endpoint: str, params: dict[str, str], max_pages: int) -> list[dict[str, object]]:
        all_rows: list[dict[str, object]] = []
        for page in range(1, max_pages + 1):
            page_params = {
                "serviceKey": self.config.data_go_kr_service_key,
                "returnType": "JSON",
                "page": str(page),
                "perPage": "100",
                "pageNo": str(page),
                "numOfRows": "100",
            }
            page_params.update(params)
            payload = json.loads(self._fetch_text(endpoint, page_params))
            rows = self._extract_json_rows(payload)
            if not rows:
                break
            all_rows.extend(rows)
            if len(rows) < 100:
                break
        return all_rows

    def _fetch_text(self, endpoint: str, params: dict[str, str] | None = None) -> str:
        url = endpoint
        if params:
            query = urllib.parse.urlencode(params, doseq=True)
            url = f"{endpoint}?{query}"
        request = urllib.request.Request(url, headers={"User-Agent": "mofa-monitor/1.0"})
        try:
            with urllib.request.urlopen(request, timeout=self.config.request_timeout_seconds) as response:
                return response.read().decode("utf-8", errors="replace")
        except Exception as exc:  # noqa: BLE001
            raise SourceFetchError(str(exc)) from exc

    @staticmethod
    def _extract_xml_rows(root: ET.Element) -> list[dict[str, str]]:
        items = root.findall(".//item")
        rows: list[dict[str, str]] = []
        for item in items:
            rows.append({child.tag: normalize_text(child.text or "") for child in item})
        return rows

    @staticmethod
    def _extract_json_rows(payload: dict[str, object]) -> list[dict[str, object]]:
        if isinstance(payload.get("data"), list):
            return [row for row in payload["data"] if isinstance(row, dict)]
        response = payload.get("response")
        if isinstance(response, dict):
            body = response.get("body")
            if isinstance(body, dict):
                items = body.get("items")
                if isinstance(items, list):
                    return [row for row in items if isinstance(row, dict)]
                if isinstance(items, dict):
                    item = items.get("item")
                    if isinstance(item, list):
                        return [row for row in item if isinstance(row, dict)]
                    if isinstance(item, dict):
                        return [item]
        return []

    @staticmethod
    def _raise_if_xml_error(root: ET.Element) -> None:
        result_code = root.findtext(".//resultCode", default="")
        result_msg = root.findtext(".//resultMsg", default="")
        if result_code and result_code not in {"00", "0"}:
            raise SourceFetchError(f"{result_code} {result_msg}".strip())
