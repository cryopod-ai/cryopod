"""Cryopod versions command - show all stored versions of a pod."""

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


def _fetch_versions(name: str, api_key: str, base_url: str) -> list[dict]:
    """Fetch all versions for a pod with pagination.

    Returns list of version dicts with fields: version, created_at,
    file_size, source_type.
    """
    headers = {"Authorization": f"Bearer {api_key}"}
    all_items: list[dict] = []
    page = 1
    page_size = 50

    with api_errors(), httpx.Client(timeout=60) as client:
        while True:
            resp = client.get(
                f"{base_url}/api/pods/{name}/versions/",
                params={"page": page, "page_size": page_size},
                headers=headers,
            )

            if resp.status_code != 200:
                raise_for_status(resp, context=f'Pod "{name}"')

            data = resp.json()
            items = data.get("items", [])
            count = data.get("count", 0)
            all_items.extend(items)

            if len(all_items) >= count:
                break

            page += 1

    return all_items


@click.command()
@click.argument("name")
def versions_command(name: str) -> None:
    """Show all stored versions of a pod."""
    # Step 1: Validate API key
    api_key = require_api_key()

    # Step 2: Fetch versions
    base_url = API_BASE_URL
    versions = _fetch_versions(name, api_key, base_url)

    # Step 3: Handle empty result
    if not versions:
        console.print(f'Pod "{name}" has no versions.')
        return

    # Step 4: Sort by version descending (newest first)
    versions_sorted = sorted(versions, key=lambda v: v["version"], reverse=True)

    # Step 5: Build and render table
    table = Table(show_header=True, show_edge=False, pad_edge=False)
    table.add_column("VERSION", style="bold")
    table.add_column("CREATED", style="dim")
    table.add_column("SIZE", style="dim")
    table.add_column("SOURCE", style="dim")

    for ver in versions_sorted:
        version_num = str(ver["version"])
        created = format_timestamp(ver["created_at"])
        size = format_size(ver["file_size"])
        source = ver.get("source_type", "\u2014")

        table.add_row(version_num, created, size, source)

    count = len(versions_sorted)
    title = f"{name} \u2014 {count} version{'s' if count != 1 else ''}"
    console.print(Panel(table, box=HEAVY, title=title))
