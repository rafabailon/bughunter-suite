# BugHunter Suite

A local-only e-commerce QA Automation Suite built with Python, pytest, Requests, Flask, and Playwright. It includes a small fictional shop as the system under test, so API and browser tests can be run reproducibly without contacting external services.

## What is included

- **API integration tests:** catalog schema and response time, health/version endpoints, product detail, account registration, JWT login, bearer-authenticated cart, inventory validation, and simulated checkout.
- **Browser E2E tests:** product search, account creation, adding an item to the bag, checkout validation, and simulated order confirmation.
- **Page Object Model:** storefront selectors and user workflows are centralized in `tests/pages/storefront.py`.
- **Reports:** terminal output, standalone HTML report, and line/branch coverage reports.
- **Safe local target:** the demo server binds to `127.0.0.1`; API tests create an ephemeral local server. There is no supported remote-target override.

## Requirements

- Python 3.10 or newer.
- `pip` and Python `venv`.
- Playwright Chromium for browser tests.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[test]'
python -m playwright install chromium
```

## Run the suite

Run API and browser tests together:

```bash
python -m pytest
```

Run focused suites and produce reports:

```bash
python -m pytest -m api
python -m pytest -m e2e
mkdir -p reports
python -m pytest --html=reports/pytest-report.html --self-contained-html
python -m pytest --cov=src --cov-report=term-missing --cov-report=html:reports/coverage
```

`make test`, `make api`, `make e2e`, `make report`, and `make coverage` are shortcuts for these commands. Generated reports are ignored by Git. Use `PYTHONPATH=src` if running from the repository root without installing in editable mode.

## Run the fictional demo shop manually

```bash
python -m app
```

Visit <http://127.0.0.1:5000>. The demo uses a local SQLite database under `instance/`. For a local signing key, set `SHOP_SECRET_KEY` before launching. This development app is not intended to be exposed publicly.

All products, accounts, and orders are test data. Checkout is simulated and does not collect card details or process payments. Do not enter real credentials.

## Test design and quality notes

The API tests use Requests against a fixture-managed ephemeral loopback HTTP server, temporary SQLite database, and bounded request timeouts. The E2E tests create an isolated browser context and use explicit Playwright assertions rather than fixed sleeps. API response latency is measured locally with a generous threshold to detect gross regressions, not to claim production performance.

## Safety boundary

This suite is intentionally tied to the included fictional demo application and loopback-only server. It does not accept a target URL, scan hosts, attempt security bypasses, or test third-party systems. Its JWTs and shop data are for local QA practice only.

## License

MIT. See [LICENSE](LICENSE).
