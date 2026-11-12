# Plan: Step 8 — Edit Expense

Source spec: `.claude/specs/08-edit-expense.md` (branch `features/edit-expense`).
To be saved as: `.claude/plans/08-edit-expense-setup.md`.

## Context

`/expenses/<int:id>/edit` in `app.py:344` is a GET-only placeholder that returns a string.
In Step 8 it becomes a working GET + POST form, so a logged-in user can correct one of their
own expenses. Ownership is checked in SQL, and a missing expense or one owned by another user
returns 404. The profile transaction table gets an "Edit" link on each row. That link needs the
expense `id`, which `get_recent_transactions` does not return yet. There are no schema changes.
Delete stays a stub for Step 9.

## Reuse (already in the repo)

- `get_db()`, `CATEGORIES`: `database/db.py`
- `get_user_by_id`: `database/queries.py`. Same auth and stale-session guard as `add_expense()` in `app.py:297`
- `_validate_expense_form(values, today)`: `app.py:262`. It has the same rules as Add: finite amount > 0 and ≤ `MAX_AMOUNT`, category in `CATEGORIES`, valid non-future date, description ≤ 200 characters, blank description becomes `None`, amount rounded to 2 places. It returns `(cleaned, error)`, and `cleaned` already uses the `expense_date` key
- `create_expense`: `database/queries.py:31`. Its INSERT/commit/`finally` shape is the model for `update_expense`
- `templates/add_expense.html`: copy its markup and classes (`.auth-section`, `.auth-card`, `.auth-error`, `.form-group`, `.form-input`, `.form-actions`, `.btn-submit`, `.form-cancel`)

## Implementation steps

1. **`database/queries.py`**
   - `get_expense_by_id(expense_id, user_id)`: `SELECT id, amount, category, date, description FROM expenses WHERE id = ? AND user_id = ?`. Returns the row, or `None` if not found or owned by someone else. Close the connection in `finally`.
   - `update_expense(expense_id, user_id, amount, category, expense_date, description)`: `UPDATE expenses SET amount = ?, category = ?, date = ?, description = ? WHERE id = ? AND user_id = ?`, then `commit()`. Return `cur.rowcount` (0 means nothing was changed, and no error is raised). Close the connection in `finally`.
   - `get_recent_transactions`: add `id` to the `SELECT` and include `"id": r["id"]` in each returned dict.

2. **`app.py`**
   - Import `get_expense_by_id` and `update_expense`. Add `abort` to the flask imports.
   - Replace the placeholder with `@app.route("/expenses/<int:id>/edit", methods=["GET", "POST"])`:
     - Auth guard copied from `add_expense()`: no session sends the user to `login`, and a stale user clears the session and sends them to `login`. This runs before any DB lookup, so logged-out GET and POST both return 302 to `/login`.
     - `expense = get_expense_by_id(id, user_id)`. If it is `None`, call `abort(404)`. This applies to GET and POST.
     - GET: `values` is built from the stored row: amount, category, date, and description (`or ""`).
     - POST: build `values` from the stripped form fields the same way `add_expense()` does, then call `_validate_expense_form(values, today)`. On success, call `update_expense(id, user_id, **cleaned)` and redirect to `url_for("profile")`.
     - Render `edit_expense.html` with `expense`, `categories=CATEGORIES`, `today`, `description_max=DESCRIPTION_MAX_LENGTH`, `error`, and `values`. **Status 200 on validation errors**, as the spec's route tests require. (Add uses 400. The spec explicitly asks for 200 here.)
   - `user_id` comes only from `session`. Leave the `delete_expense` placeholder untouched.

3. **`templates/edit_expense.html`** (new file, extends `base.html`): a copy of `add_expense.html` with these changes:
   - Title and heading say "Edit expense".
   - `action="{{ url_for('edit_expense', id=expense.id) }}"` with `method="POST"`.
   - The fields are pre-filled from `values`, so a failed POST shows the submitted values and not the stored ones. The selected category comes from `values.category`.
   - The submit button says "Save Changes", and Cancel links to `url_for('profile')`. No inline styles.

4. **`templates/profile.html`**
   - Add `<th>Actions</th>` to the header.
   - Add `<td><a href="{{ url_for('edit_expense', id=t.id) }}" class="txn-edit">Edit</a></td>` to each row.
   - Change the empty-state row to `colspan="5"`.

5. **`static/css/style.css`**: add a small `.txn-edit` link style that uses existing colour variables only (no hex values).

## Out of scope

Running tests or pytest. The spec's "Tests to write" section (`tests/test_edit_expense.py`) is handled separately through `/text-feature 08-edit-expense`. Also out of scope: the delete route, schema changes, and other stubs.

## Verification (manual: `python app.py`, http://localhost:5001)

Work through the spec's Definition of done:
- While logged out, `/expenses/1/edit` redirects to `/login`.
- Log in as `demo@spendly.com` / `demo123`. Each transaction row has an Edit link pointing to the correct `/expenses/<id>/edit`.
- The edit page shows the current amount, date and description, and the right category is selected.
- Submitting valid changes redirects to `/profile`. The updated values appear, and the totals and category breakdown update.
- A missing or zero amount, a bad category (edit the HTML in devtools), or an invalid date shows an error and keeps the submitted values. The DB row stays unchanged.
- A blank description saves as `NULL`.
- Editing another user's expense id, or an id that does not exist, returns 404.
- `/expenses/add` still works, and `/expenses/<id>/delete` still returns its placeholder text.
