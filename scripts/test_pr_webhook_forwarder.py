import copy
import hashlib
import hmac
import http.client
import json
import threading
import unittest
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer

from pr_webhook_forwarder import MAX_BODY, PATH, make_server

BRANCH = "codeguardian-auto-review-test-fixture"
SHA = "a" * 40
PAYLOAD = {
    "action": "opened",
    "repository": {"id": 1318546304, "full_name": "DhyanMehta/flask-task-api"},
    "installation": {"id": 161715271},
    "pull_request": {
        "draft": False,
        "base": {"ref": "main"},
        "head": {"ref": BRANCH, "sha": SHA, "repo": {"id": 1318546304}},
    },
}


@contextmanager
def serving(server):
    with server:
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
        thread.start()
        try:
            yield server
        finally:
            server.shutdown()
            thread.join()


class DummyUpstream(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_POST(self):
        raw = self.rfile.read(int(self.headers["Content-Length"]))
        self.server.received.append((self.path, raw, dict(self.headers)))
        digest = hmac.new(b"test-only", raw, hashlib.sha256).hexdigest()
        valid = hmac.compare_digest(self.headers["X-Hub-Signature-256"], f"sha256={digest}")
        self.send_response(202 if valid else 401)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status":"accepted"}' if valid else b'{"detail":"invalid signature"}')


class ForwarderTests(unittest.TestCase):
    def request(self, server, *, raw=b"", path=PATH, method="POST", changes=None):
        digest = hmac.new(b"test-only", raw, hashlib.sha256).hexdigest()
        headers = {
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": f"sha256={digest}",
            "X-GitHub-Delivery": "12345678-1234-1234-1234-123456789abc",
        }
        headers.update(changes or {})
        conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
        try:
            conn.request(method, path, body=raw, headers=headers)
            response = conn.getresponse()
            return response.status, response.read(), headers
        finally:
            conn.close()

    def test_preserves_signed_bytes_and_headers_and_upstream_response(self):
        raw = ("  " + json.dumps(PAYLOAD, indent=2) + "\r\n").encode()
        with serving(HTTPServer(("127.0.0.1", 0), DummyUpstream)) as upstream:
            upstream.received = []
            with serving(make_server(BRANCH, SHA, port=0, upstream_port=upstream.server_port)) as relay:
                status, body, headers = self.request(relay, raw=raw)
                self.assertEqual((status, body), (202, b'{"status":"accepted"}'))
                path, received, forwarded = upstream.received[0]
                self.assertEqual((path, received), (PATH, raw))
                for name, value in headers.items():
                    self.assertEqual(forwarded[name], value)
                status, body, _ = self.request(relay, raw=raw, changes={"X-Hub-Signature-256": "sha256=" + "0" * 64})
                self.assertEqual((status, body), (401, b'{"detail":"invalid signature"}'))

    def test_rejects_unrelated_and_malformed_requests_without_upstream_contact(self):
        with serving(HTTPServer(("127.0.0.1", 0), DummyUpstream)) as upstream:
            upstream.received = []
            with serving(make_server(BRANCH, SHA, port=0, upstream_port=upstream.server_port)) as relay:
                for keys, value in [
                    (("action",), "synchronize"),
                    (("repository", "id"), 42),
                    (("repository", "full_name"), "other/repo"),
                    (("installation", "id"), 42),
                    (("pull_request", "draft"), True),
                    (("pull_request", "base", "ref"), "dev"),
                    (("pull_request", "head", "repo", "id"), 42),
                    (("pull_request", "head", "ref"), "other"),
                    (("pull_request", "head", "sha"), "b" * 40),
                ]:
                    with self.subTest(keys=keys):
                        payload = copy.deepcopy(PAYLOAD)
                        target = payload
                        for key in keys[:-1]:
                            target = target[key]
                        target[keys[-1]] = value
                        self.assertEqual(self.request(relay, raw=json.dumps(payload).encode())[0], 403)
                self.assertEqual(self.request(relay, path="/health/live")[0], 404)
                self.assertEqual(self.request(relay, method="GET")[0], 501)
                self.assertEqual(self.request(relay, raw=b"{")[0], 400)
                self.assertEqual(self.request(relay, changes={"X-GitHub-Event": "push"})[0], 403)
                self.assertEqual(self.request(relay, changes={"X-Hub-Signature-256": ""})[0], 403)
                self.assertEqual(self.request(relay, changes={"Content-Length": str(MAX_BODY + 1)})[0], 413)
                self.assertEqual(upstream.received, [])
