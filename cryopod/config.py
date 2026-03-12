"""Shared configuration helpers for Cryopod CLI."""

import os
from pathlib import Path

import click

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

API_BASE_URL = os.environ.get("CRYOPOD_API_URL", "https://cryopod.ai")


class MalformedConfigError(click.ClickException):
    """Raised when .cryopod.toml cannot be parsed."""

    def __init__(self, path: str = ".cryopod.toml"):
        super().__init__(f"{path} is malformed. Run `cryopod init` to recreate it.")


def load_config(config_path: Path) -> dict | None:
    """Read and parse .cryopod.toml. Returns None if file missing."""
    if not config_path.exists():
        return None
    try:
        with open(config_path, "rb") as f:
            return tomllib.load(f)
    except tomllib.TOMLDecodeError as err:
        raise MalformedConfigError(str(config_path)) from err


def require_config(config_path: Path) -> dict:
    """Load config, raising ClickException if missing or malformed."""
    result = load_config(config_path)
    if result is None:
        raise click.ClickException("No .cryopod.toml found. Run `cryopod init` first.")
    return result


def get_secret_key() -> str | None:
    """Read CRYOPOD_SECRET_KEY from env. Returns None if unset or empty."""
    key = os.environ.get("CRYOPOD_SECRET_KEY", "")
    return key if key else None


def require_api_key() -> str:
    """Read CRYOPOD_API_KEY from env, raising ClickException if missing."""
    api_key = os.environ.get("CRYOPOD_API_KEY", "")
    if not api_key:
        raise click.ClickException(
            "CRYOPOD_API_KEY is not set. Export it before running freeze."
        )
    return api_key
