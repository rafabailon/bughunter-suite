"""Minimal fictional shop used as a safe, local QA target."""

from __future__ import annotations

from functools import wraps
import re
import sqlite3
import time
from pathlib import Path
from typing import Any, Callable, TypeVar, cast

import jwt
from flask import Flask, g, jsonify, render_template, request
from werkzeug.security import check_password_hash, generate_password_hash

TOKEN_TTL_SECONDS = 3600
PRODUCTS = (
    {"id": 1, "name": "Aurora Desk Lamp", "price_cents": 4599, "stock": 12},
    {"id": 2, "name": "Field Notes Set", "price_cents": 1299, "stock": 30},
    {"id": 3, "name": "Orbit Travel Mug", "price_cents": 2199, "stock": 8},
)
PRODUCTS_BY_ID = {product["id"]: product for product in PRODUCTS}
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
VERSION = "1.0.0"
F = TypeVar("F", bound=Callable[..., Any])


def get_db() -> sqlite3.Connection:
    """Get a connection scoped to the active Flask request."""
    if "db" not in g:
        connection = sqlite3.connect(g.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        g.db = connection
    return g.db


def _close_db(_error: BaseException | None = None) -> None:
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def _initialize_database(path: str) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            PRAGMA foreign_keys = ON;
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS carts (
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                product_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL CHECK (quantity BETWEEN 1 AND 20),
                PRIMARY KEY (user_id, product_id)
            );
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                total_cents INTEGER NOT NULL CHECK (total_cents > 0),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )


def create_shop_app(config: dict[str, Any] | None = None) -> Flask:
    """Build the deterministic demonstration shop and JSON API."""
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_mapping(
        SECRET_KEY="local-test-secret-change-me",
        DATABASE=str(Path(__file__).resolve().parent.parent / "instance" / "shop.sqlite3"),
        MAX_CONTENT_LENGTH=4096,
        TESTING=False,
    )
    if config:
        app.config.update(config)
    if app.config["DATABASE"] == ":memory:":
        raise ValueError("Use a file-backed SQLite database for threaded local testing.")
    Path(str(app.config["DATABASE"])).parent.mkdir(parents=True, exist_ok=True)
    _initialize_database(str(app.config["DATABASE"]))
    app.teardown_appcontext(_close_db)

    @app.before_request
    def bind_database_path() -> None:
        g.database_path = app.config["DATABASE"]

    @app.after_request
    def security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; object-src 'none'; "
            "base-uri 'self'; frame-ancestors 'none'"
        )
        return response

    def require_auth(view: F) -> F:
        @wraps(view)
        def wrapped(*args: Any, **kwargs: Any):
            header = request.headers.get("Authorization", "")
            scheme, _, token = header.partition(" ")
            if scheme.lower() != "bearer" or not token:
                return jsonify({"error": "Bearer token required."}), 401
            try:
                claims = jwt.decode(
                    token,
                    app.config["SECRET_KEY"],
                    algorithms=["HS256"],
                    options={"require": ["sub", "exp"]},
                )
                user_id = int(claims["sub"])
            except (jwt.InvalidTokenError, TypeError, ValueError):
                return jsonify({"error": "Invalid or expired access token."}), 401
            user = get_db().execute(
                "SELECT id, email FROM users WHERE id = ?", (user_id,)
            ).fetchone()
            if user is None:
                return jsonify({"error": "Account no longer exists."}), 401
            g.user = user
            return view(*args, **kwargs)

        return cast(F, wrapped)

    @app.get("/")
    def storefront():
        return render_template("index.html", products=PRODUCTS)

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok", "service": "bughunter-suite", "version": VERSION})

    @app.get("/api/version")
    def version():
        return jsonify({"service": "bughunter-suite", "version": VERSION})

    @app.get("/api/products")
    def products():
        return jsonify({"products": list(PRODUCTS)})

    @app.get("/api/products/<int:product_id>")
    def product_detail(product_id: int):
        product = PRODUCTS_BY_ID.get(product_id)
        if product is None:
            return jsonify({"error": "Product not found."}), 404
        return jsonify({"product": dict(product)})

    @app.post("/api/register")
    def register():
        payload = request.get_json(silent=True)
        if (
            not isinstance(payload, dict)
            or set(payload) != {"email", "password"}
            or not isinstance(payload["email"], str)
            or not isinstance(payload["password"], str)
        ):
            return jsonify({"error": "Provide an email and password."}), 400
        email = payload["email"].strip().lower()
        password = payload["password"]
        if len(email) > 254 or not EMAIL_PATTERN.fullmatch(email):
            return jsonify({"error": "Enter a valid email address."}), 400
        if not 10 <= len(password) <= 128:
            return jsonify({"error": "Password must contain 10 to 128 characters."}), 400
        try:
            with get_db():
                cursor = get_db().execute(
                    "INSERT INTO users (email, password_hash) VALUES (?, ?)",
                    (email, generate_password_hash(password)),
                )
        except sqlite3.IntegrityError:
            return jsonify({"error": "An account with that email already exists."}), 409
        return jsonify({"id": cursor.lastrowid, "email": email}), 201

    @app.post("/api/login")
    def login():
        payload = request.get_json(silent=True)
        if (
            not isinstance(payload, dict)
            or set(payload) != {"email", "password"}
            or not isinstance(payload["email"], str)
            or not isinstance(payload["password"], str)
        ):
            return jsonify({"error": "Provide an email and password."}), 400
        user = get_db().execute(
            "SELECT id, email, password_hash FROM users WHERE email = ? COLLATE NOCASE",
            (payload["email"].strip(),),
        ).fetchone()
        if user is None or not check_password_hash(user["password_hash"], payload["password"]):
            return jsonify({"error": "Email or password is incorrect."}), 401
        token = jwt.encode(
            {"sub": str(user["id"]), "exp": time.time() + TOKEN_TTL_SECONDS},
            app.config["SECRET_KEY"],
            algorithm="HS256",
        )
        return jsonify({"access_token": token, "token_type": "Bearer", "expires_in": TOKEN_TTL_SECONDS})

    @app.get("/api/cart")
    @require_auth
    def get_cart():
        rows = get_db().execute(
            "SELECT product_id, quantity FROM carts WHERE user_id = ? ORDER BY product_id",
            (g.user["id"],),
        ).fetchall()
        items = []
        for row in rows:
            product = PRODUCTS_BY_ID.get(row["product_id"])
            if product is None:
                continue
            items.append(
                {
                    **product,
                    "quantity": row["quantity"],
                    "line_total_cents": product["price_cents"] * row["quantity"],
                }
            )
        return jsonify(
            {
                "items": items,
                "total_cents": sum(item["line_total_cents"] for item in items),
            }
        )

    @app.post("/api/cart/items")
    @require_auth
    def add_cart_item():
        payload = request.get_json(silent=True)
        if (
            not isinstance(payload, dict)
            or set(payload) != {"product_id", "quantity"}
            or isinstance(payload["product_id"], bool)
            or not isinstance(payload["product_id"], int)
            or isinstance(payload["quantity"], bool)
            or not isinstance(payload["quantity"], int)
        ):
            return jsonify({"error": "Provide integer product_id and quantity values."}), 400
        product = PRODUCTS_BY_ID.get(payload["product_id"])
        quantity = payload["quantity"]
        if product is None:
            return jsonify({"error": "Product not found."}), 404
        if not 1 <= quantity <= 20:
            return jsonify({"error": "Quantity must be between 1 and 20."}), 400
        if quantity > product["stock"]:
            return jsonify({"error": "Requested quantity exceeds available stock."}), 409
        db = get_db()
        current = db.execute(
            "SELECT quantity FROM carts WHERE user_id = ? AND product_id = ?",
            (g.user["id"], product["id"]),
        ).fetchone()
        total_quantity = quantity + (current["quantity"] if current else 0)
        if total_quantity > min(20, product["stock"]):
            return jsonify({"error": "Cart quantity exceeds available stock."}), 409
        with db:
            db.execute(
                """
                INSERT INTO carts (user_id, product_id, quantity) VALUES (?, ?, ?)
                ON CONFLICT(user_id, product_id) DO UPDATE SET quantity = excluded.quantity
                """,
                (g.user["id"], product["id"], total_quantity),
            )
        return jsonify({"message": "Item added.", "quantity": total_quantity}), 201

    @app.post("/api/checkout")
    @require_auth
    def checkout():
        payload = request.get_json(silent=True)
        if (
            not isinstance(payload, dict)
            or set(payload) != {"full_name", "email"}
            or not all(isinstance(payload[key], str) for key in ("full_name", "email"))
        ):
            return jsonify({"error": "Provide full_name and email for the simulated checkout."}), 400
        if not payload["full_name"].strip() or not EMAIL_PATTERN.fullmatch(payload["email"].strip()):
            return jsonify({"error": "Enter a name and valid email address."}), 400
        db = get_db()
        rows = db.execute(
            "SELECT product_id, quantity FROM carts WHERE user_id = ?",
            (g.user["id"],),
        ).fetchall()
        if not rows:
            return jsonify({"error": "Your cart is empty."}), 409
        total = 0
        for row in rows:
            product = PRODUCTS_BY_ID.get(row["product_id"])
            if product is None:
                continue
            total += product["price_cents"] * row["quantity"]
        if total <= 0:
            return jsonify({"error": "Your cart is empty."}), 409
        with db:
            cursor = db.execute(
                "INSERT INTO orders (user_id, total_cents) VALUES (?, ?)",
                (g.user["id"], total),
            )
            db.execute("DELETE FROM carts WHERE user_id = ?", (g.user["id"],))
        return jsonify(
            {
                "order_id": cursor.lastrowid,
                "total_cents": total,
                "status": "simulated",
                "message": "Order simulated; no payment was collected.",
            }
        ), 201

    return app
