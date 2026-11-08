from database.queries import (
    get_category_breakdown,
    get_recent_transactions,
    get_summary_stats,
    get_user_by_id,
)

CATEGORIES = {"Shopping", "Bills", "Entertainment", "Food", "Health", "Other", "Transport"}


# ---------------------------------------------------------------- unit tests

def test_get_user_by_id_valid(demo_id):
    user = get_user_by_id(demo_id)
    assert user["name"] == "Demo User"
    assert user["email"] == "demo@spendly.com"
    assert user["initials"] == "DU"
    assert len(user["member_since"].split()) == 2  # "Month YYYY"


def test_get_user_by_id_missing(app):
    assert get_user_by_id(99999) is None


def test_summary_stats_with_expenses(demo_id):
    stats = get_summary_stats(demo_id)
    assert stats["total_spent"] == 5831.25
    assert stats["transaction_count"] == 8
    assert stats["top_category"] == "Shopping"


def test_summary_stats_empty(empty_user_id):
    assert get_summary_stats(empty_user_id) == {
        "total_spent": 0,
        "transaction_count": 0,
        "top_category": "—",
    }


def test_recent_transactions_newest_first(demo_id):
    txns = get_recent_transactions(demo_id)
    assert len(txns) == 8
    assert all(set(t) == {"date", "description", "category", "amount"} for t in txns)
    assert txns[0]["description"] == "Dinner out"  # day 26 is the latest seed date
    assert txns[-1]["description"] == "Groceries"  # day 1 is the earliest


def test_recent_transactions_limit(demo_id):
    assert len(get_recent_transactions(demo_id, limit=3)) == 3


def test_recent_transactions_empty(empty_user_id):
    assert get_recent_transactions(empty_user_id) == []


def test_category_breakdown(demo_id):
    cats = get_category_breakdown(demo_id)
    assert {c["name"] for c in cats} == CATEGORIES
    amounts = [c["amount"] for c in cats]
    assert amounts == sorted(amounts, reverse=True)
    assert all(isinstance(c["pct"], int) for c in cats)
    assert sum(c["pct"] for c in cats) == 100


def test_category_breakdown_empty(empty_user_id):
    assert get_category_breakdown(empty_user_id) == []


# --------------------------------------------------------------- route tests

def test_profile_requires_login(client):
    resp = client.get("/profile")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


def test_profile_shows_real_data(logged_in):
    resp = logged_in.get("/profile")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Demo User" in html
    assert "demo@spendly.com" in html
    assert "₹5,831.25" in html
    assert "Shopping" in html
    for name in CATEGORIES:
        assert name in html
    # newest-first: Dinner out (day 26) appears before Groceries (day 1)
    assert html.index("Dinner out") < html.index("Groceries")


def test_profile_new_user_empty_state(client):
    client.post(
        "/register",
        data={"name": "New Person", "email": "new@example.com", "password": "password123"},
    )
    client.post("/login", data={"email": "new@example.com", "password": "password123"})
    resp = client.get("/profile")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "New Person" in html
    assert "₹0.00" in html
    assert "No transactions yet." in html


def test_profile_stale_session_redirects(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 99999
    resp = client.get("/profile")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")
