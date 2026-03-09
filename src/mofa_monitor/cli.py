from __future__ import annotations

import argparse
import json
import sys

from .config import Config
from .monitor import run_monitor


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Monitor MOFA safety updates.")
    parser.add_argument("--state-path", default="state.json", help="Path to persisted state JSON file.")
    parser.add_argument("--dry-run", action="store_true", help="Print Telegram messages instead of sending them.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        config = Config.from_env(args.state_path, dry_run=args.dry_run)
        result = run_monitor(config)
    except Exception as exc:  # noqa: BLE001
        print(str(exc), file=sys.stderr)
        return 1

    summary = {
        "fetched_items": len(result.fetched_items),
        "changes": len(result.changes),
        "source_errors": result.source_errors,
    }
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
