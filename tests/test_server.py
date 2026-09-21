"""Tests for the local proxy.

The proxy exists for one reason: the API key must stay on the server side.
The browser never sees it, and every upstream call must carry it.
"""
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import server  # noqa: E402

SECRET = "apikey_test_secret_123"


class LoadKeyTest(unittest.TestCase):
    def _env_file(self, text):
        f = tempfile.NamedTemporaryFile("w", suffix=".env", delete=False)
        f.write(text)
        f.close()
        self.addCleanup(os.unlink, f.name)
        return f.name

    def test_reads_named_var_with_export_and_quotes(self):
        path = self._env_file(f'OTHER=1\nexport MY_KEY="{SECRET}"\n')
        self.assertEqual(server.load_key(["MY_KEY"], path, environ={}), SECRET)

    def test_process_env_wins_over_file(self):
        path = self._env_file("MY_KEY=from_file\n")
        self.assertEqual(server.load_key(["MY_KEY"], path, environ={"MY_KEY": "from_env"}), "from_env")

    def test_first_matching_name_is_used(self):
        path = self._env_file("B=bee\nA=ay\n")
        self.assertEqual(server.load_key(["A", "B"], path, environ={}), "ay")

    def test_missing_key_returns_none(self):
        path = self._env_file("NOPE=1\n")
        self.assertIsNone(server.load_key(["MY_KEY"], path, environ={}))


class FakeUpstream(BaseHTTPRequestHandler):
    seen = []

    def _reply(self, status, body):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        FakeUpstream.seen.append(("GET", self.path, self.headers.get("Authorization"), None))
        self._reply(200, {"models": [{"name": "jev-latest"}]})

    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"])).decode()
        FakeUpstream.seen.append(("POST", self.path, self.headers.get("Authorization"), body))
        if json.loads(body).get("state") == "bad":
            self._reply(422, {"detail": "invalid"})
        else:
            self._reply(200, {"answers": {"x": {"type": "noul", "noul": 0.9}}})

    def log_message(self, *a):
        pass


def _serve(handler):
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


class ProxyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.upstream = _serve(FakeUpstream)
        handler = server.make_handler(SECRET, f"http://127.0.0.1:{cls.upstream.server_port}")
        cls.app = _serve(handler)
        cls.base = f"http://127.0.0.1:{cls.app.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.app.shutdown()
        cls.upstream.shutdown()

    def setUp(self):
        FakeUpstream.seen.clear()

    def _get(self, path):
        with urllib.request.urlopen(self.base + path) as r:
            return r.status, r.read().decode()

    def _post(self, path, payload):
        req = urllib.request.Request(
            self.base + path, data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_systemone_forwards_body_with_bearer_key(self):
        payload = {"state": "hi", "model": "jev-latest", "questions": {}}
        status, body = self._post("/api/systemone", payload)
        self.assertEqual(status, 200)
        self.assertEqual(body["answers"]["x"]["noul"], 0.9)
        method, path, auth, sent = FakeUpstream.seen[0]
        self.assertEqual((method, path, auth), ("POST", "/v1/systemone", f"Bearer {SECRET}"))
        self.assertEqual(json.loads(sent), payload)

    def test_models_forwards_with_bearer_key(self):
        status, text = self._get("/api/models")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(text)["models"][0]["name"], "jev-latest")
        self.assertEqual(FakeUpstream.seen[0][:3], ("GET", "/v1/models", f"Bearer {SECRET}"))

    def test_upstream_error_status_and_body_pass_through(self):
        # The UI shows API validation errors, so they must not be swallowed.
        status, body = self._post("/api/systemone", {"state": "bad"})
        self.assertEqual(status, 422)
        self.assertEqual(body, {"detail": "invalid"})

    def test_page_is_served_and_never_contains_key(self):
        status, html = self._get("/")
        self.assertEqual(status, 200)
        self.assertIn("<html", html)
        self.assertNotIn(SECRET, html)


if __name__ == "__main__":
    unittest.main()
