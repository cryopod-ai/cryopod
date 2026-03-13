# cryopod

[![CI](https://github.com/cryopod-ai/cryopod/actions/workflows/ci.yml/badge.svg)](https://github.com/cryopod-ai/cryopod/actions/workflows/ci.yml)

CLI for the [cryopod.ai](https://cryopod.ai) agent configuration backup and sync service.

Cryopod archives agent configuration directories, optionally encrypts them
client-side, and uploads them to the Cryopod API for backup and cross-machine
sync.

## Installation

Requires Python 3.11 or later.

```bash
pip install cryopod
```

## Quick Start

```bash
# 1. Set your API key
export CRYOPOD_API_KEY=<your-key>

# 2. Initialize a project (discovers agents, creates .cryopod.toml)
cryopod init

# 3. Archive and upload agent configs
cryopod freeze --all

# 4. Download and restore on another machine
cryopod thaw --all
```

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `CRYOPOD_API_KEY` | Yes (for API operations) | Sent as a Bearer token with every API request. Required for `freeze`, `thaw`, `manifest`, `purge`, and `list`. |
| `CRYOPOD_SECRET_KEY` | No | Enables client-side Fernet encryption before upload. Generate one with `cryopod keygen`. **If you lose this key, encrypted pods cannot be recovered.** |

### Project Config

Running `cryopod init` creates a `.cryopod.toml` file in the current directory.
This file tracks which agents are configured for backup in the project. Per-agent
`max_versions` can be set to control how many versions are retained on the server.

## Commands

| Command | Description |
|---------|-------------|
| `add` | Add a new agent to the local Cryopod config. |
| `freeze` | Archive and upload agent configs to Cryopod. |
| `init` | Initialize a new Cryopod project. |
| `keygen` | Generate a secret key for encrypting backups. |
| `list` | List agents with merged local and remote status. |
| `manifest` | Show pods stored on the Cryopod backend. |
| `purge` | Purge a pod from the Cryopod server. |
| `remove` | Remove an agent from the local Cryopod config. |
| `skill` | Print a markdown CLI reference for AI agents. |
| `status` | Show current Cryopod status. |
| `thaw` | Download and restore agent configs from Cryopod. |
| `update` | Update an existing agent in the local Cryopod config. |

The primary workflow is **freeze** (archive and upload) and **thaw** (download
and restore). Together they provide a round-trip backup and sync cycle for your
agent configurations.

Run `cryopod <command> --help` for detailed usage on any command.

## License

[MIT](https://opensource.org/licenses/MIT)
