"""Cryopod manifest command - show remote pod inventory."""

import click
import httpx
from rich.box import HEAVY
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from cryopod.api import api_errors, raise_for_status
from cryopod.config import API_BASE_URL, require_api_key
from cryopod.formatting import format_size, format_timestamp

console = Console()


def _fetch_all_pods(api_key: str, base_url: str) -> list[dict]:
    """Fetch all remote pods with pagination.

    Returns list of pod dicts with fields: name, file_size, version,
    created_at, updated_at.
    """
    headers = {"Authorization": f"Bearer {api_key}"}
    all_items: list[dict] = []
    page = 1
    page_size = 50

    with api_errors(), httpx.Client(timeout=60) as client:
        while True:
            resp = client.get(
                f"{base_url}/api/pods/",
                params={"page": page, "page_size": page_size},
                headers=headers,
            )

            if resp.status_code != 200:
                raise_for_status(resp)

            data = resp.json()
            items = data.get("items", [])
            count = data.get("count", 0)
            all_items.extend(items)

            if len(all_items) >= count:
                break

            page += 1

    return all_items


@click.command()
def manifest_command() -> None:
    """Show pods stored on the Cryopod backend."""
    # Step 1: Validate API key
    api_key = require_api_key()

    # Step 2: Fetch remote pods
    base_url = API_BASE_URL
    remote_pods = _fetch_all_pods(api_key, base_url)

    # Step 3: Build and render table
    table = Table(show_header=True, show_edge=False, pad_edge=False)
    table.add_column("POD", style="bold")
    table.add_column("LAST FROZEN", style="dim")
    table.add_column("SIZE", style="dim")
    table.add_column("ENCRYPTED", style="dim")

    for pod in sorted(remote_pods, key=lambda p: p["name"]):
        last_frozen = format_timestamp(pod["updated_at"])
        size = format_size(pod["file_size"])
        encrypted = "\u2014"

        table.add_row(pod["name"], last_frozen, size, encrypted)

    console.print(Panel(table, box=HEAVY, title="CRYOPOD // MANIFEST"))
