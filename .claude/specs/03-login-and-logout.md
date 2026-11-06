# Spec: Login and Logout

## Overview

Turn the GET-only `/login` page into a working sign-in flow and replace the `/logout` placeholder with a real sign-out. A visitor submits email and password; the server verifies them against the werkzeug hash stored in `users`, stores the user's id in the Flask session, and redirects to the profile page. Logout clears the session. This introduces sessions (and a `secret_key`) for the first time and makes the navbar aware of whether the user is signed in. It follows Registration, which already redirects to `/login` on success.

## Depends on

- Step 1 — Database setup (`users` table, `get_db()`)
- Step 2 — Registration (users with hashed passwords can be created; redirects to `/login`)

## Routes

- `GET /login` — render the sign-in form (already exists); if already signed in, redirect to `/profile` — public
- `POST /login` — validate credentials, set `session["user_id"]`, redirect to `/profile` on success; re-render the form with an error on failure — public
- `GET /logout` — clear the session and redirect to `/` (replaces the "coming in Step 3" placeholder) — logged-in (harmless if not signed in: still redirects to `/`)

No other new routes. `/profile` remains the Step 4 placeholder and is only used as the redirect target.

## Database changes

No database changes. The existing `users` table (`id`, `name`, `email` UNIQUE, `password_hash`) is sufficient.

## Templates

- **Create:** none
- **Modify:**
  - `templates/login.html` — post to `{{ url_for('login') }}`; re-populate the `email` input after a failed submit (never the password); keep the existing `{% if error %}` block
  - `templates/base.html` — navbar: if `session.get("user_id")` is set, show "Profile" (`url_for('profile')`) and "Sign out" (`url_for('logout')`) instead of "Sign in" / "Get started"; otherwise keep the current links

## Files to change

- `app.py` — import `session` from Flask and `check_password_hash` from werkzeug; set `app.secret_key`; make `/login` accept `GET` and `POST` with form handling; implement `/logout`
- `templates/login.html` — as described above
- `templates/base.html` — as described above

## Files to create

None.

## New dependencies

No new dependencies (sessions and password checking ship with Flask/werkzeug).

## Rules for implementation

- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug; verify with `check_password_hash`, never compare plain text, never store or log the plain password
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Implement only Step 3: do not implement `/profile` content, expenses routes, or other stubs
- `app.secret_key` read from the `SECRET_KEY` environment variable, with a clearly-labelled dev-only fallback string; never commit a real secret
- Server-side validation:
  - email: trimmed and lowercased before lookup
  - password: required (non-empty)
- Use one generic error ("Invalid email or password.") for both unknown email and wrong password, so accounts cannot be enumerated
- On failure re-render the form with `error` and HTTP 400/401; do not redirect
- On success call `session.clear()` before setting `session["user_id"]` (avoids session fixation), then redirect (302) to `url_for('profile')`
- Store only the user id in the session, not the hash or email
- Logout must call `session.clear()` and redirect to `url_for('landing')`
- Use `get_db()` and close the connection in a `finally` block
- Do not add an open-redirect `next` parameter in this step

## Definition of done

- [ ] `GET /login` renders the form
- [ ] Signing in as `demo@spendly.com` / `demo123` redirects to `/profile` (shows the Step 4 placeholder text)
- [ ] Email is case-insensitive (`Demo@Spendly.com` also works) and surrounding whitespace is ignored
- [ ] A wrong password shows "Invalid email or password." and the user is not signed in
- [ ] An unknown email shows the same "Invalid email or password." message
- [ ] An empty password shows an error and the user is not signed in
- [ ] After a failed submit the email field keeps its value; the password field is empty
- [ ] A user registered via `/register` can sign in with the credentials they chose
- [ ] While signed in, the navbar shows "Profile" and "Sign out" and hides "Sign in" / "Get started"
- [ ] While signed out, the navbar shows "Sign in" and "Get started"
- [ ] Visiting `/login` while signed in redirects to `/profile`
- [ ] `/logout` clears the session, redirects to `/`, and the navbar returns to the signed-out links
- [ ] The session persists across page loads until logout (refresh `/` while signed in; navbar still shows "Sign out")
- [ ] The app starts with `python app.py` without errors
