# Spec: Add Expense

## Overview

Step 7 replaces the `/expenses/add` placeholder with a working form so a
logged-in user can record a new expense (amount, category, date, optional
description). Until now the only expenses in the app are the seeded demo rows;
this step makes the profile page's summary stats, transaction list, and category
breakdown reflect real user input. On success the user is redirected to
`/profile` where the new expense appears. Editing and deleting expenses remain
stubs for Steps 8 and 9.

## Depends on

- Step 1: Database setup (`expenses` table and `CATEGORIES` list in `database/db.py`)
- Step 3: Login and logout (`session["user_id"]` identifies the current user)
- Step 4/5: Profile page backed by the database (so the new expense is visible)

## Routes

- `GET /expenses/add` — render the add-expense form (date defaults to today) — logged-in
- `POST /expenses/add` — validate and insert the expense, then redirect to `/profile` — logged-in

Unauthenticated requests to either method redirect to `/login`. A stale session
(user row no longer exists) clears the session and redirects to `/login`,
matching the `profile()` behaviour.

## Database changes

No database changes. The existing `expenses` table
(`id, user_id, amount REAL, category, date TEXT, description, created_at`)
already supports this feature. Categories come from the existing `CATEGORIES`
list in `database/db.py`.

## Templates

- **Create:** `templates/add_expense.html` — form with fields `amount`
  (number, step 0.01, min 0.01), `category` (select populated from
  `CATEGORIES`), `date` (`type="date"`, defaults to today), `description`
  (optional text); inline error banner; Cancel link back to `/profile`
- **Modify:** `templates/profile.html` — add an "Add expense" link/button that
  uses `url_for('add_expense')`

## Files to change

- `app.py` — replace the `add_expense` placeholder with a GET/POST view; import
  `CATEGORIES` from `database.db`
- `database/queries.py` — add `create_expense(user_id, amount, category, date, description)`
  (raw parameterised INSERT via `get_db()`)
- `templates/profile.html` — add the "Add expense" entry point
- `static/css/style.css` — styles for the add-expense form, reusing existing
  `.auth-*`/`.form-*` patterns where possible

## Files to create

- `templates/add_expense.html`

## New dependencies

No new dependencies.

## Rules for implementation

- No SQLAlchemy or ORMs — raw `sqlite3` only via `get_db()`
- Parameterised queries only — never string-format values into SQL
- Passwords hashed with werkzeug (no auth changes in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline styles
- `user_id` always comes from `session`, never from the form
- Server-side validation (re-render the form with an error and HTTP 400,
  preserving the entered values):
  - `amount` must parse as a number, be finite, and be greater than 0; round
    to 2 decimal places
  - `category` must be one of `CATEGORIES`
  - `date` must parse with `datetime.strptime(value, "%Y-%m-%d")`; reject
    dates in the future
  - `description` is optional, stripped, max 200 characters; store `NULL`
    (not empty string) when blank
- Reuse the existing `_parse_iso_date` helper in `app.py` for date parsing
- Always close the DB connection in a `finally` block
- Implement only Step 7; leave edit/delete placeholders untouched

## Definition of done

- [ ] Visiting `/expenses/add` while logged out redirects to `/login`
- [ ] Visiting `/expenses/add` while logged in shows the form with today's date
      pre-filled and all seven categories in the dropdown
- [ ] Submitting valid data redirects to `/profile` and the new expense appears
      in the transaction list with the ₹ symbol
- [ ] Summary stats (total spent, transaction count) and the category breakdown
      on `/profile` update to include the new expense
- [ ] The expense is stored against the logged-in user and is not visible to
      other users
- [ ] Submitting an empty, zero, negative, or non-numeric amount shows an error
      and saves nothing
- [ ] Submitting a category not in the list (e.g. via edited HTML) shows an
      error and saves nothing
- [ ] Submitting a malformed or future date shows an error and saves nothing
- [ ] After a failed submission the previously entered values are still in the
      form
- [ ] A blank description saves successfully (stored as `NULL`)
- [ ] A description over 200 characters is rejected with an error
- [ ] The profile page has a working "Add expense" link to this form
- [ ] The app starts without errors and `/expenses/<id>/edit` and
      `/expenses/<id>/delete` still return their placeholder text
