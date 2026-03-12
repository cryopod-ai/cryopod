"""Tests for the cryopod restore command."""

from unittest.mock import MagicMock, patch

import httpx
from click.testing import CliRunner

from cryopod.cli import cli
from tests.helpers import make_mock_httpx_client


def _mock_post_response(
    status_code: int, json_data: dict | None = None, text: str = ""
):
    """Create a mock httpx.Client that returns a response for POST."""
    mock_client, mock_context = make_mock_httpx_client()

    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    if json_data is not None:
        resp.json.return_value = json_data
    else:
        resp.json.side_effect = Exception("No JSON")
    mock_client.post.return_value = resp

    return mock_context, mock_client


class TestApiKeyValidation:
    """Tests for API key validation."""

    def test_no_api_key(self, monkeypatch):
        """Exit code 1 when CRYOPOD_API_KEY is not set."""
        monkeypatch.delenv("CRYOPOD_API_KEY", raising=False)

        runner = CliRunner()
        result = runner.invoke(cli, ["restore", "mypod", "2"])

        assert result.exit_code != 0
        assert "CRYOPOD_API_KEY" in result.output

    def test_empty_api_key(self, monkeypatch):
        """Exit code 1 when CRYOPOD_API_KEY is empty string."""
        monkeypatch.setenv("CRYOPOD_API_KEY", "")

        runner = CliRunner()
        result = runner.invoke(cli, ["restore", "mypod", "2"])

        assert result.exit_code != 0
        assert "CRYOPOD_API_KEY" in result.output


class TestVersionArgValidation:
    """Tests for version argument validation."""

    def test_non_integer_version(self):
        """Non-integer version argument results in error."""
        runner = CliRunner()
        result = runner.invoke(cli, ["restore", "mypod", "abc"])

        assert result.exit_code != 0

    def test_zero_version(self, monkeypatch):
        """Version 0 results in a clear error."""
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        runner = CliRunner()
        result = runner.invoke(cli, ["restore", "mypod", "0"])

        assert result.exit_code != 0
        assert "positive integer" in result.output

    def test_negative_version(self, monkeypatch):
        """Negative version results in a clear error."""
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        runner = CliRunner()
        result = runner.invoke(cli, ["restore", "mypod", "-1"])

        assert result.exit_code != 0

    def test_missing_arguments(self):
        """Omitting arguments results in error."""
        runner = CliRunner()
        result = runner.invoke(cli, ["restore"])

        assert result.exit_code != 0


class TestSuccessfulRestore:
    """Tests for successful restore."""

    def test_200_response(self, monkeypatch):
        """200 response with new version results in success."""
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_ctx, mock_client = _mock_post_response(200, json_data={"version": 5})

        with patch("cryopod.restore.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["restore", "mypod", "2"])

        assert result.exit_code == 0
        assert "restored" in result.output
        assert "version 5" in result.output
        assert "from version 2" in result.output

    def test_output_contains_pod_name(self, monkeypatch):
        """Success output includes the pod name."""
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_ctx, _ = _mock_post_response(200, json_data={"version": 3})

        with patch("cryopod.restore.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["restore", "my-agent", "1"])

        assert result.exit_code == 0
        assert "my-agent" in result.output


class TestCorrectUrlCalled:
    """Tests that the correct URL and headers are used."""

    def test_correct_url_and_auth(self, monkeypatch):
        """POST request sent to correct URL with auth header."""
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_ctx, mock_client = _mock_post_response(200, json_data={"version": 5})

        with (
            patch("cryopod.restore.API_BASE_URL", "https://api.example.com"),
            patch("cryopod.restore.httpx.Client", return_value=mock_ctx),
        ):
            runner = CliRunner()
            result = runner.invoke(cli, ["restore", "my-agent", "2"])

        assert result.exit_code == 0
        mock_client.post.assert_called_once_with(
            "https://api.example.com/api/pods/my-agent/versions/2/restore/",
            headers={"Authorization": "Bearer test-key"},
        )


class TestErrorHandling:
    """Tests for error responses."""

    def test_404_not_found(self, monkeypatch):
        """404 response shows 'not found' error."""
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_ctx, _ = _mock_post_response(404)

        with patch("cryopod.restore.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["restore", "mypod", "99"])

        assert result.exit_code != 0
        assert "not found" in result.output

    def test_401_auth_error(self, monkeypatch):
        """401 response shows authentication error."""
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_ctx, _ = _mock_post_response(401)

        with patch("cryopod.restore.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["restore", "mypod", "2"])

        assert result.exit_code != 0
        assert "Authentication failed" in result.output

    def test_403_auth_error(self, monkeypatch):
        """403 response shows authentication error."""
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_ctx, _ = _mock_post_response(403)

        with patch("cryopod.restore.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["restore", "mypod", "2"])

        assert result.exit_code != 0
        assert "Authentication failed" in result.output

    def test_500_server_error(self, monkeypatch):
        """500 response shows status code in error."""
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_ctx, _ = _mock_post_response(
            500,
            json_data={"detail": "Internal server error"},
            text="Internal server error",
        )

        with patch("cryopod.restore.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["restore", "mypod", "2"])

        assert result.exit_code != 0
        assert "500" in result.output

    def test_connect_error(self, monkeypatch):
        """ConnectError produces friendly error message."""
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_client, mock_context = make_mock_httpx_client()
        mock_client.post.side_effect = httpx.ConnectError("Connection refused")

        with patch("cryopod.restore.httpx.Client", return_value=mock_context):
            runner = CliRunner()
            result = runner.invoke(cli, ["restore", "mypod", "2"])

        assert result.exit_code != 0
        assert "Could not connect" in result.output

    def test_timeout_error(self, monkeypatch):
        """TimeoutException produces friendly error message."""
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_client, mock_context = make_mock_httpx_client()
        mock_client.post.side_effect = httpx.TimeoutException("Timed out")

        with patch("cryopod.restore.httpx.Client", return_value=mock_context):
            runner = CliRunner()
            result = runner.invoke(cli, ["restore", "mypod", "2"])

        assert result.exit_code != 0
        assert "timed out" in result.output
