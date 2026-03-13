"""Cryopod add command - add an agent to local config."""

from pathlib import Path

import click
import tomli_w

from cryopod.agents import _build_ignore
from cryopod.config import MalformedConfigError, load_config


@click.command()
@click.argument("name")
@click.option(
    "--directory",
    required=True,
    help="Directory path for the agent config",
)
@click.option(
    "--ignore",
    multiple=True,
    help="Additional ignore pattern (repeatable)",
)
@click.option(
    "--max-versions",
    type=click.IntRange(1, 100),
    default=None,
    help="Maximum number of versions to retain (1–100)",
)
@click.option(
    "--config",
    default=".cryopod.toml",
    type=click.Path(),
    help="Path to config file",
)
def add_command(
    name: str,
    directory: str,
    ignore: tuple[str, ...],
    max_versions: int | None,
    config: str,
) -> None:
    """Add a new agent to the local Cryopod config."""
    config_path = Path(config).resolve()

    # Load existing config or start fresh
    try:
        result = load_config(config_path)
    except MalformedConfigError as err:
        raise click.ClickException(
            f"{config_path} is malformed. Fix the file or run `cryopod init` to recreate it."
        ) from err
    data = {"agents": {}} if result is None else result

    # Ensure agents key exists
    if "agents" not in data:
        data["agents"] = {}

    # Check for duplicate
    if name in data["agents"]:
        raise click.ClickException(
            f"Agent '{name}' already exists in {config_path}. "
            "Use a different name or edit the file directly."
        )

    # Build ignore list: global + known-agent + user-supplied, deduplicated
    ignore_list = _build_ignore(name) + list(ignore)
    ignore_list = list(dict.fromkeys(ignore_list))

    # Add agent entry
    agent_entry: dict = {
        "directory": directory,
        "ignore": ignore_list,
    }
    if max_versions is not None:
        agent_entry["max_versions"] = max_versions
    data["agents"][name] = agent_entry

    # Write config
    with open(config_path, "wb") as f:
        tomli_w.dump(data, f)

    click.echo(f"Added agent '{name}' to {config_path}")
