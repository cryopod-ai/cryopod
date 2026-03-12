"""Tests for the cryopod init command."""

from click.testing import CliRunner

from cryopod.cli import cli
from tests.helpers import read_toml


class TestDiscovery:
    """Tests for agent auto-discovery."""

    def test_discovers_known_dirs(self, tmp_path, monkeypatch):
        """Auto-discovery finds .claude and .codex dirs."""
        (tmp_path / ".claude").mkdir()
        (tmp_path / ".codex").mkdir()
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        # Confirm claude (y), no custom name (n),
        # Confirm codex (y), no custom name (n),
        # No additional agents (n)
        result = runner.invoke(cli, ["init"], input="y\nn\ny\nn\nn\n")

        assert result.exit_code == 0
        config = read_toml(tmp_path / ".cryopod.toml")
        assert "claude" in config["agents"]
        assert "codex" in config["agents"]
        assert config["agents"]["claude"]["directory"] == ".claude"
        assert config["agents"]["codex"]["directory"] == ".codex"

    def test_skips_missing_dirs(self, tmp_path, monkeypatch):
        """No agent dirs exist - prompts for custom agents."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        # No additional agents (n)
        result = runner.invoke(cli, ["init"], input="n\n")

        assert result.exit_code == 0
        assert not (tmp_path / ".cryopod.toml").exists()
        assert "No agents configured" in result.output

    def test_file_not_dir_ignored(self, tmp_path, monkeypatch):
        """A file named .claude (not a dir) is not discovered."""
        (tmp_path / ".claude").write_text("not a directory")
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        # No additional agents (n)
        result = runner.invoke(cli, ["init"], input="n\n")

        assert result.exit_code == 0
        assert "AGENTS DETECTED" not in result.output


class TestOpenCodeDiscovery:
    """Tests for OpenCode agent discovery."""

    def test_discovers_opencode_dir(self, tmp_path, monkeypatch):
        """Auto-discovery finds .opencode dir and writes it to config."""
        (tmp_path / ".opencode").mkdir()
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        # Confirm opencode (y), no custom name (n), no additional agents (n)
        result = runner.invoke(cli, ["init"], input="y\nn\nn\n")

        assert result.exit_code == 0
        config = read_toml(tmp_path / ".cryopod.toml")
        assert "opencode" in config["agents"]
        assert config["agents"]["opencode"]["directory"] == ".opencode"

    def test_opencode_no_dir_no_prompt(self, tmp_path, monkeypatch):
        """No opencode prompt when .opencode dir does not exist."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        # No additional agents (n)
        result = runner.invoke(cli, ["init"], input="n\n")

        assert result.exit_code == 0
        assert "opencode" not in result.output

    def test_discovers_all_three_agents(self, tmp_path, monkeypatch):
        """All three known agents are discovered when their dirs exist."""
        (tmp_path / ".claude").mkdir()
        (tmp_path / ".codex").mkdir()
        (tmp_path / ".opencode").mkdir()
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        # Confirm claude (y), no custom name (n),
        # Confirm codex (y), no custom name (n),
        # Confirm opencode (y), no custom name (n),
        # No additional agents (n)
        result = runner.invoke(cli, ["init"], input="y\nn\ny\nn\ny\nn\nn\n")

        assert result.exit_code == 0
        config = read_toml(tmp_path / ".cryopod.toml")
        assert "claude" in config["agents"]
        assert "codex" in config["agents"]
        assert "opencode" in config["agents"]

    def test_opencode_gets_only_global_ignore(self, tmp_path, monkeypatch):
        """OpenCode agent gets global ignores but no agent-specific ignores."""
        (tmp_path / ".opencode").mkdir()
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        # Confirm opencode (y), no custom name (n), no additional agents (n)
        result = runner.invoke(cli, ["init"], input="y\nn\nn\n")

        assert result.exit_code == 0
        config = read_toml(tmp_path / ".cryopod.toml")
        ignore = config["agents"]["opencode"]["ignore"]
        assert "*.log" in ignore
        assert "__pycache__/" in ignore
        assert "settings.local.json" not in ignore


class TestCursorWindsurfGeminiDiscovery:
    """Tests for Cursor, Windsurf, and Gemini CLI agent discovery."""

    def test_discovers_cursor_dir(self, tmp_path, monkeypatch):
        """Auto-discovery finds .cursor dir and writes it to config."""
        (tmp_path / ".cursor").mkdir()
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        # Confirm cursor (y), no custom name (n), no additional agents (n)
        result = runner.invoke(cli, ["init"], input="y\nn\nn\n")

        assert result.exit_code == 0
        config = read_toml(tmp_path / ".cryopod.toml")
        assert "cursor" in config["agents"]
        assert config["agents"]["cursor"]["directory"] == ".cursor"

    def test_discovers_windsurf_dir(self, tmp_path, monkeypatch):
        """Auto-discovery finds .windsurf dir and writes it to config."""
        (tmp_path / ".windsurf").mkdir()
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        # Confirm windsurf (y), no custom name (n), no additional agents (n)
        result = runner.invoke(cli, ["init"], input="y\nn\nn\n")

        assert result.exit_code == 0
        config = read_toml(tmp_path / ".cryopod.toml")
        assert "windsurf" in config["agents"]
        assert config["agents"]["windsurf"]["directory"] == ".windsurf"

    def test_discovers_gemini_dir(self, tmp_path, monkeypatch):
        """Auto-discovery finds .gemini dir and writes it to config."""
        (tmp_path / ".gemini").mkdir()
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        # Confirm gemini (y), no custom name (n), no additional agents (n)
        result = runner.invoke(cli, ["init"], input="y\nn\nn\n")

        assert result.exit_code == 0
        config = read_toml(tmp_path / ".cryopod.toml")
        assert "gemini" in config["agents"]
        assert config["agents"]["gemini"]["directory"] == ".gemini"

    def test_cursor_ignore_includes_mcp_json(self, tmp_path, monkeypatch):
        """Cursor agent includes mcp.json in its ignore list."""
        (tmp_path / ".cursor").mkdir()
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        result = runner.invoke(cli, ["init"], input="y\nn\nn\n")

        assert result.exit_code == 0
        config = read_toml(tmp_path / ".cryopod.toml")
        ignore = config["agents"]["cursor"]["ignore"]
        assert "mcp.json" in ignore
        assert "*.log" in ignore
        assert "__pycache__/" in ignore
        assert "settings.local.json" not in ignore
        assert "settings.json" not in ignore

    def test_windsurf_gets_only_global_ignore(self, tmp_path, monkeypatch):
        """Windsurf agent gets global ignores but no agent-specific ignores."""
        (tmp_path / ".windsurf").mkdir()
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        result = runner.invoke(cli, ["init"], input="y\nn\nn\n")

        assert result.exit_code == 0
        config = read_toml(tmp_path / ".cryopod.toml")
        ignore = config["agents"]["windsurf"]["ignore"]
        assert "*.log" in ignore
        assert "__pycache__/" in ignore
        assert "settings.local.json" not in ignore
        assert "mcp.json" not in ignore
        assert "settings.json" not in ignore

    def test_gemini_ignore_includes_settings_json(self, tmp_path, monkeypatch):
        """Gemini agent includes settings.json in its ignore list."""
        (tmp_path / ".gemini").mkdir()
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        result = runner.invoke(cli, ["init"], input="y\nn\nn\n")

        assert result.exit_code == 0
        config = read_toml(tmp_path / ".cryopod.toml")
        ignore = config["agents"]["gemini"]["ignore"]
        assert "settings.json" in ignore
        assert "*.log" in ignore
        assert "__pycache__/" in ignore
        assert "settings.local.json" not in ignore
        assert "mcp.json" not in ignore

    def test_discovers_all_six_agents(self, tmp_path, monkeypatch):
        """All six known agents are discovered when their dirs exist."""
        for dirname in [
            ".claude",
            ".codex",
            ".opencode",
            ".cursor",
            ".windsurf",
            ".gemini",
        ]:
            (tmp_path / dirname).mkdir()
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        # Confirm each agent (y), no custom name (n) x6, no additional agents (n)
        result = runner.invoke(cli, ["init"], input="y\nn\n" * 6 + "n\n")

        assert result.exit_code == 0
        config = read_toml(tmp_path / ".cryopod.toml")
        for agent in ["claude", "codex", "opencode", "cursor", "windsurf", "gemini"]:
            assert agent in config["agents"]

    def test_no_prompt_when_dirs_absent(self, tmp_path, monkeypatch):
        """No prompts for cursor/windsurf/gemini when their dirs don't exist."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        # No additional agents (n)
        result = runner.invoke(cli, ["init"], input="n\n")

        assert result.exit_code == 0
        for name in ["cursor", "windsurf", "gemini"]:
            assert name not in result.output.lower()


class TestPromptConfig:
    """Tests for agent configuration prompts."""

    def test_decline_discovered_agent(self, tmp_path, monkeypatch):
        """User declines a discovered agent - excluded from config."""
        (tmp_path / ".claude").mkdir()
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        # Decline claude (n), no additional agents (n)
        result = runner.invoke(cli, ["init"], input="n\nn\n")

        assert result.exit_code == 0
        assert not (tmp_path / ".cryopod.toml").exists()

    def test_custom_agent_name(self, tmp_path, monkeypatch):
        """User renames a discovered agent."""
        (tmp_path / ".claude").mkdir()
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        # Confirm claude (y), custom name (y), name "my-claude",
        # no additional agents (n)
        result = runner.invoke(cli, ["init"], input="y\ny\nmy-claude\nn\n")

        assert result.exit_code == 0
        config = read_toml(tmp_path / ".cryopod.toml")
        assert "my-claude" in config["agents"]
        assert "claude" not in config["agents"]

    def test_additional_agents(self, tmp_path, monkeypatch):
        """User adds a custom agent beyond discovered ones."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        # Add another (y), name "custom", dir ".custom",
        # add another (n)
        result = runner.invoke(cli, ["init"], input="y\ncustom\n.custom\nn\n")

        assert result.exit_code == 0
        config = read_toml(tmp_path / ".cryopod.toml")
        assert "custom" in config["agents"]
        assert config["agents"]["custom"]["directory"] == ".custom"


class TestOverwrite:
    """Tests for config overwrite behavior."""

    def test_overwrite_confirmed(self, tmp_path, monkeypatch):
        """Existing config is overwritten when user confirms."""
        config_file = tmp_path / ".cryopod.toml"
        config_file.write_text("old content")
        (tmp_path / ".claude").mkdir()
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        # Confirm overwrite (y), confirm claude (y), no custom name (n),
        # no additional agents (n)
        result = runner.invoke(cli, ["init"], input="y\ny\nn\nn\n")

        assert result.exit_code == 0
        content = config_file.read_text()
        assert content != "old content"

    def test_overwrite_aborted(self, tmp_path, monkeypatch):
        """Existing config is unchanged when user declines overwrite."""
        config_file = tmp_path / ".cryopod.toml"
        config_file.write_text("old content")
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        # Decline overwrite (n)
        result = runner.invoke(cli, ["init"], input="n\n")

        assert result.exit_code != 0  # click.confirm abort
        assert config_file.read_text() == "old content"


class TestApiKeyWarning:
    """Tests for CRYOPOD_API_KEY warning."""

    def test_api_key_not_set(self, tmp_path, monkeypatch):
        """Warning shown when CRYOPOD_API_KEY is not set."""
        (tmp_path / ".claude").mkdir()
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("CRYOPOD_API_KEY", raising=False)

        runner = CliRunner()
        result = runner.invoke(cli, ["init"], input="y\nn\nn\n")

        assert result.exit_code == 0
        assert "CRYOPOD_API_KEY not set" in result.output

    def test_api_key_present(self, tmp_path, monkeypatch):
        """No warning when CRYOPOD_API_KEY is set."""
        (tmp_path / ".claude").mkdir()
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        runner = CliRunner()
        result = runner.invoke(cli, ["init"], input="y\nn\nn\n")

        assert result.exit_code == 0
        assert "CRYOPOD_API_KEY not set" not in result.output


class TestNoAgents:
    """Tests for no agents selected."""

    def test_no_agents_no_file(self, tmp_path, monkeypatch):
        """No file written when no agents selected."""
        (tmp_path / ".claude").mkdir()
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        # Decline claude (n), no additional (n)
        result = runner.invoke(cli, ["init"], input="n\nn\n")

        assert result.exit_code == 0
        assert not (tmp_path / ".cryopod.toml").exists()
        assert "No agents configured" in result.output


class TestCustomConfigPath:
    """Tests for --config option."""

    def test_custom_config_path(self, tmp_path, monkeypatch):
        """--config writes to custom path."""
        (tmp_path / ".claude").mkdir()
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["init", "--config", str(tmp_path / "custom.toml")],
            input="y\nn\nn\n",
        )

        assert result.exit_code == 0
        assert (tmp_path / "custom.toml").exists()
        config = read_toml(tmp_path / "custom.toml")
        assert "claude" in config["agents"]


class TestDefaultIgnore:
    """Tests for default ignore patterns."""

    def test_default_ignore_patterns(self, tmp_path, monkeypatch):
        """Each agent gets default ignore patterns."""
        (tmp_path / ".claude").mkdir()
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        result = runner.invoke(cli, ["init"], input="y\nn\nn\n")

        assert result.exit_code == 0
        config = read_toml(tmp_path / ".cryopod.toml")
        ignore = config["agents"]["claude"]["ignore"]
        assert "settings.local.json" in ignore
        assert "*.log" in ignore
        assert "__pycache__/" in ignore

    def test_codex_ignores_exclude_settings_local_json(self, tmp_path, monkeypatch):
        """Codex gets global ignores but not Claude-specific settings.local.json."""
        (tmp_path / ".claude").mkdir()
        (tmp_path / ".codex").mkdir()
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        # Confirm claude (y), no custom name (n),
        # Confirm codex (y), no custom name (n),
        # No additional agents (n)
        result = runner.invoke(cli, ["init"], input="y\nn\ny\nn\nn\n")

        assert result.exit_code == 0
        config = read_toml(tmp_path / ".cryopod.toml")

        claude_ignore = config["agents"]["claude"]["ignore"]
        assert "settings.local.json" in claude_ignore
        assert "*.log" in claude_ignore
        assert "__pycache__/" in claude_ignore

        codex_ignore = config["agents"]["codex"]["ignore"]
        assert "settings.local.json" not in codex_ignore
        assert "*.log" in codex_ignore
        assert "__pycache__/" in codex_ignore

    def test_custom_agent_gets_only_global_ignore(self, tmp_path, monkeypatch):
        """A custom/unknown agent gets only global ignore patterns."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        # Add another (y), name "custom", dir ".custom",
        # add another (n)
        result = runner.invoke(cli, ["init"], input="y\ncustom\n.custom\nn\n")

        assert result.exit_code == 0
        config = read_toml(tmp_path / ".cryopod.toml")
        ignore = config["agents"]["custom"]["ignore"]
        assert "*.log" in ignore
        assert "__pycache__/" in ignore
        assert "settings.local.json" not in ignore

    def test_renamed_agent_keeps_original_ignore(self, tmp_path, monkeypatch):
        """A renamed Claude agent retains Claude-specific ignore patterns."""
        (tmp_path / ".claude").mkdir()
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        # Confirm claude (y), custom name (y), name "my-claude",
        # no additional agents (n)
        result = runner.invoke(cli, ["init"], input="y\ny\nmy-claude\nn\n")

        assert result.exit_code == 0
        config = read_toml(tmp_path / ".cryopod.toml")
        ignore = config["agents"]["my-claude"]["ignore"]
        assert "settings.local.json" in ignore
        assert "*.log" in ignore
        assert "__pycache__/" in ignore
