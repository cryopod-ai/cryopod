"""Tests for the cryopod freeze command."""

import io
import tarfile
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from cryopod.agents import CREDENTIAL_IGNORE, _build_ignore
from cryopod.cli import cli
from cryopod.crypto import decrypt_archive, encrypt_archive
from cryopod.freeze import _build_archive
from tests.helpers import make_mock_httpx_client, write_config


def _tar_names(archive_bytes: bytes) -> list[str]:
    """Extract file names from a tar.gz archive."""
    buf = io.BytesIO(archive_bytes)
    with tarfile.open(fileobj=buf, mode="r:gz") as tar:
        return sorted(tar.getnames())


def _mock_successful_upload():
    """Create a mock httpx.Client that simulates successful upload."""
    mock_client, mock_context = make_mock_httpx_client()

    post_resp = MagicMock()
    post_resp.status_code = 201
    post_resp.json.return_value = {
        "upload_url": "https://storage.example.com/upload/presigned",
        "version": 1,
    }
    mock_client.post.return_value = post_resp

    put_resp = MagicMock()
    put_resp.status_code = 200
    mock_client.put.return_value = put_resp

    return mock_context


def _mock_upload_with_response(response_data: dict):
    """Create a mock httpx.Client that returns a custom API response."""
    mock_client, mock_context = make_mock_httpx_client()

    post_resp = MagicMock()
    post_resp.status_code = 201
    post_resp.json.return_value = response_data
    mock_client.post.return_value = post_resp

    put_resp = MagicMock()
    put_resp.status_code = 200
    mock_client.put.return_value = put_resp

    return mock_context


class TestConfigValidation:
    """Tests for config validation in freeze command."""

    def test_no_config(self, tmp_path, monkeypatch):
        """Exit code 1 when no .cryopod.toml exists."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        runner = CliRunner()
        result = runner.invoke(cli, ["freeze", "claude"])

        assert result.exit_code != 0
        assert "cryopod init" in result.output

    def test_agent_not_in_config(self, tmp_path, monkeypatch):
        """Exit code 1 when agent name not found in config."""
        write_config(
            tmp_path / ".cryopod.toml",
            {"claude": {"directory": ".claude"}},
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        runner = CliRunner()
        result = runner.invoke(cli, ["freeze", "nonexistent"])

        assert result.exit_code != 0
        assert "nonexistent" in result.output
        assert "not found" in result.output

    def test_agent_directory_missing_absolute(self, tmp_path, monkeypatch):
        """Exit code 1 when agent directory (absolute path) doesn't exist on disk."""
        write_config(
            tmp_path / ".cryopod.toml",
            {"claude": {"directory": str(tmp_path / ".claude")}},
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        runner = CliRunner()
        result = runner.invoke(cli, ["freeze", "claude"])

        assert result.exit_code != 0
        assert "does not exist" in result.output

    def test_agent_directory_missing_relative(self, tmp_path, monkeypatch):
        """Exit code 1 when agent directory (relative path) doesn't exist on disk."""
        write_config(
            tmp_path / ".cryopod.toml",
            {"claude": {"directory": ".claude"}},
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        runner = CliRunner()
        result = runner.invoke(cli, ["freeze", "claude"])

        assert result.exit_code != 0
        assert "does not exist" in result.output

    def test_agent_directory_empty(self, tmp_path, monkeypatch):
        """Exit code 1 when agent has no directory configured."""
        write_config(
            tmp_path / ".cryopod.toml",
            {"claude": {"directory": ""}},
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        runner = CliRunner()
        result = runner.invoke(cli, ["freeze", "claude"])

        assert result.exit_code != 0
        assert "no directory configured" in result.output


class TestApiKeyValidation:
    """Tests for API key validation."""

    def test_no_api_key(self, tmp_path, monkeypatch):
        """Exit code 1 when CRYOPOD_API_KEY is not set."""
        write_config(
            tmp_path / ".cryopod.toml",
            {"claude": {"directory": ".claude"}},
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("CRYOPOD_API_KEY", raising=False)

        runner = CliRunner()
        result = runner.invoke(cli, ["freeze", "claude"])

        assert result.exit_code != 0
        assert "CRYOPOD_API_KEY" in result.output

    def test_empty_api_key(self, tmp_path, monkeypatch):
        """Exit code 1 when CRYOPOD_API_KEY is empty string."""
        write_config(
            tmp_path / ".cryopod.toml",
            {"claude": {"directory": ".claude"}},
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "")

        runner = CliRunner()
        result = runner.invoke(cli, ["freeze", "claude"])

        assert result.exit_code != 0
        assert "CRYOPOD_API_KEY" in result.output


class TestBuildArchive:
    """Tests for _build_archive function."""

    def test_creates_valid_archive(self, tmp_path):
        """Creates a valid tar.gz with expected files."""
        agent_dir = tmp_path / "agent"
        agent_dir.mkdir()
        (agent_dir / "config.json").write_text('{"key": "value"}')
        (agent_dir / "settings.toml").write_text("[settings]")

        result = _build_archive(agent_dir, [])
        names = _tar_names(result)

        assert "config.json" in names
        assert "settings.toml" in names

    def test_ignores_files_by_pattern(self, tmp_path):
        """Files matching ignore patterns are excluded."""
        agent_dir = tmp_path / "agent"
        agent_dir.mkdir()
        (agent_dir / "config.json").write_text("{}")
        (agent_dir / "debug.log").write_text("log data")
        (agent_dir / "error.log").write_text("error data")

        result = _build_archive(agent_dir, ["*.log"])
        names = _tar_names(result)

        assert "config.json" in names
        assert "debug.log" not in names
        assert "error.log" not in names

    def test_ignores_directories_by_pattern(self, tmp_path):
        """Directories matching ignore patterns are excluded."""
        agent_dir = tmp_path / "agent"
        agent_dir.mkdir()
        (agent_dir / "config.json").write_text("{}")
        cache_dir = agent_dir / "__pycache__"
        cache_dir.mkdir()
        (cache_dir / "module.pyc").write_text("bytecode")

        result = _build_archive(agent_dir, ["__pycache__/"])
        names = _tar_names(result)

        assert "config.json" in names
        assert "__pycache__" not in names
        assert "__pycache__/module.pyc" not in names

    def test_empty_directory(self, tmp_path):
        """Empty directory produces a valid archive."""
        agent_dir = tmp_path / "agent"
        agent_dir.mkdir()

        result = _build_archive(agent_dir, [])

        # Should be valid tar.gz, just empty
        buf = io.BytesIO(result)
        with tarfile.open(fileobj=buf, mode="r:gz") as tar:
            assert tar.getnames() == []

    def test_nested_files(self, tmp_path):
        """Nested files are archived with correct relative paths."""
        agent_dir = tmp_path / "agent"
        agent_dir.mkdir()
        sub = agent_dir / "subdir"
        sub.mkdir()
        (sub / "nested.txt").write_text("hello")

        result = _build_archive(agent_dir, [])
        names = _tar_names(result)

        assert "subdir/nested.txt" in names


class TestUploadMocked:
    """Tests for freeze with mocked HTTP."""

    def test_successful_freeze(self, tmp_path, monkeypatch):
        """Successful freeze shows FROZEN message with name and size."""
        agent_dir = tmp_path / ".claude"
        agent_dir.mkdir()
        (agent_dir / "config.json").write_text('{"key": "value"}')

        write_config(
            tmp_path / ".cryopod.toml",
            {"claude": {"directory": str(agent_dir)}},
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_ctx = _mock_successful_upload()

        with patch("cryopod.freeze.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["freeze", "claude"])

        assert result.exit_code == 0
        assert "▸ FROZEN claude" in result.output

    def test_409_fallback_to_patch(self, tmp_path, monkeypatch):
        """On 409 conflict, falls back to PATCH and succeeds."""
        agent_dir = tmp_path / ".claude"
        agent_dir.mkdir()
        (agent_dir / "config.json").write_text("{}")

        write_config(
            tmp_path / ".cryopod.toml",
            {"claude": {"directory": str(agent_dir)}},
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_client, mock_context = make_mock_httpx_client()

        # POST returns 409
        post_resp = MagicMock()
        post_resp.status_code = 409
        mock_client.post.return_value = post_resp

        # PATCH returns 200
        patch_resp = MagicMock()
        patch_resp.status_code = 200
        patch_resp.json.return_value = {
            "upload_url": "https://storage.example.com/upload/presigned"
        }
        mock_client.patch.return_value = patch_resp

        # PUT returns 200
        put_resp = MagicMock()
        put_resp.status_code = 200
        mock_client.put.return_value = put_resp

        with patch("cryopod.freeze.httpx.Client", return_value=mock_context):
            runner = CliRunner()
            result = runner.invoke(cli, ["freeze", "claude"])

        assert result.exit_code == 0
        assert "▸ FROZEN claude" in result.output
        mock_client.patch.assert_called_once()

    def test_api_error_500(self, tmp_path, monkeypatch):
        """API 500 error produces a clear error message."""
        agent_dir = tmp_path / ".claude"
        agent_dir.mkdir()
        (agent_dir / "config.json").write_text("{}")

        write_config(
            tmp_path / ".cryopod.toml",
            {"claude": {"directory": str(agent_dir)}},
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_client, mock_context = make_mock_httpx_client()

        post_resp = MagicMock()
        post_resp.status_code = 500
        post_resp.json.return_value = {"detail": "Internal server error"}
        post_resp.text = "Internal server error"
        mock_client.post.return_value = post_resp

        with patch("cryopod.freeze.httpx.Client", return_value=mock_context):
            runner = CliRunner()
            result = runner.invoke(cli, ["freeze", "claude"])

        assert result.exit_code != 0
        assert "500" in result.output

    def test_upload_put_error(self, tmp_path, monkeypatch):
        """PUT upload failure produces error."""
        agent_dir = tmp_path / ".claude"
        agent_dir.mkdir()
        (agent_dir / "config.json").write_text("{}")

        write_config(
            tmp_path / ".cryopod.toml",
            {"claude": {"directory": str(agent_dir)}},
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_client, mock_context = make_mock_httpx_client()

        post_resp = MagicMock()
        post_resp.status_code = 201
        post_resp.json.return_value = {
            "upload_url": "https://storage.example.com/upload/presigned"
        }
        mock_client.post.return_value = post_resp

        put_resp = MagicMock()
        put_resp.status_code = 403
        put_resp.text = "Forbidden"
        mock_client.put.return_value = put_resp

        with patch("cryopod.freeze.httpx.Client", return_value=mock_context):
            runner = CliRunner()
            result = runner.invoke(cli, ["freeze", "claude"])

        assert result.exit_code != 0
        assert "Upload failed" in result.output


class TestNetworkErrors:
    """Tests for network error handling."""

    def test_connect_error(self, tmp_path, monkeypatch):
        """Connection error produces a friendly error message."""
        agent_dir = tmp_path / ".claude"
        agent_dir.mkdir()
        (agent_dir / "config.json").write_text("{}")

        write_config(
            tmp_path / ".cryopod.toml",
            {"claude": {"directory": str(agent_dir)}},
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        import httpx

        with patch(
            "cryopod.freeze._upload_pod",
            side_effect=httpx.ConnectError("Connection refused"),
        ):
            runner = CliRunner()
            result = runner.invoke(cli, ["freeze", "claude"])

        assert result.exit_code != 0
        assert "Could not connect" in result.output

    def test_timeout_error(self, tmp_path, monkeypatch):
        """Timeout error produces a friendly error message."""
        agent_dir = tmp_path / ".claude"
        agent_dir.mkdir()
        (agent_dir / "config.json").write_text("{}")

        write_config(
            tmp_path / ".cryopod.toml",
            {"claude": {"directory": str(agent_dir)}},
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        import httpx

        with patch(
            "cryopod.freeze._upload_pod",
            side_effect=httpx.TimeoutException("Timed out"),
        ):
            runner = CliRunner()
            result = runner.invoke(cli, ["freeze", "claude"])

        assert result.exit_code != 0
        assert "timed out" in result.output


class TestFreezeAll:
    """Tests for --all flag."""

    def test_freeze_all_agents(self, tmp_path, monkeypatch):
        """--all freezes all agents sequentially."""
        for name in ("claude", "codex"):
            agent_dir = tmp_path / f".{name}"
            agent_dir.mkdir()
            (agent_dir / "config.json").write_text("{}")

        write_config(
            tmp_path / ".cryopod.toml",
            {
                "claude": {"directory": str(tmp_path / ".claude")},
                "codex": {"directory": str(tmp_path / ".codex")},
            },
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_ctx = _mock_successful_upload()

        with patch("cryopod.freeze.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["freeze", "--all"])

        assert result.exit_code == 0
        assert "▸ FROZEN claude" in result.output
        assert "▸ FROZEN codex" in result.output


class TestMutualExclusivity:
    """Tests for argument/flag mutual exclusivity."""

    def test_both_name_and_all(self, tmp_path, monkeypatch):
        """Error when both agent name and --all provided."""
        write_config(
            tmp_path / ".cryopod.toml",
            {"claude": {"directory": ".claude"}},
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        runner = CliRunner()
        result = runner.invoke(cli, ["freeze", "claude", "--all"])

        assert result.exit_code != 0
        assert "not both" in result.output

    def test_neither_name_nor_all(self, tmp_path, monkeypatch):
        """Error when neither agent name nor --all provided."""
        write_config(
            tmp_path / ".cryopod.toml",
            {"claude": {"directory": ".claude"}},
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        runner = CliRunner()
        result = runner.invoke(cli, ["freeze"])

        assert result.exit_code != 0


class TestOutputFormat:
    """Tests for output format."""

    def test_frozen_message_format(self, tmp_path, monkeypatch):
        """Success message matches FROZEN {name} ({size}) pattern."""
        agent_dir = tmp_path / ".claude"
        agent_dir.mkdir()
        (agent_dir / "config.json").write_text('{"key": "value"}')

        write_config(
            tmp_path / ".cryopod.toml",
            {"claude": {"directory": str(agent_dir)}},
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_ctx = _mock_successful_upload()

        with patch("cryopod.freeze.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["freeze", "claude"])

        assert result.exit_code == 0
        # Should match pattern: FROZEN claude (X.X KB) or similar
        assert "FROZEN claude (" in result.output
        assert ")" in result.output


class TestEncryption:
    """Tests for archive encryption."""

    def test_encrypt_decrypt_roundtrip(self):
        """Encrypt then decrypt returns original bytes."""
        original = b"hello world this is test data"
        secret = "my-secret-key"
        encrypted = encrypt_archive(original, secret)
        decrypted = decrypt_archive(encrypted, secret)
        assert decrypted == original

    def test_wrong_key_fails(self):
        """Decrypt with wrong key raises ClickException."""
        original = b"sensitive data"
        encrypted = encrypt_archive(original, "key-a")

        import click

        with pytest.raises(click.ClickException, match="Decryption failed"):
            decrypt_archive(encrypted, "key-b")

    def test_encrypted_output_has_magic_header(self):
        """Encrypted output starts with CRYOPOD_ENC\\x01."""
        encrypted = encrypt_archive(b"test data", "secret")
        assert encrypted[:11] == b"CRYOPOD_ENC"
        assert encrypted[11:12] == b"\x01"

    def test_freeze_with_secret_key_shows_warning(self, tmp_path, monkeypatch):
        """Freeze with CRYOPOD_SECRET_KEY shows encryption warning."""
        agent_dir = tmp_path / ".claude"
        agent_dir.mkdir()
        (agent_dir / "config.json").write_text("{}")

        write_config(
            tmp_path / ".cryopod.toml",
            {"claude": {"directory": str(agent_dir)}},
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")
        monkeypatch.setenv("CRYOPOD_SECRET_KEY", "my-secret")

        mock_ctx = _mock_successful_upload()

        with patch("cryopod.freeze.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["freeze", "claude"])

        assert result.exit_code == 0
        assert "ENCRYPTION ENABLED" in result.output
        assert "CRYOPOD_SECRET_KEY" in result.output

    def test_freeze_with_secret_key_encrypts(self, tmp_path, monkeypatch):
        """Freeze with CRYOPOD_SECRET_KEY sends encrypted bytes (magic header)."""
        agent_dir = tmp_path / ".claude"
        agent_dir.mkdir()
        (agent_dir / "config.json").write_text("{}")

        write_config(
            tmp_path / ".cryopod.toml",
            {"claude": {"directory": str(agent_dir)}},
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")
        monkeypatch.setenv("CRYOPOD_SECRET_KEY", "my-secret")

        mock_client, mock_context = make_mock_httpx_client()

        post_resp = MagicMock()
        post_resp.status_code = 201
        post_resp.json.return_value = {
            "upload_url": "https://storage.example.com/upload/presigned"
        }
        mock_client.post.return_value = post_resp

        put_resp = MagicMock()
        put_resp.status_code = 200
        mock_client.put.return_value = put_resp

        with patch("cryopod.freeze.httpx.Client", return_value=mock_context):
            runner = CliRunner()
            result = runner.invoke(cli, ["freeze", "claude"])

        assert result.exit_code == 0
        # Get the bytes sent to PUT
        put_call = mock_client.put.call_args
        uploaded_bytes = put_call.kwargs.get("content", put_call[1].get("content"))
        assert uploaded_bytes[:11] == b"CRYOPOD_ENC"
        # Should NOT start with gzip magic
        assert uploaded_bytes[:2] != b"\x1f\x8b"

    def test_freeze_without_secret_key_no_encryption(self, tmp_path, monkeypatch):
        """Freeze without CRYOPOD_SECRET_KEY sends plain gzip bytes."""
        agent_dir = tmp_path / ".claude"
        agent_dir.mkdir()
        (agent_dir / "config.json").write_text("{}")

        write_config(
            tmp_path / ".cryopod.toml",
            {"claude": {"directory": str(agent_dir)}},
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")
        monkeypatch.delenv("CRYOPOD_SECRET_KEY", raising=False)

        mock_client, mock_context = make_mock_httpx_client()

        post_resp = MagicMock()
        post_resp.status_code = 201
        post_resp.json.return_value = {
            "upload_url": "https://storage.example.com/upload/presigned"
        }
        mock_client.post.return_value = post_resp

        put_resp = MagicMock()
        put_resp.status_code = 200
        mock_client.put.return_value = put_resp

        with patch("cryopod.freeze.httpx.Client", return_value=mock_context):
            runner = CliRunner()
            result = runner.invoke(cli, ["freeze", "claude"])

        assert result.exit_code == 0
        put_call = mock_client.put.call_args
        uploaded_bytes = put_call.kwargs.get("content", put_call[1].get("content"))
        # Should start with gzip magic
        assert uploaded_bytes[:2] == b"\x1f\x8b"

    def test_encrypting_stage_shown(self, tmp_path, monkeypatch):
        """Freeze with CRYOPOD_SECRET_KEY shows ENCRYPTING in output."""
        agent_dir = tmp_path / ".claude"
        agent_dir.mkdir()
        (agent_dir / "config.json").write_text("{}")

        write_config(
            tmp_path / ".cryopod.toml",
            {"claude": {"directory": str(agent_dir)}},
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")
        monkeypatch.setenv("CRYOPOD_SECRET_KEY", "my-secret")

        mock_ctx = _mock_successful_upload()

        with patch("cryopod.freeze.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["freeze", "claude"])

        assert result.exit_code == 0
        assert "▸ FROZEN claude" in result.output


class TestVersionInOutput:
    """Tests for version number display in freeze output."""

    def test_version_shown_when_present(self, tmp_path, monkeypatch):
        """Success message includes version when API returns it."""
        agent_dir = tmp_path / ".claude"
        agent_dir.mkdir()
        (agent_dir / "config.json").write_text("{}")

        write_config(
            tmp_path / ".cryopod.toml",
            {"claude": {"directory": str(agent_dir)}},
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_ctx = _mock_upload_with_response(
            {"upload_url": "https://storage.example.com/upload/presigned", "version": 4}
        )

        with patch("cryopod.freeze.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["freeze", "claude"])

        assert result.exit_code == 0
        assert "version 4" in result.output
        assert "▸ FROZEN claude" in result.output

    def test_version_not_shown_when_absent(self, tmp_path, monkeypatch):
        """Success message omits version when API doesn't return it."""
        agent_dir = tmp_path / ".claude"
        agent_dir.mkdir()
        (agent_dir / "config.json").write_text("{}")

        write_config(
            tmp_path / ".cryopod.toml",
            {"claude": {"directory": str(agent_dir)}},
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_ctx = _mock_upload_with_response(
            {"upload_url": "https://storage.example.com/upload/presigned"}
        )

        with patch("cryopod.freeze.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["freeze", "claude"])

        assert result.exit_code == 0
        assert "▸ FROZEN claude" in result.output
        assert "version" not in result.output

    def test_version_shown_per_agent_with_all(self, tmp_path, monkeypatch):
        """--all shows version for each agent when API returns it."""
        for name in ("claude", "codex"):
            agent_dir = tmp_path / f".{name}"
            agent_dir.mkdir()
            (agent_dir / "config.json").write_text("{}")

        write_config(
            tmp_path / ".cryopod.toml",
            {
                "claude": {"directory": str(tmp_path / ".claude")},
                "codex": {"directory": str(tmp_path / ".codex")},
            },
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_ctx = _mock_upload_with_response(
            {"upload_url": "https://storage.example.com/upload/presigned", "version": 7}
        )

        with patch("cryopod.freeze.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["freeze", "--all"])

        assert result.exit_code == 0
        assert "▸ FROZEN claude" in result.output
        assert "▸ FROZEN codex" in result.output
        # Version shown for each agent
        assert result.output.count("version 7") == 2


class TestCredentialIgnore:
    """Tests for credential and local-settings file exclusion."""

    def test_env_files_excluded(self, tmp_path):
        """`.env`, `.env.local`, `.env.production` are excluded from archives."""
        agent_dir = tmp_path / "agent"
        agent_dir.mkdir()
        (agent_dir / ".env").write_text("SECRET=abc")
        (agent_dir / ".env.local").write_text("LOCAL=xyz")
        (agent_dir / ".env.production").write_text("PROD=123")
        (agent_dir / "config.json").write_text("{}")

        result = _build_archive(agent_dir, list(CREDENTIAL_IGNORE))
        names = _tar_names(result)

        assert "config.json" in names
        assert ".env" not in names
        assert ".env.local" not in names
        assert ".env.production" not in names

    def test_local_settings_excluded(self, tmp_path):
        """Files matching `*.local` and `*.local.json` are excluded."""
        agent_dir = tmp_path / "agent"
        agent_dir.mkdir()
        (agent_dir / "settings.local").write_text("{}")
        (agent_dir / "config.local.json").write_text("{}")
        (agent_dir / "config.json").write_text("{}")

        result = _build_archive(agent_dir, list(CREDENTIAL_IGNORE))
        names = _tar_names(result)

        assert "config.json" in names
        assert "settings.local" not in names
        assert "config.local.json" not in names

    def test_key_and_pem_excluded(self, tmp_path):
        """`.pem` and `.key` files are excluded."""
        agent_dir = tmp_path / "agent"
        agent_dir.mkdir()
        (agent_dir / "server.pem").write_text("-----BEGIN CERTIFICATE-----")
        (agent_dir / "private.key").write_text("-----BEGIN PRIVATE KEY-----")
        (agent_dir / "config.json").write_text("{}")

        result = _build_archive(agent_dir, list(CREDENTIAL_IGNORE))
        names = _tar_names(result)

        assert "config.json" in names
        assert "server.pem" not in names
        assert "private.key" not in names

    def test_credentials_json_excluded(self, tmp_path):
        """credentials.json is excluded."""
        agent_dir = tmp_path / "agent"
        agent_dir.mkdir()
        (agent_dir / "credentials.json").write_text("{}")
        (agent_dir / "config.json").write_text("{}")

        result = _build_archive(agent_dir, list(CREDENTIAL_IGNORE))
        names = _tar_names(result)

        assert "config.json" in names
        assert "credentials.json" not in names

    def test_normal_files_not_affected(self, tmp_path):
        """Normal config files are not excluded by credential patterns."""
        agent_dir = tmp_path / "agent"
        agent_dir.mkdir()
        (agent_dir / "config.json").write_text("{}")
        (agent_dir / "settings.toml").write_text("[settings]")
        (agent_dir / "README.md").write_text("# Readme")

        result = _build_archive(agent_dir, list(CREDENTIAL_IGNORE))
        names = _tar_names(result)

        assert "config.json" in names
        assert "settings.toml" in names
        assert "README.md" in names

    def test_freeze_excludes_env_even_without_config_ignore(
        self, tmp_path, monkeypatch
    ):
        """Freeze enforces credential exclusions even when config has no ignore patterns."""
        agent_dir = tmp_path / ".claude"
        agent_dir.mkdir()
        (agent_dir / "config.json").write_text("{}")
        (agent_dir / ".env").write_text("SECRET=abc")
        (agent_dir / "credentials.json").write_text("{}")

        write_config(
            tmp_path / ".cryopod.toml",
            {"claude": {"directory": str(agent_dir)}},
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")
        monkeypatch.delenv("CRYOPOD_SECRET_KEY", raising=False)

        uploaded_bytes = None

        def capture_upload(name, archive, api_key, base_url, max_versions=None):
            nonlocal uploaded_bytes
            uploaded_bytes = archive
            return {"version": 1}

        with patch("cryopod.freeze._upload_pod", side_effect=capture_upload):
            runner = CliRunner()
            result = runner.invoke(cli, ["freeze", "claude"])

        assert result.exit_code == 0
        assert uploaded_bytes is not None
        names = _tar_names(uploaded_bytes)
        assert "config.json" in names
        assert ".env" not in names
        assert "credentials.json" not in names


class TestMaxVersions:
    """Tests for max_versions being sent in API payloads."""

    def test_max_versions_sent_in_post(self, tmp_path, monkeypatch):
        """POST payload includes max_versions when configured."""
        agent_dir = tmp_path / ".claude"
        agent_dir.mkdir()
        (agent_dir / "config.json").write_text("{}")

        write_config(
            tmp_path / ".cryopod.toml",
            {"claude": {"directory": str(agent_dir), "max_versions": 5}},
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")
        monkeypatch.delenv("CRYOPOD_SECRET_KEY", raising=False)

        mock_client, mock_context = make_mock_httpx_client()

        post_resp = MagicMock()
        post_resp.status_code = 201
        post_resp.json.return_value = {
            "upload_url": "https://storage.example.com/upload/presigned",
            "version": 1,
        }
        mock_client.post.return_value = post_resp

        put_resp = MagicMock()
        put_resp.status_code = 200
        mock_client.put.return_value = put_resp

        with patch("cryopod.freeze.httpx.Client", return_value=mock_context):
            runner = CliRunner()
            result = runner.invoke(cli, ["freeze", "claude"])

        assert result.exit_code == 0
        post_call = mock_client.post.call_args
        payload = post_call.kwargs.get("json", post_call[1].get("json"))
        assert payload["max_versions"] == 5
        assert payload["name"] == "claude"

    def test_max_versions_sent_in_patch_on_409(self, tmp_path, monkeypatch):
        """PATCH payload includes max_versions on 409 conflict."""
        agent_dir = tmp_path / ".claude"
        agent_dir.mkdir()
        (agent_dir / "config.json").write_text("{}")

        write_config(
            tmp_path / ".cryopod.toml",
            {"claude": {"directory": str(agent_dir), "max_versions": 5}},
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")
        monkeypatch.delenv("CRYOPOD_SECRET_KEY", raising=False)

        mock_client, mock_context = make_mock_httpx_client()

        # POST returns 409
        post_resp = MagicMock()
        post_resp.status_code = 409
        mock_client.post.return_value = post_resp

        # PATCH returns 200
        patch_resp = MagicMock()
        patch_resp.status_code = 200
        patch_resp.json.return_value = {
            "upload_url": "https://storage.example.com/upload/presigned",
            "version": 2,
        }
        mock_client.patch.return_value = patch_resp

        put_resp = MagicMock()
        put_resp.status_code = 200
        mock_client.put.return_value = put_resp

        with patch("cryopod.freeze.httpx.Client", return_value=mock_context):
            runner = CliRunner()
            result = runner.invoke(cli, ["freeze", "claude"])

        assert result.exit_code == 0
        patch_call = mock_client.patch.call_args
        payload = patch_call.kwargs.get("json", patch_call[1].get("json"))
        assert payload["max_versions"] == 5

    def test_max_versions_omitted_when_absent(self, tmp_path, monkeypatch):
        """POST payload does not contain max_versions when not configured."""
        agent_dir = tmp_path / ".claude"
        agent_dir.mkdir()
        (agent_dir / "config.json").write_text("{}")

        write_config(
            tmp_path / ".cryopod.toml",
            {"claude": {"directory": str(agent_dir)}},
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")
        monkeypatch.delenv("CRYOPOD_SECRET_KEY", raising=False)

        mock_client, mock_context = make_mock_httpx_client()

        post_resp = MagicMock()
        post_resp.status_code = 201
        post_resp.json.return_value = {
            "upload_url": "https://storage.example.com/upload/presigned",
            "version": 1,
        }
        mock_client.post.return_value = post_resp

        put_resp = MagicMock()
        put_resp.status_code = 200
        mock_client.put.return_value = put_resp

        with patch("cryopod.freeze.httpx.Client", return_value=mock_context):
            runner = CliRunner()
            result = runner.invoke(cli, ["freeze", "claude"])

        assert result.exit_code == 0
        post_call = mock_client.post.call_args
        payload = post_call.kwargs.get("json", post_call[1].get("json"))
        assert "max_versions" not in payload

    def test_max_versions_sent_with_freeze_all(self, tmp_path, monkeypatch):
        """--all sends max_versions only for agents that have it configured."""
        for name in ("claude", "codex"):
            agent_dir = tmp_path / f".{name}"
            agent_dir.mkdir()
            (agent_dir / "config.json").write_text("{}")

        write_config(
            tmp_path / ".cryopod.toml",
            {
                "claude": {"directory": str(tmp_path / ".claude"), "max_versions": 3},
                "codex": {"directory": str(tmp_path / ".codex")},
            },
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")
        monkeypatch.delenv("CRYOPOD_SECRET_KEY", raising=False)

        mock_client, mock_context = make_mock_httpx_client()

        post_resp = MagicMock()
        post_resp.status_code = 201
        post_resp.json.return_value = {
            "upload_url": "https://storage.example.com/upload/presigned",
            "version": 1,
        }
        mock_client.post.return_value = post_resp

        put_resp = MagicMock()
        put_resp.status_code = 200
        mock_client.put.return_value = put_resp

        with patch("cryopod.freeze.httpx.Client", return_value=mock_context):
            runner = CliRunner()
            result = runner.invoke(cli, ["freeze", "--all"])

        assert result.exit_code == 0
        # Check the two POST calls
        post_calls = mock_client.post.call_args_list
        assert len(post_calls) == 2
        payloads = {}
        for call in post_calls:
            payload = call.kwargs.get("json", call[1].get("json"))
            payloads[payload["name"]] = payload

        assert payloads["claude"]["max_versions"] == 3
        assert "max_versions" not in payloads["codex"]


class TestBuildIgnoreIncludesCredentials:
    """Tests for _build_ignore including credential patterns."""

    def test_build_ignore_includes_credential_patterns(self):
        """_build_ignore() includes CREDENTIAL_IGNORE patterns for any agent."""
        result = _build_ignore("claude")
        for pattern in CREDENTIAL_IGNORE:
            assert pattern in result

    def test_build_ignore_includes_credential_patterns_unknown_agent(self):
        """_build_ignore() includes CREDENTIAL_IGNORE even for unknown agents."""
        result = _build_ignore("unknown-agent")
        for pattern in CREDENTIAL_IGNORE:
            assert pattern in result
