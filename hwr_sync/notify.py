from __future__ import annotations

import platform
import subprocess


def notify(title: str, body: str) -> None:
    system = platform.system()
    try:
        if system == "Darwin":
            _notify_macos(title, body)
        elif system == "Linux":
            _notify_linux(title, body)
        elif system == "Windows":
            _notify_windows(title, body)
    except Exception:
        # Notifications are best-effort — never crash the sync
        pass


def _notify_macos(title: str, body: str) -> None:
    script = f'display notification "{body}" with title "{title}"'
    subprocess.run(["osascript", "-e", script], check=False, capture_output=True)


def _notify_linux(title: str, body: str) -> None:
    subprocess.run(["notify-send", title, body], check=False, capture_output=True)


def _notify_windows(title: str, body: str) -> None:
    # PowerShell toast — no extra dependency needed
    ps = (
        f"[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] | Out-Null;"
        f"$template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02);"
        f"$template.GetElementsByTagName('text')[0].AppendChild($template.CreateTextNode('{title}')) | Out-Null;"
        f"$template.GetElementsByTagName('text')[1].AppendChild($template.CreateTextNode('{body}')) | Out-Null;"
        f"$toast = [Windows.UI.Notifications.ToastNotification]::new($template);"
        f"[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('hwr-sync').Show($toast);"
    )
    subprocess.run(
        ["powershell", "-WindowStyle", "Hidden", "-Command", ps],
        check=False,
        capture_output=True,
    )
