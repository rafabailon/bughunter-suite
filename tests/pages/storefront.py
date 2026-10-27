"""Page Object Model for storefront browsing, account setup, and checkout."""

from __future__ import annotations

from playwright.sync_api import Locator, Page


class StorefrontPage:
    """Encapsulate the user-facing shop selectors and workflows."""

    def __init__(self, page: Page, base_url: str) -> None:
        self.page = page
        self.base_url = base_url

    def open(self) -> None:
        self.page.goto(self.base_url, wait_until="networkidle")

    def search(self, term: str) -> None:
        self.page.get_by_role("searchbox", name="Search products").fill(term)

    def product_card(self, product_name: str) -> Locator:
        return self.page.locator(".product-card").filter(has_text=product_name)

    def create_account(self, email: str, password: str) -> None:
        form = self.page.locator("#register-form")
        form.locator('input[name="email"]').fill(email)
        form.locator('input[name="password"]').fill(password)
        form.get_by_role("button", name="Create demo account").click()

    def add_product(self, product_name: str) -> None:
        self.product_card(product_name).get_by_role("button", name="Add to bag").click()

    def checkout(self, full_name: str, email: str) -> None:
        form = self.page.locator("#checkout-form")
        form.locator('input[name="full_name"]').fill(full_name)
        form.locator('input[name="email"]').fill(email)
        form.get_by_role("button", name="Place demo order").click()
