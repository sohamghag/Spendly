import os
import sqlite3

from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash

from database.db import get_db, init_db, seed_db

app = Flask(__name__)
# The fallback key is for local development only; set SECRET_KEY in production.
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-insecure-key-change-me")

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


@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    # Hardcoded for Step 4; mirrors the demo seed. Real queries arrive in Step 5.
    user = {
        "name": "Demo User",
        "email": "demo@spendly.com",
        "initials": "DU",
        "member_since": "November 2026",
    }
    stats = {
        "total_spent": 5831.25,
        "transaction_count": 8,
        "top_category": "Shopping",
    }
    transactions = [
        {"date": "26 Nov 2026", "description": "Dinner out", "category": "Food", "amount": 320.75},
        {"date": "18 Nov 2026", "description": "New shoes", "category": "Shopping", "amount": 2200.00},
        {"date": "14 Nov 2026", "description": "Movie night", "category": "Entertainment", "amount": 600.00},
        {"date": "10 Nov 2026", "description": "Pharmacy", "category": "Health", "amount": 450.50},
        {"date": "07 Nov 2026", "description": "Electricity bill", "category": "Bills", "amount": 1800.00},
    ]
    categories = [
        {"name": "Shopping", "total": 2200.00, "percent": 38},
        {"name": "Bills", "total": 1800.00, "percent": 31},
        {"name": "Entertainment", "total": 600.00, "percent": 10},
        {"name": "Food", "total": 570.75, "percent": 10},
        {"name": "Health", "total": 450.50, "percent": 8},
        {"name": "Other", "total": 150.00, "percent": 3},
        {"name": "Transport", "total": 60.00, "percent": 1},
    ]
    return render_template(
        "profile.html",
        user=user,
        stats=stats,
        transactions=transactions,
        categories=categories,
    )


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
