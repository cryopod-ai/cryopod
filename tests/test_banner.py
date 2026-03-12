"""Tests for the ASCII banner display."""

from io import StringIO

from click.testing import CliRunner
from rich.console import Console

from cryopod.banner import BannerGroup, get_help_epilog, print_banner
from cryopod.cli import cli


class TestHelpBanner:
    """Tests that the banner appears in --help output."""

    def test_help_contains_banner(self):
        """Banner ASCII art appears in CLI help output."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "___ ___ _   _ ___" in result.output
        assert "\\___|_|_\\" in result.output

    def test_banner_appears_before_usage(self):
        """Banner appears before the Usage: line in help output."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        banner_pos = result.output.index("___ ___ _   _ ___")
        usage_pos = result.output.index("Usage:")
        assert banner_pos < usage_pos

    def test_help_contains_commands(self):
        """Commands section is still present in help output."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "Commands:" in result.output
        assert "init" in result.output
        assert "freeze" in result.output

    def test_subcommand_help_no_banner(self):
        """Subcommand help does not include the banner."""
        runner = CliRunner()
        result = runner.invoke(cli, ["init", "--help"])

        assert result.exit_code == 0
        assert "___ ___ _   _ ___" not in result.output


class TestInitBanner:
    """Tests that the banner appears in init command output."""

    def test_init_shows_banner(self, tmp_path, monkeypatch):
        """Banner appears at the top of init output."""
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        # No agents discovered, no additional agents (n)
        result = runner.invoke(cli, ["init"], input="n\n")

        assert result.exit_code == 0
        assert "\\___|_|_\\" in result.output


class TestStatusBanner:
    """Tests that the banner appears in status command output."""

    def test_status_shows_banner(self, tmp_path, monkeypatch):
        """Banner appears at the top of status output."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("CRYOPOD_API_KEY", raising=False)

        runner = CliRunner()
        result = runner.invoke(cli, ["status"])

        assert result.exit_code == 0
        assert "\\___|_|_\\" in result.output


class TestBannerStyling:
    """Tests for banner styling helpers."""

    def test_banner_is_bold_styled(self):
        """get_help_epilog returns a string with ANSI bold escape codes."""
        epilog = get_help_epilog()
        # ANSI bold escape code
        assert "\033[1m" in epilog
        assert "___ ___ _   _ ___" in epilog

    def test_print_banner_uses_bold(self):
        """print_banner outputs the banner text to the console."""
        buf = StringIO()
        console = Console(file=buf, force_terminal=True)
        print_banner(console)
        output = buf.getvalue()
        assert "___ ___ _   _ ___" in output

    def test_epilog_starts_with_backslash_b(self):
        """Epilog starts with \\b\\n to prevent Click re-wrapping."""
        epilog = get_help_epilog()
        assert epilog.startswith("\b\n")


class TestBannerGroup:
    """Tests for the BannerGroup custom click.Group."""

    def test_banner_group_is_used(self):
        """The CLI uses BannerGroup as its group class."""
        assert isinstance(cli, BannerGroup)
