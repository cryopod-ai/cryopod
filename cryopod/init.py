"""Cryopod init command - interactive project setup."""

import os
from pathlib import Path

import click
import tomli_w
from rich.box import HEAVY
from rich.console import Console
from rich.panel import Panel

from cryopod.agents import KNOWN_AGENTS, _build_ignore
from cryopod.banner import print_banner

console = Console()


def discover_agents(base_path: Path) -> dict[str, Path]:
    """Scan base_path for directories matching known agent configs."""
    found: dict[str, Path] = {}
    for name, entry in KNOWN_AGENTS.items():
        candidate = base_path / entry["directory"]
        if candidate.is_dir():
            found[name] = candidate
    return found


def prompt_agent_config(name: str, directory: str, discovered: bool) -> dict | None:
    """Prompt user to confirm and optionally rename a discovered agent."""
    if discovered:
        include = click.confirm(
            f"Include discovered agent '{name}' ({directory})?", default=True
        )
        if not include:
            return None

    original_name = name
    custom = click.confirm(f"Use custom name instead of '{name}'?", default=False)
    if custom:
        name = click.prompt("Agent name", type=str)

    return {
        "name": name,
        "directory": directory,
        "ignore": _build_ignore(original_name),
    }


def prompt_additional_agents() -> list[dict]:
    """Prompt user to add custom agent directories."""
    agents: list[dict] = []
    while click.confirm("Add another agent directory?", default=False):
        name = click.prompt("Agent name", type=str)
        directory = click.prompt("Directory path", type=str)
        agents.append(
            {
                "name": name,
                "directory": directory,
                "ignore": _build_ignore(name),
            }
        )
    return agents


def write_config(agents: list[dict], config_path: Path) -> None:
    """Write agent configs to a .cryopod.toml file."""
    data: dict = {
        "agents": {
            a["name"]: {
                "directory": a["directory"],
                "ignore": a["ignore"],
            }
            for a in agents
        }
    }
    with open(config_path, "wb") as f:
        tomli_w.dump(data, f)


@click.command()
@click.option(
    "--config",
    default=".cryopod.toml",
    type=click.Path(),
    help="Path to config file",
)
def init_command(config: str) -> None:
    """Initialize a new Cryopod project."""
    print_banner(console)
    config_path = Path(config).resolve()

    # Warn if config already exists
    if config_path.exists():
        console.print(
            Panel(
                f"Config file already exists: {config_path}",
                box=HEAVY,
                title="CRYOPOD // WARNING",
                style="bold yellow",
            )
        )
        click.confirm("Overwrite?", abort=True)

    # Discover agents
    discovered = discover_agents(Path.cwd())
    agents: list[dict] = []

    if discovered:
        console.print("AGENTS DETECTED", style="bold")
        for name, path in discovered.items():
            result = prompt_agent_config(
                name, str(path.relative_to(Path.cwd())), discovered=True
            )
            if result is not None:
                agents.append(result)

    # Prompt for additional agents
    additional = prompt_additional_agents()
    agents.extend(additional)

    # No agents selected
    if not agents:
        console.print(
            "No agents configured. Nothing to write.",
            style="bold yellow",
        )
        return

    # Write config
    write_config(agents, config_path)

    # API key warning
    if not os.environ.get("CRYOPOD_API_KEY"):
        console.print(
            "CRYOPOD_API_KEY not set - you will need this to freeze or thaw pods.",
            style="bold yellow",
        )

    # Success
    console.print(
        Panel(
            f"Initialized {len(agents)} agent(s) in {config_path}",
            box=HEAVY,
            title="CRYOPOD // INIT",
            style="bold green",
        )
    )
