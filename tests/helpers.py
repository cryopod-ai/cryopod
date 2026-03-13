"""Shared test helpers for cryopod CLI tests."""

from pathlib import Path


def write_config(path: Path, agents: dict) -> None:
    """Write a .cryopod.toml config file."""
    import tomli_w

    entries = {}
    for name, info in agents.items():
        entry = {"directory": info["directory"], "ignore": info.get("ignore", [])}
        if "max_versions" in info:
            entry["max_versions"] = info["max_versions"]
        entries[name] = entry
    data = {"agents": entries}
    with open(path, "wb") as f:
        tomli_w.dump(data, f)


def read_toml(path: Path) -> dict:
    """Read and parse a TOML file."""
    try:
        import tomllib
    except ModuleNotFoundError:
        import tomli as tomllib

    with open(path, "rb") as f:
        return tomllib.load(f)


def make_mock_httpx_client():
    """Create a mock httpx.Client with context manager support.

    Returns (mock_client, mock_context) where mock_context is suitable
    for patching httpx.Client as a return value.
    """
    from unittest.mock import MagicMock

    mock_client = MagicMock()
    mock_context = MagicMock()
    mock_context.__enter__ = MagicMock(return_value=mock_client)
    mock_context.__exit__ = MagicMock(return_value=False)
    return mock_client, mock_context
