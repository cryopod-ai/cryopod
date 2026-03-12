"""Cryopod purge command - remove pods from the server."""

import click
import httpx
from rich.console import Console

from cryopod.api import api_errors, raise_for_status
from cryopod.config import API_BASE_URL, require_api_key

console = Console()


def _purge_pod(name: str, api_key: str, base_url: str) -> None:
    """Send DELETE request to remove a pod by name.

    Raises click.ClickException on any non-success response or network error.
    """
    headers = {"Authorization": f"Bearer {api_key}"}

    with api_errors(), httpx.Client(timeout=60) as client:
        resp = client.delete(f"{base_url}/api/pods/{name}/", headers=headers)

        if resp.status_code in (200, 204):
            return

        raise_for_status(resp, context=f'Pod "{name}"')


@click.command()
@click.argument("name")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
def purge_command(name: str, yes: bool) -> None:
    """Purge a pod from the Cryopod server."""
    api_key = require_api_key()

    if not yes:
        click.confirm(f'Purge pod "{name}"?', default=False, abort=True)

    _purge_pod(name, api_key, API_BASE_URL)

    console.print(f"[bold green]PURGED {name}[/bold green]")
