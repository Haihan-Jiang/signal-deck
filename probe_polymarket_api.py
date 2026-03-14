#!/usr/bin/env python3
"""Read-only Polymarket connectivity probe.

This script validates:
- public CLOB connectivity
- wallet-based CLOB auth and API credential derivation
- relayer API key access

It does not create orders.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from polymarket_executor import DEFAULT_ENV_PATH, probe_polymarket_connection


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only Polymarket connectivity probe.")
    parser.add_argument(
        "--env-path",
        type=Path,
        default=DEFAULT_ENV_PATH,
        help="Path to polymarket.env runtime file.",
    )
    parser.add_argument(
        "--persist-api-creds",
        action="store_true",
        help="Persist derived CLOB API creds back into the env file.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = probe_polymarket_connection(
        env_path=args.env_path,
        persist_api_creds=args.persist_api_creds,
    )
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
