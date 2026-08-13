from __future__ import annotations

import platform


def _get_impl():
    system = platform.system()
    if system == "Darwin":
        from hwr_sync.scheduler import launchd as impl
    elif system == "Linux":
        from hwr_sync.scheduler import systemd as impl
    elif system == "Windows":
        from hwr_sync.scheduler import wintask as impl
    else:
        raise OSError(f"Unsupported platform: {system}")
    return impl


def install(interval_hours: int) -> None:
    _get_impl().install(interval_hours)


def uninstall() -> None:
    _get_impl().uninstall()


def is_installed() -> bool:
    return _get_impl().is_installed()
