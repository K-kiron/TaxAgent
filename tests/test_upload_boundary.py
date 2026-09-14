
from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from taxagent.web.local_app import app


BASE_URL = "http://127.0.0.1:8056"
SECURITY_HEADER = "content-security-policy"


def _client() -> TestClient:
    return TestClient(app, base_url=BASE_URL, raise_server_exceptions=False)


def test_import_pdfs_rejects_malformed_content_length_without_500() -> None:
    response = _client().post("/api/import-pdfs", content=b"", headers={"content-length": "not-a-number"})

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "invalid_content_length"
    assert response.headers[SECURITY_HEADER]


def test_import_pdfs_rejects_negative_content_length_without_500() -> None:
    response = _client().post("/api/import-pdfs", content=b"", headers={"content-length": "-1"})

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "invalid_content_length"
    assert response.headers[SECURITY_HEADER]


def test_import_pdfs_rejects_oversize_content_length_without_500() -> None:
    response = _client().post("/api/import-pdfs", content=b"", headers={"content-length": "26000001"})

    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "batch_too_large"
    assert response.headers[SECURITY_HEADER]


def test_import_pdfs_rejects_missing_content_length_without_500() -> None:
    async def call_app_without_content_length() -> tuple[int, dict[str, str], bytes]:
        messages = []
        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/api/import-pdfs",
            "raw_path": b"/api/import-pdfs",
            "query_string": b"",
            "headers": [(b"host", b"127.0.0.1:8056")],
            "client": ("127.0.0.1", 12345),
            "server": ("127.0.0.1", 8056),
        }

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            messages.append(message)

        await app(scope, receive, send)
        start = next(message for message in messages if message["type"] == "http.response.start")
        body = b"".join(
            message.get("body", b"") for message in messages if message["type"] == "http.response.body"
        )
        headers = {key.decode().lower(): value.decode() for key, value in start["headers"]}
        return start["status"], headers, body

    status, headers, body = asyncio.run(call_app_without_content_length())

    assert status == 411
    assert b"missing_content_length" in body
    assert headers[SECURITY_HEADER]
