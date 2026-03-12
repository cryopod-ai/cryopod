"""Tests for the cryopod manifest command."""

from unittest.mock import MagicMock, patch

import httpx
from click.testing import CliRunner

from cryopod.cli import cli
from cryopod.formatting import format_timestamp
from tests.helpers import make_mock_httpx_client


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


def _mock_paginated_pods_response(pages: list[tuple[list[dict], int]]):
    """Create a mock httpx.Client that returns pods across multiple pages.

    pages: list of (items, count) tuples, one per page.
    """
    mock_client, mock_context = make_mock_httpx_client()

    responses = []
    for items, count in pages:
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"items": items, "count": count}
        responses.append(resp)

    mock_client.get.side_effect = responses

    return mock_context


SAMPLE_POD = {
    "name": "claude",
    "file_size": 2048,
    "version": 1,
    "created_at": "2026-03-07T10:00:00+00:00",
    "updated_at": "2026-03-07T14:32:00+00:00",
}


class TestApiKeyValidation:
    """Tests for API key validation."""

    def test_no_api_key(self, monkeypatch):
        """Exit code 1 when CRYOPOD_API_KEY is not set."""
        monkeypatch.delenv("CRYOPOD_API_KEY", raising=False)

        runner = CliRunner()
        result = runner.invoke(cli, ["manifest"])

        assert result.exit_code != 0
        assert "CRYOPOD_API_KEY" in result.output

    def test_empty_api_key(self, monkeypatch):
        """Exit code 1 when CRYOPOD_API_KEY is empty string."""
        monkeypatch.setenv("CRYOPOD_API_KEY", "")

        runner = CliRunner()
        result = runner.invoke(cli, ["manifest"])

        assert result.exit_code != 0
        assert "CRYOPOD_API_KEY" in result.output


class TestManifestRendering:
    """Tests for manifest table rendering with mocked HTTP."""

    def test_shows_remote_pods(self, monkeypatch):
        """Remote pod names appear in output."""
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_ctx = _mock_pods_response([SAMPLE_POD])

        with patch("cryopod.manifest.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["manifest"])

        assert result.exit_code == 0
        assert "claude" in result.output

    def test_columns_pod_last_frozen_size_encrypted(self, monkeypatch):
        """All four column headers appear in output."""
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_ctx = _mock_pods_response([SAMPLE_POD])

        with patch("cryopod.manifest.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["manifest"])

        assert result.exit_code == 0
        assert "POD" in result.output
        assert "LAST FROZEN" in result.output
        assert "SIZE" in result.output
        assert "ENCRYPTED" in result.output

    def test_last_frozen_and_size_shown(self, monkeypatch):
        """Remote pod's updated_at and file_size appear formatted."""
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_ctx = _mock_pods_response([SAMPLE_POD])

        with patch("cryopod.manifest.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["manifest"])

        assert result.exit_code == 0
        assert "2026-03-07 14:32" in result.output
        assert "2.0 KB" in result.output

    def test_encrypted_column_shows_dash(self, monkeypatch):
        """Encrypted column shows dash for all rows."""
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_ctx = _mock_pods_response([SAMPLE_POD])

        with patch("cryopod.manifest.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["manifest"])

        assert result.exit_code == 0
        assert "\u2014" in result.output

    def test_empty_remote_shows_empty_table(self, monkeypatch):
        """No error when API returns zero pods."""
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_ctx = _mock_pods_response([])

        with patch("cryopod.manifest.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["manifest"])

        assert result.exit_code == 0
        assert "CRYOPOD // MANIFEST" in result.output

    def test_no_config_option_accepted(self):
        """--config option is rejected (no longer supported)."""
        runner = CliRunner()
        result = runner.invoke(cli, ["manifest", "--config", "foo"])

        assert result.exit_code != 0
        assert "No such option" in result.output or "no such option" in result.output


class TestApiErrors:
    """Tests for API error handling."""

    def test_api_error_500(self, monkeypatch):
        """API returns 500, command exits with error, no partial table."""
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_client, mock_context = make_mock_httpx_client()

        resp = MagicMock()
        resp.status_code = 500
        resp.json.return_value = {"detail": "Internal server error"}
        resp.text = "Internal server error"
        mock_client.get.return_value = resp

        with patch("cryopod.manifest.httpx.Client", return_value=mock_context):
            runner = CliRunner()
            result = runner.invoke(cli, ["manifest"])

        assert result.exit_code != 0
        assert "500" in result.output

    def test_connect_error(self, monkeypatch):
        """httpx.ConnectError produces friendly error message."""
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        with patch(
            "cryopod.manifest._fetch_all_pods",
            side_effect=httpx.ConnectError("Connection refused"),
        ):
            runner = CliRunner()
            result = runner.invoke(cli, ["manifest"])

        assert result.exit_code != 0

    def test_connect_error_via_client(self, monkeypatch):
        """httpx.ConnectError from client produces friendly error message."""
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_client, mock_context = make_mock_httpx_client()
        mock_client.get.side_effect = httpx.ConnectError("Connection refused")

        with patch("cryopod.manifest.httpx.Client", return_value=mock_context):
            runner = CliRunner()
            result = runner.invoke(cli, ["manifest"])

        assert result.exit_code != 0
        assert "Could not connect" in result.output

    def test_timeout_error(self, monkeypatch):
        """httpx.TimeoutException produces friendly error message."""
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_client, mock_context = make_mock_httpx_client()
        mock_client.get.side_effect = httpx.TimeoutException("Timed out")

        with patch("cryopod.manifest.httpx.Client", return_value=mock_context):
            runner = CliRunner()
            result = runner.invoke(cli, ["manifest"])

        assert result.exit_code != 0
        assert "timed out" in result.output

    def test_auth_error_401(self, monkeypatch):
        """API returns 401, command exits with auth error."""
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_client, mock_context = make_mock_httpx_client()

        resp = MagicMock()
        resp.status_code = 401
        mock_client.get.return_value = resp

        with patch("cryopod.manifest.httpx.Client", return_value=mock_context):
            runner = CliRunner()
            result = runner.invoke(cli, ["manifest"])

        assert result.exit_code != 0
        assert "Authentication failed" in result.output


class TestPagination:
    """Tests for pagination handling."""

    def test_multiple_pages_fetched(self, monkeypatch):
        """Mock API returning 2 pages, verify all pods appear."""
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        pod1 = {
            "name": "agent-a",
            "file_size": 1024,
            "version": 1,
            "created_at": "2026-03-07T10:00:00+00:00",
            "updated_at": "2026-03-07T10:00:00+00:00",
        }
        pod2 = {
            "name": "agent-b",
            "file_size": 2048,
            "version": 1,
            "created_at": "2026-03-07T11:00:00+00:00",
            "updated_at": "2026-03-07T11:00:00+00:00",
        }

        mock_ctx = _mock_paginated_pods_response(
            [
                ([pod1], 2),  # Page 1: 1 item, total count 2
                ([pod2], 2),  # Page 2: 1 item, total count 2
            ]
        )

        with patch("cryopod.manifest.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["manifest"])

        assert result.exit_code == 0
        assert "agent-a" in result.output
        assert "agent-b" in result.output


class TestFormatTimestamp:
    """Tests for format_timestamp helper."""

    def test_format_iso_timestamp(self):
        """ISO string formatted correctly."""
        result = format_timestamp("2026-03-07T14:32:00")
        assert result == "2026-03-07 14:32"

    def test_format_timestamp_with_timezone(self):
        """Timezone-aware string handled."""
        result = format_timestamp("2026-03-07T14:32:00+00:00")
        assert result == "2026-03-07 14:32"
