# Spec: Analysis Design

## Overview

Step 10 replaces the "Coming Soon" placeholder at `/analytics` with the full
analytics page designed in Figma (file `foOogSp4D5NouI09SQJuns`, node `2:2`).
The page shows, for the logged-in user: a greeting header, three summary cards
(Total Expense, Total Income, Total Savings), a monthly budget progress bar, a
six-month income-vs-expense bar chart, a "Where your money goes" donut chart
with a category list, and a table of the latest 8 transactions. Expense data is
real and comes from the `expenses` table. The schema has no income or budget
data and must not change, so income and the monthly budget are fixed demo
values defined in `app.py` and labelled as demo values in the UI, exactly as
the Figma design does.

## Depends on

- Step 1: Database setup (`users` and `expenses` tables, `get_db()`)
- Step 3: Login / Logout (`session["user_id"]`)
- Step 5: Backend routes for profile page (`get_summary_stats`,
  `get_recent_transactions`, `get_category_breakdown` in `database/queries.py`)
- Step 6: Date filter for profile (the `date_from` / `date_to` query helpers)

## Routes

No new routes. The existing `GET /analytics` (logged-in only) changes from
rendering a static stub to computing and passing real data to the template.
Unauthenticated and stale-session behaviour is unchanged (redirect to `/login`).

## Database changes

No database changes. `database/db.py` defines only `users` and `expenses`;
there is no income, savings or budget storage, and none is added. Those values
are demo constants (see Rules).

## Templates

- **Modify:** `templates/analytics.html`
  - Remove the Coming Soon card markup; keep `{% extends "base.html" %}`
  - `head` block: load Inter (400/500/600/700) and the Chart.js CDN script
    (pinned version, loaded with `defer`)
  - `content` block, in this order: greeting, summary cards, monthly budget,
    income-vs-expense chart card, category breakdown card, recent
    transactions card, demo footnote
  - `scripts` block: vanilla JS that builds the two charts from JSON embedded
    via `{{ data|tojson }}` in a `<script type="application/json">` tag
  - Do not duplicate the navbar or footer; they come from `base.html`
- **Create:** none (icons are static SVG files, see below)

## Files to change

- `app.py`
  - Add constants `DEMO_MONTHLY_INCOME = 35_000` and `MONTHLY_BUDGET = 20_000`
  - Import the new query helper(s) from `database.queries`
  - Extend the `analytics()` view to compute: current-month summary, budget
    used / remaining / percent, 6-month series, current-month category
    breakdown, and the latest 8 transactions, and pass them to the template
- `database/queries.py`
  - Add `get_monthly_totals(user_id, months=6, today=None)` returning one
    `{"label", "year_month", "expense"}` dict per month, oldest first, with
    `0` for months that have no expenses
  - Reuse `get_summary_stats`, `get_category_breakdown` and
    `get_recent_transactions(limit=8)` with the current month's
    `date_from` / `date_to`; do not duplicate their SQL
- `templates/analytics.html` (see Templates)
- `static/css/style.css`
  - Remove the now-unused Coming Soon (`cs-*`) rules and the `--cs-*`
    variables; add the analytics styles in a clearly commented section
  - Add the analytics colour tokens as CSS variables under `:root`

## Files to create

- `static/img/analytics/` — SVG icons exported from the Figma design (metric
  icons: expense, income, savings; calendar; the seven category icons).
  Downloaded with the Figma MCP asset URLs; no temporary Figma URLs may remain
  in code.

## New dependencies

No new pip packages. Chart.js is loaded from a CDN (`cdn.jsdelivr.net` or
`cdnjs.cloudflare.com`) with an exact pinned version. No other JS framework.

## Rules for implementation

- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug (no auth changes in this step)
- Use CSS variables — never hardcode hex values outside `:root`. Hex values
  for the analytics palette live only in the `:root` token block, e.g.
  `--an-bg #f6f8fa`, `--an-surface #ffffff`, `--an-border #e6edec`,
  `--an-primary #087f70`, `--an-primary-tint #e9f5f1`, `--an-text #172c2b`,
  `--an-muted #667775`, `--an-track #eaf0ee`, `--an-income #b1dbcf`,
  `--an-grid #ecf0ef`, `--an-highlight #f0f7f4`, plus the seven category
  colours: Food `#087f70`, Transport `#369d8b`, Bills `#204e4c`,
  Health `#5d8c83`, Entertainment `#73b5a2`, Shopping `#48756d`,
  Other `#a0cfc1`
- Chart colours are read from these CSS variables in JS
  (`getComputedStyle`), not hardcoded in the script
- All templates extend `base.html`; no inline styles
- No schema changes. Income (`DEMO_MONTHLY_INCOME`) and budget
  (`MONTHLY_BUDGET`) are demo constants; the UI must label income as demo data
  ("Demo value", "Income is demo data"). Savings =
  `DEMO_MONTHLY_INCOME - current-month expense`
- Budget: `percent_used = round(spent / MONTHLY_BUDGET * 100)`, bar width
  capped at 100%; if spent exceeds the budget show "₹X over budget" instead of
  "left to spend" and use `--danger` for the text
- Currency always displays as ₹ with thousands separators (e.g. ₹14,200);
  transaction amounts render as `−₹420`
- Dates in the transactions table use the existing `dd Mon YYYY` format
- Greeting reflects the time of day (morning / afternoon / evening) using
  server local time; the date line shows today's date
- Typography: Inter, matching the Figma sizes and weights; scoped to the
  analytics page via its own class so other pages keep DM Sans / DM Serif
- Charts: Chart.js bar chart (6 months, income + expense grouped, y-axis in
  ₹k, current month emphasised) and doughnut chart (7 categories, total in the
  centre). The Figma "current month highlight" panel behind the Nov bars is
  drawn with a small Chart.js plugin or a CSS overlay; if it cannot be matched
  exactly, flag it rather than skip silently
- Empty states: no expenses this month → zero values, empty-state text in the
  category card and transactions table, charts still render without errors
- Responsive: below 768px stack the summary cards and chart cards in one
  column, and show transactions as compact rows with the amount right-aligned
  (the design's "Mobile layout" note)
- The Figma navbar and the "Mobile layout" guidance panel are design
  annotations, not page content: use `base.html`'s navbar and do not render
  the guidance panel
- Do not touch unrelated routes, templates or the stubbed delete route

## Definition of done

- [ ] `/analytics` while logged out redirects to `/login`
- [ ] `/analytics` while logged in loads with HTTP 200 for the seeded demo user
      (`demo@spendly.com` / `demo123`) and no longer shows "Coming Soon"
- [ ] The page uses `base.html`'s navbar and footer exactly once each; the
      Analytics nav link is marked active
- [ ] Greeting shows the logged-in user's name and today's date
- [ ] Total Expense equals the sum of the current month's expenses; Total
      Income shows ₹35,000 labelled as demo; Total Savings = income − expense
- [ ] Budget bar shows spent, the ₹20,000 limit, percent used and amount left,
      and the bar width matches the percentage
- [ ] Income-vs-expense chart renders six months oldest to newest, with
      months that have no expenses shown as zero and the current month
      emphasised
- [ ] Donut chart and category list show current-month totals per category;
      shares add up to 100%; the centre shows the total expense
- [ ] Recent transactions table shows at most 8 rows, newest first, with
      category icon and colour, description, date and `−₹` amount
- [ ] A user with no expenses sees empty states and no JavaScript console
      errors
- [ ] Adding an expense via `/expenses/add` and reloading `/analytics` updates
      every figure
- [ ] The page matches the Figma screenshot (colours, spacing, Inter
      typography, card layout) at 1440px, and stacks cleanly below 768px
- [ ] No hex colour values appear outside the `:root` block in `style.css`
      or in the template/JS; no temporary Figma asset URLs remain
- [ ] `git diff` touches no unrelated routes, templates or the DB schema
