/* ==========================================================================
   app.js — theme toggle + Kanban drag-and-drop
   ========================================================================== */

// ---- Theme (light/dark) persistence -------------------------------------
(function () {
    const saved = localStorage.getItem("ticketing-theme");
    if (saved) document.documentElement.setAttribute("data-theme", saved);

    document.addEventListener("DOMContentLoaded", function () {
        const btn = document.getElementById("theme-toggle");
        if (!btn) return;
        btn.addEventListener("click", function () {
            const cur = document.documentElement.getAttribute("data-theme");
            const next = cur === "dark" ? "light" : "dark";
            document.documentElement.setAttribute("data-theme", next);
            localStorage.setItem("ticketing-theme", next);
        });
    });
})();

// ---- Kanban drag-and-drop ------------------------------------------------
document.addEventListener("DOMContentLoaded", function () {
    const cards = document.querySelectorAll(".kanban-card");
    const columns = document.querySelectorAll(".kanban-col");
    if (!cards.length) return;

    let dragged = null;

    cards.forEach(function (card) {
        card.setAttribute("draggable", "true");
        card.addEventListener("dragstart", function () {
            dragged = card;
            card.classList.add("dragging");
        });
        card.addEventListener("dragend", function () {
            card.classList.remove("dragging");
            dragged = null;
        });
    });

    columns.forEach(function (col) {
        const dropzone = col.querySelector(".kanban-cards");

        col.addEventListener("dragover", function (e) {
            e.preventDefault();
            col.classList.add("drag-over");
        });
        col.addEventListener("dragleave", function () {
            col.classList.remove("drag-over");
        });
        col.addEventListener("drop", function (e) {
            e.preventDefault();
            col.classList.remove("drag-over");
            if (!dragged) return;

            const newStatus = col.getAttribute("data-status");
            const issueKey = dragged.getAttribute("data-key");

            // Move the card in the DOM immediately for a snappy feel.
            dropzone.appendChild(dragged);
            updateColumnCounts();

            // Persist to the backend.
            fetch("/api/kanban/move", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ issue_key: issueKey, status: newStatus }),
            })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (!data.ok) alert("Could not update status.");
            })
            .catch(function () { alert("Network error updating status."); });
        });
    });

    function updateColumnCounts() {
        columns.forEach(function (col) {
            const count = col.querySelectorAll(".kanban-card").length;
            const el = col.querySelector(".kanban-count");
            if (el) el.textContent = count;
        });
    }
});
