from __future__ import annotations

import re

from flow.services.hotspot import (
    HotspotManager,
    generate_default_password,
    generate_default_ssid,
)


class _FakeBackend:
    def __init__(self):
        self.started = None
        self.active = False

    def is_supported(self):
        return True

    def start(self, ssid, password):
        self.started = (ssid, password)
        self.active = True
        return True

    def stop(self):
        self.active = False

    def is_active(self):
        return self.active

    def last_error(self):
        return ""

    def gateway_ip(self):
        return "10.42.0.1" if self.active else None

    def support_message(self):
        return ""

    def captive_portal_installed(self):
        return False

    def captive_portal_install_command(self):
        return ["true"]


def test_generate_default_ssid_format():
    assert re.fullmatch(r"Flow-[0-9A-F]{4}", generate_default_ssid())


def test_generate_default_password_len():
    pw = generate_default_password()
    assert len(pw) >= 8 and pw.isalnum()


def test_manager_delegates_and_emits(qapp):
    be = _FakeBackend()
    mgr = HotspotManager(backend=be)
    fired = []
    mgr.state_changed.connect(lambda: fired.append(1))
    assert mgr.is_supported() is True
    assert mgr.start("Flow-0001", "pw123456") is True
    assert be.started == ("Flow-0001", "pw123456")
    assert mgr.is_active() is True
    assert mgr.gateway_ip() == "10.42.0.1"
    mgr.stop()
    assert mgr.is_active() is False
    assert len(fired) == 2


def test_manager_default_backend_on_this_os(qapp):
    mgr = HotspotManager()
    assert isinstance(mgr.is_supported(), bool)
    assert isinstance(mgr.support_message(), str)
    assert isinstance(mgr.captive_portal_installed(), bool)


def test_linux_start_builds_nmcli_command():
    from flow.services.hotspot import _LinuxHotspot

    calls = []

    class R:
        returncode = 0
        stdout = "wld0:wifi\n"
        stderr = ""

    def fake_run(args, **kw):
        calls.append(args)
        return R()

    be = _LinuxHotspot(run=fake_run, which=lambda n: "/usr/bin/nmcli")
    assert be.start("Flow-0001", "pw123456") is True
    hotspot_calls = [c for c in calls if "hotspot" in c]
    assert hotspot_calls, calls
    args = hotspot_calls[0]
    assert args[:4] == ["nmcli", "device", "wifi", "hotspot"]
    assert "Flow-0001" in args and "pw123456" in args


def test_linux_start_failure_sets_error():
    from flow.services.hotspot import _LinuxHotspot

    class R:
        returncode = 1
        stdout = "wld0:wifi\n"
        stderr = "Wi-Fi adapter busy"

    # _wifi_device needs a wifi line; same R works (stdout has wld0:wifi)
    be = _LinuxHotspot(run=lambda a, **k: R(), which=lambda n: "/usr/bin/nmcli")
    assert be.start("s", "p12345678") is False
    assert "busy" in be.last_error()


def test_linux_not_supported_without_nmcli():
    from flow.services.hotspot import _LinuxHotspot

    be = _LinuxHotspot(run=lambda a, **k: None, which=lambda n: None)
    assert be.is_supported() is False
    assert be.support_message() != ""


def test_linux_captive_install_command():
    from flow.services.hotspot import _LinuxHotspot

    be = _LinuxHotspot(run=lambda a, **k: None, which=lambda n: "/usr/bin/nmcli")
    cmd = be.captive_portal_install_command()
    assert cmd[0] == "pkexec" and cmd[1] == "bash"
    assert cmd[-1].endswith("install_captive.sh")
