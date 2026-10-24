"""Fake FCM (BUILDPLAN A1, 1.3.7): accepts FCM HTTP v1 sends and records them. Stdlib only.

FCM v1:
    POST /v1/projects/{project}/messages:send   {"message": {...}, "validate_only": false}
        → 200 {"name": "projects/{project}/messages/{id}"}
        → 400 INVALID_ARGUMENT for malformed messages, or an injected error for the token
Test control:
    GET    /fake/messages                      → {"messages": [{"id", "project", "validate_only", "message"}]}
    DELETE /fake/messages                      → clears messages and injected errors
    POST   /fake/tokens/{token}/error          {"errorCode": "UNREGISTERED"} → later sends to it fail
    GET    /fake/health                        → {"ok": true}

    python dev/fake-fcm/server.py [--host 127.0.0.1] [--port 9101]
"""

from __future__ import annotations

import argparse
import itertools
import json
import re
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote

SEND_PATH = re.compile(r"^/v1/projects/([^/]+)/messages:send$")
TOKEN_ERROR_PATH = re.compile(r"^/fake/tokens/([^/]+)/error$")

# FCM v1 error codes → HTTP status and google.rpc status (https://firebase.google.com/docs/reference/fcm/rest/v1/ErrorCode)
ERRORS = {
    "UNREGISTERED": (404, "NOT_FOUND", "Requested entity was not found."),
    "INVALID_ARGUMENT": (400, "INVALID_ARGUMENT", "Request contains an invalid argument."),
    "SENDER_ID_MISMATCH": (403, "PERMISSION_DENIED", "SenderId mismatch"),
    "QUOTA_EXCEEDED": (429, "RESOURCE_EXHAUSTED", "Quota exceeded."),
    "UNAVAILABLE": (503, "UNAVAILABLE", "The service is currently unavailable."),
    "INTERNAL": (500, "INTERNAL", "Internal error encountered."),
}


class State:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.messages: list[dict] = []
        self.token_errors: dict[str, str] = {}
        self.ids = itertools.count(1)

    def reset(self) -> None:
        with self.lock:
            self.messages.clear()
            self.token_errors.clear()


def error_body(code: str, message: str | None = None) -> tuple[int, dict]:
    status, rpc_status, default = ERRORS[code]
    body = {
        "error": {
            "code": status,
            "message": message or default,
            "status": rpc_status,
            "details": [{"@type": "type.googleapis.com/google.firebase.fcm.v1.FcmError", "errorCode": code}],
        }
    }
    return status, body


def validate(message: object) -> str | None:
    if not isinstance(message, dict):
        return "message must be an object"
    targets = [key for key in ("token", "topic", "condition") if key in message]
    if len(targets) != 1:
        return "message needs exactly one of token, topic, condition"
    data = message.get("data", {})
    if not isinstance(data, dict) or not all(isinstance(v, str) for v in data.values()):
        return "data values must be strings"
    android = message.get("android", {})
    if not isinstance(android, dict) or android.get("priority", "NORMAL").upper() not in ("NORMAL", "HIGH"):
        return "android.priority must be NORMAL or HIGH"
    return None


def make_handler(state: State) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args) -> None:
            sys.stderr.write(f"fake-fcm: {fmt % args}\n")

        def _json(self, status: int, body: dict) -> None:
            payload = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _body(self) -> object:
            length = int(self.headers.get("Content-Length") or 0)
            try:
                return json.loads(self.rfile.read(length) or b"{}")
            except json.JSONDecodeError:
                return None

        def do_GET(self) -> None:
            if self.path == "/fake/health":
                return self._json(200, {"ok": True})
            if self.path == "/fake/messages":
                with state.lock:
                    return self._json(200, {"messages": list(state.messages)})
            return self._json(404, {"error": {"code": 404, "status": "NOT_FOUND", "message": self.path}})

        def do_DELETE(self) -> None:
            if self.path == "/fake/messages":
                state.reset()
                return self._json(200, {})
            return self._json(404, {"error": {"code": 404, "status": "NOT_FOUND", "message": self.path}})

        def do_POST(self) -> None:
            body = self._body()
            if match := TOKEN_ERROR_PATH.match(self.path):
                code = body.get("errorCode") if isinstance(body, dict) else None
                if code not in ERRORS:
                    return self._json(400, {"error": f"errorCode must be one of {sorted(ERRORS)}"})
                with state.lock:
                    state.token_errors[unquote(match.group(1))] = code
                return self._json(200, {})
            if match := SEND_PATH.match(self.path):
                project = match.group(1)
                if not isinstance(body, dict):
                    return self._json(*error_body("INVALID_ARGUMENT", "body must be JSON"))
                message = body.get("message")
                problem = validate(message)
                if problem:
                    return self._json(*error_body("INVALID_ARGUMENT", problem))
                with state.lock:
                    injected = state.token_errors.get(message.get("token", ""))
                    if injected:
                        return self._json(*error_body(injected))
                    message_id = next(state.ids)
                    state.messages.append(
                        {
                            "id": message_id,
                            "project": project,
                            "validate_only": bool(body.get("validate_only")),
                            "message": message,
                        }
                    )
                return self._json(200, {"name": f"projects/{project}/messages/{message_id}"})
            return self._json(404, {"error": {"code": 404, "status": "NOT_FOUND", "message": self.path}})

    return Handler


def make_server(host: str, port: int) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), make_handler(State()))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="fake FCM HTTP v1 server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9101)
    args = parser.parse_args(argv)
    server = make_server(args.host, args.port)
    print(f"fake-fcm: listening on http://{args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
