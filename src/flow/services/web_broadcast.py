"""Web broadcast service: serves a viewer web page over HTTP (stdlib,
background thread) and pushes live slide updates over WebSocket
(PySide6 QtWebSockets, Qt main thread).

PySide6.QtHttpServer is FORBIDDEN in this codebase (confirmed response-body
bug in this PySide6 build) — HTTP is served via stdlib http.server instead.
"""
from __future__ import annotations

import base64
import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from PySide6.QtCore import QBuffer, QIODevice, QObject, Signal
from PySide6.QtNetwork import QAbstractSocket, QHostAddress, QNetworkInterface
from PySide6.QtWebSockets import QWebSocketServer

from flow.services.markdown import (
    PatchStore,
    apply_patches,
    effective_background,
    parse,
    resolve_attrs,
)
from flow.services.markdown.parser import SongSpec
from flow.services.markdown.renderer import _app_assets_dir

logger = logging.getLogger(__name__)

_INDEX_HTML_PATH = (
    Path(__file__).resolve().parents[1] / "resources" / "web" / "index.html"
)
_FALLBACK_INDEX_HTML = b"<html><body>Flow web broadcast</body></html>"
_WS_PORT_PLACEHOLDER = "{{WS_PORT}}"
_HTTP_PORT_DEFAULT = 8777
_WS_PORT_DEFAULT = 8778

CLEAR_PAYLOAD: dict[str, Any] = {"type": "clear"}

_APP_ASSET_PREFIX = "@app/"


def detect_local_ips() -> list[str]:
    """Return non-loopback IPv4 addresses of this machine."""
    ips: list[str] = []
    for addr in QNetworkInterface.allAddresses():
        if (
            addr.protocol() == QAbstractSocket.NetworkLayerProtocol.IPv4Protocol
            and not addr.isLoopback()
        ):
            ips.append(addr.toString())
    return ips


def build_markdown_payload(
    spec: SongSpec, local_index: int, song_dir: Path, last_bg: str | None
) -> tuple[dict, str | None]:
    """Build the WS payload for a markdown song slide.

    ``spec`` must already be parsed (and patched, if applicable) by the
    caller — this function stays pure and does no file I/O.

    Returns (payload, bg_key) where bg_key is the comparison key used for
    the next call's ``last_bg``: a hex color string as-is, or the resolved
    absolute path of the background file (falling back to the raw
    identifier string when the file can't be resolved). Resolving to an
    absolute path avoids collisions between different songs that happen to
    use the same relative background filename (e.g. "bg.jpg").
    """
    slide = spec.slides[local_index]  # IndexError propagates to caller
    attrs = resolve_attrs(spec, slide)
    bg = effective_background(spec, slide, attrs)

    payload: dict[str, Any] = {
        "type": "markdown",
        "main_text": slide.main,
        "sub_text": attrs.sub_text,
    }
    if bg.startswith("#"):
        bg_key: str | None = bg
        payload["background_color"] = bg
    else:
        resolved = resolve_background_file(bg, song_dir)
        bg_key = str(resolved) if resolved is not None else bg
    return payload, bg_key


def resolve_background_file(bg: str, song_dir: Path) -> Path | None:
    """Resolve a background identifier string to an actual file path.

    A hex color has no backing file and resolves to None.
    """
    if bg.startswith("#"):
        return None
    if bg.startswith(_APP_ASSET_PREFIX):
        path = _app_assets_dir() / bg[len(_APP_ASSET_PREFIX):]
    else:
        candidate = Path(bg)
        path = candidate if candidate.is_absolute() else (song_dir / bg)
    return path if path.exists() else None


# 슬라이드 이미지를 웹으로 보낼 때 쓰는 형식.
# PNG는 1920x1080 한 장에 ~600ms가 걸린다. 이 인코딩은 슬라이드 송출
# 슬롯 안에서 GUI 스레드를 잡고 도는데, 그동안 Qt가 이벤트 루프로
# 돌아가지 못해 송출 화면 페인트까지 같이 밀린다 — PPT 기반 곡에서
# 전환이 1초쯤 늦게 보이던 원인이 이것이다 (마크다운 곡은 텍스트
# 페이로드로 나가서 이 경로를 타지 않는다).
# q92 JPEG면 같은 그림이 ~48ms에 인코딩되고 크기는 1/5다.
_IMAGE_FORMAT = "JPEG"
_IMAGE_QUALITY = 92
_IMAGE_MIME = "image/jpeg"


def encode_image_payload(image) -> dict:
    """Encode a QImage as a base64 JPEG data URL payload."""
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, _IMAGE_FORMAT, _IMAGE_QUALITY)
    data = bytes(buffer.data())
    buffer.close()
    encoded = base64.b64encode(data).decode("ascii")
    return {"type": "image", "data_url": f"data:{_IMAGE_MIME};base64,{encoded}"}


def _bg_content_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in (".jpg", ".jpeg"):
        return "image/jpeg"
    return "image/png"


class _WebBroadcastRequestHandler(BaseHTTPRequestHandler):
    """Minimal request handler; server instance is set as `server.owner`."""

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        pass

    def do_GET(self) -> None:  # noqa: N802
        owner: WebBroadcastServer = self.server.owner  # type: ignore[attr-defined]
        path = self.path.split("?", 1)[0]
        if path == "/":
            body = owner._index_html_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/bg":
            current_bg = owner._current_bg
            if current_bg is None:
                self.send_response(404)
                self.end_headers()
                return
            data, content_type = current_bg
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if path in ("/generate_204", "/gen_204"):
            self.send_response(204)
            self.end_headers()
            return
        if path in (
            "/hotspot-detect.html",
            "/library/test/success.html",
            "/success.txt",
            "/ncsi.txt",
        ):
            body = (
                b"<HTML><HEAD><TITLE>Success</TITLE></HEAD>"
                b"<BODY>Success</BODY></HTML>"
            )
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self.end_headers()


class WebBroadcastServer(QObject):
    """Serves the viewer page over HTTP and pushes slide updates over WS."""

    client_count_changed = Signal(int)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._http_server: ThreadingHTTPServer | None = None
        self._http_thread: threading.Thread | None = None
        self._http_port: int | None = None
        self._ws_server: QWebSocketServer | None = None
        self._ws_port: int | None = None
        self._clients: list[Any] = []
        self._last_payload_json: str | None = None
        self._last_bg_key: str | None = None
        self._current_bg: tuple[bytes, str] | None = None
        self._bg_version: int = 0

    # -- lifecycle ---------------------------------------------------

    def start(self) -> str | None:
        if self.is_running():
            urls = self.local_urls()
            if urls:
                return urls[0]
            if self._http_port is not None:
                return f"http://127.0.0.1:{self._http_port}"
            return None

        # WS must be listening before the first page is served, otherwise
        # the served index.html could embed a not-yet-real {{WS_PORT}}.
        self._start_ws()
        self._start_http()

        urls = self.local_urls()
        if urls:
            return urls[0]
        if self._http_port is not None:
            return f"http://127.0.0.1:{self._http_port}"
        return None

    def _start_http(self) -> None:
        try:
            server = ThreadingHTTPServer(
                ("0.0.0.0", _HTTP_PORT_DEFAULT), _WebBroadcastRequestHandler
            )
        except OSError:
            server = ThreadingHTTPServer(("0.0.0.0", 0), _WebBroadcastRequestHandler)
        server.owner = self  # type: ignore[attr-defined]
        self._http_server = server
        self._http_port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self._http_thread = thread

    def _start_ws(self) -> None:
        # A fixed default port lets firewalld/nft rules (e.g. Flow's hotspot
        # captive-portal setup) allow it in advance — an OS-assigned random
        # port would be unreachable behind a restrictive firewall zone that
        # only opens known ports.
        server = QWebSocketServer(
            "flow-web", QWebSocketServer.SslMode.NonSecureMode, parent=self
        )
        server.newConnection.connect(self._on_new_connection)
        if not server.listen(QHostAddress.SpecialAddress.Any, _WS_PORT_DEFAULT):
            server.listen(QHostAddress.SpecialAddress.Any, 0)
        self._ws_server = server
        self._ws_port = server.serverPort()

    def stop(self) -> None:
        if self._http_server is not None:
            self._http_server.shutdown()
            self._http_server.server_close()
            if self._http_thread is not None:
                self._http_thread.join(timeout=2)
        self._http_server = None
        self._http_thread = None
        self._http_port = None

        for client in list(self._clients):
            client.close()
        self._clients = []

        if self._ws_server is not None:
            self._ws_server.close()
            self._ws_server.deleteLater()
        self._ws_server = None
        self._ws_port = None

        self._last_payload_json = None
        self._last_bg_key = None
        self._current_bg = None
        self._bg_version = 0

    def is_running(self) -> bool:
        return self._http_server is not None and self._ws_server is not None

    def http_port(self) -> int | None:
        """The HTTP port actually bound to, or ``None`` if not running."""
        return self._http_port if self.is_running() else None

    def ws_port(self) -> int | None:
        """The WebSocket port actually bound to, or ``None`` if not running."""
        return self._ws_port if self.is_running() else None

    def local_urls(self) -> list[str]:
        if self._http_port is None:
            return []
        return [f"http://{ip}:{self._http_port}" for ip in detect_local_ips()]

    def client_count(self) -> int:
        return len(self._clients)

    # -- websocket -----------------------------------------------------

    def _on_new_connection(self) -> None:
        if self._ws_server is None:
            return
        socket = self._ws_server.nextPendingConnection()
        if socket is None:
            return
        self._clients.append(socket)
        socket.disconnected.connect(lambda s=socket: self._on_client_disconnected(s))
        self.client_count_changed.emit(len(self._clients))
        if self._last_payload_json is not None:
            socket.sendTextMessage(self._last_payload_json)

    def _on_client_disconnected(self, socket: Any) -> None:
        if socket in self._clients:
            self._clients.remove(socket)
        self.client_count_changed.emit(len(self._clients))

    # -- http helpers ----------------------------------------------------

    def _index_html_bytes(self) -> bytes:
        try:
            body = _INDEX_HTML_PATH.read_bytes()
        except OSError:
            body = _FALLBACK_INDEX_HTML
        ws_port = self._ws_port if self._ws_port is not None else 0
        return body.replace(
            _WS_PORT_PLACEHOLDER.encode("utf-8"), str(ws_port).encode("utf-8")
        )

    # -- push --------------------------------------------------------

    def push_current_slide(self, song: Any, local_index: int, image: Any) -> None:
        try:
            self._push_current_slide(song, local_index, image)
        except Exception:
            logger.debug("push_current_slide failed", exc_info=True)

    def _push_current_slide(self, song: Any, local_index: int, image: Any) -> None:
        if song is not None and getattr(song, "slide_source", None) == "markdown":
            try:
                payload = self._build_markdown_slide_payload(song, local_index)
            except Exception:
                logger.debug(
                    "markdown payload build failed, falling back to image",
                    exc_info=True,
                )
                if image is None:
                    raise
                payload = encode_image_payload(image)
        elif image is not None:
            payload = encode_image_payload(image)
        elif image is None and song is None:
            payload = dict(CLEAR_PAYLOAD)
        else:
            return

        self._last_payload_json = json.dumps(payload)
        for client in self._clients:
            client.sendTextMessage(self._last_payload_json)

    def _build_markdown_slide_payload(self, song: Any, local_index: int) -> dict:
        """Parse the song's markdown, apply any emergency-edit patches (same
        pipeline the desktop editor uses), and build the WS payload.

        Applying patches here keeps EDIT patches from showing stale text on
        the web viewer, and lets ``build_markdown_payload``'s IndexError (on
        a stale index vs. a freshly-APPENDed slide) propagate to the caller,
        which falls back to the projector image instead of freezing.
        """
        md_text = song.markdown_path.read_text(encoding="utf-8")
        spec = parse(md_text)
        store = PatchStore(song.markdown_path.parent / ".patches.json")
        if store.patches:
            spec = apply_patches(spec, store.patches)

        payload, bg_key = build_markdown_payload(
            spec, local_index, song.abs_folder, self._last_bg_key
        )
        if "background_color" not in payload:
            if bg_key != self._last_bg_key:
                bg_path = Path(bg_key) if bg_key is not None else None
                if bg_path is not None and bg_path.exists():
                    self._current_bg = (
                        bg_path.read_bytes(),
                        _bg_content_type(bg_path),
                    )
                    self._bg_version += 1
            if self._current_bg is not None:
                payload["background_url"] = f"/bg?v={self._bg_version}"
        self._last_bg_key = bg_key
        return payload
