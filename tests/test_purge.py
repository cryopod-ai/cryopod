"""Tests for the cryopod purge command."""

from unittest.mock import MagicMock, patch

import httpx
from click.testing import CliRunner

from cryopod.cli import cli
from tests.helpers import make_mock_httpx_client


def _mock_delete_response(
    status_code: int, json_data: dict | None = None, text: str = ""
):
    """Create a mock httpx.Client that returns a response for DELETE."""
    mock_client, mock_context = make_mock_httpx_client()

    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    if json_data is not None:
        resp.json.return_value = json_data
    else:
        resp.json.side_effect = Exception("No JSON")
    mock_client.delete.return_value = resp

    return mock_context, mock_client


class TestApiKeyValidation:
    """Tests for API key validation."""

    def test_no_api_key(self, monkeypatch):
        """Exit code 1 when CRYOPOD_API_KEY is not set."""
        monkeypatch.delenv("CRYOPOD_API_KEY", raising=False)

        runner = CliRunner()
        result = runner.invoke(cli, ["purge", "mypod", "--yes"])

        assert result.exit_code != 0
        assert "CRYOPOD_API_KEY" in result.output

    def test_empty_api_key(self, monkeypatch):
        """Exit code 1 when CRYOPOD_API_KEY is empty string."""
        monkeypatch.setenv("CRYOPOD_API_KEY", "")

        runner = CliRunner()
        result = runner.invoke(cli, ["purge", "mypod", "--yes"])

        assert result.exit_code != 0
        assert "CRYOPOD_API_KEY" in result.output


class TestConfirmationPrompt:
    """Tests for the confirmation prompt."""

    def test_default_input_aborts(self, monkeypatch):
        """Empty input (default=No) aborts the command."""
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        runner = CliRunner()
        result = runner.invoke(cli, ["purge", "mypod"], input="\n")

        assert result.exit_code != 0

    def test_y_input_proceeds(self, monkeypatch):
        """Typing 'y' proceeds with purge."""
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_ctx, mock_client = _mock_delete_response(204)

        with patch("cryopod.purge.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["purge", "mypod"], input="y\n")

        assert result.exit_code == 0
        assert "PURGED" in result.output
        mock_client.delete.assert_called_once()

    def test_yes_flag_skips_prompt(self, monkeypatch):
        """--yes flag skips the confirmation prompt."""
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_ctx, mock_client = _mock_delete_response(204)

        with patch("cryopod.purge.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["purge", "mypod", "--yes"])

        assert result.exit_code == 0
        assert "PURGED" in result.output
        # No prompt text should appear
        assert "Purge pod" not in result.output

    def test_y_short_flag_skips_prompt(self, monkeypatch):
        """-y flag skips the confirmation prompt."""
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_ctx, _ = _mock_delete_response(204)

        with patch("cryopod.purge.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["purge", "mypod", "-y"])

        assert result.exit_code == 0
        assert "PURGED" in result.output


class TestSuccessfulPurge:
    """Tests for successful purge."""

    def test_200_response(self, monkeypatch):
        """200 response results in success."""
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_ctx, mock_client = _mock_delete_response(200)

        with patch("cryopod.purge.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["purge", "mypod", "--yes"])

        assert result.exit_code == 0
        assert "PURGED" in result.output
        assert "mypod" in result.output

    def test_204_response(self, monkeypatch):
        """204 response results in success."""
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_ctx, _ = _mock_delete_response(204)

        with patch("cryopod.purge.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["purge", "mypod", "--yes"])

        assert result.exit_code == 0
        assert "PURGED" in result.output

    def test_correct_url_called(self, monkeypatch):
        """DELETE request sent to correct URL with auth header."""
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_ctx, mock_client = _mock_delete_response(204)

        with (
            patch("cryopod.purge.API_BASE_URL", "https://api.example.com"),
            patch("cryopod.purge.httpx.Client", return_value=mock_ctx),
        ):
            runner = CliRunner()
            result = runner.invoke(cli, ["purge", "my-agent", "--yes"])

        assert result.exit_code == 0
        mock_client.delete.assert_called_once_with(
            "https://api.example.com/api/pods/my-agent/",
            headers={"Authorization": "Bearer test-key"},
        )


class TestErrorHandling:
    """Tests for error responses."""

    def test_404_not_found(self, monkeypatch):
        """404 response shows 'not found' error."""
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_ctx, _ = _mock_delete_response(404)

        with patch("cryopod.purge.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["purge", "mypod", "--yes"])

        assert result.exit_code != 0
        assert "not found" in result.output

    def test_401_auth_error(self, monkeypatch):
        """401 response shows authentication error."""
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_ctx, _ = _mock_delete_response(401)

        with patch("cryopod.purge.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["purge", "mypod", "--yes"])

        assert result.exit_code != 0
        assert "Authentication failed" in result.output

    def test_403_auth_error(self, monkeypatch):
        """403 response shows authentication error."""
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_ctx, _ = _mock_delete_response(403)

        with patch("cryopod.purge.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["purge", "mypod", "--yes"])

        assert result.exit_code != 0
        assert "Authentication failed" in result.output

    def test_500_server_error(self, monkeypatch):
        """500 response shows status code in error."""
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_ctx, _ = _mock_delete_response(
            500,
            json_data={"detail": "Internal server error"},
            text="Internal server error",
        )

        with patch("cryopod.purge.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["purge", "mypod", "--yes"])

        assert result.exit_code != 0
        assert "500" in result.output

    def test_connect_error(self, monkeypatch):
        """ConnectError produces friendly error message."""
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_client, mock_context = make_mock_httpx_client()
        mock_client.delete.side_effect = httpx.ConnectError("Connection refused")

        with patch("cryopod.purge.httpx.Client", return_value=mock_context):
            runner = CliRunner()
            result = runner.invoke(cli, ["purge", "mypod", "--yes"])

        assert result.exit_code != 0
        assert "Could not connect" in result.output

    def test_timeout_error(self, monkeypatch):
        """TimeoutException produces friendly error message."""
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_client, mock_context = make_mock_httpx_client()
        mock_client.delete.side_effect = httpx.TimeoutException("Timed out")

        with patch("cryopod.purge.httpx.Client", return_value=mock_context):
            runner = CliRunner()
            result = runner.invoke(cli, ["purge", "mypod", "--yes"])

        assert result.exit_code != 0
        assert "timed out" in result.output


class TestNameArgument:
    """Tests for the required name argument."""

    def test_missing_name(self):
        """Omitting name argument results in error."""
        runner = CliRunner()
        result = runner.invoke(cli, ["purge"])

        assert result.exit_code != 0


class TestDeleteCommandRemoved:
    """Tests that the old 'delete' command no longer exists."""

    def test_delete_is_not_valid_command(self):
        """'cryopod delete' should not be a valid command."""
        runner = CliRunner()
        result = runner.invoke(cli, ["delete", "mypod", "--yes"])

        assert result.exit_code != 0
