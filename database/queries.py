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


# SUBAGENT 1 — transaction history
def get_recent_transactions(user_id, limit=10):
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT date, description, category, amount FROM expenses "
            "WHERE user_id = ? ORDER BY date DESC, id DESC LIMIT ?",
            (user_id, limit),
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
def get_summary_stats(user_id):
    conn = get_db()
    try:
        total, count = conn.execute(
            "SELECT COALESCE(SUM(amount), 0), COUNT(*) FROM expenses WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if not count:
            return {"total_spent": 0, "transaction_count": 0, "top_category": "—"}
        row = conn.execute(
            "SELECT category FROM expenses WHERE user_id = ? "
            "GROUP BY category ORDER BY SUM(amount) DESC, category ASC LIMIT 1",
            (user_id,),
        ).fetchone()
        return {
            "total_spent": float(total),
            "transaction_count": int(count),
            "top_category": row[0] if row else "—",
        }
    finally:
        conn.close()


# SUBAGENT 3 — category breakdown
def get_category_breakdown(user_id):
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT category, SUM(amount) AS amount FROM expenses "
            "WHERE user_id = ? GROUP BY category "
            "ORDER BY amount DESC, category ASC",
            (user_id,),
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
