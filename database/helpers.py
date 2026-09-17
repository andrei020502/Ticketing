"""
database/helpers.py
Shared business-logic helpers used by both the HTML routes and the REST API.

Keeps route files thin and avoids duplicating logic like ID generation,
activity logging, and time formatting.
"""

from datetime import datetime
from database.db import db
from database.models import Issue, Project, Label, ActivityLog


# ---------------------------------------------------------------------------
# Issue key generation:  DEV-1, DEV-2, HOME-1 ...
# ---------------------------------------------------------------------------
def generate_issue_key(project):
    """Increment the project counter and return the next readable key."""
    project.issue_counter = (project.issue_counter or 0) + 1
    return f"{project.key}-{project.issue_counter}"


# ---------------------------------------------------------------------------
# Activity logging
# ---------------------------------------------------------------------------
def log_activity(issue, action):
    """Append a human-readable entry to an issue's activity history."""
    db.session.add(ActivityLog(issue_id=issue.id, action=action))


# ---------------------------------------------------------------------------
# Labels — resolve names to Label rows, creating them if needed.
# ---------------------------------------------------------------------------
def resolve_labels(label_names):
    labels = []
    for raw in label_names:
        name = (raw or "").strip()
        if not name:
            continue
        label = Label.query.filter_by(name=name).first()
        if not label:
            label = Label(name=name)
            db.session.add(label)
        labels.append(label)
    return labels


# ---------------------------------------------------------------------------
# Date parsing helper (accepts YYYY-MM-DD or empty).
# ---------------------------------------------------------------------------
def parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d")
    except (ValueError, AttributeError):
        return None


# ---------------------------------------------------------------------------
# Time formatting: minutes -> "2h 30m"
# ---------------------------------------------------------------------------
def format_minutes(total_minutes):
    if not total_minutes:
        return "0m"
    hours, minutes = divmod(int(total_minutes), 60)
    parts = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    return " ".join(parts) if parts else "0m"


def parse_time_to_minutes(value):
    """Parse '4h', '30m', '2h 30m', '90' (minutes) into an integer of minutes."""
    if not value:
        return 0
    value = str(value).strip().lower()
    if value.isdigit():
        return int(value)
    total = 0
    import re
    for amount, unit in re.findall(r"(\d+)\s*([hm])", value):
        if unit == "h":
            total += int(amount) * 60
        else:
            total += int(amount)
    return total


def recalc_actual_time(issue):
    """Sum all time entries into the issue's actual_minutes field."""
    issue.actual_minutes = sum(t.minutes for t in issue.time_entries)
