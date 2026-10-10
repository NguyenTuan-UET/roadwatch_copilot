"""Serve the web demo and forward /api and /health to the RoadWatch server, so the page talks to it same-origin.

    python -m src.roadwatch.web                          # backend, http://127.0.0.1:8765
    python presentation/web-demo/serve.py                # then open http://127.0.0.1:8000/?live

RW_API (default http://127.0.0.1:8765) points at the backend; PORT (default 8000) is where the demo listens.
Bodies stream both ways, so video uploads, SSE (/api/events), MJPEG (/api/stream) and byte ranges pass through.
"""
import http.client
import os
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

API = urlsplit(os.environ.get('RW_API', 'http://127.0.0.1:8765'))
PORT = int(os.environ.get('PORT', 8000))
FORWARD = ('/api/', '/health')
REQUEST_HEADERS = ('authorization', 'content-type', 'content-length', 'range', 'accept', 'cache-control')
HOP = {'connection', 'keep-alive', 'transfer-encoding', 'te', 'trailer', 'upgrade', 'proxy-authenticate'}


class Handler(SimpleHTTPRequestHandler):
    def _forward(self):
        conn = http.client.HTTPConnection(API.hostname, API.port or 80, timeout=None)
        headers = {k: v for k, v in self.headers.items() if k.lower() in REQUEST_HEADERS}
        length = int(self.headers.get('content-length') or 0)
        try:
            conn.putrequest(self.command, self.path, skip_accept_encoding=True)
            for k, v in headers.items():
                conn.putheader(k, v)
            conn.endheaders()
            while length:
                chunk = self.rfile.read(min(length, 1 << 20))
                if not chunk:
                    break
                conn.send(chunk)
                length -= len(chunk)
            r = conn.getresponse()
        except OSError as e:
            self.send_error(502, f'backend {API.geturl()} unreachable: {e}')
            return
        self.send_response(r.status, r.reason)
        for k, v in r.getheaders():
            if k.lower() not in HOP:
                self.send_header(k, v)
        self.end_headers()
        try:
            while chunk := r.read1(1 << 16):
                self.wfile.write(chunk)
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass   # the browser closed an SSE or MJPEG stream
        finally:
            conn.close()

    def _route(self, static):
        if self.path.startswith(FORWARD):
            self._forward()
        elif static:
            static()
        else:
            self.send_error(405)

    def do_GET(self):
        self._route(super().do_GET)

    def do_HEAD(self):
        self._route(super().do_HEAD)

    def do_POST(self):
        self._route(None)

    def do_DELETE(self):
        self._route(None)


if __name__ == '__main__':
    server = ThreadingHTTPServer(('127.0.0.1', PORT), partial(Handler, directory=str(Path(__file__).parent)))
    print(f'http://127.0.0.1:{PORT}/?live  ->  {API.geturl()}')
    server.serve_forever()
