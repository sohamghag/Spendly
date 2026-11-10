# Plan: Step 7 — Add Expense

Source spec: `.claude/specs/07-add-expense.md` (branch `features/add-expense`).

## Context

`/expenses/add` in `app.py:257` is a placeholder string. Step 7 makes it a real
logged-in form (GET renders, POST validates + inserts + redirects to `/profile`)
so the profile page's stats, transaction list and category breakdown reflect
user-entered data. Edit/delete stay stubs (Steps 8/9). No schema changes.

## Reuse (already in the repo)

- `get_db()`, `CATEGORIES` — `database/db.py`
- `get_user_by_id` — `database/queries.py` (stale-session check, same pattern as `profile()` / `analytics()` in `app.py`)
- `_parse_iso_date` — `app.py:137`
- Form markup/CSS: `.auth-section`, `.auth-container`, `.auth-card`, `.auth-error`, `.form-group`, `.form-input`, `.btn-submit` (`style.css` ~581–684); template pattern from `templates/login.html`
- Colour tokens in `:root` (`style.css:5`) — use variables only

## Implementation steps

1. **`database/queries.py`** — add `create_expense(user_id, amount, category, date, description)`:
   `get_db()`, `INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)`,
   `commit()`, close in `finally`. Return `lastrowid`.

2. **`app.py`**
   - Import `CATEGORIES` from `database.db` and `create_expense` from `database.queries`.
   - Replace placeholder with `@app.route("/expenses/add", methods=["GET", "POST"])`:
     - Auth guard: no `session["user_id"]` → redirect `login`; `get_user_by_id` is None → `session.clear()` + redirect `login`.
     - GET: render `add_expense.html` with `categories=CATEGORIES`, `today=date.today().isoformat()`, and defaults.
     - POST: read `amount`, `category`, `date`, `description` (strip). Local `fail(message)` helper re-renders with error + entered values, status 400 (mirrors `register()`).
       - amount: `float()` in try/except; reject non-finite (`math.isfinite`) and `<= 0`; `round(…, 2)`.
       - category: must be in `CATEGORIES`.
       - date: `_parse_iso_date`; reject None and `> date.today()`.
       - description: max 200 chars; `None` if blank.
     - On success: `create_expense(session["user_id"], …)` then `redirect(url_for("profile"))`. `user_id` only from session.
   - Leave `edit_expense` / `delete_expense` placeholders untouched.

3. **`templates/add_expense.html`** (extends `base.html`, modeled on `login.html`): title block, error banner (`.auth-error`), form `method="POST" action="{{ url_for('add_expense') }}"` with amount (`type=number step=0.01 min=0.01 required`), category `<select>` looping `categories` (selected = submitted value), date (`type=date`, `max=today`, value defaults to today), description (`maxlength=200`, optional), submit button + Cancel link to `url_for('profile')`. No inline styles.

4. **`templates/profile.html`** — add an "Add expense" link (`url_for('add_expense')`), e.g. in the transactions panel header or near the filter bar, styled with existing `.btn-primary`.

5. **`static/css/style.css`** — small additions only if needed (select styling to match `.form-input`, form action row for submit + cancel, profile "Add expense" placement). CSS variables only, no hex.

## Out of scope

Edit/delete routes, new tests (not requested), schema changes, other stubs.

## Verification (run the app: `python app.py`, http://localhost:5001)

Walk the spec's Definition of done:
- Logged out → `/expenses/add` redirects to `/login`.
- Log in as `demo@spendly.com` / `demo123`; form shows today's date and all 7 categories.
- Valid submit → redirects to `/profile`; new row visible with ₹; total, count, category breakdown update.
- Invalid amount (empty/0/negative/`abc`), bad category (edit HTML in devtools), malformed/future date, description >200 chars → error shown, nothing saved, entered values preserved.
- Blank description saves (check `description IS NULL` in `expense_tracker.db`).
- A second user does not see the new expense.
- "Add expense" link on profile works; `/expenses/1/edit` and `/delete` still return placeholder text; app starts without errors.
