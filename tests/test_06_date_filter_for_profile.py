"""Tests for Step 6: date filter on GET /profile (date_from / date_to)."""
import os
import sqlite3
import tempfile
from datetime import date, timedelta

# Point the DB at a throwaway file BEFORE importing app, because importing app
# runs init_db()/seed_db() at module level and must never touch the real DB.
import database.db as _db

_IMPORT_DB = os.path.join(tempfile.mkdtemp(), "import_time.db")
_db.DB_PATH = _IMPORT_DB

import pytest  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402

from app import app as flask_app  # noqa: E402

TODAY = date.today()


def iso(d):
    return d.isoformat()


def days_ago(n):
    return TODAY - timedelta(days=n)


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = str(tmp_path / "test.db")
    monkeypatch.setattr(_db, "DB_PATH", path)
    _db.init_db()
    return path


@pytest.fixture
def app(db_path):
    flask_app.config.update(TESTING=True)
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


def _add_user(db_path, name, email):
    conn = sqlite3.connect(db_path)
    cur = conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        (name, email, generate_password_hash("password123")),
    )
    conn.commit()
    uid = cur.lastrowid
    conn.close()
    return uid


def _add_expense(db_path, uid, amount, category, d, desc):
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO expenses (user_id, amount, category, date, description) "
        "VALUES (?, ?, ?, ?, ?)",
        (uid, amount, category, iso(d), desc),
    )
    conn.commit()
    conn.close()


@pytest.fixture
def user_id(db_path):
    uid = _add_user(db_path, "Test User", "test@example.com")
    _add_expense(db_path, uid, 100.00, "Food", TODAY, "ITEM_TODAY")
    _add_expense(db_path, uid, 200.00, "Transport", days_ago(40), "ITEM_40D")
    _add_expense(db_path, uid, 400.00, "Bills", days_ago(100), "ITEM_100D")
    _add_expense(db_path, uid, 800.00, "Health", days_ago(200), "ITEM_200D")
    _add_expense(db_path, uid, 1600.00, "Shopping", days_ago(400), "ITEM_400D")
    return uid


@pytest.fixture
def auth_client(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
    return client


def get_profile(client, **params):
    return client.get("/profile", query_string=params)


def present(resp, *markers):
    body = resp.get_data(as_text=True)
    return {m: (m in body) for m in markers}


ALL = ["ITEM_TODAY", "ITEM_40D", "ITEM_100D", "ITEM_200D", "ITEM_400D"]


# ------------------------------------------------------------------ #
# Auth guard                                                          #
# ------------------------------------------------------------------ #

class TestAuthGuard:
    def test_profile_unauthenticated_redirects_to_login(self, client):
        resp = client.get("/profile")
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]

    def test_profile_with_filter_params_unauthenticated_redirects(self, client):
        resp = get_profile(client, date_from="2020-01-01", date_to="2030-01-01")
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]


# ------------------------------------------------------------------ #
# Unfiltered                                                          #
# ------------------------------------------------------------------ #

class TestUnfiltered:
    def test_no_params_shows_all_expenses(self, auth_client):
        resp = get_profile(auth_client)
        assert resp.status_code == 200
        p = present(resp, *ALL)
        assert all(p.values()), p

    def test_no_params_summary_total_includes_everything(self, auth_client):
        body = get_profile(auth_client).get_data(as_text=True)
        assert "₹3,100.00" in body
        assert "5" in body

    def test_only_date_from_falls_back_to_unfiltered(self, auth_client):
        resp = get_profile(auth_client, date_from=iso(days_ago(50)))
        assert resp.status_code == 200
        assert all(present(resp, *ALL).values())

    def test_only_date_to_falls_back_to_unfiltered(self, auth_client):
        resp = get_profile(auth_client, date_to=iso(days_ago(50)))
        assert resp.status_code == 200
        assert all(present(resp, *ALL).values())

    def test_empty_params_fall_back_to_unfiltered(self, auth_client):
        resp = get_profile(auth_client, date_from="", date_to="")
        assert resp.status_code == 200
        assert all(present(resp, *ALL).values())


# ------------------------------------------------------------------ #
# Custom range                                                        #
# ------------------------------------------------------------------ #

class TestCustomRange:
    def test_valid_range_limits_transactions(self, auth_client):
        resp = get_profile(
            auth_client, date_from=iso(days_ago(120)), date_to=iso(days_ago(30))
        )
        p = present(resp, *ALL)
        assert resp.status_code == 200
        assert p["ITEM_40D"] and p["ITEM_100D"]
        assert not (p["ITEM_TODAY"] or p["ITEM_200D"] or p["ITEM_400D"]), p

    def test_valid_range_limits_summary_total(self, auth_client):
        resp = get_profile(
            auth_client, date_from=iso(days_ago(120)), date_to=iso(days_ago(30))
        )
        body = resp.get_data(as_text=True)
        assert "₹600.00" in body  # 200 + 400
        assert "₹3,100.00" not in body

    def test_valid_range_limits_category_breakdown(self, auth_client):
        body = get_profile(
            auth_client, date_from=iso(days_ago(120)), date_to=iso(days_ago(30))
        ).get_data(as_text=True)
        assert "Bills" in body and "Transport" in body
        assert "Shopping" not in body.split("By category")[1]
        assert "Health" not in body.split("By category")[1]

    def test_top_category_reflects_range(self, auth_client):
        body = get_profile(
            auth_client, date_from=iso(days_ago(300)), date_to=iso(days_ago(150))
        ).get_data(as_text=True)
        # Only Health (200d ago) is in range.
        stat = body.split("Top category")[1].split("</span>")[1]
        assert "Health" in stat

    def test_bounds_are_inclusive(self, auth_client):
        resp = get_profile(
            auth_client, date_from=iso(days_ago(100)), date_to=iso(days_ago(40))
        )
        p = present(resp, *ALL)
        assert p["ITEM_100D"] and p["ITEM_40D"], "both boundary dates must be included"
        assert not p["ITEM_TODAY"] and not p["ITEM_200D"]

    def test_single_day_range(self, auth_client):
        d = iso(days_ago(40))
        resp = get_profile(auth_client, date_from=d, date_to=d)
        p = present(resp, *ALL)
        assert p["ITEM_40D"]
        assert not any(v for k, v in p.items() if k != "ITEM_40D")

    def test_filter_fields_reflect_submitted_values(self, auth_client):
        f, t = iso(days_ago(120)), iso(days_ago(30))
        body = get_profile(auth_client, date_from=f, date_to=t).get_data(as_text=True)
        assert f'value="{f}"' in body
        assert f'value="{t}"' in body

    def test_empty_range_shows_zero_state(self, auth_client):
        resp = get_profile(
            auth_client,
            date_from=iso(days_ago(3000)),
            date_to=iso(days_ago(2900)),
        )
        body = resp.get_data(as_text=True)
        assert resp.status_code == 200
        assert "₹0.00" in body
        assert not any(present(resp, *ALL).values())
        assert "No spending yet" in body
        assert "No transactions yet" in body


# ------------------------------------------------------------------ #
# Presets                                                             #
# ------------------------------------------------------------------ #

class TestPresets:
    def test_all_preset_labels_present(self, auth_client):
        body = get_profile(auth_client).get_data(as_text=True)
        for label in ("This Month", "Last 3 Months", "Last 6 Months", "All Time"):
            assert label in body, f"missing preset {label}"

    def test_this_month_preset_filters_to_current_month(self, auth_client):
        first = TODAY.replace(day=1)
        resp = get_profile(auth_client, date_from=iso(first), date_to=iso(TODAY))
        p = present(resp, *ALL)
        assert p["ITEM_TODAY"]
        assert not (p["ITEM_40D"] or p["ITEM_100D"] or p["ITEM_200D"] or p["ITEM_400D"])

    def test_this_month_link_has_first_of_month_and_today(self, auth_client):
        body = get_profile(auth_client).get_data(as_text=True)
        assert f"date_from={iso(TODAY.replace(day=1))}" in body
        assert f"date_to={iso(TODAY)}" in body

    def test_last_3_months_window_excludes_older(self, auth_client):
        # Build the link the page offers and follow it.
        body = get_profile(auth_client).get_data(as_text=True)
        import re
        links = re.findall(r'href="([^"]*date_from=[^"]*)"', body)
        assert len(links) >= 3, links
        # Order per spec: This Month, Last 3 Months, Last 6 Months
        resp = auth_client.get(links[1].replace("&amp;", "&"))
        p = present(resp, *ALL)
        assert p["ITEM_TODAY"] and p["ITEM_40D"]
        assert not (p["ITEM_100D"] or p["ITEM_200D"] or p["ITEM_400D"]), p

    def test_last_6_months_window_excludes_older(self, auth_client):
        import re
        body = get_profile(auth_client).get_data(as_text=True)
        links = re.findall(r'href="([^"]*date_from=[^"]*)"', body)
        resp = auth_client.get(links[2].replace("&amp;", "&"))
        p = present(resp, *ALL)
        assert p["ITEM_TODAY"] and p["ITEM_40D"] and p["ITEM_100D"]
        assert not (p["ITEM_200D"] or p["ITEM_400D"]), p

    def test_all_time_link_is_clean_profile_url(self, auth_client):
        import re
        body = get_profile(auth_client).get_data(as_text=True)
        m = re.search(r'<a [^>]*href="([^"]*)"[^>]*>\s*All Time\s*</a>', body)
        assert m, "All Time link not found"
        assert "?" not in m.group(1), "All Time must pass no query params"
        assert m.group(1).endswith("/profile")

    def test_all_time_shows_everything_after_filter(self, auth_client):
        resp = auth_client.get("/profile")
        assert all(present(resp, *ALL).values())


# ------------------------------------------------------------------ #
# Active state                                                        #
# ------------------------------------------------------------------ #

class TestActiveState:
    def test_all_time_active_with_no_filter(self, auth_client):
        import re
        body = get_profile(auth_client).get_data(as_text=True)
        m = re.search(r'<a [^>]*class="([^"]*)"[^>]*>\s*All Time\s*</a>', body)
        assert m and "active" in m.group(1), "All Time should be active by default"

    def test_this_month_active_when_this_month_selected(self, auth_client):
        import re
        body = get_profile(
            auth_client, date_from=iso(TODAY.replace(day=1)), date_to=iso(TODAY)
        ).get_data(as_text=True)
        m = re.search(r'<a [^>]*class="([^"]*)"[^>]*>\s*This Month\s*</a>', body)
        assert m and "active" in m.group(1)
        m2 = re.search(r'<a [^>]*class="([^"]*)"[^>]*>\s*All Time\s*</a>', body)
        assert m2 and "active" not in m2.group(1)

    def test_custom_range_marks_no_preset_active(self, auth_client):
        import re
        body = get_profile(
            auth_client, date_from="2001-02-03", date_to="2001-04-05"
        ).get_data(as_text=True)
        for label in ("This Month", "Last 3 Months", "Last 6 Months", "All Time"):
            m = re.search(
                r'<a [^>]*class="([^"]*)"[^>]*>\s*' + label + r'\s*</a>', body
            )
            assert m and "active" not in m.group(1), f"{label} wrongly active"
        assert "is-active" in body, "custom range form should show an active state"


# ------------------------------------------------------------------ #
# Validation                                                          #
# ------------------------------------------------------------------ #

class TestValidation:
    def test_from_after_to_flashes_error_and_is_unfiltered(self, auth_client):
        resp = get_profile(
            auth_client, date_from=iso(days_ago(10)), date_to=iso(days_ago(100))
        )
        body = resp.get_data(as_text=True)
        assert resp.status_code == 200
        assert "Start date must be before end date." in body
        assert all(present(resp, *ALL).values())

    def test_no_error_flash_for_valid_range(self, auth_client):
        body = get_profile(
            auth_client, date_from=iso(days_ago(100)), date_to=iso(days_ago(10))
        ).get_data(as_text=True)
        assert "Start date must be before end date." not in body

    @pytest.mark.parametrize(
        "params",
        [
            {"date_from": "not-a-date", "date_to": "2030-01-01"},
            {"date_from": "2020-01-01", "date_to": "garbage"},
            {"date_from": "not-a-date", "date_to": "also-bad"},
            {"date_from": "2024-13-01", "date_to": "2030-01-01"},
            {"date_from": "2024-02-30", "date_to": "2030-01-01"},
            {"date_from": "01/02/2024", "date_to": "2030-01-01"},
            {"date_from": "2024-1-1x", "date_to": "2030-01-01"},
            {"date_from": "   ", "date_to": "   "},
            {"date_from": "9" * 500, "date_to": "9" * 500},
        ],
    )
    def test_malformed_dates_fall_back_without_crash(self, auth_client, params):
        resp = get_profile(auth_client, **params)
        assert resp.status_code == 200
        assert all(present(resp, *ALL).values()), "should be unfiltered"

    def test_malformed_date_does_not_show_range_error(self, auth_client):
        body = get_profile(
            auth_client, date_from="not-a-date", date_to="2030-01-01"
        ).get_data(as_text=True)
        assert "Start date must be before end date." not in body

    @pytest.mark.parametrize(
        "payload",
        [
            "' OR '1'='1",
            "2020-01-01'; DROP TABLE expenses;--",
            "1 UNION SELECT * FROM users",
        ],
    )
    def test_sql_injection_input_is_harmless(self, auth_client, db_path, payload):
        resp = get_profile(auth_client, date_from=payload, date_to=payload)
        assert resp.status_code == 200
        assert all(present(resp, *ALL).values())
        conn = sqlite3.connect(db_path)
        n = conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
        conn.close()
        assert n == 5, "expenses table must be intact"

    def test_injection_in_one_valid_one_malicious_param(self, auth_client):
        resp = get_profile(
            auth_client, date_from="2000-01-01", date_to="2030-01-01' OR '1'='1"
        )
        assert resp.status_code == 200
        assert all(present(resp, *ALL).values())

    def test_xss_in_date_param_not_reflected_raw(self, auth_client):
        resp = get_profile(
            auth_client, date_from="<script>alert(1)</script>", date_to="2030-01-01"
        )
        assert b"<script>alert(1)</script>" not in resp.data


# ------------------------------------------------------------------ #
# Isolation between users                                             #
# ------------------------------------------------------------------ #

class TestUserIsolation:
    def test_filtered_view_excludes_other_users_expenses(
        self, client, db_path, user_id
    ):
        other = _add_user(db_path, "Other Person", "other@example.com")
        _add_expense(db_path, other, 9999.00, "Other", TODAY, "OTHER_USER_ITEM")
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
        resp = get_profile(
            client, date_from=iso(days_ago(5)), date_to=iso(TODAY)
        )
        body = resp.get_data(as_text=True)
        assert "ITEM_TODAY" in body
        assert "OTHER_USER_ITEM" not in body
        assert "9,999.00" not in body

    def test_user_with_no_expenses_sees_zero_state_with_filter(
        self, client, db_path
    ):
        uid = _add_user(db_path, "Empty User", "empty@example.com")
        with client.session_transaction() as sess:
            sess["user_id"] = uid
        resp = get_profile(client, date_from="2000-01-01", date_to="2100-01-01")
        body = resp.get_data(as_text=True)
        assert resp.status_code == 200
        assert "₹0.00" in body
        assert "No transactions yet" in body
        assert "No spending yet" in body


# ------------------------------------------------------------------ #
# Currency and rendering                                              #
# ------------------------------------------------------------------ #

class TestRendering:
    @pytest.mark.parametrize(
        "params",
        [
            {},
            {"date_from": "2000-01-01", "date_to": "2100-01-01"},
            {"date_from": "1990-01-01", "date_to": "1990-01-02"},
        ],
    )
    def test_rupee_symbol_always_shown(self, auth_client, params):
        body = get_profile(auth_client, **params).get_data(as_text=True)
        assert "₹" in body

    def test_filter_bar_has_date_inputs_and_apply_button(self, auth_client):
        body = get_profile(auth_client).get_data(as_text=True)
        assert 'type="date"' in body
        assert 'name="date_from"' in body
        assert 'name="date_to"' in body
        assert "Apply" in body

    def test_filter_form_submits_via_get(self, auth_client):
        body = get_profile(auth_client).get_data(as_text=True)
        assert 'method="get"' in body.lower()

    def test_filter_bar_appears_before_summary_stats(self, auth_client):
        body = get_profile(auth_client).get_data(as_text=True)
        assert body.index("This Month") < body.index("Total spent")

    def test_transactions_still_ordered_newest_first_when_filtered(
        self, auth_client
    ):
        body = get_profile(
            auth_client, date_from=iso(days_ago(120)), date_to=iso(TODAY)
        ).get_data(as_text=True)
        assert body.index("ITEM_TODAY") < body.index("ITEM_40D") < body.index("ITEM_100D")
