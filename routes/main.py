"""
routes/main.py
Dashboard, reports, settings, and backup/export/import.
"""

import os
import json
import csv
import io
import shutil
from datetime import datetime
from flask import (
    Blueprint, render_template, redirect, url_for, flash, send_file, request
)

import config
from database.db import db
from database.models import Issue, Project, Label, Comment, TimeEntry
from database.helpers import format_minutes

bp = Blueprint("main", __name__)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
@bp.route("/")
def dashboard():
    now = datetime.utcnow()

    open_count = Issue.query.filter(Issue.status.notin_(["Done"])).count()
    in_progress = Issue.query.filter(Issue.status == "In Progress").count()
    blocked = Issue.query.filter(Issue.status == "Blocked").count()
    done = Issue.query.filter(Issue.status == "Done").count()

    recent_created = Issue.query.order_by(Issue.created_date.desc()).limit(8).all()
    recent_updated = Issue.query.order_by(Issue.updated_date.desc()).limit(8).all()
    overdue = Issue.query.filter(
        Issue.due_date.isnot(None), Issue.due_date < now, Issue.status != "Done"
    ).order_by(Issue.due_date.asc()).all()
    high_priority = Issue.query.filter(
        Issue.priority.in_(["High", "Highest"]), Issue.status != "Done"
    ).order_by(Issue.updated_date.desc()).limit(10).all()
    blocked_issues = Issue.query.filter(Issue.status == "Blocked").all()
    upcoming = Issue.query.filter(
        Issue.due_date.isnot(None), Issue.due_date >= now, Issue.status != "Done"
    ).order_by(Issue.due_date.asc()).limit(10).all()

    return render_template(
        "dashboard.html",
        stats={"open": open_count, "in_progress": in_progress,
               "blocked": blocked, "done": done},
        recent_created=recent_created,
        recent_updated=recent_updated,
        overdue=overdue,
        high_priority=high_priority,
        blocked_issues=blocked_issues,
        upcoming=upcoming,
        now=now,
    )


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------
@bp.route("/reports")
def reports():
    all_issues = Issue.query.all()

    by_type, by_project, by_priority, by_status = {}, {}, {}, {}
    for i in all_issues:
        by_type[i.issue_type] = by_type.get(i.issue_type, 0) + 1
        by_priority[i.priority] = by_priority.get(i.priority, 0) + 1
        by_status[i.status] = by_status.get(i.status, 0) + 1
        pk = i.project.key if i.project else "—"
        by_project[pk] = by_project.get(pk, 0) + 1

    # Time spent per project (minutes -> readable)
    time_per_project = {}
    for p in Project.query.all():
        minutes = sum(
            t.minutes for iss in p.issues for t in iss.time_entries
        )
        if minutes:
            time_per_project[p.key] = format_minutes(minutes)

    # Completed over time (by month)
    completed_over_time = {}
    for i in all_issues:
        if i.status == "Done":
            month = i.updated_date.strftime("%Y-%m") if i.updated_date else "—"
            completed_over_time[month] = completed_over_time.get(month, 0) + 1

    return render_template(
        "reports.html",
        total=len(all_issues),
        open_count=sum(1 for i in all_issues if i.status != "Done"),
        completed=sum(1 for i in all_issues if i.status == "Done"),
        by_type=by_type,
        by_project=by_project,
        by_priority=by_priority,
        by_status=by_status,
        time_per_project=time_per_project,
        completed_over_time=dict(sorted(completed_over_time.items())),
    )


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
@bp.route("/settings")
def settings():
    return render_template(
        "settings.html",
        db_path=config.DB_PATH,
        attachments_dir=config.ATTACHMENTS_DIR,
        backup_dir=config.BACKUP_DIR,
        issue_count=Issue.query.count(),
        project_count=Project.query.count(),
    )


# ---------------------------------------------------------------------------
# Backup: copy the SQLite file
# ---------------------------------------------------------------------------
@bp.route("/backup/database")
def backup_database():
    os.makedirs(config.BACKUP_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = os.path.join(config.BACKUP_DIR, f"ticketing_backup_{stamp}.db")
    shutil.copy2(config.DB_PATH, dest)
    return send_file(dest, as_attachment=True,
                     download_name=f"ticketing_backup_{stamp}.db")


# ---------------------------------------------------------------------------
# Export issues to JSON
# ---------------------------------------------------------------------------
@bp.route("/export/json")
def export_json():
    issues = [i.to_dict(full=True) for i in Issue.query.all()]
    payload = json.dumps({"exported_at": datetime.utcnow().isoformat(),
                          "issues": issues}, indent=2)
    buffer = io.BytesIO(payload.encode("utf-8"))
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return send_file(buffer, as_attachment=True, mimetype="application/json",
                     download_name=f"issues_export_{stamp}.json")


# ---------------------------------------------------------------------------
# Export issues to CSV
# ---------------------------------------------------------------------------
@bp.route("/export/csv")
def export_csv():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Issue ID", "Title", "Type", "Status", "Priority", "Project",
        "Assignee", "Created", "Updated", "Due", "Estimated (min)",
        "Actual (min)", "Resolution", "Labels",
    ])
    for i in Issue.query.all():
        writer.writerow([
            i.issue_key, i.title, i.issue_type, i.status, i.priority,
            i.project.key if i.project else "", i.assignee,
            i.created_date, i.updated_date, i.due_date or "",
            i.estimated_minutes, i.actual_minutes, i.resolution or "",
            "; ".join(l.name for l in i.labels),
        ])
    buffer = io.BytesIO(output.getvalue().encode("utf-8"))
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return send_file(buffer, as_attachment=True, mimetype="text/csv",
                     download_name=f"issues_export_{stamp}.csv")


# ---------------------------------------------------------------------------
# Import issues from a previously exported JSON file
# ---------------------------------------------------------------------------
@bp.route("/import/json", methods=["POST"])
def import_json():
    file = request.files.get("file")
    if not file or not file.filename:
        flash("No file selected.", "error")
        return redirect(url_for("main.settings"))

    try:
        data = json.load(file.stream)
    except (ValueError, UnicodeDecodeError):
        flash("Invalid JSON file.", "error")
        return redirect(url_for("main.settings"))

    from database.helpers import generate_issue_key, resolve_labels, parse_date
    imported = 0
    for row in data.get("issues", []):
        # Match project by key, or create a catch-all IMPORT project.
        pkey = row.get("project_key") or "IMPORT"
        project = Project.query.filter_by(key=pkey).first()
        if not project:
            project = Project(name=f"Imported ({pkey})", key=pkey)
            db.session.add(project)
            db.session.flush()

        issue = Issue(
            issue_key=generate_issue_key(project),
            title=row.get("title", "Untitled"),
            description=row.get("description", ""),
            issue_type=row.get("issue_type", "Task"),
            status=row.get("status", "Backlog"),
            priority=row.get("priority", "Medium"),
            project_id=project.id,
            assignee=row.get("assignee", config.DEFAULT_ASSIGNEE),
            estimated_minutes=row.get("estimated_minutes", 0) or 0,
            actual_minutes=row.get("actual_minutes", 0) or 0,
            resolution=row.get("resolution"),
        )
        issue.labels = resolve_labels(row.get("labels", []))
        db.session.add(issue)
        imported += 1

    db.session.commit()
    flash(f"Imported {imported} issue(s).", "success")
    return redirect(url_for("main.settings"))
