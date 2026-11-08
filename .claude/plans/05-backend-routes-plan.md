# Plan: Step 05 — Backend Routes for Profile Page

## Context

Spec: `.claude/specs/05-backend-routes-for-profile-page.md` (titled "Backend Connection"). `/profile` (`app.py:115-154`) still renders hardcoded dicts from Step 4. This step replaces them with live SQLite queries, so each logged-in user sees their own data. The query helpers go in a new `database/queries.py`, and the step adds the project's first tests.

Current state:

- `get_db()` (`database/db.py:23`) reads the module-level `DB_PATH` at call time. Tests can monkeypatch `database.db.DB_PATH` to a temp file.
- `seed_db()` (`database/db.py:64`) inserts Demo User with 8 expenses dated `today.replace(day=N)` as ISO `YYYY-MM-DD`. `users.created_at` is stored as `YYYY-MM-DD HH:MM:SS`.
- `templates/profile.html` uses `user.initials`, `c.total` and `c.percent`. Amounts already use the ₹ symbol.
- No `tests/` directory exists yet.

### Spec issues and how this plan resolves them

1. **The spec's expected numbers don't match the seed.** The spec says ₹346.24 and top category "Bills". The seed in `db.py:78-87` gives **₹5,831.25** (8 txns) with **Shopping** on top (2200 vs Bills 1800). The tests and verification below use the real seed values.
2. **The spec's key names differ from the template's.** The spec uses `amount`/`pct` for categories, but the template reads `total`/`percent`. The plan follows the spec's contract and updates the 3 template references.
3. **The template needs initials.** The template needs `user.initials`, so `get_user_by_id` also returns `initials`, alongside the `name`/`email`/`member_since` the spec asks for.
4. **Parallel subagents.** The spec mentions three parallel subagents. The work is 4 small functions in one file, and parallel edits to that file would conflict, so it is implemented directly.

## Changes

### 0. Save this plan

Copy this plan to `.claude/plans/05-backend-routes-plan.md`.

### 1. New `database/queries.py`

This module has no Flask imports. It does `from database.db import get_db`, and each function wraps its work in `conn = get_db()` / `try` / `finally: conn.close()`. All SQL is parameterised (`?`).

- `get_user_by_id(user_id)` runs `SELECT name, email, created_at FROM users WHERE id = ?`.
  - Returns `None` if no row matches.
  - Otherwise returns `{name, email, initials, member_since}`:
    - `initials`: the first letter of up to the first two words of the name, uppercased.
    - `member_since`: `datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S").strftime("%B %Y")`.
- `get_summary_stats(user_id)`:
  - Runs `SELECT COALESCE(SUM(amount),0), COUNT(*) FROM expenses WHERE user_id = ?`.
  - Gets the top category with `SELECT category FROM expenses WHERE user_id = ? GROUP BY category ORDER BY SUM(amount) DESC, category ASC LIMIT 1`.
  - Returns `{total_spent, transaction_count, top_category}`, with `"—"` as the top category when the user has no expenses.
- `get_recent_transactions(user_id, limit=10)`:
  - Runs `SELECT date, description, category, amount ... WHERE user_id = ? ORDER BY date DESC, id DESC LIMIT ?`.
  - Formats `date` as `"%d %b %Y"` (e.g. "26 Nov 2026").
  - Returns `[]` when the user has no expenses.
- `get_category_breakdown(user_id)`:
  - Runs `SELECT category, SUM(amount) AS amount ... GROUP BY category ORDER BY amount DESC, category ASC`.
  - Returns `[]` if there are no rows.
  - Otherwise computes `pct = round(amount / grand_total * 100)` and adds `100 - sum(pcts)` to the first (largest) entry. With the seed, the raw values sum to 101, so Shopping becomes 37.
  - Returns `[{name, amount, pct}]`.

### 2. `app.py`: rewrite `profile()`

```python
from database.queries import (get_user_by_id, get_summary_stats,
                              get_recent_transactions, get_category_breakdown)

@app.route("/profile")
def profile():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))
    user = get_user_by_id(user_id)
    if user is None:            # stale session (user deleted)
        session.clear()
        return redirect(url_for("login"))
    return render_template("profile.html", user=user,
        stats=get_summary_stats(user_id),
        transactions=get_recent_transactions(user_id),
        categories=get_category_breakdown(user_id))
```

All hardcoded data is removed. Other routes are untouched.

### 3. `templates/profile.html`: minimal edits

- `c.total` → `c.amount` and `c.percent` → `c.pct` (lines 67 and 69).
- Add empty states:
  - In the transactions table: `{% else %}<tr><td colspan="4">No transactions yet.</td></tr>`.
  - In the category list: `{% else %}<li>No spending yet.</li>`.
- No inline styles and no hex values. The existing CSS classes are reused.

### 4. Tests: new `tests/conftest.py` and `tests/test_backend_connection.py`

- **`conftest.py`** sets up an isolated database:
  - Monkeypatches `database.db.DB_PATH` to `tmp_path / "test.db"`, then runs `init_db()` and `seed_db()`.
  - Provides an `app` fixture (`app.config["TESTING"] = True`) and a `client` fixture.
  - Provides a helper that inserts a second user with no expenses.
  - Importing `app` runs init/seed against the real DB once, which is harmless because the real DB already exists. The tests themselves only touch the temp DB.
- **Unit tests** cover the 8 rows of the spec table:
  - Demo user: total 5831.25, count 8, top "Shopping".
  - Transactions are newest-first.
  - The breakdown has 7 entries, sorted by amount descending, with integer `pct` values summing to 100.
  - A nonexistent id returns `None`, and an empty user gets zeros, `"—"` and `[]`.
- **Route tests**:
  - Logged out: `/profile` returns 302 to `/login`.
  - Logged in as the demo user via `POST /login`: the page returns 200 and contains "Demo User", "demo@spendly.com", "₹5,831.25", "Shopping" and all 7 category names.
  - A new user's page returns 200 and contains "₹0.00".
  - A stale `session["user_id"]` (set via `client.session_transaction()`) redirects to `/login`.

### Out of scope

Add/edit/delete expenses (Steps 7–9), filters and date ranges, a `login_required` decorator, CSS changes, and any `db.py` schema or seed changes.

## Verification

1. `pytest` passes.
2. `python app.py`, then log in as `demo@spendly.com` / `demo123`. `/profile` shows:
   - Demo User, the email, and "Member since <month year of created_at>".
   - Stats ₹5,831.25 · 8 · Shopping.
   - 8 rows, newest date first.
   - 7 categories whose bars add up to 100%.
3. Register a new user, log in, and open `/profile`. It shows ₹0.00 · 0 · —, the empty-state rows, and no errors.
4. Logged out: `/profile` redirects to `/login`.
5. `grep -nE "#[0-9a-fA-F]{3,6}\b|style=" templates/profile.html` returns no matches.
