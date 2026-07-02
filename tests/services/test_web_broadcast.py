from __future__ import annotations

import json
import urllib.request

from PySide6.QtCore import QUrl
from PySide6.QtWebSockets import QWebSocket

from flow.services.web_broadcast import (
    WebBroadcastServer,
    build_markdown_payload,
    detect_local_ips,
    encode_image_payload,
)

_MD = "# 바다\n\n푸른 바다가 보이네\n\n노을이 물든다\n"


def test_build_markdown_payload_first_send(tmp_path):
    payload, bg_key = build_markdown_payload(_MD, 0, tmp_path, last_bg=None)
    assert payload["type"] == "markdown"
    assert payload["main_text"] == "푸른 바다가 보이네"
    assert payload["changed_background"] is True
    assert bg_key is not None


def test_build_markdown_payload_same_bg_skips(tmp_path):
    _, bg_key = build_markdown_payload(_MD, 0, tmp_path, last_bg=None)
    payload2, bg_key2 = build_markdown_payload(_MD, 1, tmp_path, last_bg=bg_key)
    assert payload2["changed_background"] is False
    assert bg_key2 == bg_key
    assert payload2["main_text"] == "노을이 물든다"


def test_build_markdown_payload_hex_color(tmp_path):
    md = '---\nbackground: "#112233"\n---\n\n# 곡\n\n가사\n'
    payload, _ = build_markdown_payload(md, 0, tmp_path, last_bg=None)
    assert payload["background_color"] == "#112233"


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
