"""Cryopod keygen command - generate encryption keys."""

import os
import secrets

import click
from rich.box import HEAVY
from rich.console import Console
from rich.panel import Panel

console = Console(stderr=True)


@click.command()
@click.option(
    "--shell",
    "shell_format",
    type=click.Choice(["bash", "zsh", "fish"]),
    default=None,
    help="Shell format for export statement",
)
def keygen_command(shell_format: str | None) -> None:
    """Generate a secret key for encrypting backups."""
    key = secrets.token_urlsafe(32)

    # Determine shell format
    if shell_format is None:
        detected_shell = os.environ.get("SHELL", "")
        is_fish = "fish" in detected_shell
    else:
        is_fish = shell_format == "fish"

    # Print export statement to stdout (clean for piping)
    if is_fish:
        click.echo(f"set -x CRYOPOD_SECRET_KEY {key}")
    else:
        click.echo(f"export CRYOPOD_SECRET_KEY={key}")

    # Print warning to stderr via Rich
    console.print(
        Panel(
            "[bold]Save this key somewhere safe.[/bold]\n"
            "If you lose it, your encrypted backups cannot be recovered.\n"
            "Each invocation generates a new, unique key.",
            box=HEAVY,
            title="CRYOPOD // WARNING",
            style="bold yellow",
        )
    )
