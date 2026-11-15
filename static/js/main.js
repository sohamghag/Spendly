// main.js — shared JavaScript

// Confirm before deleting an expense (profile transactions table).
document.addEventListener("submit", function (e) {
    if (e.target.matches(".txn-delete-form") &&
        !confirm("Delete this expense? This cannot be undone.")) {
        e.preventDefault();
    }
});
