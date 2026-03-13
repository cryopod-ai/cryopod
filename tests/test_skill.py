"""Tests for the cryopod skill command."""

from click.testing import CliRunner

from cryopod.cli import cli


class TestSkillCommand:
    """Tests for the skill command output."""

    def test_skill_exit_code(self):
        """cryopod skill exits with code 0."""
        runner = CliRunner()
        result = runner.invoke(cli, ["skill"])

        assert result.exit_code == 0

    def test_skill_output_is_markdown(self):
        """Output starts with a markdown heading."""
        runner = CliRunner()
        result = runner.invoke(cli, ["skill"])

        assert result.output.startswith("# ")

    def test_skill_contains_all_commands(self):
        """Output contains all 14 command names."""
        runner = CliRunner()
        result = runner.invoke(cli, ["skill"])

        commands = [
            "init",
            "freeze",
            "thaw",
            "keygen",
            "add",
            "remove",
            "update",
            "manifest",
            "list",
            "status",
            "purge",
            "restore",
            "versions",
            "skill",
        ]
        for cmd in commands:
            assert f"`{cmd}`" in result.output, f"Missing command: {cmd}"

    def test_skill_contains_auth_section(self):
        """Output contains CRYOPOD_API_KEY."""
        runner = CliRunner()
        result = runner.invoke(cli, ["skill"])

        assert "CRYOPOD_API_KEY" in result.output

    def test_skill_contains_encryption_section(self):
        """Output contains CRYOPOD_SECRET_KEY."""
        runner = CliRunner()
        result = runner.invoke(cli, ["skill"])

        assert "CRYOPOD_SECRET_KEY" in result.output

    def test_skill_contains_supported_agents(self):
        """Output contains all supported agent directories."""
        runner = CliRunner()
        result = runner.invoke(cli, ["skill"])

        assert ".claude/" in result.output
        assert ".codex/" in result.output
        assert ".opencode/" in result.output

    def test_skill_no_ansi_codes(self):
        """Output does not contain ANSI escape sequences."""
        runner = CliRunner()
        result = runner.invoke(cli, ["skill"])

        assert "\x1b[" not in result.output
        assert "\033[" not in result.output

    def test_skill_contains_config_section(self):
        """Output contains .cryopod.toml."""
        runner = CliRunner()
        result = runner.invoke(cli, ["skill"])

        assert ".cryopod.toml" in result.output

    def test_skill_no_rclone_reference(self):
        """Output does not mention rclone."""
        runner = CliRunner()
        result = runner.invoke(cli, ["skill"])

        assert "rclone" not in result.output.lower()

    def test_skill_contains_api_url_env_var(self):
        """Output documents CRYOPOD_API_URL."""
        runner = CliRunner()
        result = runner.invoke(cli, ["skill"])

        assert "CRYOPOD_API_URL" in result.output

    def test_skill_contains_env_vars_section(self):
        """Output contains an Environment Variables section."""
        runner = CliRunner()
        result = runner.invoke(cli, ["skill"])

        assert "## Environment Variables" in result.output

    def test_skill_appears_in_help(self):
        """cryopod --help output contains skill."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        assert "skill" in result.output

    def test_skill_documents_versions_command(self):
        """Output documents the versions command usage."""
        runner = CliRunner()
        result = runner.invoke(cli, ["skill"])

        assert "cryopod versions <agent>" in result.output

    def test_skill_documents_restore_command(self):
        """Output documents the restore command usage."""
        runner = CliRunner()
        result = runner.invoke(cli, ["skill"])

        assert "cryopod restore <agent> <version>" in result.output

    def test_skill_documents_thaw_version_flag(self):
        """Output documents the --version flag on thaw."""
        runner = CliRunner()
        result = runner.invoke(cli, ["skill"])

        assert "cryopod thaw <agent> --version <N>" in result.output

    def test_skill_documents_version_all_mutual_exclusion(self):
        """Output mentions --version is mutually exclusive with --all."""
        runner = CliRunner()
        result = runner.invoke(cli, ["skill"])

        assert "`--version` is mutually exclusive with `--all`" in result.output

    def test_skill_documents_max_versions_flag(self):
        """Output documents the --max-versions flag."""
        runner = CliRunner()
        result = runner.invoke(cli, ["skill"])

        assert "--max-versions" in result.output

    def test_skill_documents_max_versions_range(self):
        """Output documents the valid range 1–100."""
        runner = CliRunner()
        result = runner.invoke(cli, ["skill"])

        assert "1–100" in result.output

    def test_skill_documents_max_versions_in_config(self):
        """Output documents max_versions in the Configuration section."""
        runner = CliRunner()
        result = runner.invoke(cli, ["skill"])

        assert "max_versions" in result.output

    def test_skill_documents_versions_max_display(self):
        """Output mentions the (max: N) display in versions output."""
        runner = CliRunner()
        result = runner.invoke(cli, ["skill"])

        assert "(max: N)" in result.output
