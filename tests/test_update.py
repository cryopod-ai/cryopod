"""Tests for the cryopod update command."""

from click.testing import CliRunner

from cryopod.cli import cli
from tests.helpers import read_toml


class TestUpdateBasic:
    """Tests for basic update functionality."""

    def test_update_directory_only(self, tmp_path, monkeypatch):
        """Updates only the directory, leaving ignore unchanged."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        runner.invoke(cli, ["add", "myagent", "--directory", "/old/path"])
        config_before = read_toml(tmp_path / ".cryopod.toml")
        old_ignore = config_before["agents"]["myagent"]["ignore"]

        result = runner.invoke(cli, ["update", "myagent", "--directory", "/new/path"])

        assert result.exit_code == 0
        config = read_toml(tmp_path / ".cryopod.toml")
        assert config["agents"]["myagent"]["directory"] == "/new/path"
        assert config["agents"]["myagent"]["ignore"] == old_ignore

    def test_update_ignore_only(self, tmp_path, monkeypatch):
        """Updates only ignore patterns, leaving directory unchanged."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        runner.invoke(cli, ["add", "myagent", "--directory", "/some/path"])

        result = runner.invoke(
            cli, ["update", "myagent", "--ignore", "*.log", "--ignore", "*.tmp"]
        )

        assert result.exit_code == 0
        config = read_toml(tmp_path / ".cryopod.toml")
        assert config["agents"]["myagent"]["directory"] == "/some/path"
        assert config["agents"]["myagent"]["ignore"] == ["*.log", "*.tmp"]

    def test_update_both(self, tmp_path, monkeypatch):
        """Updates both directory and ignore patterns."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        runner.invoke(cli, ["add", "myagent", "--directory", "/old/path"])

        result = runner.invoke(
            cli,
            [
                "update",
                "myagent",
                "--directory",
                "/new/path",
                "--ignore",
                "build/",
            ],
        )

        assert result.exit_code == 0
        config = read_toml(tmp_path / ".cryopod.toml")
        assert config["agents"]["myagent"]["directory"] == "/new/path"
        assert config["agents"]["myagent"]["ignore"] == ["build/"]

    def test_other_agents_preserved(self, tmp_path, monkeypatch):
        """Updating one agent leaves other agents unchanged."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        runner.invoke(cli, ["add", "first", "--directory", "/first"])
        runner.invoke(cli, ["add", "second", "--directory", "/second"])

        result = runner.invoke(cli, ["update", "first", "--directory", "/updated"])

        assert result.exit_code == 0
        config = read_toml(tmp_path / ".cryopod.toml")
        assert config["agents"]["first"]["directory"] == "/updated"
        assert config["agents"]["second"]["directory"] == "/second"

    def test_success_output_mentions_changed_fields(self, tmp_path, monkeypatch):
        """Output lists which fields were changed."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        runner.invoke(cli, ["add", "myagent", "--directory", "/old"])

        result = runner.invoke(
            cli,
            [
                "update",
                "myagent",
                "--directory",
                "/new",
                "--ignore",
                "*.log",
            ],
        )

        assert result.exit_code == 0
        assert "myagent" in result.output
        assert "directory" in result.output
        assert "ignore" in result.output
        assert ".cryopod.toml" in result.output


class TestUpdateNotFound:
    """Tests for updating nonexistent agents."""

    def test_update_nonexistent_agent(self, tmp_path, monkeypatch):
        """Updating an agent that doesn't exist fails with 'not found'."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        runner.invoke(cli, ["add", "other", "--directory", "/other"])
        result = runner.invoke(cli, ["update", "nonexistent", "--directory", "/new"])

        assert result.exit_code != 0
        assert "not found" in result.output.lower()


class TestUpdateNoOptions:
    """Tests for calling update with no options."""

    def test_no_options_fails(self, tmp_path, monkeypatch):
        """Calling update with neither --directory nor --ignore fails."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        runner.invoke(cli, ["add", "myagent", "--directory", "/path"])
        result = runner.invoke(cli, ["update", "myagent"])

        assert result.exit_code != 0
        assert "nothing to update" in result.output.lower()


class TestUpdateIgnoreReplacement:
    """Tests for ignore pattern replacement semantics."""

    def test_ignore_fully_replaces(self, tmp_path, monkeypatch):
        """--ignore fully replaces existing patterns, does not merge."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        runner.invoke(
            cli,
            ["add", "myagent", "--directory", "/path", "--ignore", "old_pattern"],
        )
        result = runner.invoke(cli, ["update", "myagent", "--ignore", "new_pattern"])

        assert result.exit_code == 0
        config = read_toml(tmp_path / ".cryopod.toml")
        ignore = config["agents"]["myagent"]["ignore"]
        assert "new_pattern" in ignore
        assert "old_pattern" not in ignore

    def test_multiple_ignore_flags(self, tmp_path, monkeypatch):
        """Multiple --ignore flags result in multiple patterns."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        runner.invoke(cli, ["add", "myagent", "--directory", "/path"])
        result = runner.invoke(
            cli,
            [
                "update",
                "myagent",
                "--ignore",
                "*.log",
                "--ignore",
                "*.tmp",
                "--ignore",
                "build/",
            ],
        )

        assert result.exit_code == 0
        config = read_toml(tmp_path / ".cryopod.toml")
        assert config["agents"]["myagent"]["ignore"] == ["*.log", "*.tmp", "build/"]


class TestUpdateConfigOption:
    """Tests for --config option."""

    def test_custom_config_path(self, tmp_path, monkeypatch):
        """--config custom.toml reads/writes the specified file."""
        monkeypatch.chdir(tmp_path)
        custom = str(tmp_path / "custom.toml")

        runner = CliRunner()
        runner.invoke(
            cli, ["add", "myagent", "--directory", "/path", "--config", custom]
        )
        result = runner.invoke(
            cli,
            ["update", "myagent", "--directory", "/new", "--config", custom],
        )

        assert result.exit_code == 0
        config = read_toml(tmp_path / "custom.toml")
        assert config["agents"]["myagent"]["directory"] == "/new"


class TestUpdateMissingConfig:
    """Tests for missing config file."""

    def test_no_config_file(self, tmp_path, monkeypatch):
        """No .cryopod.toml exists, fails with message about running cryopod init."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        result = runner.invoke(cli, ["update", "myagent", "--directory", "/new"])

        assert result.exit_code != 0
        assert "init" in result.output.lower()


class TestUpdateRename:
    """Tests for renaming agents via --name."""

    def test_rename_only(self, tmp_path, monkeypatch):
        """Provide --name without --directory or --ignore. Old key gone, new key has all original fields."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        runner.invoke(cli, ["add", "oldname", "--directory", "/some/path"])

        result = runner.invoke(cli, ["update", "oldname", "--name", "newname"])

        assert result.exit_code == 0
        config = read_toml(tmp_path / ".cryopod.toml")
        assert "oldname" not in config["agents"]
        assert "newname" in config["agents"]
        assert config["agents"]["newname"]["directory"] == "/some/path"

    def test_rename_with_directory(self, tmp_path, monkeypatch):
        """Provide both --name and --directory. Both changes applied."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        runner.invoke(cli, ["add", "oldname", "--directory", "/old/path"])

        result = runner.invoke(
            cli, ["update", "oldname", "--name", "newname", "--directory", "/new/path"]
        )

        assert result.exit_code == 0
        config = read_toml(tmp_path / ".cryopod.toml")
        assert "oldname" not in config["agents"]
        assert config["agents"]["newname"]["directory"] == "/new/path"

    def test_rename_with_ignore(self, tmp_path, monkeypatch):
        """Provide both --name and --ignore. Both changes applied."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        runner.invoke(cli, ["add", "oldname", "--directory", "/path"])

        result = runner.invoke(
            cli, ["update", "oldname", "--name", "newname", "--ignore", "*.log"]
        )

        assert result.exit_code == 0
        config = read_toml(tmp_path / ".cryopod.toml")
        assert "oldname" not in config["agents"]
        assert config["agents"]["newname"]["ignore"] == ["*.log"]

    def test_rename_with_all_options(self, tmp_path, monkeypatch):
        """Provide --name, --directory, and --ignore. All three changes applied."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        runner.invoke(cli, ["add", "oldname", "--directory", "/old"])

        result = runner.invoke(
            cli,
            [
                "update",
                "oldname",
                "--name",
                "newname",
                "--directory",
                "/new",
                "--ignore",
                "build/",
            ],
        )

        assert result.exit_code == 0
        config = read_toml(tmp_path / ".cryopod.toml")
        assert "oldname" not in config["agents"]
        assert config["agents"]["newname"]["directory"] == "/new"
        assert config["agents"]["newname"]["ignore"] == ["build/"]

    def test_rename_duplicate_name_fails(self, tmp_path, monkeypatch):
        """Renaming to an existing agent name fails with 'already exists'."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        runner.invoke(cli, ["add", "first", "--directory", "/first"])
        runner.invoke(cli, ["add", "second", "--directory", "/second"])

        result = runner.invoke(cli, ["update", "first", "--name", "second"])

        assert result.exit_code != 0
        assert "already exists" in result.output.lower()

    def test_rename_preserves_other_agents(self, tmp_path, monkeypatch):
        """Renaming one agent leaves other agents untouched."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        runner.invoke(cli, ["add", "first", "--directory", "/first"])
        runner.invoke(cli, ["add", "second", "--directory", "/second"])

        result = runner.invoke(cli, ["update", "first", "--name", "renamed"])

        assert result.exit_code == 0
        config = read_toml(tmp_path / ".cryopod.toml")
        assert "first" not in config["agents"]
        assert "renamed" in config["agents"]
        assert config["agents"]["second"]["directory"] == "/second"

    def test_rename_success_message(self, tmp_path, monkeypatch):
        """Output contains old name, new name, and 'name' in changed fields."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        runner.invoke(cli, ["add", "oldname", "--directory", "/path"])

        result = runner.invoke(cli, ["update", "oldname", "--name", "newname"])

        assert result.exit_code == 0
        assert "oldname" in result.output
        assert "newname" in result.output
        assert "name" in result.output
        assert "->" in result.output

    def test_rename_to_same_name_fails(self, tmp_path, monkeypatch):
        """Renaming agent to its current name fails with 'already exists'."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        runner.invoke(cli, ["add", "myagent", "--directory", "/path"])

        result = runner.invoke(cli, ["update", "myagent", "--name", "myagent"])

        assert result.exit_code != 0
        assert "already exists" in result.output.lower()


class TestUpdateMaxVersions:
    """Tests for --max-versions option."""

    def test_max_versions_writes_to_config(self, tmp_path, monkeypatch):
        """--max-versions 5 writes max_versions = 5 to the agent's config entry."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        runner.invoke(cli, ["add", "myagent", "--directory", "/path"])
        result = runner.invoke(cli, ["update", "myagent", "--max-versions", "5"])

        assert result.exit_code == 0
        config = read_toml(tmp_path / ".cryopod.toml")
        assert config["agents"]["myagent"]["max_versions"] == 5

    def test_max_versions_out_of_range_rejected(self, tmp_path, monkeypatch):
        """--max-versions with an out-of-range value is rejected by Click."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        runner.invoke(cli, ["add", "myagent", "--directory", "/path"])

        result_zero = runner.invoke(cli, ["update", "myagent", "--max-versions", "0"])
        assert result_zero.exit_code != 0

        result_over = runner.invoke(cli, ["update", "myagent", "--max-versions", "101"])
        assert result_over.exit_code != 0


class TestUpdateMalformedConfig:
    """Tests for malformed config file."""

    def test_malformed_config(self, tmp_path, monkeypatch):
        """Invalid TOML fails with 'malformed' in output."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".cryopod.toml").write_text("this is [[[not valid toml")

        runner = CliRunner()
        result = runner.invoke(cli, ["update", "myagent", "--directory", "/new"])

        assert result.exit_code != 0
        assert "malformed" in result.output.lower()
