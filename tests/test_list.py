"""Tests for the cryopod list command."""

from unittest.mock import MagicMock, patch

import httpx
from click.testing import CliRunner

from cryopod.cli import cli
from tests.helpers import make_mock_httpx_client, write_config


def _mock_pods_response(pods: list[dict], count: int | None = None):
    """Create a mock httpx.Client that returns pods from GET /api/pods/."""
    if count is None:
        count = len(pods)

    mock_client, mock_context = make_mock_httpx_client()

    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"items": pods, "count": count}
    mock_client.get.return_value = resp

    return mock_context


SAMPLE_POD = {
    "name": "claude",
    "file_size": 2048,
    "version": 1,
    "created_at": "2026-03-07T10:00:00+00:00",
    "updated_at": "2026-03-07T14:32:00+00:00",
}


class TestApiKeyValidation:
    """Tests for API key validation in list command."""

    def test_no_api_key(self, tmp_path, monkeypatch):
        """Exit code 1 when CRYOPOD_API_KEY is not set."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("CRYOPOD_API_KEY", raising=False)

        runner = CliRunner()
        result = runner.invoke(cli, ["list"])

        assert result.exit_code != 0
        assert "CRYOPOD_API_KEY" in result.output

    def test_empty_api_key(self, tmp_path, monkeypatch):
        """Exit code 1 when CRYOPOD_API_KEY is empty string."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "")

        runner = CliRunner()
        result = runner.invoke(cli, ["list"])

        assert result.exit_code != 0
        assert "CRYOPOD_API_KEY" in result.output


class TestListRendering:
    """Tests for list table rendering with mocked HTTP."""

    def test_synchronized_status(self, tmp_path, monkeypatch):
        """Agent in both local config and remote shows Synchronized."""
        write_config(
            tmp_path / ".cryopod.toml",
            {"claude": {"directory": ".claude"}},
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_ctx = _mock_pods_response([SAMPLE_POD])

        with patch("cryopod.manifest.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["list"])

        assert result.exit_code == 0
        assert "Pod Synchronized" in result.output

    def test_awaiting_upload_status(self, tmp_path, monkeypatch):
        """Agent in local config only shows Awaiting Upload."""
        write_config(
            tmp_path / ".cryopod.toml",
            {"claude": {"directory": ".claude"}},
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_ctx = _mock_pods_response([])

        with patch("cryopod.manifest.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["list"])

        assert result.exit_code == 0
        assert "Awaiting Upload" in result.output

    def test_awaiting_download_status(self, tmp_path, monkeypatch):
        """Agent in remote only shows Awaiting Download."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_ctx = _mock_pods_response([SAMPLE_POD])

        with patch("cryopod.manifest.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["list"])

        assert result.exit_code == 0
        assert "Awaiting Download" in result.output

    def test_mixed_statuses(self, tmp_path, monkeypatch):
        """Multiple agents with different statuses all appear."""
        write_config(
            tmp_path / ".cryopod.toml",
            {
                "claude": {"directory": ".claude"},
                "local-only": {"directory": ".local-only"},
            },
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        remote_pods = [
            SAMPLE_POD,  # claude — synchronized
            {
                "name": "remote-only",
                "file_size": 1024,
                "version": 1,
                "created_at": "2026-03-06T10:00:00+00:00",
                "updated_at": "2026-03-06T12:00:00+00:00",
            },
        ]
        mock_ctx = _mock_pods_response(remote_pods)

        with patch("cryopod.manifest.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["list"])

        assert result.exit_code == 0
        assert "Pod Synchronized" in result.output
        assert "Pod Awaiting Upload" in result.output
        assert "Pod Awaiting Download" in result.output

    def test_last_frozen_and_size_shown(self, tmp_path, monkeypatch):
        """Remote pod's updated_at and file_size appear formatted."""
        write_config(
            tmp_path / ".cryopod.toml",
            {"claude": {"directory": ".claude"}},
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_ctx = _mock_pods_response([SAMPLE_POD])

        with patch("cryopod.manifest.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["list"])

        assert result.exit_code == 0
        assert "2026-03-07 14:32" in result.output
        assert "2.0 KB" in result.output

    def test_no_remote_shows_dash(self, tmp_path, monkeypatch):
        """Local-only agents show dashes for Last Frozen and Size."""
        write_config(
            tmp_path / ".cryopod.toml",
            {"claude": {"directory": ".claude"}},
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_ctx = _mock_pods_response([])

        with patch("cryopod.manifest.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["list"])

        assert result.exit_code == 0
        assert "\u2014" in result.output

    def test_panel_title(self, tmp_path, monkeypatch):
        """Output contains CRYOPOD // LIST panel title."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_ctx = _mock_pods_response([SAMPLE_POD])

        with patch("cryopod.manifest.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["list"])

        assert result.exit_code == 0
        assert "CRYOPOD // LIST" in result.output

    def test_no_encrypted_column(self, tmp_path, monkeypatch):
        """List command should not have an ENCRYPTED column."""
        write_config(
            tmp_path / ".cryopod.toml",
            {"claude": {"directory": ".claude"}},
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_ctx = _mock_pods_response([SAMPLE_POD])

        with patch("cryopod.manifest.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["list"])

        assert result.exit_code == 0
        assert "ENCRYPTED" not in result.output

    def test_empty_state(self, tmp_path, monkeypatch):
        """No local config and no remote pods renders without crashing."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_ctx = _mock_pods_response([])

        with patch("cryopod.manifest.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["list"])

        assert result.exit_code == 0
        assert "CRYOPOD // LIST" in result.output


class TestNoConfig:
    """Tests for missing config file."""

    def test_missing_config_shows_remote_only(self, tmp_path, monkeypatch):
        """No .cryopod.toml, remote pods appear as Awaiting Download."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_ctx = _mock_pods_response([SAMPLE_POD])

        with patch("cryopod.manifest.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["list"])

        assert result.exit_code == 0
        assert "Awaiting Download" in result.output
        assert "claude" in result.output


class TestApiErrors:
    """Tests for API error handling in list command."""

    def test_api_error_500(self, tmp_path, monkeypatch):
        """API returns 500, command exits with error."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_client, mock_context = make_mock_httpx_client()

        resp = MagicMock()
        resp.status_code = 500
        resp.json.return_value = {"detail": "Internal server error"}
        resp.text = "Internal server error"
        mock_client.get.return_value = resp

        with patch("cryopod.manifest.httpx.Client", return_value=mock_context):
            runner = CliRunner()
            result = runner.invoke(cli, ["list"])

        assert result.exit_code != 0
        assert "500" in result.output

    def test_connect_error_via_client(self, tmp_path, monkeypatch):
        """httpx.ConnectError from client produces friendly error message."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_client, mock_context = make_mock_httpx_client()
        mock_client.get.side_effect = httpx.ConnectError("Connection refused")

        with patch("cryopod.manifest.httpx.Client", return_value=mock_context):
            runner = CliRunner()
            result = runner.invoke(cli, ["list"])

        assert result.exit_code != 0
        assert "Could not connect" in result.output

    def test_timeout_error(self, tmp_path, monkeypatch):
        """httpx.TimeoutException produces friendly error message."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_client, mock_context = make_mock_httpx_client()
        mock_client.get.side_effect = httpx.TimeoutException("Timed out")

        with patch("cryopod.manifest.httpx.Client", return_value=mock_context):
            runner = CliRunner()
            result = runner.invoke(cli, ["list"])

        assert result.exit_code != 0
        assert "timed out" in result.output

    def test_auth_error_401(self, tmp_path, monkeypatch):
        """API returns 401, command exits with auth error."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_client, mock_context = make_mock_httpx_client()

        resp = MagicMock()
        resp.status_code = 401
        mock_client.get.return_value = resp

        with patch("cryopod.manifest.httpx.Client", return_value=mock_context):
            runner = CliRunner()
            result = runner.invoke(cli, ["list"])

        assert result.exit_code != 0
        assert "Authentication failed" in result.output


class TestConfigOverride:
    """Tests for --config option."""

    def test_custom_config_path(self, tmp_path, monkeypatch):
        """--config option loads config from custom path."""
        custom_config = tmp_path / "custom.toml"
        write_config(
            custom_config,
            {"my-agent": {"directory": ".my-agent"}},
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_ctx = _mock_pods_response([])

        with patch("cryopod.manifest.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["list", "--config", str(custom_config)])

        assert result.exit_code == 0
        assert "my-agent" in result.output
        assert "Awaiting Upload" in result.output
