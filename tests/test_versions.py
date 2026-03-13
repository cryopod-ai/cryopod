"""Tests for the cryopod versions command."""

from unittest.mock import MagicMock, patch

import httpx
from click.testing import CliRunner

from cryopod.cli import cli
from tests.helpers import make_mock_httpx_client


def _mock_versions_response(
    versions: list[dict],
    count: int | None = None,
    max_versions: int | None = None,
):
    """Create a mock httpx.Client that returns versions from GET /api/pods/{name}/versions/."""
    if count is None:
        count = len(versions)

    mock_client, mock_context = make_mock_httpx_client()

    resp_data = {"items": versions, "count": count}
    if max_versions is not None:
        resp_data["max_versions"] = max_versions

    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = resp_data
    mock_client.get.return_value = resp

    return mock_context


def _mock_paginated_versions_response(
    pages: list[tuple[list[dict], int]],
    max_versions: int | None = None,
):
    """Create a mock httpx.Client that returns versions across multiple pages.

    pages: list of (items, count) tuples, one per page.
    """
    mock_client, mock_context = make_mock_httpx_client()

    responses = []
    for items, count in pages:
        resp_data = {"items": items, "count": count}
        if max_versions is not None:
            resp_data["max_versions"] = max_versions
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = resp_data
        responses.append(resp)

    mock_client.get.side_effect = responses

    return mock_context


SAMPLE_VERSIONS = [
    {
        "version": 1,
        "created_at": "2026-03-09T10:00:00+00:00",
        "file_size": 1024,
        "source_type": "freeze",
    },
    {
        "version": 2,
        "created_at": "2026-03-10T12:30:00+00:00",
        "file_size": 2048,
        "source_type": "freeze",
    },
    {
        "version": 3,
        "created_at": "2026-03-11T14:00:00+00:00",
        "file_size": 4096,
        "source_type": "restore (from v1)",
    },
]


class TestApiKeyValidation:
    """Tests for API key validation."""

    def test_no_api_key(self, monkeypatch):
        """Exit code 1 when CRYOPOD_API_KEY is not set."""
        monkeypatch.delenv("CRYOPOD_API_KEY", raising=False)

        runner = CliRunner()
        result = runner.invoke(cli, ["versions", "claude"])

        assert result.exit_code != 0
        assert "CRYOPOD_API_KEY" in result.output

    def test_empty_api_key(self, monkeypatch):
        """Exit code 1 when CRYOPOD_API_KEY is empty string."""
        monkeypatch.setenv("CRYOPOD_API_KEY", "")

        runner = CliRunner()
        result = runner.invoke(cli, ["versions", "claude"])

        assert result.exit_code != 0
        assert "CRYOPOD_API_KEY" in result.output


class TestVersionsRendering:
    """Tests for versions table rendering with mocked HTTP."""

    def test_shows_agent_name_and_count(self, monkeypatch):
        """Agent name and version count appear in output."""
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_ctx = _mock_versions_response(SAMPLE_VERSIONS)

        with patch("cryopod.versions.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["versions", "claude"])

        assert result.exit_code == 0
        assert "claude" in result.output
        assert "3 versions" in result.output

    def test_columns_version_created_size_source(self, monkeypatch):
        """All four column headers appear in output."""
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_ctx = _mock_versions_response(SAMPLE_VERSIONS)

        with patch("cryopod.versions.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["versions", "claude"])

        assert result.exit_code == 0
        assert "VERSION" in result.output
        assert "CREATED" in result.output
        assert "SIZE" in result.output
        assert "SOURCE" in result.output

    def test_version_numbers_displayed(self, monkeypatch):
        """All version numbers appear in output."""
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_ctx = _mock_versions_response(SAMPLE_VERSIONS)

        with patch("cryopod.versions.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["versions", "claude"])

        assert result.exit_code == 0
        # Check version numbers are present
        for ver in SAMPLE_VERSIONS:
            assert str(ver["version"]) in result.output

    def test_timestamps_and_sizes_displayed(self, monkeypatch):
        """Timestamps and sizes appear formatted in output."""
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_ctx = _mock_versions_response(SAMPLE_VERSIONS)

        with patch("cryopod.versions.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["versions", "claude"])

        assert result.exit_code == 0
        assert "2026-03-09 10:00" in result.output
        assert "2026-03-11 14:00" in result.output
        assert "1.0 KB" in result.output
        assert "4.0 KB" in result.output

    def test_source_types_displayed(self, monkeypatch):
        """Source type values appear in output."""
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_ctx = _mock_versions_response(SAMPLE_VERSIONS)

        with patch("cryopod.versions.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["versions", "claude"])

        assert result.exit_code == 0
        assert "freeze" in result.output
        assert "restore (from v1)" in result.output

    def test_versions_sorted_descending(self, monkeypatch):
        """Versions appear newest first (descending order)."""
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_ctx = _mock_versions_response(SAMPLE_VERSIONS)

        with patch("cryopod.versions.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["versions", "claude"])

        assert result.exit_code == 0
        # Version 3 should appear before version 1 in the output
        pos_v3 = result.output.index("2026-03-11 14:00")
        pos_v1 = result.output.index("2026-03-09 10:00")
        assert pos_v3 < pos_v1

    def test_single_version_singular_label(self, monkeypatch):
        """Single version uses singular 'version' not 'versions'."""
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_ctx = _mock_versions_response([SAMPLE_VERSIONS[0]])

        with patch("cryopod.versions.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["versions", "claude"])

        assert result.exit_code == 0
        assert "1 version" in result.output


class TestPodNotFound:
    """Tests for pod not found handling."""

    def test_404_shows_not_found_message(self, monkeypatch):
        """Mock 404 produces clear 'not found' message."""
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_client, mock_context = make_mock_httpx_client()

        resp = MagicMock()
        resp.status_code = 404
        mock_client.get.return_value = resp

        with patch("cryopod.versions.httpx.Client", return_value=mock_context):
            runner = CliRunner()
            result = runner.invoke(cli, ["versions", "nonexistent"])

        assert result.exit_code != 0
        assert "not found" in result.output


class TestNoVersions:
    """Tests for empty versions list."""

    def test_empty_versions_shows_message(self, monkeypatch):
        """Mock empty list produces clear 'no versions' message."""
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_ctx = _mock_versions_response([])

        with patch("cryopod.versions.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["versions", "claude"])

        assert result.exit_code == 0
        assert "no versions" in result.output


class TestApiErrors:
    """Tests for API error handling."""

    def test_auth_error_401(self, monkeypatch):
        """API returns 401, command exits with auth error."""
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_client, mock_context = make_mock_httpx_client()

        resp = MagicMock()
        resp.status_code = 401
        mock_client.get.return_value = resp

        with patch("cryopod.versions.httpx.Client", return_value=mock_context):
            runner = CliRunner()
            result = runner.invoke(cli, ["versions", "claude"])

        assert result.exit_code != 0
        assert "Authentication failed" in result.output

    def test_auth_error_403(self, monkeypatch):
        """API returns 403, command exits with auth error."""
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_client, mock_context = make_mock_httpx_client()

        resp = MagicMock()
        resp.status_code = 403
        mock_client.get.return_value = resp

        with patch("cryopod.versions.httpx.Client", return_value=mock_context):
            runner = CliRunner()
            result = runner.invoke(cli, ["versions", "claude"])

        assert result.exit_code != 0
        assert "Authentication failed" in result.output

    def test_api_error_500(self, monkeypatch):
        """API returns 500, command exits with error."""
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_client, mock_context = make_mock_httpx_client()

        resp = MagicMock()
        resp.status_code = 500
        resp.json.return_value = {"detail": "Internal server error"}
        resp.text = "Internal server error"
        mock_client.get.return_value = resp

        with patch("cryopod.versions.httpx.Client", return_value=mock_context):
            runner = CliRunner()
            result = runner.invoke(cli, ["versions", "claude"])

        assert result.exit_code != 0
        assert "500" in result.output

    def test_connect_error(self, monkeypatch):
        """httpx.ConnectError produces friendly error message."""
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_client, mock_context = make_mock_httpx_client()
        mock_client.get.side_effect = httpx.ConnectError("Connection refused")

        with patch("cryopod.versions.httpx.Client", return_value=mock_context):
            runner = CliRunner()
            result = runner.invoke(cli, ["versions", "claude"])

        assert result.exit_code != 0
        assert "Could not connect" in result.output

    def test_timeout_error(self, monkeypatch):
        """httpx.TimeoutException produces friendly error message."""
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_client, mock_context = make_mock_httpx_client()
        mock_client.get.side_effect = httpx.TimeoutException("Timed out")

        with patch("cryopod.versions.httpx.Client", return_value=mock_context):
            runner = CliRunner()
            result = runner.invoke(cli, ["versions", "claude"])

        assert result.exit_code != 0
        assert "timed out" in result.output


class TestPagination:
    """Tests for pagination handling."""

    def test_multiple_pages_fetched(self, monkeypatch):
        """Mock API returning 2 pages, verify all versions appear."""
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        v1 = {
            "version": 1,
            "created_at": "2026-03-09T10:00:00+00:00",
            "file_size": 1024,
            "source_type": "freeze",
        }
        v2 = {
            "version": 2,
            "created_at": "2026-03-10T12:30:00+00:00",
            "file_size": 2048,
            "source_type": "freeze",
        }

        mock_ctx = _mock_paginated_versions_response(
            [
                ([v1], 2),  # Page 1: 1 item, total count 2
                ([v2], 2),  # Page 2: 1 item, total count 2
            ]
        )

        with patch("cryopod.versions.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["versions", "claude"])

        assert result.exit_code == 0
        assert "2026-03-09 10:00" in result.output
        assert "2026-03-10 12:30" in result.output
        assert "2 versions" in result.output


class TestMaxVersionsDisplay:
    """Tests for max_versions display in panel title."""

    def test_max_versions_shown_in_title(self, monkeypatch):
        """Panel title includes max_versions when API provides it."""
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_ctx = _mock_versions_response(SAMPLE_VERSIONS, max_versions=20)

        with patch("cryopod.versions.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["versions", "claude"])

        assert result.exit_code == 0
        assert "3 versions (max: 20)" in result.output

    def test_max_versions_absent_graceful_fallback(self, monkeypatch):
        """Panel title omits max info when API does not return max_versions."""
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_ctx = _mock_versions_response(SAMPLE_VERSIONS)

        with patch("cryopod.versions.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["versions", "claude"])

        assert result.exit_code == 0
        assert "3 versions" in result.output
        assert "(max:" not in result.output

    def test_max_versions_with_single_version(self, monkeypatch):
        """Singular 'version' label with max_versions present."""
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_ctx = _mock_versions_response([SAMPLE_VERSIONS[0]], max_versions=10)

        with patch("cryopod.versions.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["versions", "claude"])

        assert result.exit_code == 0
        assert "1 version (max: 10)" in result.output

    def test_max_versions_shown_in_title_boundary(self, monkeypatch):
        """Boundary case: max_versions of 1."""
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_ctx = _mock_versions_response([SAMPLE_VERSIONS[0]], max_versions=1)

        with patch("cryopod.versions.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["versions", "claude"])

        assert result.exit_code == 0
        assert "(max: 1)" in result.output
