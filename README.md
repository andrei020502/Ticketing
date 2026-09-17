# Ticketing — Local Personal Issue Tracker

A lightweight, local-only issue tracker inspired by Jira, Plane, ServiceNow, and
GitHub Issues. Built with **Python + Flask + SQLite**. Runs entirely on your
machine at `http://127.0.0.1:5000` — no cloud, no internet required after
install, no telemetry, and it never exposes itself to your network.

---

## Features

- **Projects** with custom keys (DEV, HOME, AUTO…) that generate readable issue
  IDs like `DEV-1`, `HOME-3`.
- **Issues** with types (Bug, Task, Feature, Story, Improvement, Idea, Question),
  status workflow (Backlog → To Do → In Progress → Blocked → Testing → Done),
  priority, labels, assignee, due dates, parent/sub-issues, estimates and
  actual time.
- **Dashboard** with open/in-progress/blocked/done counts, plus recently
  created/updated, overdue, high-priority, blocked, and upcoming issues.
- **Kanban board** with drag-and-drop that updates status in the database.
- **Issue detail page** with description, private notes, comments, attachments,
  time logging, and a full activity history.
- **Search & filter** by ID, title, description, status, type, priority,
  project, label, and overdue; sort by created/updated/priority/due.
- **Reports**: issues by type/project/priority/status, completed over time,
  time spent per project.
- **Backup & export**: copy the SQLite database, export issues to JSON/CSV,
  and import from JSON.
- **Light & dark mode**.

---

## Requirements

- Windows 10/11
- **Python 3.10 or newer** — install from <https://www.python.org/downloads/>
  (during install, tick **"Add Python to PATH"**).

---

## Quick start (recommended)

1. Copy the `ticketing` folder anywhere on your machine
   (e.g. `C:\Tools\ticketing`).
2. Open **PowerShell** in that folder (Shift + right-click → *Open PowerShell
   window here*).
3. Run:

   ```powershell
   .\Start-Ticketing.ps1
   ```

   On the first run this automatically creates a virtual environment, installs
   the dependencies, starts the server, and opens the app in Microsoft Edge.

4. To stop the server, press **Ctrl+C** in the PowerShell window.

> If PowerShell blocks the script, run this once (safe, current-user only):
>
> ```powershell
> Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
> ```

---

## Manual start (alternative)

```powershell
cd C:\Tools\ticketing
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Then open <http://127.0.0.1:5000> in your browser.

---

## Where your data lives

Everything is stored locally under the `data/` folder, created automatically on
first launch:

```
data/
├── ticketing.db        ← the SQLite database (all issues, projects, comments…)
├── attachments/        ← uploaded files, stored as-is on disk
└── backups/            ← database backups you create from Settings
```

**Attachments** are copied into `data/attachments/` with a unique prefix and are
never uploaded anywhere. To back everything up, just copy the whole `data/`
folder, or use **Settings → Backup Database**.

---

## REST API

The app also exposes a simple local REST API (handy for scripts/automation):

```
GET    /api/issues                 list issues (optional ?status= ?project= ?type=)
GET    /api/issues/<KEY>           get one issue (e.g. /api/issues/DEV-1)
POST   /api/issues                 create  { "title": "...", "project_key": "DEV", ... }
PUT    /api/issues/<KEY>           update  { "status": "Done", ... }
DELETE /api/issues/<KEY>           delete

GET    /api/projects               list projects
POST   /api/projects               create  { "name": "...", "key": "DEV" }
```

Example (PowerShell):

```powershell
Invoke-RestMethod http://127.0.0.1:5000/api/issues
```

---

## Project structure

```
ticketing/
├── app.py                  Flask entry point (create_app + run)
├── config.py               Paths, host/port, vocab (types/statuses/priorities)
├── requirements.txt
├── Start-Ticketing.ps1     One-click Windows launcher (opens Edge)
├── README.md
│
├── database/
│   ├── db.py               SQLAlchemy instance + auto-init + seed projects
│   ├── models.py           ORM models (projects, issues, comments, …)
│   └── helpers.py          ID generation, activity log, time parsing
│
├── routes/
│   ├── main.py             Dashboard, reports, settings, backup/export/import
│   ├── issues.py           Issue CRUD, comments, time, attachments, Kanban
│   ├── projects.py         Project CRUD
│   └── api.py              REST API
│
├── templates/              Jinja2 HTML (base, dashboard, issues, issue, kanban…)
├── static/
│   ├── css/style.css       Light/dark theme
│   └── js/app.js           Theme toggle + Kanban drag-and-drop
│
└── data/                   Created automatically on first launch
```

---

## Security notes

- Binds **only** to `127.0.0.1` — never `0.0.0.0`, never the LAN.
- No firewall ports are opened and nothing is exposed to the internet.
- No cloud authentication, no external API calls, no telemetry.
- Because it is localhost-only and single-user, there is no login by default.

---

## Resetting

To start completely fresh, stop the server and delete the `data/` folder. It
will be recreated (with the sample projects) on the next launch.
