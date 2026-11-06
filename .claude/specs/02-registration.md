# Spec: Registration

## Overview

Turn the GET-only `/register` page into a working sign-up flow. A visitor submits name, email and password; the server validates them, stores a new user with a werkzeug-hashed password in the `users` table, and redirects to the login page. This is the first write path into the database and the prerequisite for login/logout (Step 3).

## Depends on

- Step 1 — Database setup (`users` table, `get_db()`, `init_db()` in `database/db.py`)

## Routes

- `GET /register` — render the registration form (already exists) — public
- `POST /register` — validate the form, create the user, redirect to `/login` on success; re-render the form with an error message on failure — public

No other new routes.

## Database changes

No database changes. The existing `users` table already has `name`, `email` (UNIQUE), `password_hash` and `created_at`. Duplicate emails are handled by checking first and by catching `sqlite3.IntegrityError` as a safety net.

## Templates

- **Create:** none
- **Modify:** `templates/register.html`
  - Re-populate `name` and `email` inputs after a failed submit (never the password)
  - Keep the existing `{% if error %}` block for error display
  - Add `minlength="8"` to the password input to match the placeholder

## Files to change

- `app.py` — change `/register` to accept `GET` and `POST`, add form handling; import `request`, `redirect`, `url_for` from Flask and `generate_password_hash` from werkzeug; import `sqlite3` for `IntegrityError`
- `templates/register.html` — as described above

## Files to create

None.

## New dependencies

No new dependencies (werkzeug ships with Flask).

## Rules for implementation

- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug (`generate_password_hash`); never store or log the plain password
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Implement only Step 2: do not add login, sessions, `secret_key`, or logout (Step 3)
- Server-side validation (do not rely on HTML attributes alone):
  - name: required, trimmed, non-empty
  - email: required, trimmed, lowercased, must contain `@` with text on both sides
  - password: required, at least 8 characters
- Normalise email to lowercase before the duplicate check and the insert
- Use `get_db()` and close the connection in a `finally` block
- On validation failure return the form with an `error` message and HTTP 200 (or 400); do not redirect
- On success redirect to `url_for('login')` after a 302 (post/redirect/get)

## Definition of done

- [ ] `GET /register` still renders the form
- [ ] Submitting valid name, a new email and an 8+ character password redirects to `/login`
- [ ] The new row exists in `users` and `password_hash` is a werkzeug hash, not the plain password
- [ ] Registering the same email again (including different letter case, e.g. `A@x.com` vs `a@x.com`) shows an error and creates no second row
- [ ] A password shorter than 8 characters shows an error and creates no row
- [ ] An empty or whitespace-only name shows an error and creates no row
- [ ] An invalid email (e.g. `foo`) shows an error and creates no row
- [ ] After a failed submit the name and email fields keep their values; the password field is empty
- [ ] The demo user (`demo@spendly.com`) cannot be re-registered
- [ ] The app starts with `python app.py` without errors
