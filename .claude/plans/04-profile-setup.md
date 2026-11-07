/# Plan: Step 04 — Profile Page (static UI)

## Context

Spec: `.claude/specs/04-profile-page.md`. Step 4 replaces the `/profile` stub with the full profile page UI, using **hardcoded data only**. Real DB queries come in Step 5.

Current state:

- `/profile` (`app.py:129-131`) returns "Profile page — coming in Step 4". Login (Step 3) already sets `session["user_id"]` and redirects here.
- `templates/base.html:22-28` already switches the navbar on `session.get("user_id")`: "Profile" + "Sign out" when signed in.
- **The profile CSS already exists** in the uncommitted `static/css/style.css:754-922`, with mobile rules at `:959` and `:980-981`. Classes: `.profile-section`, `.profile-container`, `.profile-card`, `.profile-avatar`, `.profile-name`, `.profile-email`, `.profile-meta`, `.profile-stats`, `.stat-tile`, `.stat-label`, `.stat-value`, `.profile-grid`, `.profile-panel`, `.panel-title`, `.table-wrap`, `.txn-table`, `.txn-amount`, `.badge` + `.badge-<category>`, `.cat-list`, `.cat-head`, `.cat-name`, `.cat-total`, `.cat-bar`. The template uses these classes and no CSS work is needed.

Outcome: a protected `/profile` that renders `profile.html` with four sections from hardcoded Python data.

## Changes

### 0. Save this plan

Write this plan to `.claude/plans/04-profile-setup.md`, matching the existing `01-…-setup.md` to `03-…-setup.md` files.

### 1. `app.py`: replace the `/profile` stub

Move it out of the "Placeholder routes" section so it sits after `logout()`:

```python
@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    user = {...}; stats = {...}; transactions = [...]; categories = [...]
    return render_template("profile.html", user=user, stats=stats,
                           transactions=transactions, categories=categories)
```

The hardcoded data mirrors the demo seed in `database/db.py:71-96`, so Step 5 totals will match:

- `user`: name "Demo User", email "demo@spendly.com", initials "DU", member_since "November 2026"
- `stats`: total_spent 5831.25, transaction_count 8, top_category "Shopping"
- `transactions` (newest first; `date`, `description`, `category`, `amount`): Dinner out / Food 320.75 · New shoes / Shopping 2200.00 · Movie night / Entertainment 600.00 · Pharmacy / Health 450.50 · Electricity bill / Bills 1800.00. Each row has a fixed display date (e.g. "26 Nov 2026").
- `categories` (`name`, `total`, `percent`; sorted by total, descending): Shopping 2200.00/38 · Bills 1800.00/31 · Entertainment 600.00/10 · Food 570.75/10 · Health 450.50/8 · Other 150.00/3 · Transport 60.00/1

No DB calls. `login()`, `register()`, `logout()` and `database/db.py` are untouched.

### 2. `templates/profile.html` (new; extends `base.html`)

- `{% block title %}Profile — Spendly{% endblock %}`
- `<section class="profile-section"><div class="profile-container">` contains:
  1. **User card** `.profile-card`: `.profile-avatar` (initials), `.profile-name`, `.profile-email`, `.profile-meta` "Member since …"
  2. **Stats** `.profile-stats`: 3 × `.stat-tile` (`.stat-label` + `.stat-value`). The total is shown as `₹{{ "{:,.2f}".format(stats.total_spent) }}`.
  3. `.profile-grid` with two `.profile-panel`s:
     - **Transactions**: `.panel-title` + `.table-wrap` > `table.txn-table` (Date, Description, Category, Amount). Category is `<span class="badge badge-{{ t.category|lower }}">` and the amount cell is `.txn-amount` with ₹ formatting.
     - **Category breakdown**: `ul.cat-list`. Each `li` has a `.cat-head` (`.cat-name`, `.cat-total`) and `<progress class="cat-bar" max="100" value="{{ c.percent }}">`.
- No `style=` attributes and no hex values.

### Navbar

Keep `base.html` as-is: "Profile" + "Sign out" serves as the logged-in state, and the username shows on the profile card. A name in the navbar would need `base.html` and `login()` changes, which the spec's file list and its "no auth changes" rule exclude.

### Out of scope

Real DB queries (Step 5), a `login_required` decorator, profile editing, the expense add/edit/delete stubs, `main.js` and further CSS changes.

## Verification

1. `python app.py` starts without errors.
2. Signed out: `curl -i http://localhost:5001/profile` returns 302 with `Location: /login`.
3. Log in as `demo@spendly.com` / `demo123`: you land on `/profile` with a 200. It shows:
   - the DU avatar with name, email and member-since
   - 3 stats: ₹5,831.25 · 8 · Shopping
   - a 5-row table with coloured badges
   - 7 category rows with progress bars
4. The navbar shows "Profile" / "Sign out", and Sign out returns you to the landing page.
5. `grep -nE "#[0-9a-fA-F]{3,6}\b|style=" templates/profile.html` returns no matches.
6. At ~375px width the stats and panels stack, and the page has no horizontal scroll; only the table scrolls inside `.table-wrap`.
