# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

"Spendly" — a Flask + SQLite expense tracker built as a step-by-step teaching project. Many parts are intentionally stubs that get implemented in numbered steps (the stubs name their step, e.g. "coming in Step 7"). Implement only the step being asked for; don't fill in other stubs.

## Commands

```bash
python -m venv .venv && .venv\Scripts\activate   # Windows; .venv is gitignored
pip install -r requirements.txt
python app.py                                    # dev server on http://localhost:5001 (debug=True)
pytest                                           # all tests (pytest + pytest-flask are installed)
pytest path/to/test_file.py::test_name           # single test
```

No tests, linter, or build step exist yet (there is no `tests/` directory).

## Architecture

- `app.py` — single Flask app; all routes live here. Implemented routes only render templates (`/`, `/register`, `/login`, `/terms`, `/privacy`). `/logout`, `/profile`, `/expenses/add`, `/expenses/<id>/edit`, `/expenses/<id>/delete` are placeholder routes returning plain strings. Note `/register` and `/login` are GET-only so far (no form handling or auth/session yet).
- `database/db.py` — currently only a comment describing the intended contract: `get_db()` (SQLite connection with `row_factory` and foreign keys enabled), `init_db()` (`CREATE TABLE IF NOT EXISTS`), `seed_db()` (sample dev data). The SQLite file is expected to be `expense_tracker.db` (gitignored).
- `templates/base.html` — all pages extend this; it defines the `title`, `head`, `content`, and `scripts` blocks, the navbar, and the footer (with Terms/Privacy links). Page-specific CSS/JS goes in the `head`/`scripts` blocks.
- `static/css/style.css`, `static/js/main.js` — shared styling and JS (`main.js` is empty so far). Branding is "Spendly" with rupee-oriented copy.
