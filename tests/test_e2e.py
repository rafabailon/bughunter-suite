"""Browser end-to-end tests using Playwright and Page Objects."""

from __future__ import annotations

import uuid

import pytest
from playwright.sync_api import expect

from pages.storefront import StorefrontPage


pytestmark = pytest.mark.e2e


def test_product_search_filters_catalog(chromium, local_shop):
    page = chromium.new_page()
    storefront = StorefrontPage(page, local_shop)
    storefront.open()
    storefront.search("mug")
    expect(storefront.product_card("Orbit Travel Mug")).to_be_visible()
    expect(storefront.product_card("Aurora Desk Lamp")).to_be_hidden()
    expect(page.locator("#no-results")).to_be_hidden()
    page.close()


def test_add_to_bag_checkout_and_validation_errors(chromium, local_shop):
    page = chromium.new_page()
    storefront = StorefrontPage(page, local_shop)
    storefront.open()

    storefront.add_product("Field Notes Set")
    expect(page.locator("#catalog-message")).to_contain_text("Create a demo account first")

    email = f"qa-{uuid.uuid4().hex[:10]}@example.test"
    storefront.create_account(email, "end-to-end-safe-pass-938")
    expect(page.locator("#account-message")).to_contain_text("Demo account created")
    storefront.add_product("Field Notes Set")
    expect(page.locator("#cart-count")).to_have_text("1")
    expect(page.locator("#cart-items")).to_contain_text("$12.99")

    checkout = page.locator("#checkout-form")
    checkout.locator('input[name="full_name"]').fill("QA Shopper")
    checkout.locator('input[name="email"]').fill("invalid")
    checkout.get_by_role("button", name="Place demo order").click()
    expect(checkout.locator('input[name="email"]')).to_be_focused()

    storefront.checkout("QA Shopper", email)
    expect(page.locator("#checkout-message")).to_contain_text("No payment was collected")
    expect(page.locator("#cart-count")).to_have_text("0")
    page.close()
