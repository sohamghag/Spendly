# Plan: Step 1 — Database Setup

Spec: `.claude/specs/01-database-setup.md`

## Context
`database/db.py` is a comment-only stub and `app.py` has no DB wiring. All later steps (auth, profile, expenses) need a working SQLite layer. This step implements `get_db()`, `init_db()`, `seed_db()` and calls them on app startup. No new routes, files, or packages. Other stubs stay untouched.

## Files to change
1. `database/db.py` — replace stub
2. `app.py` — imports + startup calls

## `database/db.py`
- Imports: `sqlite3`, `os`, `datetime.date`, `werkzeug.security.generate_password_hash`.
- `DB_PATH` = `expense_tracker.db` in project root, computed from `__file__` (gitignored per CLAUDE.md), so it is independent of the working directory.
- `CATEGORIES` constant: Food, Transport, Bills, Health, Entertainment, Shopping, Other (reusable in later steps).
- `get_db()`: `sqlite3.connect(DB_PATH)`, `row_factory = sqlite3.Row`, `PRAGMA foreign_keys = ON`, return connection.
- `init_db()`: `CREATE TABLE IF NOT EXISTS` for
  - `users`: id INTEGER PK AUTOINCREMENT, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL, created_at TEXT DEFAULT (datetime('now'))
  - `expenses`: id INTEGER PK AUTOINCREMENT, user_id INTEGER NOT NULL REFERENCES users(id), amount REAL NOT NULL, category TEXT NOT NULL, date TEXT NOT NULL, description TEXT, created_at TEXT DEFAULT (datetime('now'))
  - Commit and close; safe to repeat.
- `seed_db()`:
  - `SELECT COUNT(*) FROM users`; return early if > 0.
  - Insert demo user (Demo User, demo@spendly.com, `generate_password_hash("demo123")`) with `?` placeholders; get `cursor.lastrowid`.
  - `executemany` 8 expenses, all parameterized, float amounts. Dates via `date.today().replace(day=N).isoformat()` with N in 1–28 (always valid, YYYY-MM-DD, spread over the current month).
  - Categories: one each of the 7 categories plus one extra Food (8 total), with short descriptions.
  - Commit and close.
- Use try/finally so connections always close; let sqlite errors propagate (IntegrityError for duplicate email / bad FK).

## `app.py`
- Add `from database.db import get_db, init_db, seed_db` (`get_db` imported per spec, unused for now).
- After `app = Flask(__name__)`: `with app.app_context(): init_db(); seed_db()`.
- Leave all routes and placeholders unchanged.

## Notes
- Startup calls run at import time, so with the debug reloader they run twice. That is harmless because both functions are idempotent.
- The spec's code snippet `fromwerkzeug.securityimportgenerate_password_hash` has lost its spaces. The intended statement is `from werkzeug.security import generate_password_hash`.

## Verification
1. `python app.py` starts cleanly and `expense_tracker.db` appears in the project root.
2. Throwaway script (in the scratchpad, not the repo) checks:
   - Both tables exist with the right columns.
   - 1 user, and `check_password_hash(hash, "demo123")` is true.
   - 8 expenses, all 7 categories present, all dates match `YYYY-MM-DD` and fall in the current month.
3. Call `init_db(); seed_db()` again: counts stay at 1 user and 8 expenses.
4. Inserting a duplicate email raises `sqlite3.IntegrityError`. Inserting an expense with `user_id=999` raises `sqlite3.IntegrityError` (FK enforced).
5. Flask test client: `/`, `/login`, `/register`, `/terms`, `/privacy` still return 200.
6. Grep `database/db.py` for f-strings or `%`/`.format` near SQL to confirm only parameterized queries.
