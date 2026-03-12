"""Tests for the cryopod remove command."""

from click.testing import CliRunner

from cryopod.cli import cli
from tests.helpers import read_toml


class TestRemoveBasic:
    """Tests for basic remove functionality."""

    def test_remove_existing_agent(self, tmp_path, monkeypatch):
        """Removes an agent that exists in the config."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        runner.invoke(cli, ["add", "myagent", "--directory", "/some/path"])
        result = runner.invoke(cli, ["remove", "myagent"])

        assert result.exit_code == 0
        config = read_toml(tmp_path / ".cryopod.toml")
        assert "myagent" not in config.get("agents", {})

    def test_other_agents_preserved(self, tmp_path, monkeypatch):
        """Removing one agent leaves other agents unchanged."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        runner.invoke(cli, ["add", "first", "--directory", "/first"])
        runner.invoke(cli, ["add", "second", "--directory", "/second"])
        result = runner.invoke(cli, ["remove", "first"])

        assert result.exit_code == 0
        config = read_toml(tmp_path / ".cryopod.toml")
        assert "first" not in config["agents"]
        assert "second" in config["agents"]
        assert config["agents"]["second"]["directory"] == "/second"

    def test_success_output(self, tmp_path, monkeypatch):
        """Output contains agent name and config path."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        runner.invoke(cli, ["add", "myagent", "--directory", "/some/path"])
        result = runner.invoke(cli, ["remove", "myagent"])

        assert result.exit_code == 0
        assert "myagent" in result.output
        assert ".cryopod.toml" in result.output


class TestRemoveNotFound:
    """Tests for removing nonexistent agents."""

    def test_remove_nonexistent_agent(self, tmp_path, monkeypatch):
        """Removing an agent that doesn't exist fails."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        runner.invoke(cli, ["add", "other", "--directory", "/other"])
        result = runner.invoke(cli, ["remove", "nonexistent"])

        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    def test_remove_from_empty_agents(self, tmp_path, monkeypatch):
        """Config with empty [agents] table still fails with 'not found'."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".cryopod.toml").write_text("[agents]\n")

        runner = CliRunner()
        result = runner.invoke(cli, ["remove", "ghost"])

        assert result.exit_code != 0
        assert "not found" in result.output.lower()


class TestRemoveConfigOption:
    """Tests for --config option."""

    def test_custom_config_path(self, tmp_path, monkeypatch):
        """--config custom.toml reads/writes the specified file."""
        monkeypatch.chdir(tmp_path)
        custom = str(tmp_path / "custom.toml")

        runner = CliRunner()
        runner.invoke(
            cli, ["add", "myagent", "--directory", "/path", "--config", custom]
        )
        result = runner.invoke(cli, ["remove", "myagent", "--config", custom])

        assert result.exit_code == 0
        config = read_toml(tmp_path / "custom.toml")
        assert "myagent" not in config.get("agents", {})


class TestRemoveMissingConfig:
    """Tests for missing config file."""

    def test_no_config_file(self, tmp_path, monkeypatch):
        """No .cryopod.toml exists, fails with message about running cryopod init."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        result = runner.invoke(cli, ["remove", "myagent"])

        assert result.exit_code != 0
        assert "init" in result.output.lower()


class TestRemoveMalformedConfig:
    """Tests for malformed config file."""

    def test_malformed_config(self, tmp_path, monkeypatch):
        """Invalid TOML fails with 'malformed' in output."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".cryopod.toml").write_text("this is [[[not valid toml")

        runner = CliRunner()
        result = runner.invoke(cli, ["remove", "myagent"])

        assert result.exit_code != 0
        assert "malformed" in result.output.lower()
