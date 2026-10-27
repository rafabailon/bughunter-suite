"""Tests for the local-only development entry point."""

from flask import Flask

from app import main


def test_demo_entry_point_binds_to_loopback(monkeypatch, tmp_path):
    calls = []

    def record_run(_app, **kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(Flask, "run", record_run)
    monkeypatch.setenv("SHOP_DATABASE", str(tmp_path / "entry.sqlite3"))
    monkeypatch.setenv("SHOP_SECRET_KEY", "entry-point-local-test-key-with-more-than-32-bytes")
    monkeypatch.setenv("PORT", "5400")
    main()
    assert calls == [{"host": "127.0.0.1", "port": 5400, "debug": False}]
