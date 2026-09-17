"""
config.py
Central configuration for the local ticketing application.

Everything here is intentionally simple and local-only. No cloud, no
external services, no telemetry.
"""

import os

# Absolute path to the folder this file lives in (the project root).
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# ---------------------------------------------------------------------------
# Data storage
# ---------------------------------------------------------------------------
# All data lives under ./data. The SQLite database file and the attachments
# folder are created automatically on first launch.
DATA_DIR = os.path.join(BASE_DIR, "data")
ATTACHMENTS_DIR = os.path.join(DATA_DIR, "attachments")
BACKUP_DIR = os.path.join(DATA_DIR, "backups")

DB_FILENAME = "ticketing.db"
DB_PATH = os.path.join(DATA_DIR, DB_FILENAME)
SQLALCHEMY_DATABASE_URI = f"sqlite:///{DB_PATH}"

# ---------------------------------------------------------------------------
# Networking — LOCAL ONLY. Do not change HOST to 0.0.0.0.
# ---------------------------------------------------------------------------
HOST = "127.0.0.1"
PORT = 5000

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------
# Secret key is only used for local session/flash messages. It is generated
# locally and never leaves this machine.
SECRET_KEY = os.environ.get("TICKETING_SECRET_KEY", "local-personal-ticketing-key")

# Default assignee for personal use.
DEFAULT_ASSIGNEE = "Me"

# Max upload size for attachments (16 MB).
MAX_CONTENT_LENGTH = 16 * 1024 * 1024

# SQLAlchemy setting — quieter logs.
SQLALCHEMY_TRACK_MODIFICATIONS = False

# ---------------------------------------------------------------------------
# Domain vocabulary (issue types, statuses, priorities)
# ---------------------------------------------------------------------------
ISSUE_TYPES = ["Bug", "Task", "Feature", "Story", "Improvement", "Idea", "Question"]

# Ordered workflow. The order matters for the Kanban board columns.
STATUSES = ["Backlog", "To Do", "In Progress", "Blocked", "Testing", "Done"]

PRIORITIES = ["Lowest", "Low", "Medium", "High", "Highest"]

RESOLUTIONS = ["Done", "Won't Do", "Duplicate", "Cannot Reproduce", "Incomplete"]
