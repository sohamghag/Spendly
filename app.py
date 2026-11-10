import calendar
import os
import sqlite3
from datetime import date, datetime

from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import generate_password_hash, check_password_hash

from database.db import get_db, init_db, seed_db
from database.queries import (
    get_user_by_id,
    get_summary_stats,
    get_recent_transactions,
    get_category_breakdown,
)

app = Flask(__name__)
# The fallback key is for local development only; production must set SECRET_KEY.
_secret_key = os.environ.get("SECRET_KEY")
if not _secret_key:
    if os.environ.get("FLASK_ENV") == "production":
        raise RuntimeError("SECRET_KEY must be set when FLASK_ENV=production")
    _secret_key = "dev-only-insecure-key-change-me"
app.secret_key = _secret_key

with app.app_context():
    init_db()
    seed_db()


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


def _is_valid_email(email):
    """Exactly one '@' with non-empty local and domain parts."""
    if email.count("@") != 1:
        return False
    local, domain = email.split("@")
    return bool(local) and bool(domain)



@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    def fail(message):
        return render_template(
            "register.html", error=message, name=name, email=email
        ), 400

    if not name:
        return fail("Please enter your name.")
    if not _is_valid_email(email):
        return fail("Please enter a valid email address.")
    if len(password) < 8:
        return fail("Password must be at least 8 characters.")

    conn = get_db()
    try:
        if conn.execute(
            "SELECT 1 FROM users WHERE email = ?", (email,)
        ).fetchone():
            return fail("An account with this email already exists.")
        try:
            conn.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                (name, email, generate_password_hash(password)),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            return fail("An account with this email already exists.")
    finally:
        conn.close()

    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("profile"))

    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    def fail(message, status):
        return render_template("login.html", error=message, email=email), status

    if not email or not password:
        return fail("Please enter your email and password.", 400)

    conn = get_db()
    try:
        user = conn.execute(
            "SELECT id, password_hash FROM users WHERE email = ?", (email,)
        ).fetchone()
    finally:
        conn.close()

    if user is None or not check_password_hash(user["password_hash"], password):
        return fail("Invalid email or password.", 401)

    session.clear()
    session["user_id"] = user["id"]
    return redirect(url_for("profile"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


def _parse_iso_date(value):
    """Return a date for a 'YYYY-MM-DD' string, or None if missing/malformed."""
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _months_ago(d, n):
    """Same day n months before d, clamped to the end of the target month."""
    month_index = d.year * 12 + (d.month - 1) - n
    year, month = divmod(month_index, 12)
    month += 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _resolve_date_range(args):
    """Return (date_from, date_to) as ISO strings, or (None, None) for no filter.

    A missing/malformed bound means no filter; a reversed range also means
    no filter and queues a flash message for the profile page.
    """
    start_date = _parse_iso_date(args.get("date_from"))
    end_date = _parse_iso_date(args.get("date_to"))
    if not (start_date and end_date):
        return None, None
    if start_date > end_date:
        flash("Start date must be before end date.", "filter")
        return None, None
    return start_date.isoformat(), end_date.isoformat()


def _build_presets(today, date_from, date_to):
    """Quick-select presets with their link URL and whether each is active.

    All Time has no bounds and links to a clean /profile URL.
    """
    end = today.isoformat()
    ranges = [
        ("This Month", today.replace(day=1).isoformat(), end),
        ("Last 3 Months", _months_ago(today, 3).isoformat(), end),
        ("Last 6 Months", _months_ago(today, 6).isoformat(), end),
        ("All Time", None, None),
    ]
    presets = []
    for label, preset_from, preset_to in ranges:
        if preset_from:
            url = url_for("profile", date_from=preset_from, date_to=preset_to)
        else:
            url = url_for("profile")
        presets.append(
            {
                "label": label,
                "url": url,
                "active": (preset_from, preset_to) == (date_from, date_to),
            }
        )
    return presets


@app.route("/profile")
def profile():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    user = get_user_by_id(user_id)
    if user is None:  # stale session: the user row no longer exists
        session.clear()
        return redirect(url_for("login"))

    date_from, date_to = _resolve_date_range(request.args)
    presets = _build_presets(date.today(), date_from, date_to)
    custom_active = date_from is not None and not any(p["active"] for p in presets)

    return render_template(
        "profile.html",
        user=user,
        stats=get_summary_stats(user_id, date_from=date_from, date_to=date_to),
        transactions=get_recent_transactions(
            user_id, date_from=date_from, date_to=date_to
        ),
        categories=get_category_breakdown(
            user_id, date_from=date_from, date_to=date_to
        ),
        presets=presets,
        date_from=date_from,
        date_to=date_to,
        custom_active=custom_active,
    )


@app.route("/analytics")
def analytics():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    if get_user_by_id(user_id) is None:  # stale session
        session.clear()
        return redirect(url_for("login"))

    return render_template("analytics.html")


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"



@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
