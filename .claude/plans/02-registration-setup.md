# Plan: Step 02 — Registration

## Context

Spec: `.claude/specs/02-registration.md`. `/register` currently only renders `templates/register.html` (GET-only, `app.py:21-23`). The form already POSTs to `/register` and already has an `{% if error %}` block styled by `.auth-error` (`static/css/style.css:619`). Step 1 already provides the `users` table (`email UNIQUE`) and `get_db()` in `database/db.py`. Goal: a working sign-up that validates input, stores a werkzeug-hashed password, and redirects to `/login`. No login, sessions, or `secret_key`; those belong to Step 3.

## Reuse

- `database.db.get_db()`: connection with `sqlite3.Row` and foreign keys on (already imported in `app.py:3`)
- `werkzeug.security.generate_password_hash`: same function the seed uses (`database/db.py:5,73`)
- Existing `.auth-error`, `.form-input`, `.form-group` CSS, so **no CSS changes**

## Changes

### 1. `app.py`

**Imports**
- `from flask import Flask, render_template, request, redirect, url_for`
- `import sqlite3` (for `sqlite3.IntegrityError`)
- `from werkzeug.security import generate_password_hash`

**Route**: `@app.route("/register", methods=["GET", "POST"])`

1. **GET** → `render_template("register.html")` (unchanged behaviour).
2. **POST** reads and normalises the fields:
   - `name = request.form.get("name", "").strip()`
   - `email = request.form.get("email", "").strip().lower()`
   - `password = request.form.get("password", "")` (no strip, since spaces are valid password chars)
3. **Validate** in order and stop at the first error:
   - `not name` → "Please enter your name."
   - email invalid → "Please enter a valid email address." The rule: exactly one `@`, with non-empty local and domain parts. It's a small inline helper, `_is_valid_email(email)`, in `app.py`.
   - `len(password) < 8` → "Password must be at least 8 characters."
4. **Persist** with `conn = get_db()` inside `try/finally: conn.close()`:
   - Pre-check `SELECT 1 FROM users WHERE email = ?` → if a row exists, return the error "An account with this email already exists."
   - `INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)` with `generate_password_hash(password)`, then `conn.commit()`
   - Catch `sqlite3.IntegrityError` to handle a race on the UNIQUE constraint and return the same duplicate-email error.
5. **On error**: `render_template("register.html", error=msg, name=name, email=email), 400`
6. **On success**: `return redirect(url_for("login"))` (302, post/redirect/get)

Keep a single render helper path so error re-renders always pass `name` and `email` back. Never log or echo the password.

### 2. `templates/register.html`

- `name` input: add `value="{{ name or '' }}"`
- `email` input: add `value="{{ email or '' }}"`
- `password` input: add `minlength="8"` and **no** `value` attribute
- No other markup changes. Jinja autoescaping covers the echoed values, and the page still extends `base.html`.

### Out of scope (do not touch)

`/login` POST, sessions, `app.secret_key`, `/logout`, flash messages, navbar changes, CSS, and `database/db.py`.

## Edge cases covered

| Input | Result |
|---|---|
| `A@X.com` when `a@x.com` exists | duplicate error (lowercased before check) |
| `demo@spendly.com` | duplicate error (seeded user) |
| name `"   "` | name error |
| email `foo`, `@x.com`, `a@` | email error |
| 7-char password | password error, no row created |
| browser validation bypassed (curl) | server-side checks still apply |

## Verification

1. `python app.py`, then open http://localhost:5001/register; the form renders.
2. Register `Test User / test@example.com / password123`; you're redirected to `/login`.
3. Check the DB:
   `python -c "import sqlite3;c=sqlite3.connect('expense_tracker.db');print(c.execute(\"select name,email,password_hash from users where email='test@example.com'\").fetchall())"`
   The hash should start with `scrypt:` or `pbkdf2:` and not be the plain password.
4. Re-submit with `TEST@example.com`; you get the duplicate error, name and email are kept, and the password is blank.
5. Submit `demo@spendly.com`; you get the duplicate error.
6. Use curl to bypass HTML validation:
   - `curl -i -X POST -d "name=&email=a@b.com&password=password123" http://localhost:5001/register` → 400 + name error
   - `... -d "name=X&email=foo&password=password123"` → 400 + email error
   - `... -d "name=X&email=x@y.com&password=short"` → 400 + password error
7. Confirm the row count in `users` only increased once overall.
8. `git diff` touches only `app.py` and `templates/register.html`.
