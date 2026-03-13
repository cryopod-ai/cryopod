"""Tests for the cryopod add command."""

from click.testing import CliRunner

from cryopod.agents import GLOBAL_IGNORE
from cryopod.cli import cli
from tests.helpers import read_toml


class TestAddBasic:
    """Tests for basic add functionality."""

    def test_add_creates_config_from_scratch(self, tmp_path, monkeypatch):
        """Creates .cryopod.toml when no config exists."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        result = runner.invoke(cli, ["add", "myagent", "--directory", "/some/path"])

        assert result.exit_code == 0
        config = read_toml(tmp_path / ".cryopod.toml")
        assert "myagent" in config["agents"]
        assert config["agents"]["myagent"]["directory"] == "/some/path"

    def test_add_appends_to_existing_config(self, tmp_path, monkeypatch):
        """Adds a second agent to an existing config; both survive."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        runner.invoke(cli, ["add", "first", "--directory", "/first"])
        result = runner.invoke(cli, ["add", "second", "--directory", "/second"])

        assert result.exit_code == 0
        config = read_toml(tmp_path / ".cryopod.toml")
        assert "first" in config["agents"]
        assert "second" in config["agents"]
        assert config["agents"]["first"]["directory"] == "/first"
        assert config["agents"]["second"]["directory"] == "/second"

    def test_success_output(self, tmp_path, monkeypatch):
        """Output contains agent name and config path."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        result = runner.invoke(cli, ["add", "myagent", "--directory", "/some/path"])

        assert result.exit_code == 0
        assert "myagent" in result.output
        assert ".cryopod.toml" in result.output


class TestAddDirectory:
    """Tests for --directory option."""

    def test_directory_required(self, tmp_path, monkeypatch):
        """Omitting --directory produces non-zero exit and error message."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        result = runner.invoke(cli, ["add", "myagent"])

        assert result.exit_code != 0
        assert (
            "directory" in result.output.lower()
            or "directory" in str(result.exception).lower()
        )

    def test_directory_not_validated_on_disk(self, tmp_path, monkeypatch):
        """A non-existent path is accepted without error."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["add", "myagent", "--directory", "/does/not/exist/anywhere"],
        )

        assert result.exit_code == 0
        config = read_toml(tmp_path / ".cryopod.toml")
        assert config["agents"]["myagent"]["directory"] == "/does/not/exist/anywhere"


class TestAddDuplicate:
    """Tests for duplicate agent name detection."""

    def test_duplicate_name_fails(self, tmp_path, monkeypatch):
        """Adding an agent with a name that already exists fails."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        runner.invoke(cli, ["add", "myagent", "--directory", "/first"])
        result = runner.invoke(cli, ["add", "myagent", "--directory", "/second"])

        assert result.exit_code != 0
        assert "already exists" in result.output


class TestAddIgnore:
    """Tests for ignore pattern handling."""

    def test_global_ignore_merged(self, tmp_path, monkeypatch):
        """Added agent gets GLOBAL_IGNORE patterns automatically."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        result = runner.invoke(cli, ["add", "custom", "--directory", "/custom"])

        assert result.exit_code == 0
        config = read_toml(tmp_path / ".cryopod.toml")
        ignore = config["agents"]["custom"]["ignore"]
        for pattern in GLOBAL_IGNORE:
            assert pattern in ignore

    def test_user_ignore_appended(self, tmp_path, monkeypatch):
        """User-supplied --ignore values are included."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "add",
                "custom",
                "--directory",
                "/custom",
                "--ignore",
                "*.tmp",
                "--ignore",
                "build/",
            ],
        )

        assert result.exit_code == 0
        config = read_toml(tmp_path / ".cryopod.toml")
        ignore = config["agents"]["custom"]["ignore"]
        assert "*.tmp" in ignore
        assert "build/" in ignore

    def test_known_agent_gets_agent_specific_ignore(self, tmp_path, monkeypatch):
        """Adding agent named 'claude' gets settings.local.json from KNOWN_AGENTS."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        result = runner.invoke(cli, ["add", "claude", "--directory", ".claude"])

        assert result.exit_code == 0
        config = read_toml(tmp_path / ".cryopod.toml")
        ignore = config["agents"]["claude"]["ignore"]
        assert "settings.local.json" in ignore

    def test_no_duplicate_ignore_patterns(self, tmp_path, monkeypatch):
        """If user passes a pattern already in global, no duplicate in result."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "add",
                "custom",
                "--directory",
                "/custom",
                "--ignore",
                "*.log",
            ],
        )

        assert result.exit_code == 0
        config = read_toml(tmp_path / ".cryopod.toml")
        ignore = config["agents"]["custom"]["ignore"]
        assert ignore.count("*.log") == 1


class TestAddConfigOption:
    """Tests for --config option."""

    def test_custom_config_path(self, tmp_path, monkeypatch):
        """--config custom.toml writes to the specified path."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "add",
                "myagent",
                "--directory",
                "/path",
                "--config",
                str(tmp_path / "custom.toml"),
            ],
        )

        assert result.exit_code == 0
        assert (tmp_path / "custom.toml").exists()
        config = read_toml(tmp_path / "custom.toml")
        assert "myagent" in config["agents"]


class TestAddMaxVersions:
    """Tests for --max-versions option."""

    def test_max_versions_written_when_provided(self, tmp_path, monkeypatch):
        """Providing --max-versions writes the value to config."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        result = runner.invoke(
            cli, ["add", "myagent", "--directory", "/path", "--max-versions", "50"]
        )

        assert result.exit_code == 0
        config = read_toml(tmp_path / ".cryopod.toml")
        assert config["agents"]["myagent"]["max_versions"] == 50

    def test_max_versions_omitted_when_not_provided(self, tmp_path, monkeypatch):
        """Omitting --max-versions leaves the key absent from config."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        result = runner.invoke(cli, ["add", "myagent", "--directory", "/path"])

        assert result.exit_code == 0
        config = read_toml(tmp_path / ".cryopod.toml")
        assert "max_versions" not in config["agents"]["myagent"]

    def test_max_versions_rejects_zero(self, tmp_path, monkeypatch):
        """--max-versions 0 is rejected with an error."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        result = runner.invoke(
            cli, ["add", "myagent", "--directory", "/path", "--max-versions", "0"]
        )

        assert result.exit_code != 0

    def test_max_versions_rejects_over_100(self, tmp_path, monkeypatch):
        """--max-versions 101 is rejected with an error."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        result = runner.invoke(
            cli, ["add", "myagent", "--directory", "/path", "--max-versions", "101"]
        )

        assert result.exit_code != 0

    def test_max_versions_rejects_negative(self, tmp_path, monkeypatch):
        """--max-versions -1 is rejected."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        result = runner.invoke(
            cli, ["add", "myagent", "--directory", "/path", "--max-versions", "-1"]
        )

        assert result.exit_code != 0

    def test_max_versions_boundary_1(self, tmp_path, monkeypatch):
        """--max-versions 1 succeeds and writes value 1."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        result = runner.invoke(
            cli, ["add", "myagent", "--directory", "/path", "--max-versions", "1"]
        )

        assert result.exit_code == 0
        config = read_toml(tmp_path / ".cryopod.toml")
        assert config["agents"]["myagent"]["max_versions"] == 1

    def test_max_versions_boundary_100(self, tmp_path, monkeypatch):
        """--max-versions 100 succeeds and writes value 100."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        result = runner.invoke(
            cli, ["add", "myagent", "--directory", "/path", "--max-versions", "100"]
        )

        assert result.exit_code == 0
        config = read_toml(tmp_path / ".cryopod.toml")
        assert config["agents"]["myagent"]["max_versions"] == 100


class TestAddMalformedConfig:
    """Tests for malformed existing config."""

    def test_malformed_existing_config_fails(self, tmp_path, monkeypatch):
        """If .cryopod.toml exists but is invalid TOML, command fails with clear error."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".cryopod.toml").write_text("this is [[[not valid toml")

        runner = CliRunner()
        result = runner.invoke(cli, ["add", "myagent", "--directory", "/path"])

        assert result.exit_code != 0
        assert "malformed" in result.output.lower()
