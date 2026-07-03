from __future__ import annotations

import secrets
import shutil
import string
import subprocess
import sys
from pathlib import Path

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

    def stop_if_started(self) -> None:
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

    def captive_portal_uninstall_command(self) -> list[str]:
        return []


_CAPTIVE_MARKER_PATH = Path(
    "/etc/NetworkManager/dnsmasq-shared.d/flow-captive.conf"
)


class _LinuxHotspot:
    """Linux hotspot backend driven by ``nmcli``."""

    def __init__(self, run=subprocess.run, which=shutil.which) -> None:
        self._run = run
        self._which = which
        self._last_error = ""
        self._started = False

    def _wifi_device(self) -> str | None:
        try:
            result = self._run(
                ["nmcli", "-t", "-f", "DEVICE,TYPE", "device"],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except Exception:
            return None
        stdout = getattr(result, "stdout", "") or ""
        for line in stdout.splitlines():
            parts = line.split(":")
            if len(parts) >= 2 and parts[1] == "wifi":
                return parts[0]
        return None

    def is_supported(self) -> bool:
        return self._which("nmcli") is not None and self._wifi_device() is not None

    def start(self, ssid: str, password: str) -> bool:
        dev = self._wifi_device()
        if dev is None:
            self._last_error = "Wi-Fi 어댑터를 찾을 수 없습니다."
            return False
        try:
            result = self._run(
                [
                    "nmcli",
                    "device",
                    "wifi",
                    "hotspot",
                    "ifname",
                    dev,
                    "ssid",
                    ssid,
                    "password",
                    password,
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
        except Exception as e:
            self._last_error = str(e)
            return False
        if result.returncode == 0:
            self._started = True
            return True
        self._last_error = (result.stderr or "").strip()
        return False

    def stop(self) -> None:
        """Explicit user-requested stop: downs the hotspot regardless of
        whether Flow was the one that started it."""
        try:
            self._run(
                ["nmcli", "connection", "down", "Hotspot"],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except Exception:
            pass
        self._started = False

    def stop_if_started(self) -> None:
        """Only stop the hotspot if this instance started it — never kill a
        hotspot the user (or another app) already had running, e.g. on app
        shutdown."""
        if self._started:
            self.stop()

    def is_active(self) -> bool:
        try:
            result = self._run(
                ["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show", "--active"],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except Exception:
            return False
        stdout = getattr(result, "stdout", "") or ""
        for line in stdout.splitlines():
            parts = line.split(":")
            if len(parts) >= 2 and parts[0] == "Hotspot" and "wireless" in parts[1]:
                return True
        return False

    def gateway_ip(self) -> str | None:
        if not self.is_active():
            return None
        try:
            dev = self._wifi_device()
            result = self._run(
                ["nmcli", "-t", "-f", "IP4.ADDRESS", "device", "show", dev],
                capture_output=True,
                text=True,
                timeout=10,
            )
            stdout = getattr(result, "stdout", "") or ""
            for line in stdout.splitlines():
                if line.startswith("IP4.ADDRESS"):
                    _, _, value = line.partition(":")
                    return value.split("/")[0].strip()
        except Exception:
            pass
        return "10.42.0.1"

    def last_error(self) -> str:
        return self._last_error

    def support_message(self) -> str:
        if self.is_supported():
            return ""
        return (
            "nmcli를 찾을 수 없거나 Wi-Fi 어댑터가 핫스팟(AP) 모드를 지원하지 "
            "않습니다."
        )

    def _captive_script_path(self) -> Path:
        return (
            Path(__file__).resolve().parents[1]
            / "resources"
            / "captive"
            / "install_captive.sh"
        )

    def _captive_uninstall_script_path(self) -> Path:
        return (
            Path(__file__).resolve().parents[1]
            / "resources"
            / "captive"
            / "uninstall_captive.sh"
        )

    def captive_portal_installed(self) -> bool:
        return _CAPTIVE_MARKER_PATH.exists()

    def captive_portal_install_command(self) -> list[str]:
        return ["pkexec", "bash", str(self._captive_script_path())]

    def captive_portal_uninstall_command(self) -> list[str]:
        """Command to remove Flow's captive-portal config (dnsmasq snippet +
        dispatcher script + nft table). Not wired to any UI button — this is
        for support/manual cleanup, run from a terminal."""
        return ["pkexec", "bash", str(self._captive_uninstall_script_path())]


_WINDOWS_CAPTIVE_MESSAGE = (
    "Windows에서는 폰 튕김 방지(캡티브 포털)를 자동 설정할 수 없습니다. "
    "폰에 '인터넷 없음' 경고가 떠도 접속을 유지하세요."
)
_WINDOWS_UNSUPPORTED_MESSAGE = (
    "Windows 모바일 핫스팟을 사용할 수 없습니다 (winsdk 미설치 또는 지원되지 "
    "않는 환경)."
)


class _WindowsHotspot:
    """Windows hotspot backend using the WinRT NetworkOperatorTetheringManager.

    All ``winsdk`` imports happen lazily inside methods so importing this
    module on non-Windows platforms (where winsdk is not installed) never
    fails.
    """

    def __init__(self) -> None:
        self._last_error = ""
        self._started = False

    def _manager(self):
        try:
            from winsdk.windows.networking.connectivity import (
                NetworkInformation,
            )
            from winsdk.windows.networking.networkoperators import (
                NetworkOperatorTetheringManager,
            )

            profile = NetworkInformation.get_internet_connection_profile()
            if profile is None:
                return None
            return NetworkOperatorTetheringManager.create_from_connection_profile(
                profile
            )
        except Exception as e:
            self._last_error = str(e)
            return None

    def is_supported(self) -> bool:
        return sys.platform == "win32" and self._manager() is not None

    def start(self, ssid: str, password: str) -> bool:
        manager = self._manager()
        if manager is None:
            self._last_error = self._last_error or "핫스팟 관리자를 찾을 수 없습니다."
            return False
        try:
            config = manager.get_current_access_point_configuration()
            config.ssid = ssid
            config.passphrase = password
            manager.configure_access_point_async(config).get()

            from winsdk.windows.networking.networkoperators import (
                TetheringOperationStatus,
            )

            result = manager.start_tethering_async().get()
            ok = bool(result.status == TetheringOperationStatus.SUCCESS)
            if ok:
                self._started = True
            return ok
        except Exception as e:
            self._last_error = str(e)
            return False

    def stop(self) -> None:
        try:
            self._manager().stop_tethering_async().get()
        except Exception:
            pass
        self._started = False

    def stop_if_started(self) -> None:
        if self._started:
            self.stop()

    def is_active(self) -> bool:
        try:
            from winsdk.windows.networking.networkoperators import (
                TetheringOperationalState,
            )

            return bool(
                self._manager().tethering_operational_state
                == TetheringOperationalState.ON
            )
        except Exception:
            return False

    def gateway_ip(self) -> str | None:
        return None

    def support_message(self) -> str:
        if self.is_supported():
            return _WINDOWS_CAPTIVE_MESSAGE
        return _WINDOWS_UNSUPPORTED_MESSAGE

    def captive_portal_installed(self) -> bool:
        return False

    def captive_portal_install_command(self) -> list[str]:
        return []

    def captive_portal_uninstall_command(self) -> list[str]:
        return []

    def last_error(self) -> str:
        return self._last_error


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

    def captive_portal_uninstall_command(self) -> list[str]:
        return self._backend.captive_portal_uninstall_command()

    def start(self, ssid: str, password: str) -> bool:
        ok = self._backend.start(ssid, password)
        if ok:
            self.state_changed.emit()
        return ok

    def stop(self) -> None:
        self._backend.stop()
        self.state_changed.emit()

    def stop_if_started(self) -> None:
        self._backend.stop_if_started()
        self.state_changed.emit()
