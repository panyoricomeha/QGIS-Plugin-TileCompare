"""Minimal HTTP server that serves local tile folders on 127.0.0.1.

QGIS reads file:// tiles one by one, which is slow on network shares. Over HTTP they load in
parallel and the QGIS disk cache applies. White-to-transparent conversion is also done here.
"""
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote

import numpy as np
from qgis.PyQt.QtCore import QBuffer, QIODevice
from qgis.PyQt.QtGui import QColor, QImage

from .tiles import WHITE_THRESHOLD, zoom_path

DEFAULT_PORT = 18765  # a fixed port keeps the QGIS cache valid across sessions
CACHE_SECONDS = 30 * 24 * 3600
CONTENT_TYPES = {'png': 'image/png', 'jpg': 'image/jpeg', 'jpeg': 'image/jpeg',
                 'webp': 'image/webp', 'gif': 'image/gif', 'tif': 'image/tiff', 'tiff': 'image/tiff'}


def _encode_png(img):
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, 'PNG')
    return bytes(buf.data())


def _empty_png():
    img = QImage(256, 256, QImage.Format.Format_ARGB32)
    img.fill(QColor(0, 0, 0, 0))
    return _encode_png(img)


def white_to_png(data):
    """PNG with near-white pixels made transparent, or None if there is no white."""
    img = QImage.fromData(data)
    if img.isNull():
        return None
    img = img.convertToFormat(QImage.Format.Format_ARGB32)
    w, h, bpl = img.width(), img.height(), img.bytesPerLine()
    ptr = img.constBits()
    ptr.setsize(bpl * h)
    px = np.frombuffer(ptr, np.uint8).reshape(h, bpl)[:, :w * 4].reshape(h, w, 4).copy()  # B,G,R,A
    t = WHITE_THRESHOLD
    mask = (px[..., 0] >= t) & (px[..., 1] >= t) & (px[..., 2] >= t)
    if not mask.any():
        return None
    px[mask] = 0
    out = QImage(px.tobytes(), w, h, w * 4, QImage.Format.Format_ARGB32)
    return _encode_png(out)


class TileServer:
    def __init__(self, port=DEFAULT_PORT):
        self.preferred_port = port
        self.sources = {}
        self.httpd = None
        self.thread = None
        self.empty_png = None

    @property
    def running(self):
        return self.httpd is not None

    @property
    def base_url(self):
        return f'http://127.0.0.1:{self.httpd.server_address[1]}' if self.httpd else None

    def start(self):
        if self.httpd:
            return
        self.empty_png = _empty_png()
        handler = self._handler_class()
        for port in (self.preferred_port, 0):
            try:
                self.httpd = ThreadingHTTPServer(('127.0.0.1', port), handler)
                break
            except OSError:
                continue
        if self.httpd is None:
            return
        self.httpd.daemon_threads = True
        self.thread = threading.Thread(target=self.httpd.serve_forever, name='TileCompareServer', daemon=True)
        self.thread.start()

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None

    def set_sources(self, sources):
        self.sources = {s['uid']: dict(s) for s in sources}

    def _handler_class(self):
        server = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'

            def do_GET(self):
                # /<uid>/<o|w>/<z>/<x>/<y>.<ext>
                parts = unquote(self.path.split('?')[0]).strip('/').split('/')
                src = server.sources.get(parts[0]) if len(parts) == 5 else None
                if src is None:
                    return self._send(404, b'', 'text/plain', cache=False)
                _, mode, z, x, name = parts
                y = name.split('.')[0]
                if not (z.isdigit() and x.isdigit() and y.isdigit()):
                    return self._send(404, b'', 'text/plain', cache=False)
                try:
                    with open(os.path.join(zoom_path(src, int(z)), x, f"{y}.{src['ext']}"), 'rb') as f:
                        data = f.read()
                except OSError:
                    # missing tiles get a transparent tile; a 404 would be re-requested every time
                    return self._send(200, server.empty_png, 'image/png')
                ctype = CONTENT_TYPES.get(src['ext'], 'application/octet-stream')
                if mode == 'w':
                    png = white_to_png(data)
                    if png is not None:
                        data, ctype = png, 'image/png'
                self._send(200, data, ctype)

            def _send(self, code, data, ctype, cache=True):
                try:
                    self.send_response(code)
                    self.send_header('Content-Type', ctype)
                    self.send_header('Content-Length', str(len(data)))
                    if cache:
                        self.send_header('Cache-Control', f'public, max-age={CACHE_SECONDS}')
                    self.end_headers()
                    self.wfile.write(data)
                except (ConnectionError, OSError):
                    pass

            def log_message(self, *args):
                pass

        return Handler
