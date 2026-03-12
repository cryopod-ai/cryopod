"""Cryopod remove command - remove an agent from local config."""

from pathlib import Path

import click
import tomli_w

from cryopod.config import require_config


@click.command()
@click.argument("name")
@click.option(
    "--config",
    default=".cryopod.toml",
    type=click.Path(),
    help="Path to config file",
)
def remove_command(name: str, config: str) -> None:
    """Remove an agent from the local Cryopod config."""
    config_path = Path(config).resolve()

    data = require_config(config_path)

    if name not in data.get("agents", {}):
        raise click.ClickException(f"Agent '{name}' not found in {config_path}.")

    del data["agents"][name]

    with open(config_path, "wb") as f:
        tomli_w.dump(data, f)

    click.echo(f"Removed agent '{name}' from {config_path}")
