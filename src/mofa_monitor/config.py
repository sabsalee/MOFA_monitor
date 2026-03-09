from __future__ import annotations

import os
import urllib.parse
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CountrySpec:
    name_ko: str
    iso2: str
    iso3: str


MONITORED_COUNTRIES = (
    CountrySpec("이란", "IR", "IRN"),
    CountrySpec("이집트", "EG", "EGY"),
    CountrySpec("이라크", "IQ", "IRQ"),
    CountrySpec("이스라엘", "IL", "ISR"),
    CountrySpec("레바논", "LB", "LBN"),
    CountrySpec("요르단", "JO", "JOR"),
    CountrySpec("사우디아라비아", "SA", "SAU"),
    CountrySpec("아랍에미리트", "AE", "ARE"),
    CountrySpec("카타르", "QA", "QAT"),
    CountrySpec("쿠웨이트", "KW", "KWT"),
    CountrySpec("오만", "OM", "OMN"),
    CountrySpec("바레인", "BH", "BHR"),
)


@dataclass(frozen=True)
class Config:
    data_go_kr_service_key: str
    telegram_bot_token: str
    telegram_chat_id: str
    state_path: Path
    request_timeout_seconds: int = 20
    dry_run: bool = False
    notice_max_pages: int = 3
    safety_max_pages: int = 3
    alert_max_pages: int = 2
    alert_on_bootstrap: bool = False

    @classmethod
    def from_env(cls, state_path: str | Path, dry_run: bool = False) -> "Config":
        _load_dotenv()
        required = ["DATA_GO_KR_SERVICE_KEY"]
        if not dry_run:
            required.extend(["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"])
        missing = [name for name in required if not os.getenv(name)]
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

        return cls(
            data_go_kr_service_key=urllib.parse.unquote(os.environ["DATA_GO_KR_SERVICE_KEY"]),
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
            state_path=Path(state_path),
            dry_run=dry_run,
            alert_on_bootstrap=os.getenv("ALERT_ON_BOOTSTRAP", "").lower() in {"1", "true", "yes"},
        )


def _load_dotenv(path: str | Path = ".env") -> None:
    dotenv_path = Path(path)
    if not dotenv_path.exists():
        return

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)
