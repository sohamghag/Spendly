from datetime import datetime

from database.db import get_db


def get_user_by_id(user_id):
    """Return {name, email, initials, member_since} or None if no such user."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT name, email, created_at FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return None

    initials = "".join(word[0] for word in row["name"].split()[:2]).upper()
    member_since = datetime.strptime(
        row["created_at"], "%Y-%m-%d %H:%M:%S"
    ).strftime("%B %Y")
    return {
        "name": row["name"],
        "email": row["email"],
        "initials": initials,
        "member_since": member_since,
    }


def _date_clause(date_from, date_to):
    """Return (sql_fragment, params) for an inclusive date range, or empty."""
    if date_from and date_to:
        return " AND date BETWEEN ? AND ?", (date_from, date_to)
    return "", ()


# SUBAGENT 1 — transaction history
def get_recent_transactions(user_id, limit=10, date_from=None, date_to=None):
    clause, range_params = _date_clause(date_from, date_to)
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT date, description, category, amount FROM expenses "
            f"WHERE user_id = ?{clause} ORDER BY date DESC, id DESC LIMIT ?",
            (user_id, *range_params, limit),
        ).fetchall()
        return [
            {
                "date": datetime.strptime(r["date"], "%Y-%m-%d").strftime("%d %b %Y"),
                "description": r["description"] or "",
                "category": r["category"],
                "amount": r["amount"],
            }
            for r in rows
        ]
    finally:
        conn.close()


# SUBAGENT 2 — summary stats
def get_summary_stats(user_id, date_from=None, date_to=None):
    clause, range_params = _date_clause(date_from, date_to)
    params = (user_id, *range_params)
    conn = get_db()
    try:
        total, count = conn.execute(
            "SELECT COALESCE(SUM(amount), 0), COUNT(*) FROM expenses "
            f"WHERE user_id = ?{clause}",
            params,
        ).fetchone()
        if not count:
            return {"total_spent": 0, "transaction_count": 0, "top_category": "—"}
        row = conn.execute(
            f"SELECT category FROM expenses WHERE user_id = ?{clause} "
            "GROUP BY category ORDER BY SUM(amount) DESC, category ASC LIMIT 1",
            params,
        ).fetchone()
        return {
            "total_spent": float(total),
            "transaction_count": int(count),
            "top_category": row[0] if row else "—",
        }
    finally:
        conn.close()


# SUBAGENT 3 — category breakdown
def get_category_breakdown(user_id, date_from=None, date_to=None):
    clause, range_params = _date_clause(date_from, date_to)
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT category, SUM(amount) AS amount FROM expenses "
            f"WHERE user_id = ?{clause} GROUP BY category "
            "ORDER BY amount DESC, category ASC",
            (user_id, *range_params),
        ).fetchall()
    finally:
        conn.close()

    grand_total = sum(r["amount"] for r in rows)
    if not rows or grand_total <= 0:
        return []

    result = [
        {
            "name": r["category"],
            "amount": r["amount"],
            "pct": int(round(r["amount"] / grand_total * 100)),
        }
        for r in rows
    ]
    result[0]["pct"] += 100 - sum(item["pct"] for item in result)
    return result
