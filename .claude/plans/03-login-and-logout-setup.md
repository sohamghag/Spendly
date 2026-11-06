# Plan: Step 03 — Login and Logout

## Context

Spec: `.claude/specs/03-login-and-logout.md`. Current state:
- `/login` (`app.py:73-75`) is GET-only and just renders `templates/login.html`. The form already POSTs to `/login` and has an `{% if error %}` block styled by `.auth-error` (`static/css/style.css:619`).
- `/logout` (`app.py:92-94`) is a placeholder string ("coming in Step 3").
- There is no `app.secret_key`, so sessions can't work yet.
- The navbar in `templates/base.html:21-24` always shows "Sign in" / "Get started".
- `/register` already redirects to `/login` on success (Step 2).

Goal: verify credentials against the werkzeug hash, keep `user_id` in the Flask session, make the navbar session-aware, and make logout clear the session. `/profile` stays the Step 4 placeholder and is only the redirect target.

## Reuse (no new helpers needed)

- `database.db.get_db()`: `sqlite3.Row` rows, so use `row["id"]` and `row["password_hash"]`.
- The Step 2 normalisation pattern in `register()` (`app.py:38`): `request.form.get("email", "").strip().lower()`. Registration stores lowercased emails, so a lowercased lookup matches.
- The Step 2 error re-render pattern: `render_template(..., error=msg, email=email), <status>`.
- `werkzeug.security`: `check_password_hash` sits alongside the existing `generate_password_hash` import.
- Existing CSS: `.auth-error`, `.form-input`, `.nav-links`, `.nav-cta`. **No CSS changes.**

## Changes

### 1. `app.py`

**Imports**
- `import os` (for `SECRET_KEY`)
- `from flask import Flask, render_template, request, redirect, url_for, session`
- `from werkzeug.security import generate_password_hash, check_password_hash`

**Secret key** (right after `app = Flask(__name__)`)
- `app.secret_key = os.environ.get("SECRET_KEY", "dev-only-insecure-key-change-me")`
- Add a one-line comment saying the fallback is for local development only.

**`/login` route**: `@app.route("/login", methods=["GET", "POST"])`
1. If `session.get("user_id")` is set (GET or POST), `redirect(url_for("profile"))`.
2. **GET** → `render_template("login.html")`.
3. **POST**:
   - `email = request.form.get("email", "").strip().lower()`
   - `password = request.form.get("password", "")` (don't strip it)
   - Local `fail(message, status)` helper, same shape as `register()`, which returns `render_template("login.html", error=message, email=email), status`.
4. **Validate**:
   - `not email or not password` → `fail("Please enter your email and password.", 400)`
5. **Look up the user** with `conn = get_db()` inside `try/finally: conn.close()`:
   - `SELECT id, password_hash FROM users WHERE email = ?` with `(email,)` → `fetchone()`
6. **Verify**: if `user is None or not check_password_hash(user["password_hash"], password)`, return `fail("Invalid email or password.", 401)`. Use the same message for both cases so emails can't be enumerated.
7. **Success**:
   - `session.clear()` (prevents session fixation)
   - `session["user_id"] = user["id"]`. Store only the id, never the email or hash.
   - `return redirect(url_for("profile"))` (302)

**`/logout` route** (replaces the placeholder; still GET):
- `session.clear()`
- `return redirect(url_for("landing"))`
- Move it out of the "Placeholder routes" section so it sits next to `/login`. The rest of that section (profile, expenses) stays untouched.

### 2. `templates/login.html`

- `email` input: add `value="{{ email or '' }}"`
- `password` input: no `value` attribute, so it is never re-populated
- Form `action="/login"` → `action="{{ url_for('login') }}"`
- Keep the `{% if error %}` block. No other markup changes.

### 3. `templates/base.html` (navbar only, lines 21-24)

```
{% if session.get("user_id") %}
    Profile  → url_for('profile')                     (plain link)
    Sign out → url_for('logout')  class="nav-cta"
{% else %}
    Sign in     → url_for('login')                    (unchanged)
    Get started → url_for('register') class="nav-cta" (unchanged)
{% endif %}
```
- Give "Sign out" the `nav-cta` class: the mobile media query (`style.css:809`) hides every non-`.nav-cta` nav link, and the signed-in user still needs a visible way to sign out on small screens.
- `session` is available in Jinja by default, so no context processor is needed.

### Out of scope (do not touch)

`/profile` content, the expense routes, `database/db.py`, CSS, flash messages, "remember me", `next=` redirects, a `login_required` decorator, and `register()` behaviour.

## Edge cases covered

| Input / situation | Result |
|---|---|
| `Demo@Spendly.com ` (case/whitespace) | logs in (lowercased + stripped) |
| wrong password | 401, "Invalid email or password." |
| unknown email | 401, same message |
| empty email or password (curl bypass) | 400, "Please enter your email and password." |
| already signed in, visits `/login` | redirect to `/profile` |
| `/logout` while signed out | still redirects to `/`, no error |
| failed submit | email kept, password blank |

## Verification

1. `python app.py` starts without errors. http://localhost:5001/login renders, and the navbar shows "Sign in" / "Get started".
2. Sign in with `demo@spendly.com` / `demo123`. You're redirected to `/profile` ("Profile page — coming in Step 4").
3. Go to `/`. The navbar shows "Profile" / "Sign out". Refresh, and it still does, so the session persists.
4. Visit `/login` while signed in. You're redirected to `/profile`.
5. Click "Sign out". You land on `/` and the navbar is back to "Sign in" / "Get started".
6. Sign in with `DEMO@spendly.com` (padded with spaces). It succeeds.
7. Wrong password, then an unknown email. Both show "Invalid email or password.", the email field is kept, and the password field is blank.
8. Register a new user via `/register`, then sign in with those credentials. It succeeds.
9. curl checks:
   - `curl -i -X POST -d "email=demo@spendly.com&password=" http://localhost:5001/login` → 400
   - `curl -i -X POST -d "email=demo@spendly.com&password=wrong" http://localhost:5001/login` → 401
   - `curl -i -X POST -d "email=demo@spendly.com&password=demo123" http://localhost:5001/login` → 302 `Location: /profile` plus a `Set-Cookie: session=...`
10. Shrink the browser to mobile width while signed in. "Sign out" is still visible.
11. `git diff` touches only `app.py`, `templates/login.html` and `templates/base.html` (plus the saved plan file).
