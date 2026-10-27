"""Isolated pytest fixtures; the test server binds exclusively to loopback."""

from __future__ import annotations

import socket
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest
from werkzeug.serving import make_server

from shop import create_shop_app


@pytest.fixture
def local_shop(tmp_path: Path) -> Iterator[str]:
    """Start a temporary demo shop at an ephemeral 127.0.0.1 port."""
    app = create_shop_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-only-secret-key-with-at-least-32-bytes",
            "DATABASE": str(tmp_path / "shop.sqlite3"),
        }
    )
    server = make_server("127.0.0.1", 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=3)
        server.server_close()


@pytest.fixture
def api(local_shop: str):
    """Provide a Requests session scoped to the local demo origin."""
    import requests

    session = requests.Session()
    session.trust_env = False
    session.headers["Accept"] = "application/json"
    session.base_url = local_shop
    yield session
    session.close()


@pytest.fixture
def authenticated_api(api):
    """Register one isolated customer and provide an authenticated API session."""
    credentials = {"email": "qa-user@example.test", "password": "safe-test-pass-482"}
    response = api.post(f"{api.base_url}/api/register", json=credentials, timeout=3)
    assert response.status_code == 201
    login = api.post(f"{api.base_url}/api/login", json=credentials, timeout=3)
    assert login.status_code == 200
    api.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
    return api


@pytest.fixture(scope="session")
def chromium():
    """Launch headless Chromium, giving actionable instructions when absent."""
    from playwright.sync_api import Error, sync_playwright

    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch()
        except Error as error:
            pytest.skip(
                "Playwright Chromium is not installed. Run `python -m playwright install chromium`. "
                f"Browser launch detail: {error}"
            )
        yield browser
        browser.close()
