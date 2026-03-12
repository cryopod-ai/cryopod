"""Shared agent constants and helpers."""

GLOBAL_IGNORE: list[str] = [
    "*.log",
    "__pycache__/",
]

CREDENTIAL_IGNORE: list[str] = [
    ".env",
    ".env.*",
    ".env.local",
    "*.local",
    "*.local.json",
    "*.local.toml",
    "*.local.yaml",
    "*.local.yml",
    "credentials.json",
    "service-account*.json",
    ".secret",
    ".secrets",
    "*.pem",
    "*.key",
]

KNOWN_AGENTS: dict[str, dict] = {
    "claude": {
        "directory": ".claude",
        "ignore": ["settings.local.json"],
    },
    "codex": {
        "directory": ".codex",
        "ignore": [],
    },
    "opencode": {
        "directory": ".opencode",
        "ignore": [],
    },
    "cursor": {
        "directory": ".cursor",
        "ignore": ["mcp.json"],
    },
    "windsurf": {
        "directory": ".windsurf",
        "ignore": [],
    },
    "gemini": {
        "directory": ".gemini",
        "ignore": ["settings.json"],
    },
}


def _build_ignore(agent_name: str) -> list[str]:
    """Build the combined ignore list for an agent (global + per-agent)."""
    per_agent = KNOWN_AGENTS.get(agent_name, {}).get("ignore", [])
    return GLOBAL_IGNORE + CREDENTIAL_IGNORE + per_agent
