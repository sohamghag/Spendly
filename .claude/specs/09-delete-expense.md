# Spec: Delete Expense

## Overview

Step 9 lets a logged-in user delete any of their own expenses. Each row in the
profile transactions table gains a "Delete" button that submits a small POST
form to `/expenses/<id>/delete`. The handler removes the row (scoped to the
owner), then redirects back to `/profile`. Deletion is a state-changing action,
so it is POST-only (the Step 1 GET placeholder is removed) and guarded by a
browser confirmation prompt. One new query helper, `delete_expense`, is added
to `database/queries.py`. This completes the add / edit / delete expense CRUD
set on the roadmap.

## Depends on

- Step 1: Database setup (`expenses` table exists)
- Step 3: Login / Logout (`session["user_id"]` is set and enforced)
- Step 5: Profile page renders transactions, including `id` (the delete button lives there)
- Step 8: Edit Expense (establishes the ownership-check and 404 pattern and the Actions column)

## Routes

- `POST /expenses/<int:id>/delete` — delete the expense if it belongs to the
  current user, then redirect to `/profile` — logged-in only

The existing GET placeholder at this path is replaced; `GET` is no longer
allowed (Flask returns 405).

## Database changes

No database changes. The existing `expenses` table is sufficient.

## Templates

- **Create:** none
- **Modify:** `templates/profile.html`
  - In the existing Actions cell for each transaction row, next to the Edit link,
    add a `<form method="POST" action="{{ url_for('delete_expense', id=t.id) }}">`
    containing a submit button labelled "Delete"
  - Give the form a class (e.g. `txn-delete-form`) so `main.js` can attach the
    confirmation prompt; no inline `onsubmit` or inline styles

## Files to change

- `database/queries.py`
  - Add `delete_expense(expense_id, user_id)` — parameterised
    `DELETE FROM expenses WHERE id = ? AND user_id = ?`; commits; returns the
    number of rows deleted
- `app.py`
  - Import `delete_expense` from `database.queries`
  - Replace the placeholder with a POST-only route:
    `@app.route("/expenses/<int:id>/delete", methods=["POST"])`
    - Not logged in → redirect to `/login`
    - Stale session (user row missing) → clear session, redirect to `/login`
    - Call `delete_expense(id, user_id)`; if 0 rows were deleted (missing or
      owned by another user) → `abort(404)`
    - On success redirect to `url_for("profile")`
  - Remove the "Placeholder routes" comment block if it becomes empty
- `templates/profile.html` — add the Delete form as described above
- `static/js/main.js` — add a `submit` listener for `.txn-delete-form` that calls
  `confirm("Delete this expense? This cannot be undone.")` and
  `preventDefault()` if the user cancels
- `static/css/style.css` — style the Delete button (danger look) and make the
  inline form sit beside the Edit link, using existing CSS variables

## Files to create

None.

## New dependencies

No new dependencies.

## Rules for implementation

- No SQLAlchemy or ORMs — raw `sqlite3` only via `get_db()`
- Parameterised queries only — never string-format values into SQL
- Passwords hashed with werkzeug (no password handling changes in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- `delete_expense` must scope its `WHERE` to both `id` and `user_id` so one user
  can never delete another user's expense
- Deletion must be POST-only — never delete on GET
- Unknown id or another user's expense → 404, and the other user's row is untouched
- Unauthenticated POST redirects to `/login` and deletes nothing
- No inline styles and no inline JS handlers
- Currency must always display as ₹ — never £ or $
- Do not implement any other stub or change other routes

## Definition of done

- [ ] Each row in the profile transaction table shows a "Delete" button beside "Edit"
- [ ] Clicking Delete shows a confirmation prompt; cancelling leaves the expense in place
- [ ] Confirming deletes the expense, redirects to `/profile`, and the row (and updated totals / category breakdown) no longer appear
- [ ] A POST to `/expenses/<id>/delete` while logged out redirects to `/login` and the expense still exists
- [ ] A POST for a non-existent id returns 404
- [ ] A POST for another user's expense returns 404 and that expense still exists
- [ ] A GET to `/expenses/<id>/delete` returns 405 and deletes nothing
- [ ] Deleting an expense while a date filter is active still redirects to `/profile` without error
- [ ] The app starts with `python app.py` with no errors and the Edit/Add flows still work
