"""Measure local API catalog and pure data-construction timings."""

from __future__ import annotations

import json
import logging
import statistics
import tempfile
import threading
import time
from pathlib import Path

import requests
from werkzeug.serving import make_server

from shop import create_shop_app


def main() -> None:
    """Benchmark the explicitly local demo app; no remote host is accepted."""
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    with tempfile.TemporaryDirectory(prefix="bughunter-benchmark-") as directory:
        app = create_shop_app(
            {
                "TESTING": True,
                "SECRET_KEY": "benchmark-only-local-key-with-32-bytes",
                "DATABASE": str(Path(directory) / "shop.sqlite3"),
            }
        )
        server = make_server("127.0.0.1", 0, app, threaded=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        samples: list[float] = []
        try:
            base_url = f"http://127.0.0.1:{server.server_port}"
            with requests.Session() as client:
                client.trust_env = False
                for _ in range(100):
                    started = time.perf_counter()
                    response = client.get(f"{base_url}/api/products", timeout=2)
                    response.raise_for_status()
                    samples.append(time.perf_counter() - started)
        finally:
            server.shutdown()
            thread.join(timeout=3)
            server.server_close()
    print(
        json.dumps(
            {
                "target": "loopback demo shop",
                "requests": len(samples),
                "mean_response_ms": statistics.mean(samples) * 1000,
                "p95_response_ms": sorted(samples)[94] * 1000,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
