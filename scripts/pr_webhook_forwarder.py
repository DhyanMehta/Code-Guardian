"""Loopback-only relay for one approved automatic-review test PR."""

import argparse
import http.client
import json
import logging
import re
from http.server import BaseHTTPRequestHandler, HTTPServer
from time import monotonic

PATH = "/webhooks/github"
REPOSITORY = "DhyanMehta/flask-task-api"
MAX_BODY = 1024 * 1024
MAX_RESPONSE = 64 * 1024
TIMEOUT = 5


class WebhookHandler(BaseHTTPRequestHandler):
    def setup(self):
        self.request.settimeout(TIMEOUT)
        super().setup()

    def log_message(self, *_args):
        # Never emit caller-controlled request lines, headers or bodies.
        pass

    def reply(self, status, body, content_type="application/json"):
        logging.info("webhook relay HTTP %d", status)
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def reject(self, status, reason):
        self.reply(status, json.dumps({"reason": reason}).encode())

    def request_body(self, length):
        deadline = monotonic() + TIMEOUT
        body = bytearray()
        while len(body) < length:
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise TimeoutError
            self.connection.settimeout(remaining)
            part = self.rfile.read1(length - len(body))
            if not part:
                raise ValueError("incomplete body")
            body.extend(part)
        return bytes(body)

    def do_POST(self):
        if self.path != PATH:
            return self.reject(404, "unexpected path")
        lengths = self.headers.get_all("Content-Length", [])
        if self.headers.get_all("Transfer-Encoding") or len(lengths) != 1 or not re.fullmatch(r"[0-9]{1,9}", lengths[0]):
            return self.reject(400, "one valid Content-Length is required")
        length = int(lengths[0])
        if length > MAX_BODY:
            return self.reject(413, "request body too large")
        forwarded = {}
        for name, pattern in (
            ("X-GitHub-Event", "pull_request"),
            ("X-Hub-Signature-256", r"sha256=[0-9a-f]{64}"),
            ("X-GitHub-Delivery", r"[0-9a-fA-F-]{36}"),
        ):
            values = self.headers.get_all(name, [])
            if len(values) != 1 or not re.fullmatch(pattern, values[0]):
                return self.reject(403, "unsupported or missing webhook headers")
            forwarded[name] = values[0]
        try:
            raw = self.request_body(length)
            payload = json.loads(raw)
        except TimeoutError:
            return self.reject(408, "request body timed out")
        except (ValueError, RecursionError):
            return self.reject(400, "invalid request body")
        if not self.in_scope(payload):
            return self.reject(403, "webhook is outside the approved PR scope")
        forwarded["Content-Type"] = "application/json"
        conn = http.client.HTTPConnection("127.0.0.1", self.server.upstream_port, timeout=TIMEOUT)
        try:
            conn.request("POST", PATH, body=raw, headers=forwarded)
            response = conn.getresponse()
            body = response.read(MAX_RESPONSE + 1)
            status = response.status
            content_type = response.getheader("Content-Type", "").split(";", 1)[0]
            if len(body) > MAX_RESPONSE:
                return self.reject(502, "upstream response too large")
        except TimeoutError:
            return self.reject(504, "upstream timed out")
        except (OSError, http.client.HTTPException):
            return self.reject(502, "upstream unavailable")
        finally:
            conn.close()
        self.reply(status, body, "application/json" if content_type == "application/json" else "text/plain")

    def in_scope(self, payload):
        try:
            repo = payload["repository"]
            pull = payload["pull_request"]
            head = pull["head"]
            return (
                payload["action"] == "opened"
                and repo["id"] == 1318546304
                and repo["full_name"] == REPOSITORY
                and payload["installation"]["id"] == 161715271
                and pull["draft"] is False
                and pull["base"]["ref"] == "main"
                and head["repo"]["id"] == repo["id"]
                and head["ref"] == self.server.branch
                and head["sha"] == self.server.sha
            )
        except (KeyError, TypeError):
            return False


def make_server(branch, sha, *, port=8081, upstream_port=8080):
    server = HTTPServer(("127.0.0.1", port), WebhookHandler)
    server.branch = branch
    server.sha = sha
    server.upstream_port = upstream_port
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--sha", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"codeguardian-auto-review-test-[A-Za-z0-9-]+", args.branch):
        parser.error("expected the approved smoke-test branch format")
    if not re.fullmatch(r"[0-9a-f]{40}", args.sha):
        parser.error("expected the full lowercase head SHA")
    logging.basicConfig(level=logging.INFO)
    with make_server(args.branch, args.sha) as server:
        server.serve_forever()


if __name__ == "__main__":
    main()
