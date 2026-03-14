"""Shared configuration helpers for Cryopod CLI."""

import os
from pathlib import Path

import click
import tomli_w

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


def ensure_agent_in_config(
    config_path: Path,
    name: str,
    directory: str,
    extra_ignore: list[str] | None = None,
    max_versions: int | None = None,
) -> bool:
    """Ensure an agent is recorded in .cryopod.toml.

    If the agent already exists, returns False (no-op).
    If the agent is new, adds it with the canonical ignore list and returns True.
    Creates the config file if it doesn't exist.
    """
    from cryopod.agents import _build_ignore

    data = load_config(config_path)
    if data is None:
        data = {"agents": {}}
    if "agents" not in data:
        data["agents"] = {}

    if name in data["agents"]:
        return False

    # Build ignore list: global + credential + per-agent + extra, deduplicated
    ignore_list = _build_ignore(name) + list(extra_ignore or [])
    ignore_list = list(dict.fromkeys(ignore_list))

    agent_entry: dict = {
        "directory": directory,
        "ignore": ignore_list,
    }
    if max_versions is not None:
        agent_entry["max_versions"] = max_versions
    data["agents"][name] = agent_entry

    with open(config_path, "wb") as f:
        tomli_w.dump(data, f)

    return True
