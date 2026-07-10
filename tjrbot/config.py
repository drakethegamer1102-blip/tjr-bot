"""Configuration: loads .env secrets and config.yaml settings."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent  # trading-bot/

# Every client_order_id prefix the engine has ever written. THE canonical copy —
# engine, execution, and reconcile all import this (2026-07-09: three hand-rolled
# copies had drifted; reconcile's was missing "tjr-", so legacy round-trips never
# reached the journal). "bot-" = legacy single-bot era, "tjr-" = pre-multi-strategy
# era, "apx-"/"rip-" = the APEX and RIPTIDE virtual bots.
BOT_PREFIXES = ("bot-", "tjr-", "apx-", "rip-")


def load_env(path: Path | None = None) -> None:
    """Minimal .env loader (KEY=VALUE per line). Does not overwrite real env vars."""
    path = path or (ROOT / ".env")
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip())


@dataclass
class Settings:
    raw: dict[str, Any]
    alpaca_key: str = ""
    alpaca_secret: str = ""
    alpaca_paper: bool = True
    telegram_token: str = ""
    telegram_chat_id: str = ""

    @property
    def profile_name(self) -> str:
        return self.raw["active_profile"]

    @property
    def profile(self) -> dict[str, Any]:
        return self.raw["profiles"][self.profile_name]

    @property
    def strategy(self) -> dict[str, Any]:
        return self.raw["strategy"]

    def __getitem__(self, key: str) -> Any:
        return self.raw[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.raw.get(key, default)


def load_settings(config_path: Path | None = None) -> Settings:
    load_env()
    config_path = config_path or (ROOT / "config.yaml")
    raw = yaml.safe_load(config_path.read_text())
    return Settings(
        raw=raw,
        alpaca_key=os.environ.get("ALPACA_API_KEY_ID", ""),
        alpaca_secret=os.environ.get("ALPACA_API_SECRET", ""),
        alpaca_paper=os.environ.get("ALPACA_PAPER", "true").lower() == "true",
        telegram_token=os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        telegram_chat_id=os.environ.get("TELEGRAM_CHAT_ID", ""),
    )
