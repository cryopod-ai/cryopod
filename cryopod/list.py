"""Cryopod list command - show merged local and remote agent status."""

from pathlib import Path

import click
from rich.box import HEAVY
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from cryopod.config import (
    API_BASE_URL,
    MalformedConfigError,
    load_config,
    require_api_key,
)
from cryopod.formatting import format_size, format_timestamp
from cryopod.manifest import _fetch_all_pods

console = Console()


@click.command()
@click.option(
    "--config",
    default=".cryopod.toml",
    type=click.Path(),
    help="Path to config file",
)
def list_command(config: str) -> None:
    """List agents with merged local and remote status."""
    # Step 1: Validate API key
    api_key = require_api_key()

    # Step 2: Load local config
    config_path = Path(config).resolve()
    try:
        result = load_config(config_path)
    except MalformedConfigError as err:
        raise click.ClickException(
            ".cryopod.toml is malformed. Run `cryopod init` to recreate it."
        ) from err

    local_config = result if result is not None else {}

    # Step 3: Fetch remote pods
    base_url = API_BASE_URL
    remote_pods = _fetch_all_pods(api_key, base_url)

    # Step 4: Merge local and remote
    local_names = set(local_config.get("agents", {}).keys())
    remote_by_name = {pod["name"]: pod for pod in remote_pods}
    all_names = sorted(local_names | remote_by_name.keys())

    # Step 5: Build and render table
    table = Table(show_header=True, show_edge=False, pad_edge=False)
    table.add_column("AGENT", style="bold")
    table.add_column("STATUS")
    table.add_column("LAST FROZEN", style="dim")
    table.add_column("SIZE", style="dim")

    for name in all_names:
        in_local = name in local_names
        in_remote = name in remote_by_name

        if in_local and in_remote:
            status = "[green]Pod Synchronized[/green]"
        elif in_local:
            status = "[red]Pod Awaiting Upload[/red]"
        else:
            status = "[yellow]Pod Awaiting Download[/yellow]"

        pod = remote_by_name.get(name)
        last_frozen = format_timestamp(pod["updated_at"]) if pod else "\u2014"
        size = format_size(pod["file_size"]) if pod else "\u2014"

        table.add_row(name, status, last_frozen, size)

    console.print(Panel(table, box=HEAVY, title="CRYOPOD // LIST"))
