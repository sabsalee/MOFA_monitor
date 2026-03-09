from __future__ import annotations

import json
import unittest
import xml.etree.ElementTree as ET

from src.mofa_monitor.fallback import fallback_notice_items, parse_notice_list, parse_travel_alert_list
from src.mofa_monitor.sources import MofaSourceClient


NOTICE_XML = """
<response>
  <body>
    <items>
      <item>
        <id>74</id>
        <title>이란 현지 시위 관련 안전공지</title>
        <wrtDt>2026-03-08</wrtDt>
        <fileUrl>https://example.com/notice.pdf</fileUrl>
      </item>
    </items>
  </body>
</response>
""".strip()

SAFETY_XML = """
<response>
  <body>
    <items>
      <item>
        <id>13</id>
        <countryName>이집트</countryName>
        <title>카이로 대규모 집회 예고</title>
        <content>도심 이동을 자제하시기 바랍니다.</content>
        <wrtDt>2026-03-09</wrtDt>
      </item>
    </items>
  </body>
</response>
""".strip()

TRAVEL_JSON = {
    "data": [
        {
            "country_nm": "이란",
            "country_iso_alp2": "IR",
            "title": "이란 전역 특별여행주의보 발령",
            "alarm_lvl": "특별여행주의보",
            "region_ty": "전지역",
            "txt_origin_cn": "긴급용무가 아닌 한 여행 취소 또는 연기 권고",
            "wrt_dt": "2026-03-09",
            "id": "TA-1",
            "file_download_url": "https://0404.go.kr/example",
        }
    ]
}

FALLBACK_NOTICE_HTML = """
<table>
  <tr>
    <td>101</td>
    <td>이집트</td>
    <td><a href="/bbs/embsyNtc/1342395/detail?ntnCd=302">카이로 시위 관련 안전공지</a></td>
    <td></td>
    <td>2026-03-09</td>
  </tr>
</table>
""".strip()

FALLBACK_TRAVEL_HTML = """
<table>
  <tr>
    <td>공지</td>
    <td>이란</td>
    <td><a href="/bbs/travelAlertAjmt/ATC0000000047791/detail">이란 특별여행주의보 발령</a></td>
    <td></td>
    <td>2026-03-09</td>
  </tr>
</table>
""".strip()


class ParserTests(unittest.TestCase):
    def test_extract_xml_rows_for_notice(self) -> None:
        rows = MofaSourceClient._extract_xml_rows(ET.fromstring(NOTICE_XML))
        self.assertEqual(rows[0]["id"], "74")
        self.assertEqual(rows[0]["title"], "이란 현지 시위 관련 안전공지")

    def test_extract_xml_rows_for_safety(self) -> None:
        rows = MofaSourceClient._extract_xml_rows(ET.fromstring(SAFETY_XML))
        self.assertEqual(rows[0]["countryName"], "이집트")
        self.assertIn("도심 이동", rows[0]["content"])

    def test_extract_json_rows_for_travel_alarm(self) -> None:
        rows = MofaSourceClient._extract_json_rows(json.loads(json.dumps(TRAVEL_JSON)))
        self.assertEqual(rows[0]["country_nm"], "이란")
        self.assertEqual(rows[0]["alarm_lvl"], "특별여행주의보")

    def test_parse_notice_fallback_html(self) -> None:
        rows = parse_notice_list(FALLBACK_NOTICE_HTML)
        items = fallback_notice_items(rows)
        self.assertEqual(items[0].country_code, "EG")
        self.assertIn("fallback:web", items[0].matched_reason)

    def test_parse_travel_fallback_html(self) -> None:
        rows = parse_travel_alert_list(FALLBACK_TRAVEL_HTML)
        self.assertEqual(rows[0]["country"], "이란")
        self.assertEqual(rows[0]["title"], "이란 특별여행주의보 발령")


if __name__ == "__main__":
    unittest.main()
