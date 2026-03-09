# MOFA Monitoring

외교부 `data.go.kr` OpenAPI와 `0404.go.kr` fallback 페이지를 이용해 중동 주요국 안전정보 변화를 감시하고, 변화가 있을 때만 Telegram으로 알리는 모니터입니다.

## What It Watches

- `country_notice`: 국가별 공지사항
- `country_safety`: 국가별 안전정보
- `travel_alarm`: 국가·지역별 여행경보 목록
- `special_travel_alarm`: 국가·지역별 특별여행주의보

감시 대상 국가는 아래 12개로 고정되어 있습니다.

- 이란
- 이집트
- 이라크
- 이스라엘
- 레바논
- 요르단
- 사우디아라비아
- 아랍에미리트
- 카타르
- 쿠웨이트
- 오만
- 바레인

## Required Secrets

- `DATA_GO_KR_SERVICE_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

GitHub Actions에서는 위 세 값을 repository secret으로 등록해야 합니다.

로컬에서는 `.env.example`을 복사해 `.env`를 만들면 자동으로 읽습니다. `.env`는 `.gitignore`에 포함되어 Git에 올라가지 않습니다.

## Local Run

```bash
export DATA_GO_KR_SERVICE_KEY=...
export TELEGRAM_BOT_TOKEN=...
export TELEGRAM_CHAT_ID=...
python3 -m unittest discover -s tests
python3 -m src.mofa_monitor.cli --state-path ./state.json --dry-run
```

`--dry-run`을 빼면 Telegram 발송까지 수행합니다.

## State Storage

상태 파일은 `monitor-state` 브랜치의 `state.json`에 저장되도록 워크플로가 구성되어 있습니다.

주요 필드:

- `source`
- `country_code`
- `item_id`
- `title`
- `published_at`
- `content_hash`
- `last_alerted_hash`
- `url`
- `matched_reason`
- `last_checked_at`

## Workflow Notes

- 스케줄은 KST 기준 매시 `17분`, `47분`입니다.
- GitHub Actions cron은 UTC를 사용하므로 워크플로에는 `17,47 * * * *`를 그대로 사용합니다.
- `monitor-state` 브랜치가 없으면 첫 실행에서 생성합니다.

## Fallback

`data.go.kr` API 실패 시 아래 0404 웹 페이지를 fallback 소스로 사용합니다.

- `https://www.0404.go.kr/bbs/embsyNtc/list`
- `https://www.0404.go.kr/bbs/travelAlertAjmt/list`

fallback은 최소한의 목록 감지만 보장하며, 주 수집 경로는 API입니다.
