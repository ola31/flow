from __future__ import annotations

import secrets
import string
import sys

from PySide6.QtCore import QObject, Signal

_UNSUPPORTED_MESSAGE = (
    "이 운영체제에서는 Flow가 핫스팟을 자동으로 켤 수 없습니다. "
    "OS 설정에서 직접 핫스팟을 켠 뒤 웹 송출을 사용하세요."
)


def generate_default_ssid() -> str:
    """Generate a default hotspot SSID like ``Flow-3F2A``."""
    return f"Flow-{secrets.token_hex(2).upper()}"


def generate_default_password() -> str:
    """Generate an 8-character alphanumeric default hotspot password."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(8))


class _UnsupportedHotspot:
    """Fallback backend for platforms with no hotspot automation support."""

    def is_supported(self) -> bool:
        return False

    def is_active(self) -> bool:
        return False

    def start(self, ssid: str, password: str) -> bool:
        return False

    def stop(self) -> None:
        return None

    def last_error(self) -> str:
        return ""

    def gateway_ip(self) -> str | None:
        return None

    def support_message(self) -> str:
        return _UNSUPPORTED_MESSAGE

    def captive_portal_installed(self) -> bool:
        return False

    def captive_portal_install_command(self) -> list[str]:
        return []


class _LinuxHotspot:
    """Linux hotspot backend (stub — implemented in a later task)."""

    def is_supported(self) -> bool:
        return False

    def is_active(self) -> bool:
        return False

    def start(self, ssid: str, password: str) -> bool:
        return False

    def stop(self) -> None:
        return None

    def last_error(self) -> str:
        return ""

    def gateway_ip(self) -> str | None:
        return None

    def support_message(self) -> str:
        return _UNSUPPORTED_MESSAGE

    def captive_portal_installed(self) -> bool:
        return False

    def captive_portal_install_command(self) -> list[str]:
        return []


class _WindowsHotspot:
    """Windows hotspot backend (stub — implemented in a later task)."""

    def is_supported(self) -> bool:
        return False

    def is_active(self) -> bool:
        return False

    def start(self, ssid: str, password: str) -> bool:
        return False

    def stop(self) -> None:
        return None

    def last_error(self) -> str:
        return ""

    def gateway_ip(self) -> str | None:
        return None

    def support_message(self) -> str:
        return _UNSUPPORTED_MESSAGE

    def captive_portal_installed(self) -> bool:
        return False

    def captive_portal_install_command(self) -> list[str]:
        return []


class HotspotManager(QObject):
    """Facade over a platform-specific hotspot backend."""

    state_changed = Signal()

    def __init__(self, backend=None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        if backend is None:
            if sys.platform.startswith("linux"):
                backend = _LinuxHotspot()
            elif sys.platform == "win32":
                backend = _WindowsHotspot()
            else:
                backend = _UnsupportedHotspot()
        self._backend = backend

    def is_supported(self) -> bool:
        return self._backend.is_supported()

    def is_active(self) -> bool:
        return self._backend.is_active()

    def last_error(self) -> str:
        return self._backend.last_error()

    def gateway_ip(self) -> str | None:
        return self._backend.gateway_ip()

    def support_message(self) -> str:
        return self._backend.support_message()

    def captive_portal_installed(self) -> bool:
        return self._backend.captive_portal_installed()

    def captive_portal_install_command(self) -> list[str]:
        return self._backend.captive_portal_install_command()

    def start(self, ssid: str, password: str) -> bool:
        ok = self._backend.start(ssid, password)
        if ok:
            self.state_changed.emit()
        return ok

    def stop(self) -> None:
        self._backend.stop()
        self.state_changed.emit()
