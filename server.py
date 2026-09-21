"""Local tester UI for the TypeSafe Jev API.

Serves index.html and proxies /api/* to api.typesafe.ai, adding the API key
on the server side so it never reaches the browser. Python stdlib only.

    python3 server.py            # http://127.0.0.1:8765
"""
import argparse
import os
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

KEY_NAMES = ["TYPESAFE_API_KEY", "TPYEAFE_JEV_API_KEY_FROM_YI_20260921"]
ENV_FILE = Path.home() / ".env"
API_BASE = "https://api.typesafe.ai"
PAGE = Path(__file__).with_name("index.html")
ROUTES = {"/api/models": "/v1/models", "/api/systemone": "/v1/systemone"}


def load_key(names, env_file, environ=os.environ):
    """Return the first key found: process env first, then the .env file."""
    for name in names:
        if environ.get(name):
            return environ[name]
    try:
        lines = Path(env_file).read_text().splitlines()
    except OSError:
        return None
    found = {}
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.removeprefix("export ").split("=", 1)
        found[k.strip()] = v.strip().strip("'\"")
    return next((found[n] for n in names if found.get(n)), None)


def make_handler(key, api_base):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, status, body, ctype):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _proxy(self, method, body=None):
            req = urllib.request.Request(
                api_base + ROUTES[self.path], data=body, method=method,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            )
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    self._send(r.status, r.read(), "application/json")
            except urllib.error.HTTPError as e:
                self._send(e.code, e.read(), "application/json")
            except urllib.error.URLError as e:
                self._send(502, f'{{"detail": "upstream unreachable: {e.reason}"}}'.encode(), "application/json")

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                self._send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
            elif self.path == "/api/models":
                self._proxy("GET")
            else:
                self._send(404, b"not found", "text/plain")

        def do_POST(self):
            if self.path != "/api/systemone":
                return self._send(404, b"not found", "text/plain")
            body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            self._proxy("POST", body)

        def log_message(self, fmt, *args):
            print(f"{self.address_string()} {fmt % args}")

    return Handler


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--host", default="127.0.0.1")
    args = p.parse_args()
    key = load_key(KEY_NAMES, ENV_FILE)
    if not key:
        raise SystemExit(f"No API key. Set one of {KEY_NAMES} in the environment or {ENV_FILE}.")
    httpd = ThreadingHTTPServer((args.host, args.port), make_handler(key, API_BASE))
    print(f"Jev tester on http://{args.host}:{args.port}")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
