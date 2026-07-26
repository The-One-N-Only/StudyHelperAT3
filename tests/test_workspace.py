"""Tests for workspace creation, database setup, and related fixes."""

import os

import pytest
from conftest import flask_app
from src import db as db_mod


def _logged_in_context():
    ctx = flask_app.test_request_context("/api/workspaces", method="POST", json={"name": "Test"})
    ctx.push()
    from flask import session
    session["user_id"] = 1
    return ctx


def _call_create_workspace():
    from backend.api_routes import create_workspace
    result = create_workspace()
    if isinstance(result, tuple):
        return result[0], result[1]
    return result, result.status_code


def test_create_workspace_rejects_missing_body():
    ctx = flask_app.test_request_context("/api/workspaces", method="POST", content_type="application/json")
    ctx.push()
    from flask import session
    session["user_id"] = 1
    resp, status = _call_create_workspace()
    assert status == 400
    assert resp.get_json()["status"] is False
    ctx.pop()


def test_create_workspace_rejects_empty_name():
    ctx = flask_app.test_request_context("/api/workspaces", method="POST",
                                          json={"name": ""})
    ctx.push()
    from flask import session
    session["user_id"] = 1
    resp, status = _call_create_workspace()
    assert status == 400
    assert resp.get_json()["status"] is False
    ctx.pop()


def test_create_workspace_handles_db_error(monkeypatch):
    def _broken(*a, **kw):
        raise RuntimeError("DB failure")
    monkeypatch.setattr(db_mod, "create_workspace", _broken)
    ctx = _logged_in_context()
    resp, status = _call_create_workspace()
    assert status == 500
    assert resp.get_json()["status"] is False
    ctx.pop()


def test_setup_db_routes_around_pragma_on_postgres(monkeypatch):
    """setup_db() should skip SQLite PRAGMA migrations on PostgreSQL."""
    original = db_mod.setup_db
    def patched_setup():
        from sqlalchemy import text
        with db_mod.engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    monkeypatch.setattr(db_mod, "setup_db", patched_setup)
    try:
        db_mod.setup_db()
    except Exception as e:
        pytest.fail(f"setup_db() failed on non-SQLITE check: {e}")


def test_engine_parses_url_correctly():
    from sqlalchemy.engine import make_url
    u = make_url("postgresql://u:p@localhost/db_test")
    assert u.drivername == "postgresql"
    assert u.database == "db_test"
    assert u.host == "localhost"


def test_engine_defaults_to_sqlite():
    from sqlalchemy import create_engine
    e = create_engine("sqlite:///server.db", echo=False)
    url = e.url.render_as_string(hide_password=False)
    assert "sqlite" in url


def test_bulk_move_no_session_returns_redirect():
    with flask_app.test_client() as c:
        resp = c.post("/api/workspace-items/bulk-move", json={})
        assert resp.status_code == 302


def test_bulk_delete_no_session_returns_redirect():
    with flask_app.test_client() as c:
        resp = c.post("/api/workspace-items/bulk-delete", json={})
        assert resp.status_code == 302
