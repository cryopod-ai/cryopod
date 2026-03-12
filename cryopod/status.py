"""Cryopod status command - show current config and API key status."""

import os
from pathlib import Path

import click
import httpx
from rich.box import HEAVY
from rich.console import Console
from rich.panel import Panel

from cryopod.banner import print_banner
from cryopod.config import API_BASE_URL, MalformedConfigError, load_config

console = Console()


def _fetch_account_info(api_key: str) -> dict | None:
    """Fetch account info from the API. Returns None on any failure."""
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(
                f"{API_BASE_URL}/api/auth/me",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            if resp.status_code == 200:
                return resp.json()
            return None
    except Exception:
        return None


@click.command()
@click.option(
    "--config",
    default=".cryopod.toml",
    type=click.Path(),
    help="Path to config file",
)
def status_command(config: str) -> None:
    """Show current Cryopod status."""
    print_banner(console)
    config_path = Path(config).resolve()
    sections: list[str] = []

    # Account section (only when API key is set)
    api_key = os.environ.get("CRYOPOD_API_KEY", "")
    if api_key:
        account = _fetch_account_info(api_key)
        if account is not None:
            username = account.get("username", "unknown")
            email = account.get("email", "")
            if email:
                sections.append(f"Account: {username} ({email})")
            else:
                sections.append(f"Account: {username}")

            total_usage = account.get("total_usage")
            available = account.get("available")
            sections.append(
                f"Total Usage: {total_usage}"
                if total_usage is not None
                else "Total Usage: —"
            )
            sections.append(
                f"Available: {available}" if available is not None else "Available: —"
            )
        else:
            sections.append(
                "Account: [bold yellow]could not fetch account info[/bold yellow]"
            )

    # Env vars section
    if api_key:
        sections.append("[bold green]CRYOPOD_API_KEY: SET[/bold green]")
    else:
        sections.append("[bold yellow]CRYOPOD_API_KEY: NOT SET[/bold yellow]")

    secret_key = os.environ.get("CRYOPOD_SECRET_KEY", "")
    if secret_key:
        sections.append("[bold green]CRYOPOD_SECRET_KEY: SET[/bold green]")
    else:
        sections.append("[bold yellow]CRYOPOD_SECRET_KEY: NOT SET[/bold yellow]")

    # Agents/pods section
    malformed = False
    try:
        result = load_config(config_path)
    except MalformedConfigError:
        malformed = True
        result = None

    if malformed:
        sections.append(
            "[bold red]CONFIG ERROR[/bold red] — .cryopod.toml is malformed"
        )
    elif result is None:
        sections.append(
            "[bold yellow]NO CONFIG FOUND[/bold yellow] — run [bold]cryopod init[/bold]"
        )
    # Render
    body = "\n".join(sections)
    console.print(Panel(body, box=HEAVY, title="CRYOPOD // STATUS"))
