from __future__ import annotations

import secrets
import shutil
import string
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

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

    def is_open_fallback(self) -> bool:
        return False


_CAPTIVE_MARKER_PATH = Path(
    "/etc/NetworkManager/dnsmasq-shared.d/flow-captive.conf"
)
_CAPTIVE_CONF_RESOURCE_PATH = (
    Path(__file__).resolve().parents[1]
    / "resources"
    / "captive"
    / "flow-captive.conf"
)
_CAPTIVE_DISPATCHER_PATH = Path(
    "/etc/NetworkManager/dispatcher.d/90-flow-captive"
)
_CAPTIVE_DISPATCHER_RESOURCE_PATH = (
    Path(__file__).resolve().parents[1]
    / "resources"
    / "captive"
    / "90-flow-captive"
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
        # WPA2 AP mode is unreliable across Wi-Fi drivers — e.g. brcmfmac on
        # Apple Silicon/Asahi Linux advertises AP support but never manages
        # to push the PSK into firmware, so no client can complete the
        # handshake. Flow always creates an open (no password) hotspot on
        # Linux to sidestep this; `password` is accepted for interface
        # parity with the Windows backend but unused here.
        dev = self._wifi_device()
        if dev is None:
            self._last_error = "Wi-Fi 어댑터를 찾을 수 없습니다."
            return False
        # A leftover "Hotspot" profile from a previous run can have
        # conflicting settings that make nmcli silently no-op, so always
        # start from a clean profile.
        self._run(
            ["nmcli", "connection", "down", "Hotspot"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self._run(
            ["nmcli", "connection", "delete", "Hotspot"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        try:
            result = self._run(
                [
                    "nmcli",
                    "connection",
                    "add",
                    "type",
                    "wifi",
                    "ifname",
                    dev,
                    "con-name",
                    "Hotspot",
                    "autoconnect",
                    "no",
                    "ssid",
                    ssid,
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if getattr(result, "returncode", 1) != 0:
                self._last_error = (getattr(result, "stderr", "") or "").strip()
                return False
            self._run(
                [
                    "nmcli",
                    "connection",
                    "modify",
                    "Hotspot",
                    "802-11-wireless.mode",
                    "ap",
                    "ipv4.method",
                    "shared",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            result = self._run(
                ["nmcli", "connection", "up", "Hotspot"],
                capture_output=True,
                text=True,
                timeout=30,
            )
        except Exception as e:
            self._last_error = str(e)
            return False
        if getattr(result, "returncode", 1) != 0:
            self._last_error = (getattr(result, "stderr", "") or "").strip()
            return False
        self._started = True
        return True

    def is_open_fallback(self) -> bool:
        """Flow always creates an open (no password) hotspot on Linux —
        WPA2 AP mode is unreliable across Wi-Fi drivers (see start())."""
        return True

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
        if not _CAPTIVE_MARKER_PATH.exists():
            return False
        # A stale install from an older Flow version can have outdated
        # dnsmasq rules (e.g. the old blanket "/#/" override that broke real
        # internet sharing) or a dispatcher script missing newer fixes (e.g.
        # the Docker DOCKER-USER forwarding workaround). Compare both
        # against the packaged resources so a content change triggers a
        # fresh (re-)install automatically.
        try:
            if _CAPTIVE_MARKER_PATH.read_bytes() != _CAPTIVE_CONF_RESOURCE_PATH.read_bytes():
                return False
        except OSError:
            pass
        try:
            if (
                _CAPTIVE_DISPATCHER_PATH.read_bytes()
                != _CAPTIVE_DISPATCHER_RESOURCE_PATH.read_bytes()
            ):
                return False
        except OSError:
            pass
        # When firewalld is running, the broadcast port (8777) and the
        # WebSocket port (8778) must also be open on the nm-shared zone, or
        # phones reach neither the web server nor the live slide feed even
        # though the page itself loads. Treat a stale install (dnsmasq
        # snippet present but ports closed) as not installed so the setup
        # button re-appears.
        if self._which("firewall-cmd") is not None:
            for port in ("8777/tcp", "8778/tcp"):
                try:
                    result = self._run(
                        ["firewall-cmd", "--zone=nm-shared", f"--query-port={port}"],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                except Exception:
                    return True
                if getattr(result, "returncode", 0) != 0:
                    return False
            # firewalld blocks inter-zone forwarding by default, which
            # silently breaks real internet sharing (e.g. via Ethernet)
            # while leaving locally-answered DNS working — DNS looks fine,
            # actual browsing doesn't. Needs a separate zone flag from the
            # port rules above.
            try:
                result = self._run(
                    ["firewall-cmd", "--zone=nm-shared", "--query-forward"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
            except Exception:
                return True
            if getattr(result, "returncode", 0) != 0:
                return False
        return True

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

    def is_open_fallback(self) -> bool:
        return False


class HotspotManager(QObject):
    """Facade over a platform-specific hotspot backend."""

    state_changed = Signal()

    _POLL_INTERVAL_MS = 3000

    def __init__(self, backend=None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        injected = backend is not None
        if backend is None:
            if sys.platform.startswith("linux"):
                backend = _LinuxHotspot()
            elif sys.platform == "win32":
                backend = _WindowsHotspot()
            else:
                backend = _UnsupportedHotspot()
        self._backend = backend
        # The user can turn the hotspot on/off outside Flow entirely (OS
        # network settings, nmcli, ...), so is_active() must be re-checked
        # periodically rather than only right after our own start()/stop()
        # calls — otherwise the toggle button drifts from reality.
        self._last_known_active = backend.is_active()
        # captive_portal_installed는 firewall-cmd 조회 3회(~800ms)라 비쌈 —
        # 설치 상태는 설치/제거 액션 때만 바뀌므로 캐시한다.
        self._captive_installed_cache: bool | None = None
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(self._POLL_INTERVAL_MS)
        self._poll_timer.timeout.connect(self._poll_active_state)
        self._poll_timer.start()

        # 캡티브 설치 검사(firewall-cmd 3회, ~800ms)를 백그라운드로 미리
        # 데워 첫 웹 송출 페이지 전환이 느려지지 않게 한다. 주입된 테스트
        # 백엔드에는 적용하지 않는다 (결정적 테스트 유지).
        if not injected:
            import threading

            def _prewarm() -> None:
                try:
                    result = self._backend.captive_portal_installed()
                    if self._captive_installed_cache is None:
                        self._captive_installed_cache = result
                except Exception:
                    pass

            threading.Thread(target=_prewarm, daemon=True).start()

    def _poll_active_state(self) -> None:
        active = self._backend.is_active()
        if active != self._last_known_active:
            self._last_known_active = active
            self.state_changed.emit()

    def is_supported(self) -> bool:
        # 하드웨어 지원 여부는 세션 중 변하지 않음 — nmcli 재호출 방지
        if not hasattr(self, "_supported_cache"):
            self._supported_cache = self._backend.is_supported()
        return self._supported_cache

    def is_active(self) -> bool:
        return self._backend.is_active()

    def last_known_active(self) -> bool:
        """폴러가 유지하는 최근 상태 — UI 표시용 (nmcli 호출 없음).

        3초 폴링 + start/stop 훅이 갱신하므로 표시 용도로 충분하다.
        실제 동작 판단(토글 등)은 is_active()를 쓸 것.
        """
        return self._last_known_active

    def last_error(self) -> str:
        return self._backend.last_error()

    def gateway_ip(self) -> str | None:
        return self._backend.gateway_ip()

    def support_message(self) -> str:
        return self._backend.support_message()

    def captive_portal_installed(self) -> bool:
        if self._captive_installed_cache is None:
            self._captive_installed_cache = (
                self._backend.captive_portal_installed()
            )
        return self._captive_installed_cache

    def invalidate_captive_cache(self) -> None:
        """설치/제거 스크립트 실행 후 호출 — 다음 조회 때 재검사."""
        self._captive_installed_cache = None

    def captive_portal_install_command(self) -> list[str]:
        return self._backend.captive_portal_install_command()

    def captive_portal_uninstall_command(self) -> list[str]:
        return self._backend.captive_portal_uninstall_command()

    def is_open_fallback(self) -> bool:
        return self._backend.is_open_fallback()

    def start(self, ssid: str, password: str) -> bool:
        ok = self._backend.start(ssid, password)
        if ok:
            self._last_known_active = True
            self.state_changed.emit()
        return ok

    def stop(self) -> None:
        self._backend.stop()
        self._last_known_active = False
        self.state_changed.emit()

    def stop_if_started(self) -> None:
        self._backend.stop_if_started()
        self._last_known_active = self._backend.is_active()
        self.state_changed.emit()
