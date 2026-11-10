"""Tests for Step 7: Add Expense (GET/POST /expenses/add).

Written from .claude/specs/07-add-expense.md. The real database is never
touched: DB_PATH is redirected to a temp location before the app is imported
(the app initialises/seeds the DB at import time), and again per test to a
fresh file.
"""
import os
import sqlite3
import sys
import tempfile
from datetime import date, timedelta

import pytest
from werkzeug.security import generate_password_hash

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import database.db as db_module  # noqa: E402

# Redirect before importing app, which runs init_db()/seed_db() on import.
_IMPORT_DB_DIR = tempfile.mkdtemp(prefix="spendly_import_")
db_module.DB_PATH = os.path.join(_IMPORT_DB_DIR, "import.db")

from app import app as flask_app  # noqa: E402

CATEGORIES = ["Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"]

USER_A = {"name": "Alice", "email": "alice@example.com", "password": "password-a-123"}
USER_B = {"name": "Bob", "email": "bob@example.com", "password": "password-b-123"}


# ------------------------------------------------------------------ #
# Fixtures / helpers                                                  #
# ------------------------------------------------------------------ #

@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = str(tmp_path / "test_spendly.db")
    monkeypatch.setattr(db_module, "DB_PATH", path)
    db_module.init_db()
    return path


@pytest.fixture
def app(db_path):
    flask_app.config.update({"TESTING": True})
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


def _create_user(db_path, user):
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (user["name"], user["email"], generate_password_hash(user["password"])),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def _login(client, user):
    resp = client.post(
        "/login",
        data={"email": user["email"], "password": user["password"]},
    )
    assert resp.status_code == 302, "Login helper failed"


def _fetch_expenses(db_path, user_id=None):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        if user_id is None:
            return conn.execute("SELECT * FROM expenses ORDER BY id").fetchall()
        return conn.execute(
            "SELECT * FROM expenses WHERE user_id = ? ORDER BY id", (user_id,)
        ).fetchall()
    finally:
        conn.close()


@pytest.fixture
def user_a_id(db_path):
    return _create_user(db_path, USER_A)


@pytest.fixture
def user_b_id(db_path):
    return _create_user(db_path, USER_B)


@pytest.fixture
def auth_client(client, user_a_id):
    _login(client, USER_A)
    return client


def _form(**overrides):
    data = {
        "amount": "123.45",
        "category": "Food",
        "date": date.today().isoformat(),
        "description": "Unique lunch note",
    }
    data.update(overrides)
    return data


def _post(client, **overrides):
    return client.post("/expenses/add", data=_form(**overrides))


# ------------------------------------------------------------------ #
# Auth guard                                                          #
# ------------------------------------------------------------------ #

class TestAuthGuard:
    def test_get_logged_out_redirects_to_login(self, client):
        resp = client.get("/expenses/add")
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/login")

    def test_post_logged_out_redirects_to_login_and_saves_nothing(self, client, db_path):
        resp = _post(client)
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/login")
        assert _fetch_expenses(db_path) == []

    def test_stale_session_get_clears_session_and_redirects(self, client):
        with client.session_transaction() as sess:
            sess["user_id"] = 99999
        resp = client.get("/expenses/add")
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/login")
        with client.session_transaction() as sess:
            assert "user_id" not in sess, "Stale session should be cleared"

    def test_stale_session_post_saves_nothing(self, client, db_path):
        with client.session_transaction() as sess:
            sess["user_id"] = 99999
        resp = _post(client)
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/login")
        assert _fetch_expenses(db_path) == []


# ------------------------------------------------------------------ #
# GET form                                                            #
# ------------------------------------------------------------------ #

class TestForm:
    def test_get_logged_in_returns_form(self, auth_client):
        resp = auth_client.get("/expenses/add")
        assert resp.status_code == 200
        for field in (b'name="amount"', b'name="category"', b'name="date"', b'name="description"'):
            assert field in resp.data, f"Missing form field {field!r}"

    def test_get_prefills_today_date(self, auth_client):
        resp = auth_client.get("/expenses/add")
        assert date.today().isoformat().encode() in resp.data

    def test_get_lists_all_seven_categories(self, auth_client):
        resp = auth_client.get("/expenses/add")
        for cat in CATEGORIES:
            assert cat.encode() in resp.data, f"Category {cat} missing from dropdown"

    def test_get_has_cancel_link_to_profile(self, auth_client):
        resp = auth_client.get("/expenses/add")
        assert b'href="/profile"' in resp.data

    def test_get_extends_base_template(self, auth_client):
        resp = auth_client.get("/expenses/add")
        assert b"Spendly" in resp.data

    def test_profile_has_add_expense_link(self, auth_client):
        resp = auth_client.get("/profile")
        assert resp.status_code == 200
        assert b"/expenses/add" in resp.data, "Profile should link to add-expense form"


# ------------------------------------------------------------------ #
# Happy path                                                          #
# ------------------------------------------------------------------ #

class TestCreateSuccess:
    def test_valid_post_redirects_to_profile(self, auth_client):
        resp = _post(auth_client)
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/profile")

    def test_valid_post_stores_row_for_logged_in_user(self, auth_client, db_path, user_a_id):
        _post(auth_client, amount="123.45", category="Transport", description="Cab ride")
        rows = _fetch_expenses(db_path, user_a_id)
        assert len(rows) == 1
        row = rows[0]
        assert row["amount"] == pytest.approx(123.45)
        assert row["category"] == "Transport"
        assert row["date"] == date.today().isoformat()
        assert row["description"] == "Cab ride"

    def test_new_expense_appears_on_profile_with_rupee(self, auth_client):
        resp = _post(auth_client, description="Unique lunch note", amount="123.45")
        assert resp.status_code == 302
        page = auth_client.get("/profile")
        assert page.status_code == 200
        assert b"Unique lunch note" in page.data
        assert "₹".encode("utf-8") in page.data or b"&#8377;" in page.data

    def test_follow_redirect_shows_profile_with_expense(self, auth_client):
        resp = auth_client.post(
            "/expenses/add", data=_form(description="Followed note"), follow_redirects=True
        )
        assert resp.status_code == 200
        assert b"Followed note" in resp.data

    def test_profile_stats_reflect_new_expense(self, auth_client):
        _post(auth_client, amount="777.00", category="Health", description="Checkup")
        page = auth_client.get("/profile")
        assert b"777" in page.data, "Total spent should include the new expense"
        assert b"Health" in page.data, "Category breakdown should include Health"

    def test_multiple_expenses_all_saved(self, auth_client, db_path, user_a_id):
        _post(auth_client, amount="10", description="one")
        _post(auth_client, amount="20", description="two")
        assert len(_fetch_expenses(db_path, user_a_id)) == 2

    @pytest.mark.parametrize("category", CATEGORIES)
    def test_every_category_accepted(self, auth_client, db_path, category):
        resp = _post(auth_client, category=category)
        assert resp.status_code == 302
        rows = _fetch_expenses(db_path)
        assert len(rows) == 1 and rows[0]["category"] == category

    def test_past_date_accepted(self, auth_client, db_path):
        past = (date.today() - timedelta(days=40)).isoformat()
        resp = _post(auth_client, date=past)
        assert resp.status_code == 302
        assert _fetch_expenses(db_path)[0]["date"] == past

    def test_minimum_amount_accepted(self, auth_client, db_path):
        resp = _post(auth_client, amount="0.01")
        assert resp.status_code == 302
        assert _fetch_expenses(db_path)[0]["amount"] == pytest.approx(0.01)

    def test_amount_rounded_to_two_decimals(self, auth_client, db_path):
        resp = _post(auth_client, amount="10.999")
        assert resp.status_code == 302
        assert _fetch_expenses(db_path)[0]["amount"] == pytest.approx(11.0)

    def test_amount_surrounding_whitespace_tolerated(self, auth_client, db_path):
        resp = _post(auth_client, amount="  50  ")
        assert resp.status_code == 302
        assert _fetch_expenses(db_path)[0]["amount"] == pytest.approx(50.0)


# ------------------------------------------------------------------ #
# Description handling                                                #
# ------------------------------------------------------------------ #

class TestDescription:
    def test_blank_description_stored_as_null(self, auth_client, db_path):
        resp = _post(auth_client, description="")
        assert resp.status_code == 302
        assert _fetch_expenses(db_path)[0]["description"] is None

    def test_whitespace_only_description_stored_as_null(self, auth_client, db_path):
        resp = _post(auth_client, description="    ")
        assert resp.status_code == 302
        assert _fetch_expenses(db_path)[0]["description"] is None

    def test_missing_description_field_stored_as_null(self, auth_client, db_path):
        data = _form()
        del data["description"]
        resp = auth_client.post("/expenses/add", data=data)
        assert resp.status_code == 302
        assert _fetch_expenses(db_path)[0]["description"] is None

    def test_description_is_stripped(self, auth_client, db_path):
        _post(auth_client, description="  padded  ")
        assert _fetch_expenses(db_path)[0]["description"] == "padded"

    def test_description_exactly_200_chars_accepted(self, auth_client, db_path):
        desc = "x" * 200
        resp = _post(auth_client, description=desc)
        assert resp.status_code == 302
        assert _fetch_expenses(db_path)[0]["description"] == desc

    def test_description_201_chars_rejected(self, auth_client, db_path):
        resp = _post(auth_client, description="x" * 201)
        assert resp.status_code == 400
        assert _fetch_expenses(db_path) == []

    def test_sql_injection_description_stored_literally(self, auth_client, db_path):
        payload = "'); DROP TABLE expenses; --"
        resp = _post(auth_client, description=payload)
        assert resp.status_code == 302
        rows = _fetch_expenses(db_path)
        assert len(rows) == 1
        assert rows[0]["description"] == payload


# ------------------------------------------------------------------ #
# Validation errors                                                   #
# ------------------------------------------------------------------ #

class TestValidation:
    @pytest.mark.parametrize(
        "amount",
        ["", "   ", "0", "0.00", "-5", "-0.01", "abc", "12abc", "nan", "inf", "-inf", "1e999"],
    )
    def test_invalid_amount_rejected_and_nothing_saved(self, auth_client, db_path, amount):
        resp = _post(auth_client, amount=amount)
        assert resp.status_code == 400, f"amount={amount!r} should be rejected"
        assert _fetch_expenses(db_path) == []

    def test_missing_amount_field_rejected(self, auth_client, db_path):
        data = _form()
        del data["amount"]
        resp = auth_client.post("/expenses/add", data=data)
        assert resp.status_code == 400
        assert _fetch_expenses(db_path) == []

    @pytest.mark.parametrize(
        "category", ["", "Groceries", "food", "FOOD", "Food ", "'; DROP TABLE expenses;--"]
    )
    def test_invalid_category_rejected_and_nothing_saved(self, auth_client, db_path, category):
        resp = _post(auth_client, category=category)
        assert resp.status_code == 400, f"category={category!r} should be rejected"
        assert _fetch_expenses(db_path) == []

    def test_missing_category_field_rejected(self, auth_client, db_path):
        data = _form()
        del data["category"]
        resp = auth_client.post("/expenses/add", data=data)
        assert resp.status_code == 400
        assert _fetch_expenses(db_path) == []

    @pytest.mark.parametrize(
        "bad_date",
        ["", "not-a-date", "2024-13-01", "2024-02-30", "01/02/2024", "2024/01/02", "2024-1-2x"],
    )
    def test_malformed_date_rejected_and_nothing_saved(self, auth_client, db_path, bad_date):
        resp = _post(auth_client, date=bad_date)
        assert resp.status_code == 400, f"date={bad_date!r} should be rejected"
        assert _fetch_expenses(db_path) == []

    def test_tomorrow_rejected(self, auth_client, db_path):
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        resp = _post(auth_client, date=tomorrow)
        assert resp.status_code == 400
        assert _fetch_expenses(db_path) == []

    def test_far_future_date_rejected(self, auth_client, db_path):
        resp = _post(auth_client, date="2999-01-01")
        assert resp.status_code == 400
        assert _fetch_expenses(db_path) == []

    def test_today_accepted(self, auth_client, db_path):
        resp = _post(auth_client, date=date.today().isoformat())
        assert resp.status_code == 302
        assert len(_fetch_expenses(db_path)) == 1

    def test_failed_submission_renders_form_not_redirect(self, auth_client):
        resp = _post(auth_client, amount="abc")
        assert resp.status_code == 400
        assert "Location" not in resp.headers
        assert b'name="amount"' in resp.data


# ------------------------------------------------------------------ #
# Values preserved after failure                                      #
# ------------------------------------------------------------------ #

class TestValuesPreserved:
    def test_entered_values_preserved_on_bad_amount(self, auth_client):
        past = (date.today() - timedelta(days=3)).isoformat()
        resp = _post(auth_client, amount="abc", category="Bills", date=past,
                     description="Keep me please")
        assert resp.status_code == 400
        assert b"abc" in resp.data
        assert past.encode() in resp.data
        assert b"Keep me please" in resp.data

    def test_amount_and_bad_date_preserved_on_date_error(self, auth_client):
        resp = _post(auth_client, date="garbage", category="Shopping", amount="42.50")
        assert resp.status_code == 400
        assert b"42.50" in resp.data
        assert b"garbage" in resp.data
        assert b"selected" in resp.data, "Chosen category should stay selected"

    def test_description_preserved_when_too_long(self, auth_client):
        long_desc = "y" * 201
        resp = _post(auth_client, description=long_desc)
        assert resp.status_code == 400
        assert long_desc.encode() in resp.data

    def test_html_in_values_is_escaped(self, auth_client):
        resp = _post(auth_client, amount="bad", description="<script>alert(1)</script>")
        assert resp.status_code == 400
        assert b"<script>alert(1)</script>" not in resp.data


# ------------------------------------------------------------------ #
# Ownership / isolation                                               #
# ------------------------------------------------------------------ #

class TestOwnership:
    def test_user_id_in_form_is_ignored(self, auth_client, db_path, user_a_id, user_b_id):
        resp = _post(auth_client, user_id=str(user_b_id))
        assert resp.status_code == 302
        assert len(_fetch_expenses(db_path, user_a_id)) == 1
        assert _fetch_expenses(db_path, user_b_id) == []

    def test_other_user_cannot_see_expense(self, app, user_a_id, user_b_id):
        client_a = app.test_client()
        client_b = app.test_client()
        _login(client_a, USER_A)
        _login(client_b, USER_B)

        _post(client_a, description="Alice private note")

        assert b"Alice private note" in client_a.get("/profile").data
        assert b"Alice private note" not in client_b.get("/profile").data

    def test_each_user_expense_stored_against_own_id(self, app, db_path, user_a_id, user_b_id):
        client_a = app.test_client()
        client_b = app.test_client()
        _login(client_a, USER_A)
        _login(client_b, USER_B)

        _post(client_a, description="from a")
        _post(client_b, description="from b")

        assert [r["description"] for r in _fetch_expenses(db_path, user_a_id)] == ["from a"]
        assert [r["description"] for r in _fetch_expenses(db_path, user_b_id)] == ["from b"]


# ------------------------------------------------------------------ #
# Out-of-scope placeholders remain untouched                          #
# ------------------------------------------------------------------ #

class TestPlaceholdersUntouched:
    def test_edit_placeholder_still_returns_text(self, client):
        resp = client.get("/expenses/1/edit")
        assert resp.status_code == 200
        assert b"coming in Step 8" in resp.data

    def test_delete_placeholder_still_returns_text(self, client):
        resp = client.get("/expenses/1/delete")
        assert resp.status_code == 200
        assert b"coming in Step 9" in resp.data
