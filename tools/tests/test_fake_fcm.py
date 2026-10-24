import importlib.util
import json
import threading
import urllib.error
import urllib.request

import pytest
from conftest import REPO

spec = importlib.util.spec_from_file_location("fake_fcm", REPO / "dev/fake-fcm/server.py")
fake_fcm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fake_fcm)


@pytest.fixture
def base_url():
    server = fake_fcm.make_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def call(method: str, url: str, body: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b"{}")


WAKE_UP = {
    "message": {
        "token": "device-token-1",
        "data": {"t": "sync"},
        "android": {"priority": "NORMAL", "collapse_key": "sync"},
    }
}


def test_send_is_recorded(base_url):
    status, body = call("POST", f"{base_url}/v1/projects/famapp-dev/messages:send", WAKE_UP)
    assert status == 200 and body["name"] == "projects/famapp-dev/messages/1"
    status, body = call("GET", f"{base_url}/fake/messages")
    assert status == 200
    [recorded] = body["messages"]
    assert recorded["project"] == "famapp-dev" and recorded["message"] == WAKE_UP["message"]
    assert recorded["validate_only"] is False


def test_validate_only_and_reset(base_url):
    call("POST", f"{base_url}/v1/projects/p/messages:send", {**WAKE_UP, "validate_only": True})
    _, body = call("GET", f"{base_url}/fake/messages")
    assert body["messages"][0]["validate_only"] is True
    assert call("DELETE", f"{base_url}/fake/messages")[0] == 200
    assert call("GET", f"{base_url}/fake/messages")[1] == {"messages": []}


@pytest.mark.parametrize(
    "message",
    [
        {"data": {"t": "sync"}},
        {"token": "a", "topic": "b"},
        {"token": "a", "data": {"t": 1}},
        {"token": "a", "android": {"priority": "URGENT"}},
    ],
)
def test_invalid_messages_rejected(base_url, message):
    status, body = call("POST", f"{base_url}/v1/projects/p/messages:send", {"message": message})
    assert status == 400 and body["error"]["status"] == "INVALID_ARGUMENT"
    assert call("GET", f"{base_url}/fake/messages")[1] == {"messages": []}


def test_injected_token_error(base_url):
    assert call("POST", f"{base_url}/fake/tokens/device-token-1/error", {"errorCode": "UNREGISTERED"})[0] == 200
    status, body = call("POST", f"{base_url}/v1/projects/p/messages:send", WAKE_UP)
    assert status == 404
    assert body["error"]["details"][0]["errorCode"] == "UNREGISTERED"
    call("DELETE", f"{base_url}/fake/messages")
    assert call("POST", f"{base_url}/v1/projects/p/messages:send", WAKE_UP)[0] == 200
