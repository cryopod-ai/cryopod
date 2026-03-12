"""ASCII banner for Cryopod CLI."""

import click
from rich.console import Console

BANNER = r"""  ___ ___ _   _ ___  ___  ___  ___
 / __| _ \ \_/ / _ \| _ \/ _ \|   \
| (__|   /\   / (_) |  _/ (_) | |) |
 \___|_|_\ |_| \___/|_|  \___/|___/"""


def print_banner(console: Console) -> None:
    """Print the ASCII banner to a rich Console with bold styling."""
    console.print(BANNER, style="bold")


def get_help_epilog() -> str:
    """Return the banner formatted for Click help epilog output.

    Uses the ``\\b`` escape to prevent Click from re-wrapping the
    pre-formatted ASCII art.

    .. deprecated::
        Use :class:`BannerGroup` instead to display the banner before help text.
    """
    return "\b\n" + click.style(BANNER, bold=True)


class BannerGroup(click.Group):
    """A click.Group that prepends the ASCII banner before help text."""

    def format_help(self, ctx, formatter):
        formatter.write(click.style(BANNER, bold=True))
        formatter.write("\n\n")
        super().format_help(ctx, formatter)
