"""Cryopod thaw command - download and restore agent configs."""

import io
import shutil
import tarfile
from pathlib import Path

import click
import httpx
from rich.console import Console

from cryopod.api import api_errors, raise_for_status
from cryopod.config import API_BASE_URL, get_secret_key, require_api_key, require_config
from cryopod.crypto import decrypt_archive, is_encrypted
from cryopod.formatting import format_size

console = Console()


def _download_pod(
    name: str, api_key: str, base_url: str, version: int | None = None
) -> bytes:
    """Download an archive from the Cryopod API.

    Step 1: GET /api/pods/{name}/download/ with Bearer auth -> JSON with download_url.
    Step 2: GET download_url -> archive bytes.

    Returns the archive bytes.
    """
    headers = {"Authorization": f"Bearer {api_key}"}

    with httpx.Client(timeout=120) as client:
        params = {}
        if version is not None:
            params["version"] = version

        resp = client.get(
            f"{base_url}/api/pods/{name}/download/", headers=headers, params=params
        )

        if resp.status_code == 404:
            if version is not None:
                raise click.ClickException(f"Pod '{name}' version {version} not found.")
            raise click.ClickException(f"Pod '{name}' not found.")

        if resp.status_code not in (200, 201):
            raise_for_status(resp)

        data = resp.json()
        download_url = data["download_url"]

        dl_resp = client.get(download_url)

        if dl_resp.status_code not in (200, 201):
            raise click.ClickException(
                f"Download failed ({dl_resp.status_code}): {dl_resp.text}"
            )

    return dl_resp.content


def _extract_archive(archive_bytes: bytes, target_dir: Path) -> None:
    """Extract tar.gz bytes into target_dir."""
    target_dir.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO(archive_bytes)
    with tarfile.open(fileobj=buf, mode="r:gz") as tar:
        tar.extractall(path=target_dir, filter="data")


def _thaw_one(
    name: str,
    agent_conf: dict,
    api_key: str,
    base_url: str,
    console: Console,
    config_dir: Path | None = None,
    no_backup: bool = False,
    version: int | None = None,
) -> None:
    """Thaw a single agent: download, decrypt, backup, and extract."""
    directory = agent_conf.get("directory", "")
    if not directory:
        raise click.ClickException(
            f"Agent '{name}' has no directory configured in .cryopod.toml."
        )

    agent_dir = Path(directory)
    # Resolve relative paths against the config file's directory
    if not agent_dir.is_absolute() and config_dir is not None:
        agent_dir = config_dir / agent_dir
    agent_dir = agent_dir.resolve()

    # Download
    version_label = f" (version {version})" if version is not None else ""
    with (
        console.status(f"\u25b8 DOWNLOADING {name}{version_label}...", spinner="dots2"),
        api_errors(),
    ):
        archive_bytes = _download_pod(name, api_key, base_url, version=version)

    # Detect encryption and decrypt if needed
    if is_encrypted(archive_bytes):
        secret_key = get_secret_key()
        if not secret_key:
            raise click.ClickException(
                "Archive is encrypted but CRYOPOD_SECRET_KEY is not set. "
                "Export it before running thaw."
            )
        with console.status(f"\u25b8 DECRYPTING {name}...", spinner="dots2"):
            archive_bytes = decrypt_archive(archive_bytes, secret_key)

    # Backup existing directory
    if not no_backup and agent_dir.is_dir():
        backup_dir = Path(str(agent_dir) + ".pre-thaw")
        if backup_dir.exists():
            console.print(f"[yellow]Removing existing backup: {backup_dir}[/yellow]")
            shutil.rmtree(backup_dir)
        shutil.move(str(agent_dir), str(backup_dir))

    # Extract
    with console.status(f"\u25b8 EXTRACTING {name}...", spinner="dots2"):
        _extract_archive(archive_bytes, agent_dir)

    size_str = format_size(len(archive_bytes))
    console.print(
        f"[bold green]\u25b8 THAWED {name}{version_label}[/bold green] [dim]({size_str})[/dim]"
    )


@click.command()
@click.argument("agent_name", required=False)
@click.option("--all", "thaw_all", is_flag=True, help="Thaw all agents")
@click.option(
    "--config",
    default=".cryopod.toml",
    type=click.Path(),
    help="Path to config file",
)
@click.option(
    "--no-backup",
    is_flag=True,
    help="Skip pre-thaw backup of existing agent directory",
)
@click.option(
    "--version",
    "pod_version",
    type=click.IntRange(min=1),
    default=None,
    help="Thaw a specific version of the pod",
)
def thaw_command(
    agent_name: str | None,
    thaw_all: bool,
    config: str,
    no_backup: bool,
    pod_version: int | None,
) -> None:
    """Download and restore agent configs from Cryopod."""
    # Validate mutual exclusivity
    if agent_name and thaw_all:
        raise click.ClickException("Provide either an agent name or --all, not both.")
    if not agent_name and not thaw_all:
        raise click.ClickException("Provide an agent name or use --all.")

    if pod_version is not None and thaw_all:
        raise click.ClickException(
            "Cannot specify --version with --all. Thaw a specific agent instead."
        )
    if pod_version is not None and agent_name is None:
        raise click.ClickException("--version requires a specific agent name.")

    # Check API key first
    api_key = require_api_key()

    # Load config
    config_path = Path(config).resolve()
    cfg = require_config(config_path)
    agents = cfg.get("agents", {})

    if not agents:
        raise click.ClickException("No agents configured in .cryopod.toml.")

    base_url = API_BASE_URL
    config_dir = config_path.parent

    if thaw_all:
        for name, agent_conf in agents.items():
            _thaw_one(
                name, agent_conf, api_key, base_url, console, config_dir, no_backup
            )
    else:
        if agent_name not in agents:
            raise click.ClickException(
                f"Agent '{agent_name}' not found in .cryopod.toml."
            )
        _thaw_one(
            agent_name,
            agents[agent_name],
            api_key,
            base_url,
            console,
            config_dir,
            no_backup,
            version=pod_version,
        )
