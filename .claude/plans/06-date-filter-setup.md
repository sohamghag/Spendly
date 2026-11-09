# Plan: Step 06 — Date Filter for Profile Page

## Context

Spec: `.claude/specs/06-date-filter-for-profile.md`. Right now `/profile` (`app.py:122-139`) always shows all-time data. This step adds a date-range filter driven by the `date_from` and `date_to` query-string parameters. It also adds a filter bar with four presets ("This Month", "Last 3 Months", "Last 6 Months", "All Time") and a custom range form. All three data sections (stats, transactions, category breakdown) follow the active filter. There are no new routes and no DB changes.

Current state:

- `database/queries.py` has `get_summary_stats(user_id)`, `get_recent_transactions(user_id, limit=10)` and `get_category_breakdown(user_id)`. Each one opens `get_db()`, runs parameterised SQL with `WHERE user_id = ?`, and closes the connection in `finally`.
- `expenses.date` is ISO `YYYY-MM-DD` text, so `BETWEEN ? AND ?` compares correctly.
- `app.secret_key` is set, so `flash()` works. However, `base.html` doesn't render flashed messages anywhere.
- All profile CSS lives in `static/css/style.css` (lines ~758-1003), and the CSS variables are defined in `:root` (`--accent`, `--accent-light`, `--border`, `--danger`, `--danger-light`, `--radius-sm`, etc.).

### Spec issues and how this plan resolves them

1. **`static/css/profile.css` doesn't exist.** The spec lists it under "Files to change" and also says "No new files". All profile styles are already in `style.css`, so the filter bar styles go there and no new file is created.
2. **Flash rendering.** `base.html` has no flash block. The plan calls `flash(...)` in the view and renders `get_flashed_messages()` inside `profile.html` only, which keeps the change scoped. Flash messages queued during a request can be read during that same render, so the message appears right away.
3. **Loose date parsing.** `strptime("%Y-%m-%d")` also accepts values like `2026-1-5`, which would break string comparison in SQL. The plan normalises every parsed value with `.isoformat()` before using it.
4. **Only one date supplied.** The spec says to use `BETWEEN` only when both dates are given, and to fall back to "All Time" if either is absent or malformed. The plan follows that: if only one date is valid, no filter is applied.

## Changes

### 0. Save this plan

Copy this plan to `.claude/plans/06-date-filter-setup.md`. The repo's existing folder is `.claude/plans/` (plural), which already holds plans 01-05, so it goes there rather than in a new `.claude/plan/` folder.

### 1. `database/queries.py`: optional date range

Add a small private helper:

```python
def _date_clause(date_from, date_to):
    if date_from and date_to:
        return " AND date BETWEEN ? AND ?", (date_from, date_to)
    return "", ()
```

Then extend each helper with `date_from=None, date_to=None` and append the clause right after `WHERE user_id = ?`, adding its params:

- `get_summary_stats(user_id, date_from=None, date_to=None)`: both queries (totals and top category) get the clause.
- `get_recent_transactions(user_id, limit=10, date_from=None, date_to=None)`: the clause goes before `ORDER BY`. The params become `(user_id, *range, limit)`. Ordering and limit stay the same.
- `get_category_breakdown(user_id, date_from=None, date_to=None)`: the clause goes before `GROUP BY`. The percentage logic stays the same.

The SQL clause is a fixed string, and the values are always passed as `?` params. With no dates, the SQL is identical to Step 5. No Flask imports.

### 2. `app.py`: `profile()` and preset helpers

- Import `flash` from flask, and `date`/`datetime` from datetime.
- `_parse_iso_date(value)` → `date` or `None`. It tries `datetime.strptime(value, "%Y-%m-%d").date()` and returns `None` on `ValueError`/`TypeError`.
- `_months_ago(d, n)` → the same day `n` months earlier, clamped to the last day of the target month (uses `calendar.monthrange`). This avoids adding a dependency.
- `_date_presets(today)` → an ordered list of `{label, date_from, date_to}` (ISO strings or `None`):
  - This Month: `today.replace(day=1)` → `today`
  - Last 3 Months: `_months_ago(today, 3)` → `today`
  - Last 6 Months: `_months_ago(today, 6)` → `today`
  - All Time: `None`, `None`
- In `profile()`, after the auth and stale-session checks:
  1. Parse `request.args.get("date_from")` and `request.args.get("date_to")`.
  2. If both are valid and `from > to`, call `flash("Start date must be before end date.")` and treat both as absent.
  3. If both are valid, convert them with `.isoformat()`. Otherwise set both to `None`.
  4. Pass `date_from`/`date_to` to all three query helpers.
  5. Build the presets. Each preset gets a `url` (`url_for("profile", date_from=..., date_to=...)`, or plain `url_for("profile")` for All Time) and an `active` flag (its range equals the active range).
  6. Set `custom_active = date_from is not None and no preset is active`.
  7. Render the template with the existing variables plus `presets`, `date_from`, `date_to` and `custom_active`.

### 3. `templates/profile.html`: filter bar

Add a `<div class="filter-bar">` between `.profile-card` and `.profile-stats`:

- **Flash messages:** `{% with msgs = get_flashed_messages() %}`, rendered as `<p class="filter-error">` items.
- **Presets:** `<nav class="filter-presets">` loops over `presets`, rendering `<a href="{{ p.url }}" class="filter-preset{% if p.active %} is-active{% endif %}">`. All URLs come from the view (`url_for`), so none are hardcoded.
- **Custom range:** `<form method="get" action="{{ url_for('profile') }}" class="filter-custom{% if custom_active %} is-active{% endif %}">` with two labelled `<input type="date">` fields, `name="date_from"`/`name="date_to"`, prefilled with `value="{{ date_from or '' }}"`/`value="{{ date_to or '' }}"`, and an "Apply" submit button.

Existing sections are unchanged. ₹ formatting is untouched. No inline styles.

### 4. `static/css/style.css`: filter bar styles

Add the following next to the profile block, using CSS variables only (no hex values):

- `.filter-bar`: card styling matching `.profile-panel` (`--paper-card`, `--border`, `--radius-md`). Flex and wrap, with the presets on the left and the custom form on the right.
- `.filter-preset`: pill links (`--border`, `--ink-soft`, `--radius-sm`).
- `.filter-preset.is-active`: `--accent` background, `--paper-card` text.
- `.filter-custom` inputs (`--border`, `--font-body`) and an Apply button reusing the `.btn-submit` look. `.filter-custom.is-active` gets an `--accent` border or outline.
- `.filter-error`: `--danger` text on `--danger-light`.
- Inside the existing `@media (max-width: 600px)`, stack the presets and the form vertically.

### Out of scope

Expense add/edit/delete (Steps 7–9), one-sided date filters, flash rendering in `base.html`, schema or seed changes, and tests. Tests come later via `/text-feature`.

## Verification

1. `python app.py`, then log in as `demo@spendly.com` / `demo123`.
2. `/profile` with no params shows the same totals, rows and categories as before. "All Time" is highlighted.
3. **This Month:** the URL contains `date_from=<YYYY-MM-01>&date_to=<today>`, and all three sections only include this month's expenses. The button is highlighted.
4. **Last 3 / Last 6 Months:** the URLs start 3 or 6 months before today. Data matches the window and the right button is highlighted.
5. **All Time:** the URL goes back to a bare `/profile`.
6. **Custom range:** a range around 2-3 seed expenses filters all sections to them, including the boundary dates. The inputs stay prefilled and the custom form is highlighted.
7. `/profile?date_from=2026-12-01&date_to=2026-01-01` shows "Start date must be before end date." and unfiltered data.
8. `/profile?date_from=not-a-date&date_to=2026-11-09` returns 200 with unfiltered data and no crash.
9. A range with no expenses (e.g. 2020-01-01 to 2020-01-31) shows ₹0.00, 0, "—" and the empty states.
10. `/profile?date_from=' OR 1=1 --&date_to=2026-11-09` returns 200 with unfiltered data, and no other users' data appears.
11. Logged out: `/profile?date_from=...` redirects to `/login`.
12. `grep -nE "#[0-9a-fA-F]{3,6}\b|style=" templates/profile.html` returns no matches.
13. Existing tests still pass: `pytest`.
