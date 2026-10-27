"""HTTP API contract and behavior tests against the disposable local demo shop."""

from __future__ import annotations

import time

import pytest


pytestmark = pytest.mark.api


def test_catalog_schema_and_local_response_time(api):
    started = time.perf_counter()
    response = api.get(f"{api.base_url}/api/products", timeout=3)
    elapsed = time.perf_counter() - started
    assert response.status_code == 200
    assert elapsed < 2.0
    products = response.json()["products"]
    assert len(products) == 3
    assert all(
        set(product) == {"id", "name", "price_cents", "stock"}
        and isinstance(product["price_cents"], int)
        and product["price_cents"] > 0
        for product in products
    )


def test_health_and_version_endpoints(api):
    health = api.get(f"{api.base_url}/api/health", timeout=3)
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert health.json()["service"] == "bughunter-suite"

    version = api.get(f"{api.base_url}/api/version", timeout=3)
    assert version.status_code == 200
    assert version.json()["service"] == "bughunter-suite"
    assert version.json()["version"]


def test_product_detail_endpoint(api):
    response = api.get(f"{api.base_url}/api/products/1", timeout=3)
    assert response.status_code == 200
    product = response.json()["product"]
    assert product["id"] == 1
    assert product["name"] == "Aurora Desk Lamp"
    assert isinstance(product["price_cents"], int)
    assert isinstance(product["stock"], int)

    missing = api.get(f"{api.base_url}/api/products/9999", timeout=3)
    assert missing.status_code == 404
    assert "error" in missing.json()


def test_registration_login_and_bearer_auth(authenticated_api):
    response = authenticated_api.get(f"{authenticated_api.base_url}/api/cart", timeout=3)
    assert response.status_code == 200
    assert response.json() == {"items": [], "total_cents": 0}


@pytest.mark.parametrize(
    ("payload", "status"),
    [
        ({"email": "not-an-email", "password": "safe-test-pass-482"}, 400),
        ({"email": "x@example.test", "password": "short"}, 400),
        ({"email": "x@example.test", "password": "safe-test-pass-482", "extra": 1}, 400),
        (None, 400),
    ],
)
def test_registration_rejects_invalid_payloads(api, payload, status):
    response = api.post(f"{api.base_url}/api/register", json=payload, timeout=3)
    assert response.status_code == status
    assert "error" in response.json()


def test_duplicate_registration_and_invalid_credentials(api):
    credentials = {"email": "repeat@example.test", "password": "safe-test-pass-482"}
    first = api.post(f"{api.base_url}/api/register", json=credentials, timeout=3)
    duplicate = api.post(f"{api.base_url}/api/register", json=credentials, timeout=3)
    wrong_password = api.post(
        f"{api.base_url}/api/login",
        json={"email": credentials["email"], "password": "not-the-password"},
        timeout=3,
    )
    assert first.status_code == 201
    assert duplicate.status_code == 409
    assert wrong_password.status_code == 401


def test_cart_requires_bearer_token(api):
    response = api.get(f"{api.base_url}/api/cart", timeout=3)
    assert response.status_code == 401
    assert "error" in response.json()


def test_cart_rejects_invalid_bearer_token(api):
    api.headers["Authorization"] = "Bearer not-a-signed-token"
    response = api.get(f"{api.base_url}/api/cart", timeout=3)
    assert response.status_code == 401
    assert response.json()["error"] == "Invalid or expired access token."


@pytest.mark.parametrize(
    ("headers", "status"),
    [
        ({"Authorization": "Basic abc123"}, 401),
        ({"Authorization": "Bearer"}, 401),
        ({}, 401),
    ],
)
def test_cart_rejects_malformed_auth_headers(api, headers, status):
    original = dict(api.headers)
    try:
        for key in list(api.headers):
            if key.lower() == "authorization":
                del api.headers[key]
        api.headers.update(headers)
        response = api.get(f"{api.base_url}/api/cart", timeout=3)
        assert response.status_code == status
    finally:
        api.headers.clear()
        api.headers.update(original)


@pytest.mark.parametrize(
    ("payload", "status"),
    [
        ({"email": "x@example.test"}, 400),
        ({"password": "safe-test-pass-482"}, 400),
        ({"email": 123, "password": "safe-test-pass-482"}, 400),
        ({"email": "x@example.test", "password": "safe-test-pass-482", "extra": 1}, 400),
    ],
)
def test_login_rejects_invalid_payloads(api, payload, status):
    response = api.post(f"{api.base_url}/api/login", json=payload, timeout=3)
    assert response.status_code == status
    assert "error" in response.json()


@pytest.mark.parametrize(
    ("payload", "status"),
    [
        ({"product_id": 9999, "quantity": 1}, 404),
        ({"product_id": 1, "quantity": 0}, 400),
        ({"product_id": 1, "quantity": 21}, 400),
        ({"product_id": True, "quantity": 1}, 400),
    ],
)
def test_cart_rejects_unknown_and_invalid_items(authenticated_api, payload, status):
    response = authenticated_api.post(
        f"{authenticated_api.base_url}/api/cart/items", json=payload, timeout=3
    )
    assert response.status_code == status


def test_cart_updates_total_and_enforces_stock(authenticated_api):
    base = authenticated_api.base_url
    first = authenticated_api.post(
        f"{base}/api/cart/items", json={"product_id": 1, "quantity": 2}, timeout=3
    )
    cart = authenticated_api.get(f"{base}/api/cart", timeout=3)
    overstock = authenticated_api.post(
        f"{base}/api/cart/items", json={"product_id": 3, "quantity": 9}, timeout=3
    )
    assert first.status_code == 201
    assert cart.json()["total_cents"] == 9198
    assert cart.json()["items"][0]["quantity"] == 2
    assert overstock.status_code == 409
    exceeds_existing = authenticated_api.post(
        f"{base}/api/cart/items", json={"product_id": 1, "quantity": 11}, timeout=3
    )
    assert exceeds_existing.status_code == 409


def test_checkout_validates_form_and_simulates_order_without_payment(authenticated_api):
    base = authenticated_api.base_url
    empty = authenticated_api.post(
        f"{base}/api/checkout",
        json={"full_name": "Test Buyer", "email": "buyer@example.test"},
        timeout=3,
    )
    authenticated_api.post(
        f"{base}/api/cart/items", json={"product_id": 2, "quantity": 1}, timeout=3
    )
    invalid = authenticated_api.post(
        f"{base}/api/checkout", json={"full_name": "", "email": "bad"}, timeout=3
    )
    completed = authenticated_api.post(
        f"{base}/api/checkout",
        json={"full_name": "Test Buyer", "email": "buyer@example.test"},
        timeout=3,
    )
    assert empty.status_code == 409
    assert invalid.status_code == 400
    assert completed.status_code == 201
    assert completed.json()["total_cents"] == 1299
    assert completed.json()["status"] == "simulated"
    assert "no payment" in completed.json()["message"].lower()
    assert authenticated_api.get(f"{base}/api/cart", timeout=3).json()["items"] == []
