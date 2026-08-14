from __future__ import annotations

import platform
import sys


def _get_impl():
    if platform.system() != "Darwin":
        print(
            "[hwr-sync] This tool currently supports macOS only.\n"
            "Linux and Windows support is planned for a future release."
        )
        sys.exit(1)
    from hwr_sync.scheduler import launchd
    return launchd


def install(interval_hours: int) -> None:
    _get_impl().install(interval_hours)


def uninstall() -> None:
    _get_impl().uninstall()


def is_installed() -> bool:
    if platform.system() != "Darwin":
        return False
    from hwr_sync.scheduler import launchd
    return launchd.is_installed()
