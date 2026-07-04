from __future__ import annotations

import json
import urllib.request
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtWebSockets import QWebSocket

from flow.services.markdown import parse
from flow.services.web_broadcast import (
    WebBroadcastServer,
    build_markdown_payload,
    detect_local_ips,
    encode_image_payload,
)

_MD = "# 바다\n\n푸른 바다가 보이네\n\n노을이 물든다\n"


def test_build_markdown_payload_first_send(tmp_path):
    spec = parse(_MD)
    payload, bg_key = build_markdown_payload(spec, 0, tmp_path, last_bg=None)
    assert payload["type"] == "markdown"
    assert payload["main_text"] == "푸른 바다가 보이네"
    assert "changed_background" not in payload
    assert bg_key is not None


def test_build_markdown_payload_bg_key_stable_across_slides(tmp_path):
    spec = parse(_MD)
    _, bg_key = build_markdown_payload(spec, 0, tmp_path, last_bg=None)
    payload2, bg_key2 = build_markdown_payload(spec, 1, tmp_path, last_bg=bg_key)
    assert bg_key2 == bg_key
    assert payload2["main_text"] == "노을이 물든다"


def test_build_markdown_payload_hex_color(tmp_path):
    md = '---\nbackground: "#112233"\n---\n\n# 곡\n\n가사\n'
    spec = parse(md)
    payload, bg_key = build_markdown_payload(spec, 0, tmp_path, last_bg=None)
    assert payload["background_color"] == "#112233"
    assert bg_key == "#112233"


def test_build_markdown_payload_bg_key_distinguishes_same_relative_name(tmp_path):
    """FIX-I1: two songs both using a relative 'bg.jpg' must not collide."""
    song_a = tmp_path / "song_a"
    song_b = tmp_path / "song_b"
    song_a.mkdir()
    song_b.mkdir()
    (song_a / "bg.jpg").write_bytes(b"AAAA")
    (song_b / "bg.jpg").write_bytes(b"BBBB")

    md = '---\nbackground: "bg.jpg"\n---\n\n# 곡\n\n가사\n'
    spec = parse(md)
    _, bg_key_a = build_markdown_payload(spec, 0, song_a, last_bg=None)
    _, bg_key_b = build_markdown_payload(spec, 0, song_b, last_bg=None)
    assert bg_key_a != bg_key_b


def test_encode_image_payload(qapp):
    from PySide6.QtGui import QImage
    img = QImage(4, 4, QImage.Format.Format_RGB32)
    img.fill(0xFF000000)
    payload = encode_image_payload(img)
    assert payload["type"] == "image"
    assert payload["data_url"].startswith("data:image/png;base64,")


def test_detect_local_ips_returns_list():
    ips = detect_local_ips()
    assert isinstance(ips, list)
    assert all(not ip.startswith("127.") for ip in ips)


def test_ws_port_defaults_to_fixed_value(qapp):
    """A fixed WS port (rather than an OS-assigned random one) lets a
    restrictive firewall zone (e.g. NetworkManager's hotspot nm-shared zone)
    allow it in advance — see Flow's captive-portal install script."""
    srv = WebBroadcastServer()
    srv.start()
    try:
        assert srv.ws_port() == 8778
    finally:
        srv.stop()
    assert srv.ws_port() is None


def test_server_start_stop_and_http_serves_page(qapp, qtbot):
    srv = WebBroadcastServer()
    srv.start()
    try:
        assert srv.is_running()
        resp = urllib.request.urlopen(
            f"http://127.0.0.1:{srv._http_port}/", timeout=3
        )
        body = resp.read().decode("utf-8")
        assert "<html" in body.lower()
        assert "{{WS_PORT}}" not in body
    finally:
        srv.stop()
    assert not srv.is_running()


def test_http_serves_real_index_html(qapp):
    srv = WebBroadcastServer()
    srv.start()
    try:
        resp = urllib.request.urlopen(
            f"http://127.0.0.1:{srv._http_port}/", timeout=3
        )
        body = resp.read().decode("utf-8")
        assert "100dvh" in body
        assert "object-fit" in body
        assert "WebSocket" in body
        assert "{{WS_PORT}}" not in body
    finally:
        srv.stop()


def test_index_html_drops_dead_changed_background_field(qapp):
    """FIX-C1: late joiners must not depend on the (dropped) changed_background
    flag — the client now dedupes/reloads bg by comparing the URL itself."""
    srv = WebBroadcastServer()
    srv.start()
    try:
        resp = urllib.request.urlopen(
            f"http://127.0.0.1:{srv._http_port}/", timeout=3
        )
        body = resp.read().decode("utf-8")
        assert "changed_background" not in body
        assert "endsWith" in body
    finally:
        srv.stop()


def test_websocket_receives_last_payload_on_connect(qapp, qtbot):
    from PySide6.QtGui import QImage
    srv = WebBroadcastServer()
    srv.start()
    try:
        img = QImage(4, 4, QImage.Format.Format_RGB32)
        img.fill(0xFF000000)

        class _FakeSong:
            slide_source = "pptx"
        srv.push_current_slide(_FakeSong(), 0, img)

        client = QWebSocket()
        received = []
        client.textMessageReceived.connect(received.append)
        client.open(QUrl(f"ws://127.0.0.1:{srv._ws_port}"))
        qtbot.waitUntil(lambda: len(received) >= 1, timeout=3000)
        msg = json.loads(received[0])
        assert msg["type"] == "image"
    finally:
        srv.stop()


def test_push_current_slide_applies_patches(qapp, tmp_path):
    """FIX-C2: emergency EDIT patches must be reflected in the pushed payload,
    not the stale raw slides.md text."""
    from flow.domain.song import Song
    from flow.services.markdown import PatchStore, PatchType, SlidePatch, slide_hash

    song_dir = tmp_path / "song"
    song_dir.mkdir()
    (song_dir / "slides.md").write_text(_MD, encoding="utf-8")

    original_main = parse(_MD).slides[0].main
    patch = SlidePatch(
        id="p1",
        type=PatchType.EDIT,
        patched_main="하늘이 맑다",
        slide_hash=slide_hash(original_main),
        slide_index=0,
        created_at="2026-07-01T00:00:00",
        created_during="live",
    )
    store = PatchStore(song_dir / ".patches.json")
    store.add(patch)
    store.save()

    song = Song(name="곡", folder=song_dir)
    srv = WebBroadcastServer()
    srv.push_current_slide(song, 0, None)

    payload = json.loads(srv._last_payload_json)
    assert payload["main_text"] == "하늘이 맑다"


def test_push_current_slide_falls_back_to_image_on_markdown_error(qapp):
    """FIX-C2: any failure building the markdown payload (stale index from an
    APPEND patch, missing file, etc.) must fall back to the projector image
    instead of leaving the viewer stuck / raising."""
    from PySide6.QtGui import QImage

    class _FakeSong:
        slide_source = "markdown"
        markdown_path = Path("/nonexistent/slides.md")
        abs_folder = Path("/nonexistent")

    img = QImage(4, 4, QImage.Format.Format_RGB32)
    img.fill(0xFF000000)

    srv = WebBroadcastServer()
    srv.push_current_slide(_FakeSong(), 0, img)

    payload = json.loads(srv._last_payload_json)
    assert payload["type"] == "image"


def test_captive_check_routes(qapp):
    srv = WebBroadcastServer()
    srv.start()
    try:
        port = srv._http_port
        r204 = urllib.request.urlopen(
            f"http://127.0.0.1:{port}/generate_204", timeout=3
        )
        assert r204.status == 204
        rios = urllib.request.urlopen(
            f"http://127.0.0.1:{port}/hotspot-detect.html", timeout=3
        )
        assert rios.status == 200
        assert b"Success" in rios.read()
    finally:
        srv.stop()
