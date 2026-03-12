"""Tests for the cryopod status command."""

from unittest.mock import patch

import httpx
import tomli_w
from click.testing import CliRunner

from cryopod.cli import cli
from tests.helpers import write_config


def _mock_account(monkeypatch, return_value=None):
    """Patch _fetch_account_info to return a controlled value."""
    monkeypatch.setattr(
        "cryopod.status._fetch_account_info",
        lambda api_key: return_value,
    )


class TestAgentsNotShown:
    """Tests that agent information is not shown in status output."""

    def test_agents_not_shown_in_output(self, tmp_path, monkeypatch):
        """Agent names and table headers do not appear in status output."""
        write_config(
            tmp_path / ".cryopod.toml",
            {
                "claude": {"directory": ".claude"},
                "codex": {"directory": ".codex"},
            },
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")
        _mock_account(monkeypatch, {"username": "alice", "email": "alice@example.com"})

        runner = CliRunner()
        result = runner.invoke(cli, ["status"])

        assert result.exit_code == 0
        assert "AGENT" not in result.output
        assert "DIRECTORY" not in result.output
        assert ".claude" not in result.output
        assert ".codex" not in result.output

    def test_no_zero_agents_message(self, tmp_path, monkeypatch):
        """Does not show '0 agents configured' when config has no agents."""
        config_file = tmp_path / ".cryopod.toml"
        with open(config_file, "wb") as f:
            tomli_w.dump({"version": 1}, f)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")
        _mock_account(monkeypatch, {"username": "alice", "email": "alice@example.com"})

        runner = CliRunner()
        result = runner.invoke(cli, ["status"])

        assert result.exit_code == 0
        assert "0 agents configured" not in result.output


class TestConfigMissing:
    """Tests for status when no config file exists."""

    def test_no_config_warning(self, tmp_path, monkeypatch):
        """Warning shown when config file is missing."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")
        _mock_account(monkeypatch, {"username": "alice", "email": "alice@example.com"})

        runner = CliRunner()
        result = runner.invoke(cli, ["status"])

        assert result.exit_code == 0
        assert "NO CONFIG FOUND" in result.output
        assert "cryopod init" in result.output


class TestConfigMalformed:
    """Tests for status when config file is malformed."""

    def test_malformed_config(self, tmp_path, monkeypatch):
        """Error shown when config file is invalid TOML."""
        config_file = tmp_path / ".cryopod.toml"
        config_file.write_text("this is [not valid toml =====")
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")
        _mock_account(monkeypatch, {"username": "alice", "email": "alice@example.com"})

        runner = CliRunner()
        result = runner.invoke(cli, ["status"])

        assert result.exit_code == 0
        assert "CONFIG ERROR" in result.output
        assert "malformed" in result.output


class TestCustomConfigPath:
    """Tests for --config option."""

    def test_custom_path(self, tmp_path, monkeypatch):
        """Reads config from custom path when --config is specified."""
        custom_path = tmp_path / "custom" / "config.toml"
        custom_path.parent.mkdir(parents=True)
        write_config(custom_path, {"claude": {"directory": ".claude"}})
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")
        _mock_account(monkeypatch, {"username": "alice", "email": "alice@example.com"})

        runner = CliRunner()
        result = runner.invoke(cli, ["status", "--config", str(custom_path)])

        assert result.exit_code == 0
        # Agent names should NOT appear in output (agents are no longer shown)
        assert "AGENT" not in result.output
        assert "DIRECTORY" not in result.output


class TestApiKeySet:
    """Tests for CRYOPOD_API_KEY when set."""

    def test_key_set(self, tmp_path, monkeypatch):
        """Shows SET when API key is present."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key-value")
        _mock_account(monkeypatch, {"username": "alice", "email": "alice@example.com"})

        runner = CliRunner()
        result = runner.invoke(cli, ["status"])

        assert result.exit_code == 0
        assert "SET" in result.output
        # Must NOT leak the actual key value
        assert "test-key-value" not in result.output

    def test_key_set_does_not_show_not_set(self, tmp_path, monkeypatch):
        """Does not show NOT SET when key is present."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")
        _mock_account(monkeypatch, {"username": "alice", "email": "alice@example.com"})

        runner = CliRunner()
        result = runner.invoke(cli, ["status"])

        assert result.exit_code == 0
        assert "CRYOPOD_API_KEY: NOT SET" not in result.output


class TestApiKeyNotSet:
    """Tests for CRYOPOD_API_KEY when not set."""

    def test_key_not_set(self, tmp_path, monkeypatch):
        """Shows NOT SET when API key is missing."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("CRYOPOD_API_KEY", raising=False)

        runner = CliRunner()
        result = runner.invoke(cli, ["status"])

        assert result.exit_code == 0
        assert "NOT SET" in result.output

    def test_key_empty_string(self, tmp_path, monkeypatch):
        """Treats empty string the same as not set."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "")

        runner = CliRunner()
        result = runner.invoke(cli, ["status"])

        assert result.exit_code == 0
        assert "NOT SET" in result.output


class TestAccountInfo:
    """Tests for account info display when API key is set."""

    def test_account_info_displayed(self, tmp_path, monkeypatch):
        """Shows username and email when API returns account info."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")
        _mock_account(monkeypatch, {"username": "alice", "email": "alice@example.com"})

        runner = CliRunner()
        result = runner.invoke(cli, ["status"])

        assert result.exit_code == 0
        assert "alice" in result.output
        assert "alice@example.com" in result.output

    def test_account_info_username_only(self, tmp_path, monkeypatch):
        """Shows username without email when email is missing."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")
        _mock_account(monkeypatch, {"username": "alice"})

        runner = CliRunner()
        result = runner.invoke(cli, ["status"])

        assert result.exit_code == 0
        assert "alice" in result.output

    def test_account_info_api_error(self, tmp_path, monkeypatch):
        """Shows warning when API returns non-200 status."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")
        _mock_account(monkeypatch, None)

        runner = CliRunner()
        result = runner.invoke(cli, ["status"])

        assert result.exit_code == 0
        assert "SET" in result.output
        assert "could not fetch account info" in result.output

    def test_account_info_auth_failure(self, tmp_path, monkeypatch):
        """Shows warning when API returns 401."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")
        _mock_account(monkeypatch, None)

        runner = CliRunner()
        result = runner.invoke(cli, ["status"])

        assert result.exit_code == 0
        assert "SET" in result.output
        assert "could not fetch account info" in result.output

    def test_account_info_network_error(self, tmp_path, monkeypatch):
        """Shows warning when network connection fails."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        def _raise_connect_error(api_key):
            raise httpx.ConnectError("connection refused")

        # Test through the actual helper by patching httpx.Client
        with patch("cryopod.status.httpx.Client") as mock_client:
            mock_client.return_value.__enter__ = lambda s: s
            mock_client.return_value.__exit__ = lambda s, *a: None
            mock_client.return_value.get.side_effect = httpx.ConnectError(
                "connection refused"
            )

            runner = CliRunner()
            result = runner.invoke(cli, ["status"])

        assert result.exit_code == 0
        assert "SET" in result.output
        assert "could not fetch account info" in result.output

    def test_account_info_timeout(self, tmp_path, monkeypatch):
        """Shows warning when API request times out."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        with patch("cryopod.status.httpx.Client") as mock_client:
            mock_client.return_value.__enter__ = lambda s: s
            mock_client.return_value.__exit__ = lambda s, *a: None
            mock_client.return_value.get.side_effect = httpx.TimeoutException(
                "timed out"
            )

            runner = CliRunner()
            result = runner.invoke(cli, ["status"])

        assert result.exit_code == 0
        assert "SET" in result.output
        assert "could not fetch account info" in result.output

    def test_no_api_call_without_key(self, tmp_path, monkeypatch):
        """No API call is made when API key is not set."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("CRYOPOD_API_KEY", raising=False)

        with patch("cryopod.status._fetch_account_info") as mock_fetch:
            runner = CliRunner()
            result = runner.invoke(cli, ["status"])

        assert result.exit_code == 0
        assert "NOT SET" in result.output
        mock_fetch.assert_not_called()


class TestSecretKeyStatus:
    """Tests for CRYOPOD_SECRET_KEY status display."""

    def test_secret_key_set(self, tmp_path, monkeypatch):
        """Shows SET when secret key is present."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")
        monkeypatch.setenv("CRYOPOD_SECRET_KEY", "my-secret-key-value")
        _mock_account(monkeypatch, {"username": "alice", "email": "alice@example.com"})

        runner = CliRunner()
        result = runner.invoke(cli, ["status"])

        assert result.exit_code == 0
        assert "CRYOPOD_SECRET_KEY: SET" in result.output
        # Must NOT leak the actual key value
        assert "my-secret-key-value" not in result.output

    def test_secret_key_not_set(self, tmp_path, monkeypatch):
        """Shows NOT SET when secret key is missing."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")
        monkeypatch.delenv("CRYOPOD_SECRET_KEY", raising=False)
        _mock_account(monkeypatch, {"username": "alice", "email": "alice@example.com"})

        runner = CliRunner()
        result = runner.invoke(cli, ["status"])

        assert result.exit_code == 0
        assert "CRYOPOD_SECRET_KEY: NOT SET" in result.output

    def test_secret_key_empty_string(self, tmp_path, monkeypatch):
        """Treats empty string the same as not set."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")
        monkeypatch.setenv("CRYOPOD_SECRET_KEY", "")
        _mock_account(monkeypatch, {"username": "alice", "email": "alice@example.com"})

        runner = CliRunner()
        result = runner.invoke(cli, ["status"])

        assert result.exit_code == 0
        assert "CRYOPOD_SECRET_KEY: NOT SET" in result.output


class TestQuotaUsage:
    """Tests for quota usage display in status output."""

    def test_quota_displayed(self, tmp_path, monkeypatch):
        """Shows total usage and available when API returns quota fields."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")
        _mock_account(
            monkeypatch,
            {
                "username": "alice",
                "email": "alice@example.com",
                "total_usage": "42 MB",
                "available": "958 MB",
            },
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["status"])

        assert result.exit_code == 0
        assert "Total Usage" in result.output
        assert "42 MB" in result.output
        assert "Available" in result.output
        assert "958 MB" in result.output

    def test_quota_fields_missing(self, tmp_path, monkeypatch):
        """Shows em dash when quota fields are missing from API response."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")
        _mock_account(
            monkeypatch,
            {"username": "alice", "email": "alice@example.com"},
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["status"])

        assert result.exit_code == 0
        assert "Total Usage: \u2014" in result.output
        assert "Available: \u2014" in result.output

    def test_quota_fields_null(self, tmp_path, monkeypatch):
        """Shows em dash when quota fields are explicitly null."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")
        _mock_account(
            monkeypatch,
            {
                "username": "alice",
                "email": "alice@example.com",
                "total_usage": None,
                "available": None,
            },
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["status"])

        assert result.exit_code == 0
        assert "Total Usage: \u2014" in result.output
        assert "Available: \u2014" in result.output

    def test_quota_not_shown_when_unauthenticated(self, tmp_path, monkeypatch):
        """Quota lines do not appear when no API key is set."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("CRYOPOD_API_KEY", raising=False)

        runner = CliRunner()
        result = runner.invoke(cli, ["status"])

        assert result.exit_code == 0
        assert "Total Usage" not in result.output

    def test_quota_not_shown_when_api_fails(self, tmp_path, monkeypatch):
        """Quota lines do not appear when API returns None."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")
        _mock_account(monkeypatch, None)

        runner = CliRunner()
        result = runner.invoke(cli, ["status"])

        assert result.exit_code == 0
        assert "Total Usage" not in result.output
        assert "could not fetch account info" in result.output

    def test_quota_section_order(self, tmp_path, monkeypatch):
        """Total Usage and Available appear after Account but before CRYOPOD_API_KEY."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")
        _mock_account(
            monkeypatch,
            {
                "username": "alice",
                "email": "alice@example.com",
                "total_usage": "42 MB",
                "available": "958 MB",
            },
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["status"])

        assert result.exit_code == 0
        output = result.output
        account_pos = output.index("Account:")
        usage_pos = output.index("Total Usage")
        available_pos = output.index("Available")
        api_key_pos = output.index("CRYOPOD_API_KEY")

        assert account_pos < usage_pos, "Total Usage should appear after Account"
        assert usage_pos < available_pos, "Available should appear after Total Usage"
        assert available_pos < api_key_pos, (
            "Available should appear before CRYOPOD_API_KEY"
        )


class TestSectionOrder:
    """Tests that sections appear in the correct order: Account, Env vars."""

    def test_section_order(self, tmp_path, monkeypatch):
        """Account appears before API key, API key appears before secret key."""
        write_config(
            tmp_path / ".cryopod.toml",
            {"claude": {"directory": ".claude"}},
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")
        monkeypatch.setenv("CRYOPOD_SECRET_KEY", "test-secret")
        _mock_account(monkeypatch, {"username": "alice", "email": "alice@example.com"})

        runner = CliRunner()
        result = runner.invoke(cli, ["status"])

        assert result.exit_code == 0
        output = result.output
        account_pos = output.index("Account:")
        api_key_pos = output.index("CRYOPOD_API_KEY: SET")
        secret_key_pos = output.index("CRYOPOD_SECRET_KEY: SET")

        assert account_pos < api_key_pos, "Account should appear before CRYOPOD_API_KEY"
        assert api_key_pos < secret_key_pos, (
            "CRYOPOD_API_KEY should appear before CRYOPOD_SECRET_KEY"
        )


class TestExitCode:
    """Tests that status always exits 0."""

    def test_exit_code_no_config(self, tmp_path, monkeypatch):
        """Exit code is 0 even when config is missing."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("CRYOPOD_API_KEY", raising=False)

        runner = CliRunner()
        result = runner.invoke(cli, ["status"])

        assert result.exit_code == 0

    def test_exit_code_with_config(self, tmp_path, monkeypatch):
        """Exit code is 0 when config is present."""
        write_config(
            tmp_path / ".cryopod.toml",
            {"claude": {"directory": ".claude"}},
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")
        _mock_account(monkeypatch, {"username": "alice", "email": "alice@example.com"})

        runner = CliRunner()
        result = runner.invoke(cli, ["status"])

        assert result.exit_code == 0

    def test_exit_code_malformed_config(self, tmp_path, monkeypatch):
        """Exit code is 0 even when config is malformed."""
        config_file = tmp_path / ".cryopod.toml"
        config_file.write_text("broken [[[")
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("CRYOPOD_API_KEY", raising=False)

        runner = CliRunner()
        result = runner.invoke(cli, ["status"])

        assert result.exit_code == 0
