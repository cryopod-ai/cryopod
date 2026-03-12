"""Cryopod restore command - promote an old pod version to the new latest."""

import click
import httpx
from rich.console import Console

from cryopod.api import api_errors, raise_for_status
from cryopod.config import API_BASE_URL, require_api_key

console = Console()


def _restore_version(name: str, version: int, api_key: str, base_url: str) -> int:
    """Send POST request to restore a pod version.

    Returns the new version number from the API response.
    Raises click.ClickException on any non-success response or network error.
    """
    headers = {"Authorization": f"Bearer {api_key}"}

    with api_errors(), httpx.Client(timeout=60) as client:
        resp = client.post(
            f"{base_url}/api/pods/{name}/versions/{version}/restore/",
            headers=headers,
        )

        if resp.status_code == 200:
            return resp.json()["version"]

        raise_for_status(resp, context=f'Pod "{name}" version {version}')


@click.command()
@click.argument("name")
@click.argument("version", type=click.INT)
def restore_command(name: str, version: int) -> None:
    """Restore an older pod version to become the new latest."""
    if version < 1:
        raise click.ClickException("Version must be a positive integer.")

    api_key = require_api_key()

    new_version = _restore_version(name, version, api_key, API_BASE_URL)

    console.print(
        f"[bold green]\u2713 {name} restored \u2192 version {new_version} "
        f"(from version {version})[/bold green]"
    )
