# Plan: Step 9 — Delete Expense

Source spec: `.claude/specs/09-delete-expense.md` (branch `features/delete-expense`).
To be saved as: `.claude/plans/09-delete-expense-setup.md`.

## Context

`/expenses/<int:id>/delete` in `app.py:393` is still a GET placeholder that returns
"Delete expense — coming in Step 9". Step 9 makes it a real, POST-only delete. Users
can then remove their own expenses from the profile transactions table, which closes out
add/edit/delete CRUD. Ownership is enforced in SQL. A missing expense or one owned by
another user returns 404. There are no schema changes.

## Reuse (already in the repo)

- `get_db()`: `database/db.py:23`
- `get_user_by_id`: `database/queries.py`. Use the same auth and stale-session guard as `edit_expense()` (`app.py:341`)
- `update_expense`: `database/queries.py:59`. Its execute/commit/`return cur.rowcount`/`finally close` shape is the model for `delete_expense`
- `abort`, `redirect`, `url_for`: already imported in `app.py`
- CSS variables `--danger`, `--danger-light`, `--radius-sm`, `--font-body` (`static/css/style.css:17-30`). `.txn-edit` (`style.css:1005`) is the style to sit beside
- `main.js` is already loaded on every page from `base.html:48` (end of body), so no template script block is needed

## Implementation steps

1. **`database/queries.py`**: add after `update_expense`:
   ```python
   def delete_expense(expense_id, user_id):
       """Delete one of user_id's expenses; return the number of rows deleted."""
       conn = get_db()
       try:
           cur = conn.execute(
               "DELETE FROM expenses WHERE id = ? AND user_id = ?",
               (expense_id, user_id),
           )
           conn.commit()
           return cur.rowcount
       finally:
           conn.close()
   ```

2. **`app.py`**
   - Add `delete_expense` to the `database.queries` import. The route function is also named `delete_expense`, so import the helper as `delete_expense as delete_expense_row`. This keeps the endpoint name `delete_expense`, which the spec's `url_for('delete_expense', ...)` relies on.
   - Replace the placeholder with:
     ```python
     @app.route("/expenses/<int:id>/delete", methods=["POST"])
     def delete_expense(id):
         user_id = session.get("user_id")
         if not user_id:
             return redirect(url_for("login"))
         if get_user_by_id(user_id) is None:  # stale session
             session.clear()
             return redirect(url_for("login"))
         if delete_expense_row(id, user_id) == 0:  # missing or not owned
             abort(404)
         return redirect(url_for("profile"))
     ```
   - Move it up beside `edit_expense` and delete the now-empty "Placeholder routes" comment block. Flask returns a 405 for GET automatically.

3. **`templates/profile.html`** (line 84): wrap the actions cell contents:
   ```html
   <td class="txn-actions">
       <a href="{{ url_for('edit_expense', id=t.id) }}" class="txn-edit">Edit</a>
       <form method="POST" action="{{ url_for('delete_expense', id=t.id) }}" class="txn-delete-form">
           <button type="submit" class="txn-delete">Delete</button>
       </form>
   </td>
   ```
   No inline styles or handlers. The empty-state `colspan="5"` stays the same.

4. **`static/js/main.js`**: use a delegated listener so the form markup needs no inline JS:
   ```js
   document.addEventListener("submit", function (e) {
       if (e.target.matches(".txn-delete-form") &&
           !confirm("Delete this expense? This cannot be undone.")) {
           e.preventDefault();
       }
   });
   ```

5. **`static/css/style.css`** (after `.txn-edit:hover`): use variables only, with no hex values:
   - `.txn-actions { display: flex; align-items: center; gap: 0.75rem; }`
   - `.txn-delete-form { display: inline; margin: 0; }`
   - `.txn-delete`: a reset button (`background: none; border: none; padding: 0; cursor: pointer; font: inherit;`) with `color: var(--danger); font-weight: 500;`. On hover, underline it.

6. After plan approval, also save this plan as `.claude/plans/09-delete-expense-setup.md`, as requested.

## Out of scope

Tests and pytest. Those run separately through `/text-feature 09-delete-expense`. No flash message, no keeping the date filter after a redirect (the spec says redirect to `/profile`), no schema changes, no other stubs.

## Verification (manual: `python app.py`, http://localhost:5001)

Work through the spec's Definition of done:
- Log in as `demo@spendly.com` / `demo123`. Every row shows Edit and a red Delete side by side.
- Click Delete, then Cancel. The row stays.
- Click Delete, then OK. You are redirected to `/profile`, the row is gone, and the totals and category breakdown update.
- With a date filter active, deleting still lands on `/profile` without error.
- Visiting `/expenses/<id>/delete` in the address bar (GET) returns 405, and the row still exists.
- While logged out, a POST (devtools `fetch` or curl) redirects to `/login` and nothing is deleted.
- A POST for an id that does not exist returns 404. A POST for another user's expense id (register a second user and add one) returns 404 and the row stays.
- Add and Edit flows still work.
