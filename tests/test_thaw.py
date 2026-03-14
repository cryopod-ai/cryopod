"""Tests for the cryopod thaw command."""

import io
import tarfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import click
from click.testing import CliRunner

from cryopod.agents import _build_ignore
from cryopod.cli import cli
from cryopod.crypto import encrypt_archive
from tests.helpers import make_mock_httpx_client, read_toml, write_config


def _build_tar_gz(files: dict[str, str]) -> bytes:
    """Build a tar.gz archive from a dict of {filename: content}."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, content in files.items():
            data = content.encode()
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def _mock_successful_download(archive_bytes: bytes):
    """Create a mock httpx.Client that simulates successful download."""
    mock_client, mock_context = make_mock_httpx_client()

    # GET /api/pods/{name}/download/ returns JSON with download_url
    get_api_resp = MagicMock()
    get_api_resp.status_code = 200
    get_api_resp.json.return_value = {
        "download_url": "https://storage.example.com/download/presigned"
    }

    # GET download_url returns archive bytes
    get_dl_resp = MagicMock()
    get_dl_resp.status_code = 200
    get_dl_resp.content = archive_bytes

    mock_client.get.side_effect = [get_api_resp, get_dl_resp]

    return mock_context


class TestThawConfigValidation:
    """Tests for config validation in thaw command."""

    def test_no_config_unknown_agent(self, tmp_path, monkeypatch):
        """Exit code 1 when no .cryopod.toml exists and agent is unknown."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        runner = CliRunner()
        result = runner.invoke(cli, ["thaw", "my-custom-agent"])

        assert result.exit_code != 0
        assert "Unknown agent" in result.output

    def test_agent_not_in_config(self, tmp_path, monkeypatch):
        """Exit code 1 when agent name not found in config."""
        write_config(
            tmp_path / ".cryopod.toml",
            {"claude": {"directory": ".claude"}},
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        runner = CliRunner()
        result = runner.invoke(cli, ["thaw", "nonexistent"])

        assert result.exit_code != 0
        assert "nonexistent" in result.output
        assert "not found" in result.output


class TestThawApiKeyValidation:
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
        result = runner.invoke(cli, ["thaw", "claude"])

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
        result = runner.invoke(cli, ["thaw", "claude"])

        assert result.exit_code != 0
        assert "CRYOPOD_API_KEY" in result.output


class TestThawMutualExclusivity:
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
        result = runner.invoke(cli, ["thaw", "claude", "--all"])

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
        result = runner.invoke(cli, ["thaw"])

        assert result.exit_code != 0


class TestThawDownload:
    """Tests for download functionality."""

    def test_successful_download(self, tmp_path, monkeypatch):
        """Successful thaw downloads and extracts archive."""
        archive = _build_tar_gz({"config.json": '{"key": "value"}'})

        write_config(
            tmp_path / ".cryopod.toml",
            {"claude": {"directory": str(tmp_path / ".claude")}},
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")
        monkeypatch.delenv("CRYOPOD_SECRET_KEY", raising=False)

        mock_ctx = _mock_successful_download(archive)

        with patch("cryopod.thaw.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["thaw", "claude"])

        assert result.exit_code == 0
        assert "▸ THAWED claude" in result.output
        assert (tmp_path / ".claude" / "config.json").exists()

    def test_404_error(self, tmp_path, monkeypatch):
        """404 response produces pod not found error."""
        write_config(
            tmp_path / ".cryopod.toml",
            {"claude": {"directory": str(tmp_path / ".claude")}},
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_client, mock_context = make_mock_httpx_client()

        resp = MagicMock()
        resp.status_code = 404
        mock_client.get.return_value = resp

        with patch("cryopod.thaw.httpx.Client", return_value=mock_context):
            runner = CliRunner()
            result = runner.invoke(cli, ["thaw", "claude"])

        assert result.exit_code != 0
        assert "not found" in result.output

    def test_auth_error(self, tmp_path, monkeypatch):
        """401 response produces auth failure error."""
        write_config(
            tmp_path / ".cryopod.toml",
            {"claude": {"directory": str(tmp_path / ".claude")}},
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_client, mock_context = make_mock_httpx_client()

        resp = MagicMock()
        resp.status_code = 401
        mock_client.get.return_value = resp

        with patch("cryopod.thaw.httpx.Client", return_value=mock_context):
            runner = CliRunner()
            result = runner.invoke(cli, ["thaw", "claude"])

        assert result.exit_code != 0
        assert "Authentication failed" in result.output

    def test_connect_error(self, tmp_path, monkeypatch):
        """Connection error produces a friendly error message."""
        write_config(
            tmp_path / ".cryopod.toml",
            {"claude": {"directory": str(tmp_path / ".claude")}},
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        import httpx

        with patch(
            "cryopod.thaw._download_pod",
            side_effect=httpx.ConnectError("Connection refused"),
        ):
            runner = CliRunner()
            result = runner.invoke(cli, ["thaw", "claude"])

        assert result.exit_code != 0
        assert "Could not connect" in result.output

    def test_timeout_error(self, tmp_path, monkeypatch):
        """Timeout error produces a friendly error message."""
        write_config(
            tmp_path / ".cryopod.toml",
            {"claude": {"directory": str(tmp_path / ".claude")}},
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        import httpx

        with patch(
            "cryopod.thaw._download_pod",
            side_effect=httpx.TimeoutException("Timed out"),
        ):
            runner = CliRunner()
            result = runner.invoke(cli, ["thaw", "claude"])

        assert result.exit_code != 0
        assert "timed out" in result.output


class TestThawDecryption:
    """Tests for encryption/decryption handling during thaw."""

    def test_encrypted_with_key(self, tmp_path, monkeypatch):
        """Encrypted archive with correct key decrypts and extracts."""
        archive = _build_tar_gz({"config.json": '{"key": "value"}'})
        encrypted = encrypt_archive(archive, "my-secret")

        write_config(
            tmp_path / ".cryopod.toml",
            {"claude": {"directory": str(tmp_path / ".claude")}},
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")
        monkeypatch.setenv("CRYOPOD_SECRET_KEY", "my-secret")

        mock_ctx = _mock_successful_download(encrypted)

        with patch("cryopod.thaw.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["thaw", "claude"])

        assert result.exit_code == 0
        assert "▸ THAWED claude" in result.output
        assert (tmp_path / ".claude" / "config.json").exists()

    def test_encrypted_no_key(self, tmp_path, monkeypatch):
        """Encrypted archive without key produces error, no filesystem changes."""
        archive = _build_tar_gz({"config.json": '{"key": "value"}'})
        encrypted = encrypt_archive(archive, "my-secret")

        write_config(
            tmp_path / ".cryopod.toml",
            {"claude": {"directory": str(tmp_path / ".claude")}},
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")
        monkeypatch.delenv("CRYOPOD_SECRET_KEY", raising=False)

        mock_ctx = _mock_successful_download(encrypted)

        with patch("cryopod.thaw.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["thaw", "claude"])

        assert result.exit_code != 0
        assert "CRYOPOD_SECRET_KEY" in result.output
        # No filesystem changes
        assert not (tmp_path / ".claude").exists()

    def test_encrypted_wrong_key(self, tmp_path, monkeypatch):
        """Encrypted archive with wrong key produces error, no filesystem changes."""
        archive = _build_tar_gz({"config.json": '{"key": "value"}'})
        encrypted = encrypt_archive(archive, "correct-key")

        write_config(
            tmp_path / ".cryopod.toml",
            {"claude": {"directory": str(tmp_path / ".claude")}},
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")
        monkeypatch.setenv("CRYOPOD_SECRET_KEY", "wrong-key")

        mock_ctx = _mock_successful_download(encrypted)

        with patch("cryopod.thaw.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["thaw", "claude"])

        assert result.exit_code != 0
        assert "Decryption failed" in result.output
        # No filesystem changes
        assert not (tmp_path / ".claude").exists()

    def test_unencrypted_no_decryption(self, tmp_path, monkeypatch):
        """Unencrypted archive skips decryption."""
        archive = _build_tar_gz({"config.json": '{"key": "value"}'})

        write_config(
            tmp_path / ".cryopod.toml",
            {"claude": {"directory": str(tmp_path / ".claude")}},
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")
        monkeypatch.delenv("CRYOPOD_SECRET_KEY", raising=False)

        mock_ctx = _mock_successful_download(archive)

        with patch("cryopod.thaw.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["thaw", "claude"])

        assert result.exit_code == 0
        assert "▸ THAWED claude" in result.output
        assert (tmp_path / ".claude" / "config.json").exists()


class TestThawBackup:
    """Tests for .pre-thaw backup behavior."""

    def test_pre_thaw_backup_created(self, tmp_path, monkeypatch):
        """.pre-thaw directory created when agent dir exists."""
        agent_dir = tmp_path / ".claude"
        agent_dir.mkdir()
        (agent_dir / "old_config.json").write_text('{"old": true}')

        archive = _build_tar_gz({"config.json": '{"new": true}'})

        write_config(
            tmp_path / ".cryopod.toml",
            {"claude": {"directory": str(agent_dir)}},
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")
        monkeypatch.delenv("CRYOPOD_SECRET_KEY", raising=False)

        mock_ctx = _mock_successful_download(archive)

        with patch("cryopod.thaw.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["thaw", "claude"])

        assert result.exit_code == 0
        backup_dir = Path(str(agent_dir) + ".pre-thaw")
        assert backup_dir.exists()
        assert (backup_dir / "old_config.json").exists()
        # New files extracted
        assert (agent_dir / "config.json").exists()
        assert not (agent_dir / "old_config.json").exists()

    def test_no_backup_flag(self, tmp_path, monkeypatch):
        """--no-backup skips .pre-thaw creation."""
        agent_dir = tmp_path / ".claude"
        agent_dir.mkdir()
        (agent_dir / "old_config.json").write_text('{"old": true}')

        archive = _build_tar_gz({"config.json": '{"new": true}'})

        write_config(
            tmp_path / ".cryopod.toml",
            {"claude": {"directory": str(agent_dir)}},
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")
        monkeypatch.delenv("CRYOPOD_SECRET_KEY", raising=False)

        mock_ctx = _mock_successful_download(archive)

        with patch("cryopod.thaw.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["thaw", "claude", "--no-backup"])

        assert result.exit_code == 0
        backup_dir = Path(str(agent_dir) + ".pre-thaw")
        assert not backup_dir.exists()

    def test_existing_pre_thaw_replaced(self, tmp_path, monkeypatch):
        """Existing .pre-thaw is replaced with warning."""
        agent_dir = tmp_path / ".claude"
        agent_dir.mkdir()
        (agent_dir / "current.json").write_text('{"current": true}')

        old_backup = Path(str(agent_dir) + ".pre-thaw")
        old_backup.mkdir()
        (old_backup / "stale.json").write_text('{"stale": true}')

        archive = _build_tar_gz({"config.json": '{"new": true}'})

        write_config(
            tmp_path / ".cryopod.toml",
            {"claude": {"directory": str(agent_dir)}},
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")
        monkeypatch.delenv("CRYOPOD_SECRET_KEY", raising=False)

        mock_ctx = _mock_successful_download(archive)

        with patch("cryopod.thaw.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["thaw", "claude"])

        assert result.exit_code == 0
        assert "Removing existing backup" in result.output
        # Old backup replaced with current dir contents
        backup_dir = Path(str(agent_dir) + ".pre-thaw")
        assert backup_dir.exists()
        assert (backup_dir / "current.json").exists()
        assert not (backup_dir / "stale.json").exists()

    def test_no_backup_when_dir_missing(self, tmp_path, monkeypatch):
        """No .pre-thaw created when agent dir doesn't exist yet."""
        archive = _build_tar_gz({"config.json": '{"new": true}'})

        write_config(
            tmp_path / ".cryopod.toml",
            {"claude": {"directory": str(tmp_path / ".claude")}},
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")
        monkeypatch.delenv("CRYOPOD_SECRET_KEY", raising=False)

        mock_ctx = _mock_successful_download(archive)

        with patch("cryopod.thaw.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["thaw", "claude"])

        assert result.exit_code == 0
        backup_dir = Path(str(tmp_path / ".claude") + ".pre-thaw")
        assert not backup_dir.exists()
        assert (tmp_path / ".claude" / "config.json").exists()


class TestThawExtract:
    """Tests for archive extraction."""

    def test_files_extracted_correctly(self, tmp_path, monkeypatch):
        """Files are extracted to the correct location with correct contents."""
        archive = _build_tar_gz(
            {
                "config.json": '{"key": "value"}',
                "settings.toml": "[settings]\nfoo = true",
            }
        )

        write_config(
            tmp_path / ".cryopod.toml",
            {"claude": {"directory": str(tmp_path / ".claude")}},
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")
        monkeypatch.delenv("CRYOPOD_SECRET_KEY", raising=False)

        mock_ctx = _mock_successful_download(archive)

        with patch("cryopod.thaw.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["thaw", "claude"])

        assert result.exit_code == 0
        assert (tmp_path / ".claude" / "config.json").read_text() == '{"key": "value"}'
        assert (
            tmp_path / ".claude" / "settings.toml"
        ).read_text() == "[settings]\nfoo = true"

    def test_empty_archive(self, tmp_path, monkeypatch):
        """Empty archive creates empty directory."""
        archive = _build_tar_gz({})

        write_config(
            tmp_path / ".cryopod.toml",
            {"claude": {"directory": str(tmp_path / ".claude")}},
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")
        monkeypatch.delenv("CRYOPOD_SECRET_KEY", raising=False)

        mock_ctx = _mock_successful_download(archive)

        with patch("cryopod.thaw.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["thaw", "claude"])

        assert result.exit_code == 0
        assert "▸ THAWED claude" in result.output
        assert (tmp_path / ".claude").is_dir()


class TestThawAll:
    """Tests for --all flag."""

    def test_thaw_all_agents(self, tmp_path, monkeypatch):
        """--all thaws all agents."""
        archive_claude = _build_tar_gz({"claude.json": "{}"})
        archive_codex = _build_tar_gz({"codex.json": "{}"})

        write_config(
            tmp_path / ".cryopod.toml",
            {
                "claude": {"directory": str(tmp_path / ".claude")},
                "codex": {"directory": str(tmp_path / ".codex")},
            },
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")
        monkeypatch.delenv("CRYOPOD_SECRET_KEY", raising=False)

        # Need separate mocks for each call
        mock_client, mock_context = make_mock_httpx_client()

        api_resp_1 = MagicMock()
        api_resp_1.status_code = 200
        api_resp_1.json.return_value = {
            "download_url": "https://storage.example.com/dl/claude"
        }
        dl_resp_1 = MagicMock()
        dl_resp_1.status_code = 200
        dl_resp_1.content = archive_claude

        api_resp_2 = MagicMock()
        api_resp_2.status_code = 200
        api_resp_2.json.return_value = {
            "download_url": "https://storage.example.com/dl/codex"
        }
        dl_resp_2 = MagicMock()
        dl_resp_2.status_code = 200
        dl_resp_2.content = archive_codex

        mock_client.get.side_effect = [api_resp_1, dl_resp_1, api_resp_2, dl_resp_2]

        with patch("cryopod.thaw.httpx.Client", return_value=mock_context):
            runner = CliRunner()
            result = runner.invoke(cli, ["thaw", "--all"])

        assert result.exit_code == 0
        assert "▸ THAWED claude" in result.output
        assert "▸ THAWED codex" in result.output
        assert (tmp_path / ".claude" / "claude.json").exists()
        assert (tmp_path / ".codex" / "codex.json").exists()


class TestThawOutput:
    """Tests for output format."""

    def test_thawed_message_format(self, tmp_path, monkeypatch):
        """Success message matches THAWED {name} ({size}) pattern."""
        archive = _build_tar_gz({"config.json": '{"key": "value"}'})

        write_config(
            tmp_path / ".cryopod.toml",
            {"claude": {"directory": str(tmp_path / ".claude")}},
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")
        monkeypatch.delenv("CRYOPOD_SECRET_KEY", raising=False)

        mock_ctx = _mock_successful_download(archive)

        with patch("cryopod.thaw.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["thaw", "claude"])

        assert result.exit_code == 0
        assert "THAWED claude (" in result.output
        assert ")" in result.output


class TestThawVersion:
    """Tests for --version flag."""

    def test_version_flag_passes_query_param(self, tmp_path, monkeypatch):
        """--version N passes version as query param to API."""
        archive = _build_tar_gz({"config.json": '{"key": "value"}'})

        write_config(
            tmp_path / ".cryopod.toml",
            {"claude": {"directory": str(tmp_path / ".claude")}},
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")
        monkeypatch.delenv("CRYOPOD_SECRET_KEY", raising=False)

        mock_client, mock_context = make_mock_httpx_client()

        api_resp = MagicMock()
        api_resp.status_code = 200
        api_resp.json.return_value = {
            "download_url": "https://storage.example.com/download/presigned"
        }

        dl_resp = MagicMock()
        dl_resp.status_code = 200
        dl_resp.content = archive

        mock_client.get.side_effect = [api_resp, dl_resp]

        with patch("cryopod.thaw.httpx.Client", return_value=mock_context):
            runner = CliRunner()
            result = runner.invoke(cli, ["thaw", "claude", "--version", "2"])

        assert result.exit_code == 0
        # Verify the first GET call included version param
        first_call = mock_client.get.call_args_list[0]
        assert first_call.kwargs.get("params") == {"version": 2}

    def test_version_with_all_error(self, tmp_path, monkeypatch):
        """--version with --all produces error."""
        write_config(
            tmp_path / ".cryopod.toml",
            {"claude": {"directory": ".claude"}},
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        runner = CliRunner()
        result = runner.invoke(cli, ["thaw", "--all", "--version", "2"])

        assert result.exit_code != 0
        assert "Cannot specify --version with --all" in result.output

    def test_version_without_agent_error(self, tmp_path, monkeypatch):
        """--version without agent name produces error."""
        write_config(
            tmp_path / ".cryopod.toml",
            {"claude": {"directory": ".claude"}},
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        runner = CliRunner()
        result = runner.invoke(cli, ["thaw", "--version", "2"])

        assert result.exit_code != 0

    def test_version_zero_rejected(self, tmp_path, monkeypatch):
        """--version 0 is rejected by Click's IntRange."""
        write_config(
            tmp_path / ".cryopod.toml",
            {"claude": {"directory": ".claude"}},
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        runner = CliRunner()
        result = runner.invoke(cli, ["thaw", "claude", "--version", "0"])

        assert result.exit_code != 0

    def test_version_negative_rejected(self, tmp_path, monkeypatch):
        """--version -1 is rejected by Click's IntRange."""
        write_config(
            tmp_path / ".cryopod.toml",
            {"claude": {"directory": ".claude"}},
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        runner = CliRunner()
        result = runner.invoke(cli, ["thaw", "claude", "--version", "-1"])

        assert result.exit_code != 0

    def test_version_non_integer_rejected(self, tmp_path, monkeypatch):
        """--version abc is rejected by Click's type system."""
        write_config(
            tmp_path / ".cryopod.toml",
            {"claude": {"directory": ".claude"}},
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        runner = CliRunner()
        result = runner.invoke(cli, ["thaw", "claude", "--version", "abc"])

        assert result.exit_code != 0

    def test_version_404_error_message(self, tmp_path, monkeypatch):
        """404 with --version mentions version in the error message."""
        write_config(
            tmp_path / ".cryopod.toml",
            {"claude": {"directory": str(tmp_path / ".claude")}},
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_client, mock_context = make_mock_httpx_client()

        resp = MagicMock()
        resp.status_code = 404
        mock_client.get.return_value = resp

        with patch("cryopod.thaw.httpx.Client", return_value=mock_context):
            runner = CliRunner()
            result = runner.invoke(cli, ["thaw", "claude", "--version", "99"])

        assert result.exit_code != 0
        assert "version 99" in result.output
        assert "not found" in result.output

    def test_version_output_message(self, tmp_path, monkeypatch):
        """Successful thaw with --version includes version in output."""
        archive = _build_tar_gz({"config.json": '{"key": "value"}'})

        write_config(
            tmp_path / ".cryopod.toml",
            {"claude": {"directory": str(tmp_path / ".claude")}},
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")
        monkeypatch.delenv("CRYOPOD_SECRET_KEY", raising=False)

        mock_ctx = _mock_successful_download(archive)

        with patch("cryopod.thaw.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["thaw", "claude", "--version", "2"])

        assert result.exit_code == 0
        assert "version 2" in result.output
        assert "THAWED claude" in result.output


class TestThawWithoutConfig:
    """Tests for thawing known agents without a .cryopod.toml file."""

    def test_known_agent_without_config(self, tmp_path, monkeypatch):
        """Known agent can be thawed without a .cryopod.toml."""
        archive = _build_tar_gz({"config.json": '{"key": "value"}'})

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")
        monkeypatch.delenv("CRYOPOD_SECRET_KEY", raising=False)

        mock_ctx = _mock_successful_download(archive)

        with patch("cryopod.thaw.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["thaw", "claude"])

        assert result.exit_code == 0
        assert "THAWED claude" in result.output
        assert (tmp_path / ".claude" / "config.json").exists()

    def test_unknown_agent_without_config(self, tmp_path, monkeypatch):
        """Unknown agent without config produces error with helpful message."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        runner = CliRunner()
        result = runner.invoke(cli, ["thaw", "my-custom-agent"])

        assert result.exit_code != 0
        assert "Unknown agent" in result.output
        assert "my-custom-agent" in result.output
        assert "--directory" in result.output

    def test_all_without_config_known_agents(self, tmp_path, monkeypatch):
        """--all without config thaws known agents from manifest."""
        archive_claude = _build_tar_gz({"claude.json": "{}"})
        archive_codex = _build_tar_gz({"codex.json": "{}"})

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")
        monkeypatch.delenv("CRYOPOD_SECRET_KEY", raising=False)

        mock_pods = [{"name": "claude"}, {"name": "codex"}]

        mock_client, mock_context = make_mock_httpx_client()

        api_resp_1 = MagicMock()
        api_resp_1.status_code = 200
        api_resp_1.json.return_value = {
            "download_url": "https://storage.example.com/dl/claude"
        }
        dl_resp_1 = MagicMock()
        dl_resp_1.status_code = 200
        dl_resp_1.content = archive_claude

        api_resp_2 = MagicMock()
        api_resp_2.status_code = 200
        api_resp_2.json.return_value = {
            "download_url": "https://storage.example.com/dl/codex"
        }
        dl_resp_2 = MagicMock()
        dl_resp_2.status_code = 200
        dl_resp_2.content = archive_codex

        mock_client.get.side_effect = [api_resp_1, dl_resp_1, api_resp_2, dl_resp_2]

        with (
            patch("cryopod.thaw._fetch_all_pods", return_value=mock_pods),
            patch("cryopod.thaw.httpx.Client", return_value=mock_context),
        ):
            runner = CliRunner()
            result = runner.invoke(cli, ["thaw", "--all"])

        assert result.exit_code == 0
        assert "THAWED claude" in result.output
        assert "THAWED codex" in result.output
        assert (tmp_path / ".claude" / "claude.json").exists()
        assert (tmp_path / ".codex" / "codex.json").exists()

    def test_all_without_config_skips_unknown(self, tmp_path, monkeypatch):
        """--all without config skips unknown agents with a warning."""
        archive_claude = _build_tar_gz({"claude.json": "{}"})

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")
        monkeypatch.delenv("CRYOPOD_SECRET_KEY", raising=False)

        mock_pods = [{"name": "claude"}, {"name": "my-custom"}]

        mock_ctx = _mock_successful_download(archive_claude)

        with (
            patch("cryopod.thaw._fetch_all_pods", return_value=mock_pods),
            patch("cryopod.thaw.httpx.Client", return_value=mock_ctx),
        ):
            runner = CliRunner()
            result = runner.invoke(cli, ["thaw", "--all"])

        assert result.exit_code == 0
        assert "THAWED claude" in result.output
        assert "Skipping unknown agent 'my-custom'" in result.output

    def test_all_without_config_only_unknown(self, tmp_path, monkeypatch):
        """--all without config errors when only unknown agents exist."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        mock_pods = [{"name": "my-custom-1"}, {"name": "my-custom-2"}]

        with patch("cryopod.thaw._fetch_all_pods", return_value=mock_pods):
            runner = CliRunner()
            result = runner.invoke(cli, ["thaw", "--all"])

        assert result.exit_code != 0
        assert "No known agents found" in result.output

    def test_all_without_config_empty_manifest(self, tmp_path, monkeypatch):
        """--all without config errors when no pods exist on server."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        with patch("cryopod.thaw._fetch_all_pods", return_value=[]):
            runner = CliRunner()
            result = runner.invoke(cli, ["thaw", "--all"])

        assert result.exit_code != 0
        assert "No pods found" in result.output

    def test_config_present_still_works(self, tmp_path, monkeypatch):
        """Config-based thaw still works when .cryopod.toml is present."""
        archive = _build_tar_gz({"config.json": '{"key": "value"}'})

        write_config(
            tmp_path / ".cryopod.toml",
            {"claude": {"directory": str(tmp_path / ".claude")}},
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")
        monkeypatch.delenv("CRYOPOD_SECRET_KEY", raising=False)

        mock_ctx = _mock_successful_download(archive)

        with patch("cryopod.thaw.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["thaw", "claude"])

        assert result.exit_code == 0
        assert "THAWED claude" in result.output
        assert (tmp_path / ".claude" / "config.json").exists()

    def test_known_agent_default_directory(self, tmp_path, monkeypatch):
        """Each known agent resolves to its expected default directory."""

        expected = {
            "claude": ".claude",
            "codex": ".codex",
            "opencode": ".opencode",
            "cursor": ".cursor",
            "windsurf": ".windsurf",
            "gemini": ".gemini",
        }

        for agent_name, expected_dir in expected.items():
            archive = _build_tar_gz({"test.json": "{}"})

            # Clean up from previous iteration
            agent_dir = tmp_path / expected_dir
            if agent_dir.exists():
                import shutil

                shutil.rmtree(agent_dir)

            # Remove config file created by auto-register in previous iteration
            config_file = tmp_path / ".cryopod.toml"
            if config_file.exists():
                config_file.unlink()

            monkeypatch.chdir(tmp_path)
            monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")
            monkeypatch.delenv("CRYOPOD_SECRET_KEY", raising=False)

            mock_ctx = _mock_successful_download(archive)

            with patch("cryopod.thaw.httpx.Client", return_value=mock_ctx):
                runner = CliRunner()
                result = runner.invoke(cli, ["thaw", agent_name])

            assert result.exit_code == 0, f"Failed for {agent_name}: {result.output}"
            assert (tmp_path / expected_dir / "test.json").exists(), (
                f"{agent_name} should extract to {expected_dir}"
            )


class TestThawDirectory:
    """Tests for --directory flag."""

    def test_directory_unknown_agent_no_config(self, tmp_path, monkeypatch):
        """Thaw unknown agent with --directory and no config file."""
        archive = _build_tar_gz({"config.json": '{"key": "value"}'})
        target = tmp_path / "my-custom-dir"

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")
        monkeypatch.delenv("CRYOPOD_SECRET_KEY", raising=False)

        mock_ctx = _mock_successful_download(archive)

        with patch("cryopod.thaw.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(
                cli, ["thaw", "my-custom-agent", "--directory", str(target)]
            )

        assert result.exit_code == 0
        assert "THAWED my-custom-agent" in result.output
        assert (target / "config.json").exists()

    def test_directory_unknown_agent_with_config(self, tmp_path, monkeypatch):
        """Thaw unknown agent (not in config) with --directory."""
        archive = _build_tar_gz({"config.json": '{"key": "value"}'})
        target = tmp_path / "custom-output"

        write_config(
            tmp_path / ".cryopod.toml",
            {"claude": {"directory": ".claude"}},
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")
        monkeypatch.delenv("CRYOPOD_SECRET_KEY", raising=False)

        mock_ctx = _mock_successful_download(archive)

        with patch("cryopod.thaw.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(
                cli, ["thaw", "my-custom-agent", "--directory", str(target)]
            )

        assert result.exit_code == 0
        assert "THAWED my-custom-agent" in result.output
        assert (target / "config.json").exists()

    def test_directory_known_agent_override(self, tmp_path, monkeypatch):
        """--directory overrides the default directory for a known agent."""
        archive = _build_tar_gz({"config.json": '{"key": "value"}'})
        target = tmp_path / "override-dir"

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")
        monkeypatch.delenv("CRYOPOD_SECRET_KEY", raising=False)

        mock_ctx = _mock_successful_download(archive)

        with patch("cryopod.thaw.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["thaw", "claude", "--directory", str(target)])

        assert result.exit_code == 0
        assert "THAWED claude" in result.output
        assert (target / "config.json").exists()
        # Should NOT go to the default directory
        assert not (tmp_path / ".claude").exists()

    def test_directory_config_agent_override(self, tmp_path, monkeypatch):
        """--directory overrides the config directory for a config-present agent."""
        archive = _build_tar_gz({"config.json": '{"key": "value"}'})
        config_dir = tmp_path / ".claude"
        target = tmp_path / "override-dir"

        write_config(
            tmp_path / ".cryopod.toml",
            {"claude": {"directory": str(config_dir)}},
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")
        monkeypatch.delenv("CRYOPOD_SECRET_KEY", raising=False)

        mock_ctx = _mock_successful_download(archive)

        with patch("cryopod.thaw.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["thaw", "claude", "--directory", str(target)])

        assert result.exit_code == 0
        assert "THAWED claude" in result.output
        assert (target / "config.json").exists()
        # Should NOT go to the config directory
        assert not config_dir.exists()

    def test_directory_with_all_error(self, tmp_path, monkeypatch):
        """--directory + --all produces a clear error."""
        write_config(
            tmp_path / ".cryopod.toml",
            {"claude": {"directory": ".claude"}},
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        runner = CliRunner()
        result = runner.invoke(
            cli, ["thaw", "--all", "--directory", str(tmp_path / "out")]
        )

        assert result.exit_code != 0
        assert "Cannot specify --directory with --all" in result.output

    def test_unknown_agent_no_directory_error_message(self, tmp_path, monkeypatch):
        """Unknown agent without --directory shows error mentioning --directory."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")

        runner = CliRunner()
        result = runner.invoke(cli, ["thaw", "my-custom-agent"])

        assert result.exit_code != 0
        assert "--directory" in result.output
        assert "my-custom-agent" in result.output

    def test_directory_creates_path(self, tmp_path, monkeypatch):
        """--directory pointing to a non-existent path creates it."""
        archive = _build_tar_gz({"config.json": '{"key": "value"}'})
        target = tmp_path / "deep" / "nested" / "dir"

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")
        monkeypatch.delenv("CRYOPOD_SECRET_KEY", raising=False)

        mock_ctx = _mock_successful_download(archive)

        with patch("cryopod.thaw.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(
                cli, ["thaw", "my-custom-agent", "--directory", str(target)]
            )

        assert result.exit_code == 0
        assert target.exists()
        assert (target / "config.json").exists()


class TestThawAutoRegister:
    """Tests for auto-registering thawed agents in .cryopod.toml."""

    def test_thaw_creates_config_file(self, tmp_path, monkeypatch):
        """No .cryopod.toml exists → thaw succeeds → file is created."""
        archive = _build_tar_gz({"config.json": '{"key": "value"}'})

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")
        monkeypatch.delenv("CRYOPOD_SECRET_KEY", raising=False)

        mock_ctx = _mock_successful_download(archive)

        with patch("cryopod.thaw.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["thaw", "claude"])

        assert result.exit_code == 0
        config_path = tmp_path / ".cryopod.toml"
        assert config_path.exists()
        data = read_toml(config_path)
        assert "claude" in data["agents"]
        assert data["agents"]["claude"]["directory"] == ".claude"

    def test_thaw_registers_with_correct_ignore_list(self, tmp_path, monkeypatch):
        """Registered agent has ignore list matching _build_ignore output."""
        archive = _build_tar_gz({"config.json": '{"key": "value"}'})

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")
        monkeypatch.delenv("CRYOPOD_SECRET_KEY", raising=False)

        mock_ctx = _mock_successful_download(archive)

        with patch("cryopod.thaw.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["thaw", "claude"])

        assert result.exit_code == 0
        data = read_toml(tmp_path / ".cryopod.toml")
        expected_ignore = list(dict.fromkeys(_build_ignore("claude")))
        assert data["agents"]["claude"]["ignore"] == expected_ignore

    def test_thaw_existing_agent_unchanged(self, tmp_path, monkeypatch):
        """Agent already in config with custom settings → thaw → config unchanged."""
        archive = _build_tar_gz({"config.json": '{"key": "value"}'})

        write_config(
            tmp_path / ".cryopod.toml",
            {
                "claude": {
                    "directory": str(tmp_path / ".claude"),
                    "ignore": ["custom-pattern"],
                    "max_versions": 5,
                }
            },
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")
        monkeypatch.delenv("CRYOPOD_SECRET_KEY", raising=False)

        mock_ctx = _mock_successful_download(archive)

        with patch("cryopod.thaw.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["thaw", "claude"])

        assert result.exit_code == 0
        data = read_toml(tmp_path / ".cryopod.toml")
        assert data["agents"]["claude"]["ignore"] == ["custom-pattern"]
        assert data["agents"]["claude"]["max_versions"] == 5

    def test_thaw_does_not_register_on_failure(self, tmp_path, monkeypatch):
        """Mock _thaw_one to raise → verify no config changes."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")
        monkeypatch.delenv("CRYOPOD_SECRET_KEY", raising=False)

        with patch(
            "cryopod.thaw._thaw_one",
            side_effect=click.ClickException("download failed"),
        ):
            runner = CliRunner()
            result = runner.invoke(cli, ["thaw", "claude"])

        assert result.exit_code != 0
        assert not (tmp_path / ".cryopod.toml").exists()

    def test_thaw_all_registers_all_agents(self, tmp_path, monkeypatch):
        """--all without config → verify all thawed agents are registered."""
        archive_claude = _build_tar_gz({"claude.json": "{}"})
        archive_codex = _build_tar_gz({"codex.json": "{}"})

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")
        monkeypatch.delenv("CRYOPOD_SECRET_KEY", raising=False)

        mock_pods = [{"name": "claude"}, {"name": "codex"}]

        mock_client, mock_context = make_mock_httpx_client()

        api_resp_1 = MagicMock()
        api_resp_1.status_code = 200
        api_resp_1.json.return_value = {
            "download_url": "https://storage.example.com/dl/claude"
        }
        dl_resp_1 = MagicMock()
        dl_resp_1.status_code = 200
        dl_resp_1.content = archive_claude

        api_resp_2 = MagicMock()
        api_resp_2.status_code = 200
        api_resp_2.json.return_value = {
            "download_url": "https://storage.example.com/dl/codex"
        }
        dl_resp_2 = MagicMock()
        dl_resp_2.status_code = 200
        dl_resp_2.content = archive_codex

        mock_client.get.side_effect = [api_resp_1, dl_resp_1, api_resp_2, dl_resp_2]

        with (
            patch("cryopod.thaw._fetch_all_pods", return_value=mock_pods),
            patch("cryopod.thaw.httpx.Client", return_value=mock_context),
        ):
            runner = CliRunner()
            result = runner.invoke(cli, ["thaw", "--all"])

        assert result.exit_code == 0
        config_path = tmp_path / ".cryopod.toml"
        assert config_path.exists()
        data = read_toml(config_path)
        assert "claude" in data["agents"]
        assert "codex" in data["agents"]
        assert data["agents"]["claude"]["directory"] == ".claude"
        assert data["agents"]["codex"]["directory"] == ".codex"

    def test_thaw_directory_override_registered(self, tmp_path, monkeypatch):
        """Thaw with --directory → verify the override directory is stored."""
        archive = _build_tar_gz({"config.json": '{"key": "value"}'})
        target = tmp_path / "custom-dir"

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")
        monkeypatch.delenv("CRYOPOD_SECRET_KEY", raising=False)

        mock_ctx = _mock_successful_download(archive)

        with patch("cryopod.thaw.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["thaw", "claude", "--directory", str(target)])

        assert result.exit_code == 0
        config_path = tmp_path / ".cryopod.toml"
        assert config_path.exists()
        data = read_toml(config_path)
        assert data["agents"]["claude"]["directory"] == str(target)

    def test_thaw_registered_message_shown(self, tmp_path, monkeypatch):
        """Registered message is shown when agent is newly added to config."""
        archive = _build_tar_gz({"config.json": '{"key": "value"}'})

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CRYOPOD_API_KEY", "test-key")
        monkeypatch.delenv("CRYOPOD_SECRET_KEY", raising=False)

        mock_ctx = _mock_successful_download(archive)

        with patch("cryopod.thaw.httpx.Client", return_value=mock_ctx):
            runner = CliRunner()
            result = runner.invoke(cli, ["thaw", "claude"])

        assert result.exit_code == 0
        assert "Registered claude" in result.output
