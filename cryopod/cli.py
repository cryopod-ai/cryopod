"""Cryopod CLI entry point."""

import click

from cryopod import __version__
from cryopod.add import add_command
from cryopod.banner import BannerGroup
from cryopod.freeze import freeze_command
from cryopod.init import init_command
from cryopod.keygen import keygen_command
from cryopod.list import list_command
from cryopod.manifest import manifest_command
from cryopod.purge import purge_command
from cryopod.remove import remove_command
from cryopod.restore import restore_command
from cryopod.skill import skill_command
from cryopod.status import status_command
from cryopod.thaw import thaw_command
from cryopod.update import update_command
from cryopod.versions import versions_command


@click.group(cls=BannerGroup)
@click.version_option(version=__version__, prog_name="cryopod")
def cli():
    """Cryopod - Agent config backup and sync.

    CLI for the cryopod.ai agent configuration backup and sync service.
    """


cli.add_command(add_command, "add")
cli.add_command(purge_command, "purge")
cli.add_command(freeze_command, "freeze")
cli.add_command(init_command, "init")
cli.add_command(keygen_command, "keygen")
cli.add_command(manifest_command, "manifest")
cli.add_command(list_command, "list")
cli.add_command(remove_command, "remove")
cli.add_command(restore_command, "restore")
cli.add_command(skill_command, "skill")
cli.add_command(status_command, "status")
cli.add_command(thaw_command, "thaw")
cli.add_command(update_command, "update")
cli.add_command(versions_command, "versions")


def main():
    cli()


if __name__ == "__main__":
    main()
