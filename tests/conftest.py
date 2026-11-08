import pytest

import database.db as db


@pytest.fixture
def app(tmp_path, monkeypatch):
    """Flask app wired to a fresh temp database seeded with the demo user."""
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    import app as app_module

    db.init_db()
    db.seed_db()
    app_module.app.config["TESTING"] = True
    return app_module.app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def demo_id(app):
    conn = db.get_db()
    try:
        return conn.execute(
            "SELECT id FROM users WHERE email = ?", ("demo@spendly.com",)
        ).fetchone()["id"]
    finally:
        conn.close()


@pytest.fixture
def empty_user_id(app):
    """A second user who has no expenses."""
    conn = db.get_db()
    try:
        cur = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("Empty User", "empty@example.com", "x"),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


@pytest.fixture
def logged_in(client):
    client.post("/login", data={"email": "demo@spendly.com", "password": "demo123"})
    return client
