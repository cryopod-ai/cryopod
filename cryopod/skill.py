"""Cryopod skill command - emit markdown CLI reference.

NOTE: When new commands or agents are added to the CLI, update SKILL_MARKDOWN
to keep the reference accurate.
"""

import click

SKILL_MARKDOWN = """\
# Cryopod CLI

Command-line interface for the [cryopod.ai](https://cryopod.ai) agent configuration backup and sync service. Cryopod archives, optionally encrypts, and uploads agent configs directly to the Cryopod API for backup and restore.

## Authentication

Set the `CRYOPOD_API_KEY` environment variable with your API key. It is sent as a Bearer token with every API request.

```bash
export CRYOPOD_API_KEY=<your-api-key>
```

Verify your connection with:

```bash
cryopod status
```

## Environment Variables

| Variable             | Required | Description                                                      |
|----------------------|----------|------------------------------------------------------------------|
| `CRYOPOD_API_KEY`    | Yes      | API key sent as a Bearer token with every request                |
| `CRYOPOD_SECRET_KEY` | No       | Symmetric key for client-side encryption before uploading        |
| `CRYOPOD_API_URL`    | No       | Override the API endpoint (defaults to `https://cryopod.ai`) |

## Encryption

Optionally encrypt your backups by setting the `CRYOPOD_SECRET_KEY` environment variable. This is a symmetric key used for client-side encryption before uploading.

Generate a key with:

```bash
cryopod keygen
```

This prints an export statement you can add to your shell profile. **Save this key somewhere safe** — if you lose it, your encrypted backups cannot be recovered.

## Command Reference

| Command    | Description                                              |
|------------|----------------------------------------------------------|
| `init`     | Initialize a `.cryopod.toml` config in the current directory |
| `freeze`   | Archive and upload agent configs to the remote           |
| `thaw`     | Download and restore agent configs from the remote       |
| `keygen`   | Generate an encryption secret key                        |
| `add`      | Add an agent to the local config                         |
| `remove`   | Remove an agent from the local config                    |
| `update`   | Update an agent's settings in the local config           |
| `manifest` | Show all pods stored on the remote                       |
| `list`     | Show merged local and remote agent status                |
| `status`   | Show account info, quota usage, and config state         |
| `purge`    | Delete a pod from the remote                             |
| `restore`  | Promote an old pod version to become the new latest      |
| `versions` | Show all stored versions of a pod                        |
| `skill`    | Print this markdown CLI reference for AI agents          |

### `cryopod init`

Initialize a `.cryopod.toml` config in the current directory. Interactively discovers known agents and prompts for confirmation.

### `cryopod freeze <agent> [--all] [--config PATH]`

Archive and upload agent configs to the remote. Specify a single agent name or `--all` to freeze every configured agent. Each freeze creates a new version. Credential and secret files are automatically excluded.

### `cryopod thaw <agent> [--all] [--version N] [--no-backup] [--config PATH]`

Download and restore agent configs from the remote. By default restores the latest version. `--version` is mutually exclusive with `--all` — you must specify a single agent name when using `--version`. Existing agent directories are backed up to `<dir>.pre-thaw` unless `--no-backup` is passed.

Thaw a specific version:

```bash
cryopod thaw <agent> --version <N>
```

### `cryopod versions <agent>`

Show all stored versions of a pod with version number, creation date, size, and source. The header displays `(max: N)` when a retention limit is configured for the pod.

### `cryopod restore <agent> <version>`

Promote an older version to become the new latest. The old version's contents are copied to a new version number — no data is deleted.

### `cryopod manifest`

Show all pods stored on the remote with last-frozen date, size, and encryption status.

### `cryopod list [--config PATH]`

Show merged local and remote agent status. Displays which agents are configured locally, which have remote backups, and their sync state.

### `cryopod status [--config PATH]`

Show account info, quota usage, environment variable status, and local config state.

### `cryopod add <name> --directory DIR [--ignore PATTERN]... [--max-versions N] [--config PATH]`

Add a new agent to the local config. Global and known-agent ignore patterns are applied automatically. `--ignore` is repeatable. `--max-versions` sets the maximum number of versions to retain for this agent (1–100). When omitted, the server default applies.

### `cryopod remove <name> [--config PATH]`

Remove an agent from the local config.

### `cryopod update <name> [--directory DIR] [--name NEW] [--ignore PATTERN]... [--max-versions N] [--config PATH]`

Update an existing agent's directory, ignore patterns, name, or version retention limit. At least one option is required. `--max-versions` works the same as in `add` (1–100).

### `cryopod purge <name> [--yes]`

Delete a pod from the remote. Prompts for confirmation unless `--yes`/`-y` is passed.

### `cryopod keygen`

Generate an encryption secret key and print an export statement for your shell profile.

## Configuration

Cryopod stores its project-level configuration in `.cryopod.toml`. Run `cryopod init` to create one interactively, or define it manually:

```toml
[agents.claude]
directory = ".claude"
ignore = ["settings.local.json"]
max_versions = 5

[agents.codex]
directory = ".codex"
ignore = []
```

Each `[agents.<name>]` section defines:
- `directory` — path to the agent's config directory (relative to the project root).
- `ignore` — list of glob patterns for files to exclude from backup.
- `max_versions` *(optional)* — maximum number of versions to retain on the server (1–100). When omitted, the server's default retention policy applies.

## Supported Agents

| Agent    | Config Directory |
|----------|-----------------|
| Claude   | `.claude/`      |
| Codex    | `.codex/`       |
| Cursor   | `.cursor/`      |
| Gemini   | `.gemini/`      |
| OpenCode | `.opencode/`    |
| Windsurf | `.windsurf/`    |"""


@click.command()
def skill_command():
    """Print a markdown CLI reference for AI agents."""
    click.echo(SKILL_MARKDOWN)
