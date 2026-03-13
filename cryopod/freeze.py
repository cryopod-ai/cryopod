"""Cryopod freeze command - archive and upload agent configs."""

import fnmatch
import io
import tarfile
from pathlib import Path

import click
import httpx
from rich.console import Console

from cryopod.agents import CREDENTIAL_IGNORE
from cryopod.api import api_errors, raise_for_status
from cryopod.config import API_BASE_URL, get_secret_key, require_api_key, require_config
from cryopod.crypto import encrypt_archive
from cryopod.formatting import format_size

console = Console()


def _build_archive(agent_dir: Path, ignore_patterns: list[str]) -> bytes:
    """Create a tar.gz archive of agent_dir, honoring ignore patterns.

    Returns the compressed archive as bytes.
    """
    buf = io.BytesIO()

    def _is_ignored(rel_path: str) -> bool:
        """Check if a relative path matches any ignore pattern."""
        parts = Path(rel_path).parts
        for pattern in ignore_patterns:
            # Strip trailing slash for directory patterns
            clean = pattern.rstrip("/")
            # Match against the full relative path and each component
            if fnmatch.fnmatch(rel_path, clean):
                return True
            for part in parts:
                if fnmatch.fnmatch(part, clean):
                    return True
        return False

    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for path in sorted(agent_dir.rglob("*")):
            rel = path.relative_to(agent_dir)
            rel_str = str(rel)
            if _is_ignored(rel_str):
                continue
            tar.add(path, arcname=rel_str)

    return buf.getvalue()


def _upload_pod(
    name: str,
    archive: bytes,
    api_key: str,
    base_url: str,
    max_versions: int | None = None,
) -> dict:
    """Upload an archive to the Cryopod API.

    Step 1: POST to create pod (or PATCH on 409 conflict).
    Step 2: PUT archive bytes to the presigned upload URL.

    Returns the API response data.
    """
    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {"name": name, "file_size": len(archive)}
    if max_versions is not None:
        payload["max_versions"] = max_versions

    with httpx.Client(timeout=60) as client:
        # Step 1: Create or update pod
        resp = client.post(f"{base_url}/api/pods/", json=payload, headers=headers)

        if resp.status_code == 409:
            # Pod already exists, update it
            patch_payload = {"file_size": len(archive)}
            if max_versions is not None:
                patch_payload["max_versions"] = max_versions
            resp = client.patch(
                f"{base_url}/api/pods/{name}/",
                json=patch_payload,
                headers=headers,
            )

        if resp.status_code not in (200, 201):
            raise_for_status(resp)

        data = resp.json()
        upload_url = data["upload_url"]

        # Step 2: Upload archive to presigned URL
        put_resp = client.put(
            upload_url,
            content=archive,
            headers={"Content-Type": "application/gzip"},
        )

        if put_resp.status_code not in (200, 201):
            raise click.ClickException(
                f"Upload failed ({put_resp.status_code}): {put_resp.text}"
            )

    return data


def _freeze_one(
    name: str,
    agent_conf: dict,
    api_key: str,
    base_url: str,
    console: Console,
    config_dir: Path | None = None,
) -> None:
    """Freeze a single agent: archive and upload."""
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

    if not agent_dir.is_dir():
        raise click.ClickException(f"Agent directory does not exist: {directory}")

    ignore_patterns = agent_conf.get("ignore", [])
    # Always enforce credential/secret exclusions at archive time
    ignore_patterns = list(set(ignore_patterns) | set(CREDENTIAL_IGNORE))

    with console.status(f"\u25b8 COMPRESSING {name}...", spinner="dots2"):
        archive = _build_archive(agent_dir, ignore_patterns)

    secret_key = get_secret_key()
    if secret_key:
        console.print(
            "[bold yellow]ENCRYPTION ENABLED. IF YOU LOSE CRYOPOD_SECRET_KEY,"
            " YOUR DATA CANNOT BE RECOVERED.[/bold yellow]"
        )
        with console.status(f"\u25b8 ENCRYPTING {name}...", spinner="dots2"):
            archive = encrypt_archive(archive, secret_key)

    max_versions = agent_conf.get("max_versions")

    with console.status(f"\u25b8 UPLOADING {name}...", spinner="dots2"), api_errors():
        data = _upload_pod(name, archive, api_key, base_url, max_versions=max_versions)

    version = data.get("version")
    size_str = format_size(len(archive))
    if version is not None:
        console.print(
            f"[bold green]\u25b8 FROZEN {name}[/bold green]"
            f" [dim](version {version} \u00b7 {size_str})[/dim]"
        )
    else:
        console.print(
            f"[bold green]\u25b8 FROZEN {name}[/bold green] [dim]({size_str})[/dim]"
        )


@click.command()
@click.argument("agent_name", required=False)
@click.option("--all", "freeze_all", is_flag=True, help="Freeze all agents")
@click.option(
    "--config",
    default=".cryopod.toml",
    type=click.Path(),
    help="Path to config file",
)
def freeze_command(agent_name: str | None, freeze_all: bool, config: str) -> None:
    """Archive and upload agent configs to Cryopod."""
    # Validate mutual exclusivity
    if agent_name and freeze_all:
        raise click.ClickException("Provide either an agent name or --all, not both.")
    if not agent_name and not freeze_all:
        raise click.ClickException("Provide an agent name or use --all.")

    # Check API key first (before any archive work)
    api_key = require_api_key()

    # Load config
    config_path = Path(config).resolve()
    cfg = require_config(config_path)
    agents = cfg.get("agents", {})

    if not agents:
        raise click.ClickException("No agents configured in .cryopod.toml.")

    base_url = API_BASE_URL
    config_dir = config_path.parent

    if freeze_all:
        for name, agent_conf in agents.items():
            _freeze_one(name, agent_conf, api_key, base_url, console, config_dir)
    else:
        if agent_name not in agents:
            raise click.ClickException(
                f"Agent '{agent_name}' not found in .cryopod.toml."
            )
        _freeze_one(
            agent_name, agents[agent_name], api_key, base_url, console, config_dir
        )
