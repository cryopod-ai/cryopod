"""Cryopod update command - update an existing agent in local config."""

from pathlib import Path

import click
import tomli_w

from cryopod.config import require_config


@click.command()
@click.argument("name")
@click.option(
    "--directory",
    default=None,
    help="New directory path for the agent",
)
@click.option(
    "--name",
    "new_name",
    default=None,
    help="Rename the agent",
)
@click.option(
    "--ignore",
    multiple=True,
    help="Replace ignore patterns (repeatable)",
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
def update_command(
    name: str,
    directory: str | None,
    ignore: tuple[str, ...],
    new_name: str | None,
    max_versions: int | None,
    config: str,
) -> None:
    """Update an existing agent in the local Cryopod config."""
    config_path = Path(config).resolve()

    data = require_config(config_path)

    if name not in data.get("agents", {}):
        raise click.ClickException(f"Agent '{name}' not found in {config_path}.")

    if (
        directory is None
        and len(ignore) == 0
        and new_name is None
        and max_versions is None
    ):
        raise click.ClickException(
            "Nothing to update. Provide --directory, --ignore, --name, and/or --max-versions."
        )

    if new_name is not None:
        if new_name == name:
            raise click.ClickException(
                f"Agent '{new_name}' already exists in {config_path}."
            )
        if new_name in data["agents"]:
            raise click.ClickException(
                f"Agent '{new_name}' already exists in {config_path}."
            )

    changed = []

    if directory is not None:
        data["agents"][name]["directory"] = directory
        changed.append("directory")

    if len(ignore) > 0:
        data["agents"][name]["ignore"] = list(ignore)
        changed.append("ignore")

    if max_versions is not None:
        data["agents"][name]["max_versions"] = max_versions
        changed.append("max_versions")

    if new_name is not None:
        data["agents"][new_name] = data["agents"].pop(name)
        changed.append("name")

    with open(config_path, "wb") as f:
        tomli_w.dump(data, f)

    fields = ", ".join(changed)
    if new_name is not None:
        click.echo(f"Updated agent '{name}' -> '{new_name}' in {config_path}: {fields}")
    else:
        click.echo(f"Updated agent '{name}' in {config_path}: {fields}")
