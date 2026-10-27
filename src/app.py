"""Loopback-only entry point for the fictional shop QA target."""

from __future__ import annotations

import os
from pathlib import Path

from shop import create_shop_app


def main() -> None:
    database = Path("instance/shop.sqlite3")
    database.parent.mkdir(parents=True, exist_ok=True)
    app = create_shop_app(
        {
            "SECRET_KEY": os.environ.get(
                "SHOP_SECRET_KEY", "local-demo-secret-set-a-private-key-for-local-use"
            ),
            "DATABASE": os.environ.get("SHOP_DATABASE", str(database)),
        }
    )
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=False)


if __name__ == "__main__":
    main()
