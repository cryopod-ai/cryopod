"""Tests for the cryopod keygen command."""

from unittest.mock import patch

from click.testing import CliRunner

from cryopod.cli import cli


class TestShellDetection:
    """Tests for shell format detection and override."""

    def test_keygen_default_bash(self, monkeypatch):
        """With SHELL=/bin/bash, output uses export format."""
        monkeypatch.setenv("SHELL", "/bin/bash")

        runner = CliRunner()
        result = runner.invoke(cli, ["keygen"])

        assert result.exit_code == 0
        assert "export CRYOPOD_SECRET_KEY=" in result.output

    def test_keygen_default_zsh(self, monkeypatch):
        """With SHELL=/bin/zsh, output uses export format."""
        monkeypatch.setenv("SHELL", "/bin/zsh")

        runner = CliRunner()
        result = runner.invoke(cli, ["keygen"])

        assert result.exit_code == 0
        assert "export CRYOPOD_SECRET_KEY=" in result.output

    def test_keygen_default_fish(self, monkeypatch):
        """With SHELL=/usr/bin/fish, output uses set -x format."""
        monkeypatch.setenv("SHELL", "/usr/bin/fish")

        runner = CliRunner()
        result = runner.invoke(cli, ["keygen"])

        assert result.exit_code == 0
        assert "set -x CRYOPOD_SECRET_KEY " in result.output

    def test_keygen_no_shell_env(self, monkeypatch):
        """With SHELL unset, defaults to export format."""
        monkeypatch.delenv("SHELL", raising=False)

        runner = CliRunner()
        result = runner.invoke(cli, ["keygen"])

        assert result.exit_code == 0
        assert "export CRYOPOD_SECRET_KEY=" in result.output

    def test_keygen_shell_flag_bash(self, monkeypatch):
        """--shell bash overrides $SHELL, uses export format."""
        monkeypatch.setenv("SHELL", "/usr/bin/fish")

        runner = CliRunner()
        result = runner.invoke(cli, ["keygen", "--shell", "bash"])

        assert result.exit_code == 0
        assert "export CRYOPOD_SECRET_KEY=" in result.output

    def test_keygen_shell_flag_zsh(self, monkeypatch):
        """--shell zsh uses export format."""
        monkeypatch.setenv("SHELL", "/usr/bin/fish")

        runner = CliRunner()
        result = runner.invoke(cli, ["keygen", "--shell", "zsh"])

        assert result.exit_code == 0
        assert "export CRYOPOD_SECRET_KEY=" in result.output

    def test_keygen_shell_flag_fish(self, monkeypatch):
        """--shell fish overrides $SHELL even if SHELL=/bin/bash."""
        monkeypatch.setenv("SHELL", "/bin/bash")

        runner = CliRunner()
        result = runner.invoke(cli, ["keygen", "--shell", "fish"])

        assert result.exit_code == 0
        assert "set -x CRYOPOD_SECRET_KEY " in result.output


class TestKeyGeneration:
    """Tests for key generation quality."""

    def test_keygen_key_is_unique(self):
        """Two invocations produce different keys."""
        runner = CliRunner()
        result1 = runner.invoke(cli, ["keygen"])
        result2 = runner.invoke(cli, ["keygen"])

        assert result1.exit_code == 0
        assert result2.exit_code == 0
        assert result1.output != result2.output

    def test_keygen_key_length(self):
        """Key portion is 43 characters (token_urlsafe(32))."""
        runner = CliRunner()
        result = runner.invoke(cli, ["keygen"])

        assert result.exit_code == 0
        # Extract key from the first line: "export CRYOPOD_SECRET_KEY=<key>"
        first_line = result.output.strip().split("\n")[0]
        key = first_line.split("=", 1)[1]
        assert len(key) == 43


class TestOutput:
    """Tests for output format and content."""

    def test_keygen_exit_code(self):
        """Exit code is 0."""
        runner = CliRunner()
        result = runner.invoke(cli, ["keygen"])

        assert result.exit_code == 0

    def test_keygen_warning_displayed(self):
        """Warning panel is printed via console (stderr)."""
        with patch("cryopod.keygen.console") as mock_console:
            runner = CliRunner()
            result = runner.invoke(cli, ["keygen"])

            assert result.exit_code == 0
            mock_console.print.assert_called_once()
            panel_arg = mock_console.print.call_args[0][0]
            # The Panel renderable contains the warning text
            assert "recover" in panel_arg.renderable.lower()

    def test_keygen_invalid_shell(self):
        """--shell powershell is rejected by Click's Choice validator."""
        runner = CliRunner()
        result = runner.invoke(cli, ["keygen", "--shell", "powershell"])

        assert result.exit_code != 0
