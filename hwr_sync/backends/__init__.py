from __future__ import annotations

import sys

from hwr_sync.backends.base import CalendarBackend


def get_backend(config, create_missing_calendar: bool = False) -> CalendarBackend:
    from hwr_sync.config import save_backend
    from hwr_sync.state import state_path_for_backend

    backend_name = config.calendar_backend

    if backend_name == "auto":
        backend_name = "apple"
        save_backend(backend_name)
        print(f"[hwr-sync] Calendar backend: {backend_name} (saved to config.yaml)")

    state_path = state_path_for_backend(backend_name)

    if backend_name == "apple":
        from hwr_sync.backends.apple import AppleCalendarBackend
        return AppleCalendarBackend(
            config.calendar_name,
            create_missing_calendar=create_missing_calendar,
            state_path=state_path,
        )

    if backend_name == "outlook":
        if not config.microsoft_client_id or not config.microsoft_tenant_id:
            print(
                "[hwr-sync] Outlook backend requires 'microsoft_client_id' and "
                "'microsoft_tenant_id' in your config.yaml.\n"
                "Run `hwr-sync settings` to edit the config."
            )
            sys.exit(1)
        from hwr_sync.backends.outlook import OutlookCalendarBackend
        return OutlookCalendarBackend(
            config.calendar_name,
            client_id=config.microsoft_client_id,
            tenant_id=config.microsoft_tenant_id,
            create_missing_calendar=create_missing_calendar,
            state_path=state_path,
        )

    print(
        f"[hwr-sync] Backend '{backend_name}' is not supported.\n"
        "Supported backends: apple, outlook\n"
        "Set calendar_backend in your config.yaml."
    )
    sys.exit(1)
