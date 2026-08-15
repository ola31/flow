from __future__ import annotations

import json
import urllib.request
from pathlib import Path

import pytest
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
    assert payload["data_url"].startswith("data:image/jpeg;base64,")


def test_encode_image_payload_is_decodable_and_small(qapp):
    """PNG로 되돌아가면 인코딩이 ~600ms로 늘어 송출 전환이 눈에 띄게 밀린다.

    시간은 기계마다 달라 못 재므로, 그 비용을 부르는 무손실 형식으로
    되돌아갔는지를 크기로 잡는다 — 사진 같은 슬라이드 한 장에서
    PNG는 JPEG의 5배 넘게 나온다.
    """
    import base64
    import math

    from PySide6.QtGui import QImage, QColor

    img = QImage(640, 360, QImage.Format.Format_RGB32)
    for y in range(img.height()):  # PNG가 못 줄이는 연속 계조
        for x in range(img.width()):
            img.setPixelColor(
                x, y, QColor(x % 256, y % 256, int(127 + 127 * math.sin(x / 40)))
            )

    payload = encode_image_payload(img)
    raw = base64.b64decode(payload["data_url"].split(",", 1)[1])

    assert raw[:2] == b"\xff\xd8", "JPEG SOI 마커여야 한다"
    assert QImage.fromData(raw).size() == img.size(), "브라우저가 열 수 있어야 한다"
    assert len(raw) < img.width() * img.height() // 4, (
        f"픽셀당 2비트도 안 되게 압축돼야 한다 (실제 {len(raw)}바이트)"
    )


def test_detect_local_ips_returns_list():
    ips = detect_local_ips()
    assert isinstance(ips, list)
    assert all(not ip.startswith("127.") for ip in ips)


def test_ws_port_defaults_to_fixed_value(qapp):
    """A fixed WS port (rather than an OS-assigned random one) lets a
    restrictive firewall zone (e.g. NetworkManager's hotspot nm-shared zone)
    allow it in advance — see Flow's captive-portal install script.

    Other tests in this suite start servers on the same fixed port, and
    under xdist they run in parallel workers: whoever loses the race falls
    back to an ephemeral port. Retry until the port is actually free so the
    assertion tests our behaviour, not the scheduler.
    """
    import time

    for _ in range(40):
        srv = WebBroadcastServer()
        srv.start()
        port = srv.ws_port()
        if port == 8778:
            srv.stop()
            assert srv.ws_port() is None
            return
        srv.stop()  # 다른 워커가 쥐고 있다 — 잠시 후 다시
        time.sleep(0.1)

    pytest.skip("8778 포트가 계속 사용 중 — 병렬 실행 충돌")


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


def test_index_html_wraps_lyrics_at_word_boundaries(qapp):
    """긴 가사가 브라우저에서 접힐 때는 띄어쓰기 단위로만 끊는다.

    데스크톱 슬라이드보다 폭이 좁아 줄바꿈이 생기는데, 기본값
    (word-break: normal)은 한글을 음절에서 끊어 "노을이"가 "노 / 을이"로
    갈라진다. 줄은 최대한 채운다 — 가운데에서 나누는 text-wrap: balance는
    쓰지 않는다.
    """
    srv = WebBroadcastServer()
    srv.start()
    try:
        resp = urllib.request.urlopen(
            f"http://127.0.0.1:{srv._http_port}/", timeout=3
        )
        body = resp.read().decode("utf-8")
        assert "word-break: keep-all" in body
        # 한 어절이 한 줄보다 길 때의 탈출구
        assert "overflow-wrap: break-word" in body
        assert "text-wrap: balance" not in body
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
