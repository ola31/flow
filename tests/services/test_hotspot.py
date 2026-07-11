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

    def is_open_fallback(self):
        return False


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


def test_manager_polls_and_detects_external_state_change(qapp, qtbot):
    """The hotspot can be toggled outside Flow entirely (OS network
    settings, nmcli, ...) — the manager must notice via polling, not just
    react to its own start()/stop() calls, or the toggle button drifts from
    reality."""
    be = _FakeBackend()
    mgr = HotspotManager(backend=be)
    mgr._poll_timer.setInterval(20)  # speed up for the test
    fired = []
    mgr.state_changed.connect(lambda: fired.append(1))

    be.active = True  # simulate e.g. nmcli/GNOME settings turning it on
    qtbot.waitUntil(lambda: bool(fired), timeout=1000)
    assert mgr.is_active() is True


def test_manager_default_backend_on_this_os(qapp):
    mgr = HotspotManager()
    assert isinstance(mgr.is_supported(), bool)
    assert isinstance(mgr.support_message(), str)
    assert isinstance(mgr.captive_portal_installed(), bool)


def test_linux_start_builds_open_hotspot_profile():
    """WPA2 AP mode is unreliable across Wi-Fi drivers (e.g. brcmfmac on
    Apple Silicon/Asahi Linux never manages to push the PSK into firmware),
    so Flow always builds an open (no password) hotspot on Linux."""
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
    assert be.is_open_fallback() is True

    joined = [" ".join(c) for c in calls]
    assert any("connection delete Hotspot" in c for c in joined)
    assert any(
        "connection add type wifi" in c and "Flow-0001" in c for c in joined
    )
    assert any(
        "802-11-wireless.mode ap" in c and "ipv4.method shared" in c
        for c in joined
    )
    assert any("connection up Hotspot" in c for c in joined)
    # no password ever passed to nmcli
    assert not any("pw123456" in c for c in joined)


def test_linux_start_failure_sets_error():
    from flow.services.hotspot import _LinuxHotspot

    class R:
        def __init__(self, returncode=0, stdout="", stderr=""):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def fake_run(args, **kw):
        if args[:3] == ["nmcli", "connection", "up"]:
            return R(returncode=1, stderr="Wi-Fi adapter busy")
        return R(stdout="wld0:wifi\n")

    be = _LinuxHotspot(run=fake_run, which=lambda n: "/usr/bin/nmcli")
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


def test_captive_install_script_exists_on_disk():
    import os

    from flow.services.hotspot import _LinuxHotspot

    be = _LinuxHotspot(run=lambda a, **k: None, which=lambda n: "/usr/bin/nmcli")
    cmd = be.captive_portal_install_command()
    assert os.path.exists(cmd[-1]), cmd[-1]


def test_captive_installed_false_when_content_stale(monkeypatch, tmp_path):
    """A stale install from an older Flow version (e.g. the old blanket
    '/#/' DNS override that broke real internet sharing over Ethernet) must
    be treated as 'not installed' so the app reinstalls the current config
    automatically instead of silently running outdated rules forever."""
    import flow.services.hotspot as hotspot_module

    stale = tmp_path / "flow-captive.conf"
    stale.write_text("address=/#/10.42.0.1\n")
    monkeypatch.setattr(hotspot_module, "_CAPTIVE_MARKER_PATH", stale)

    be = hotspot_module._LinuxHotspot(
        run=lambda a, **k: None, which=lambda n: None
    )
    assert be.captive_portal_installed() is False


def test_captive_installed_false_when_dispatcher_stale(monkeypatch, tmp_path):
    """A stale dispatcher script (e.g. missing the DOCKER-USER forwarding
    workaround) must be treated as 'not installed' too, not just a stale
    dnsmasq conf — both files need to be current."""
    import flow.services.hotspot as hotspot_module

    current_conf = tmp_path / "flow-captive.conf"
    current_conf.write_bytes(hotspot_module._CAPTIVE_CONF_RESOURCE_PATH.read_bytes())
    monkeypatch.setattr(hotspot_module, "_CAPTIVE_MARKER_PATH", current_conf)

    stale_dispatcher = tmp_path / "90-flow-captive"
    stale_dispatcher.write_text("#!/bin/bash\n# old version, no DOCKER-USER fix\n")
    monkeypatch.setattr(
        hotspot_module, "_CAPTIVE_DISPATCHER_PATH", stale_dispatcher
    )

    be = hotspot_module._LinuxHotspot(
        run=lambda a, **k: None, which=lambda n: None
    )
    assert be.captive_portal_installed() is False


def test_captive_installed_true_when_content_matches(monkeypatch, tmp_path):
    import flow.services.hotspot as hotspot_module

    current = tmp_path / "flow-captive.conf"
    current.write_bytes(hotspot_module._CAPTIVE_CONF_RESOURCE_PATH.read_bytes())
    monkeypatch.setattr(hotspot_module, "_CAPTIVE_MARKER_PATH", current)
    current_dispatcher = tmp_path / "90-flow-captive"
    current_dispatcher.write_bytes(
        hotspot_module._CAPTIVE_DISPATCHER_RESOURCE_PATH.read_bytes()
    )
    monkeypatch.setattr(
        hotspot_module, "_CAPTIVE_DISPATCHER_PATH", current_dispatcher
    )

    be = hotspot_module._LinuxHotspot(
        run=lambda a, **k: None, which=lambda n: None
    )
    assert be.captive_portal_installed() is True


def test_captive_installed_false_when_forward_disabled(monkeypatch, tmp_path):
    """firewalld blocks inter-zone forwarding by default, which silently
    breaks real internet sharing (e.g. via Ethernet) even though DNS
    (answered locally by dnsmasq) keeps working — a very confusing failure
    mode unless this is treated as an incomplete install."""
    import flow.services.hotspot as hotspot_module

    current = tmp_path / "flow-captive.conf"
    current.write_bytes(hotspot_module._CAPTIVE_CONF_RESOURCE_PATH.read_bytes())
    monkeypatch.setattr(hotspot_module, "_CAPTIVE_MARKER_PATH", current)
    current_dispatcher = tmp_path / "90-flow-captive"
    current_dispatcher.write_bytes(
        hotspot_module._CAPTIVE_DISPATCHER_RESOURCE_PATH.read_bytes()
    )
    monkeypatch.setattr(
        hotspot_module, "_CAPTIVE_DISPATCHER_PATH", current_dispatcher
    )

    class R:
        def __init__(self, returncode):
            self.returncode = returncode

    def fake_run(args, **kw):
        if "--query-forward" in args:
            return R(returncode=1)  # "no"
        return R(returncode=0)  # ports are open

    be = hotspot_module._LinuxHotspot(
        run=fake_run, which=lambda n: f"/usr/bin/{n}"
    )
    assert be.captive_portal_installed() is False


def test_captive_installed_true_when_forward_enabled(monkeypatch, tmp_path):
    import flow.services.hotspot as hotspot_module

    current = tmp_path / "flow-captive.conf"
    current.write_bytes(hotspot_module._CAPTIVE_CONF_RESOURCE_PATH.read_bytes())
    monkeypatch.setattr(hotspot_module, "_CAPTIVE_MARKER_PATH", current)
    current_dispatcher = tmp_path / "90-flow-captive"
    current_dispatcher.write_bytes(
        hotspot_module._CAPTIVE_DISPATCHER_RESOURCE_PATH.read_bytes()
    )
    monkeypatch.setattr(
        hotspot_module, "_CAPTIVE_DISPATCHER_PATH", current_dispatcher
    )

    class R:
        def __init__(self, returncode):
            self.returncode = returncode

    def fake_run(args, **kw):
        return R(returncode=0)

    be = hotspot_module._LinuxHotspot(
        run=fake_run, which=lambda n: f"/usr/bin/{n}"
    )
    assert be.captive_portal_installed() is True


def test_stop_if_started_noop_when_not_started():
    from flow.services.hotspot import _LinuxHotspot

    calls = []

    class R:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(args, **kw):
        calls.append(args)
        return R()

    be = _LinuxHotspot(run=fake_run, which=lambda n: "/usr/bin/nmcli")
    be.stop_if_started()
    assert not any("down" in c for c in calls)


def test_stop_if_started_runs_after_successful_start():
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
    calls.clear()
    be.stop_if_started()
    assert any("down" in c for c in calls)


def test_is_active_false_for_vpn_named_hotspot():
    from flow.services.hotspot import _LinuxHotspot

    class R:
        returncode = 0
        stdout = "Hotspot:vpn\n"
        stderr = ""

    be = _LinuxHotspot(run=lambda a, **k: R(), which=lambda n: "/usr/bin/nmcli")
    assert be.is_active() is False


def test_is_active_true_for_wireless_hotspot():
    from flow.services.hotspot import _LinuxHotspot

    class R:
        returncode = 0
        stdout = "Hotspot:802-11-wireless\n"
        stderr = ""

    be = _LinuxHotspot(run=lambda a, **k: R(), which=lambda n: "/usr/bin/nmcli")
    assert be.is_active() is True


def test_linux_start_deletes_stale_profile_before_creating():
    """A leftover 'Hotspot' profile from a previous run can carry mismatched
    settings that make nmcli silently no-op, so start() must always tear
    down any existing profile first."""
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
    joined = [" ".join(c) for c in calls]
    delete_idx = next(i for i, c in enumerate(joined) if "connection delete Hotspot" in c)
    add_idx = next(i for i, c in enumerate(joined) if "connection add type wifi" in c)
    assert delete_idx < add_idx


def test_windows_backend_unsupported_without_winsdk():
    from flow.services.hotspot import _WindowsHotspot

    be = _WindowsHotspot()
    # On this Linux machine winsdk isn't importable and sys.platform != win32
    assert be.is_supported() is False
    assert "Windows" in be.support_message()
    assert be.captive_portal_installed() is False
    assert be.captive_portal_install_command() == []


class TestCaptiveInstalledCache:
    """captive_portal_installed는 firewall-cmd 3회(~800ms)를 부르는 비싼
    검사 — 페이지 전환마다 재실행하지 않도록 매니저가 캐시하고, 설치/제거
    액션 후에만 무효화한다."""

    class _CountingBackend:
        def __init__(self):
            self.calls = 0

        def is_supported(self):
            return True

        def is_active(self):
            return False

        def captive_portal_installed(self):
            self.calls += 1
            return True

    def test_second_call_uses_cache(self, qapp):
        from flow.services.hotspot import HotspotManager

        backend = self._CountingBackend()
        mgr = HotspotManager(backend=backend)

        assert mgr.captive_portal_installed() is True
        assert mgr.captive_portal_installed() is True
        assert backend.calls == 1  # 캐시 히트

    def test_invalidate_forces_recheck(self, qapp):
        from flow.services.hotspot import HotspotManager

        backend = self._CountingBackend()
        mgr = HotspotManager(backend=backend)

        mgr.captive_portal_installed()
        mgr.invalidate_captive_cache()
        mgr.captive_portal_installed()

        assert backend.calls == 2
