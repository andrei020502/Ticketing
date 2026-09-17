"""
routes/issues.py
HTML views for issues: list/search/filter, detail page, create, edit,
status changes, comments, time tracking, attachments, and the Kanban board.
"""

import os
import uuid
from flask import (
    Blueprint, render_template, request, redirect, url_for, flash,
    send_from_directory, abort, current_app
)
from werkzeug.utils import secure_filename
from datetime import datetime

import config
from database.db import db
from database.models import Issue, Project, Comment, Label, Attachment, TimeEntry
from database.helpers import (
    generate_issue_key, log_activity, resolve_labels, parse_date,
    parse_time_to_minutes, recalc_actual_time
)

bp = Blueprint("issues", __name__)


# ---------------------------------------------------------------------------
# Issue list with search / filter / sort
# ---------------------------------------------------------------------------
@bp.route("/issues")
def list_issues():
    q = request.args.get("q", "").strip()
    f_status = request.args.get("status", "")
    f_type = request.args.get("type", "")
    f_priority = request.args.get("priority", "")
    f_project = request.args.get("project", "")
    f_label = request.args.get("label", "")
    f_overdue = request.args.get("overdue", "")
    sort = request.args.get("sort", "created")

    query = Issue.query

    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(
                Issue.issue_key.ilike(like),
                Issue.title.ilike(like),
                Issue.description.ilike(like),
            )
        )
    if f_status:
        query = query.filter(Issue.status == f_status)
    if f_type:
        query = query.filter(Issue.issue_type == f_type)
    if f_priority:
        query = query.filter(Issue.priority == f_priority)
    if f_project:
        query = query.filter(Issue.project_id == int(f_project))
    if f_label:
        query = query.filter(Issue.labels.any(Label.name == f_label))
    if f_overdue:
        query = query.filter(
            Issue.due_date.isnot(None),
            Issue.due_date < datetime.utcnow(),
            Issue.status != "Done",
        )

    # Sorting
    priority_order = {p: i for i, p in enumerate(config.PRIORITIES)}
    if sort == "updated":
        query = query.order_by(Issue.updated_date.desc())
    elif sort == "due":
        query = query.order_by(Issue.due_date.asc().nullslast())
    elif sort == "priority":
        # Highest priority first — handled in Python after fetch.
        issues = query.all()
        issues.sort(key=lambda i: priority_order.get(i.priority, 0), reverse=True)
        return _render_list(issues, q, f_status, f_type, f_priority, f_project, f_label, f_overdue, sort)
    else:
        query = query.order_by(Issue.created_date.desc())

    return _render_list(query.all(), q, f_status, f_type, f_priority, f_project, f_label, f_overdue, sort)


def _render_list(issues, q, f_status, f_type, f_priority, f_project, f_label, f_overdue, sort):
    return render_template(
        "issues.html",
        issues=issues,
        projects=Project.query.order_by(Project.key).all(),
        labels=Label.query.order_by(Label.name).all(),
        statuses=config.STATUSES,
        types=config.ISSUE_TYPES,
        priorities=config.PRIORITIES,
        filters={
            "q": q, "status": f_status, "type": f_type, "priority": f_priority,
            "project": f_project, "label": f_label, "overdue": f_overdue, "sort": sort,
        },
        now=datetime.utcnow(),
    )


# ---------------------------------------------------------------------------
# My Issues (assignee = Me)  and Backlog
# ---------------------------------------------------------------------------
@bp.route("/my-issues")
def my_issues():
    issues = Issue.query.filter(
        Issue.assignee == config.DEFAULT_ASSIGNEE, Issue.status != "Done"
    ).order_by(Issue.updated_date.desc()).all()
    return render_template("issues.html", issues=issues,
                           projects=Project.query.order_by(Project.key).all(),
                           labels=Label.query.order_by(Label.name).all(),
                           statuses=config.STATUSES, types=config.ISSUE_TYPES,
                           priorities=config.PRIORITIES,
                           filters={"title": "My Issues"}, now=datetime.utcnow())


@bp.route("/backlog")
def backlog():
    issues = Issue.query.filter(Issue.status == "Backlog").order_by(
        Issue.created_date.desc()).all()
    return render_template("issues.html", issues=issues,
                           projects=Project.query.order_by(Project.key).all(),
                           labels=Label.query.order_by(Label.name).all(),
                           statuses=config.STATUSES, types=config.ISSUE_TYPES,
                           priorities=config.PRIORITIES,
                           filters={"title": "Backlog"}, now=datetime.utcnow())


# ---------------------------------------------------------------------------
# Issue detail page
# ---------------------------------------------------------------------------
@bp.route("/issue/<issue_key>")
def detail(issue_key):
    issue = Issue.query.filter_by(issue_key=issue_key).first_or_404()
    return render_template(
        "issue.html",
        issue=issue,
        projects=Project.query.order_by(Project.key).all(),
        statuses=config.STATUSES,
        types=config.ISSUE_TYPES,
        priorities=config.PRIORITIES,
        resolutions=config.RESOLUTIONS,
        all_issues=Issue.query.filter(Issue.id != issue.id).all(),
    )


# ---------------------------------------------------------------------------
# Create issue
# ---------------------------------------------------------------------------
@bp.route("/issue/new", methods=["GET", "POST"])
def create():
    if request.method == "POST":
        project = Project.query.get_or_404(int(request.form["project_id"]))
        issue = Issue(
            issue_key=generate_issue_key(project),
            title=request.form["title"].strip(),
            description=request.form.get("description", "").strip(),
            issue_type=request.form.get("issue_type", "Task"),
            status=request.form.get("status", "Backlog"),
            priority=request.form.get("priority", "Medium"),
            project_id=project.id,
            assignee=request.form.get("assignee", config.DEFAULT_ASSIGNEE) or config.DEFAULT_ASSIGNEE,
            due_date=parse_date(request.form.get("due_date")),
            estimated_minutes=parse_time_to_minutes(request.form.get("estimated_time")),
            notes=request.form.get("notes", "").strip(),
        )
        parent = request.form.get("parent_id")
        if parent:
            issue.parent_id = int(parent)
        issue.labels = resolve_labels(request.form.get("labels", "").split(","))
        db.session.add(issue)
        db.session.flush()  # get issue.id for the activity log
        log_activity(issue, "Created")
        db.session.commit()
        flash(f"Created {issue.issue_key}", "success")
        return redirect(url_for("issues.detail", issue_key=issue.issue_key))

    return render_template(
        "issue_form.html",
        issue=None,
        projects=Project.query.order_by(Project.key).all(),
        statuses=config.STATUSES,
        types=config.ISSUE_TYPES,
        priorities=config.PRIORITIES,
        all_issues=Issue.query.all(),
        preselect_project=request.args.get("project", ""),
    )


# ---------------------------------------------------------------------------
# Edit issue
# ---------------------------------------------------------------------------
@bp.route("/issue/<issue_key>/edit", methods=["GET", "POST"])
def edit(issue_key):
    issue = Issue.query.filter_by(issue_key=issue_key).first_or_404()

    if request.method == "POST":
        # Track changes for the activity log.
        changes = []
        new_title = request.form["title"].strip()
        if new_title != issue.title:
            changes.append("Title updated")
            issue.title = new_title

        new_desc = request.form.get("description", "").strip()
        if new_desc != (issue.description or ""):
            changes.append("Description updated")
            issue.description = new_desc

        for field, label in [("issue_type", "Type"), ("priority", "Priority"),
                             ("status", "Status"), ("assignee", "Assignee")]:
            new_val = request.form.get(field, getattr(issue, field))
            if new_val != getattr(issue, field):
                changes.append(f"{label} changed to {new_val}")
                setattr(issue, field, new_val)

        new_due = parse_date(request.form.get("due_date"))
        if new_due != issue.due_date:
            changes.append("Due date updated")
            issue.due_date = new_due

        issue.estimated_minutes = parse_time_to_minutes(request.form.get("estimated_time"))
        issue.notes = request.form.get("notes", "").strip()
        issue.resolution = request.form.get("resolution") or None

        parent = request.form.get("parent_id")
        issue.parent_id = int(parent) if parent else None

        issue.labels = resolve_labels(request.form.get("labels", "").split(","))

        for c in changes:
            log_activity(issue, c)
        db.session.commit()
        flash(f"Updated {issue.issue_key}", "success")
        return redirect(url_for("issues.detail", issue_key=issue.issue_key))

    return render_template(
        "issue_form.html",
        issue=issue,
        projects=Project.query.order_by(Project.key).all(),
        statuses=config.STATUSES,
        types=config.ISSUE_TYPES,
        priorities=config.PRIORITIES,
        all_issues=Issue.query.filter(Issue.id != issue.id).all(),
        preselect_project="",
    )


# ---------------------------------------------------------------------------
# Delete issue
# ---------------------------------------------------------------------------
@bp.route("/issue/<issue_key>/delete", methods=["POST"])
def delete(issue_key):
    issue = Issue.query.filter_by(issue_key=issue_key).first_or_404()
    db.session.delete(issue)
    db.session.commit()
    flash(f"Deleted {issue_key}", "success")
    return redirect(url_for("issues.list_issues"))


# ---------------------------------------------------------------------------
# Quick status change (used by Kanban drag-and-drop via a normal form too)
# ---------------------------------------------------------------------------
@bp.route("/issue/<issue_key>/status", methods=["POST"])
def change_status(issue_key):
    issue = Issue.query.filter_by(issue_key=issue_key).first_or_404()
    new_status = request.form.get("status")
    if new_status and new_status != issue.status:
        log_activity(issue, f"Status changed to {new_status}")
        issue.status = new_status
        db.session.commit()
    return redirect(request.referrer or url_for("issues.detail", issue_key=issue_key))


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------
@bp.route("/issue/<issue_key>/comment", methods=["POST"])
def add_comment(issue_key):
    issue = Issue.query.filter_by(issue_key=issue_key).first_or_404()
    body = request.form.get("body", "").strip()
    if body:
        db.session.add(Comment(issue_id=issue.id, author=config.DEFAULT_ASSIGNEE, body=body))
        log_activity(issue, "Comment added")
        db.session.commit()
    return redirect(url_for("issues.detail", issue_key=issue_key) + "#comments")


# ---------------------------------------------------------------------------
# Time tracking
# ---------------------------------------------------------------------------
@bp.route("/issue/<issue_key>/time", methods=["POST"])
def add_time(issue_key):
    issue = Issue.query.filter_by(issue_key=issue_key).first_or_404()
    minutes = parse_time_to_minutes(request.form.get("time"))
    if minutes > 0:
        db.session.add(TimeEntry(issue_id=issue.id, minutes=minutes,
                                 note=request.form.get("note", "").strip()))
        db.session.flush()
        recalc_actual_time(issue)
        log_activity(issue, f"Logged {minutes} minutes")
        db.session.commit()
    return redirect(url_for("issues.detail", issue_key=issue_key))


# ---------------------------------------------------------------------------
# Attachments (stored locally under data/attachments/)
# ---------------------------------------------------------------------------
@bp.route("/issue/<issue_key>/attach", methods=["POST"])
def attach(issue_key):
    issue = Issue.query.filter_by(issue_key=issue_key).first_or_404()
    file = request.files.get("file")
    if file and file.filename:
        original = secure_filename(file.filename)
        stored = f"{uuid.uuid4().hex}_{original}"
        path = os.path.join(config.ATTACHMENTS_DIR, stored)
        file.save(path)
        db.session.add(Attachment(
            issue_id=issue.id, original_name=original, stored_name=stored,
            size_bytes=os.path.getsize(path),
        ))
        log_activity(issue, f"Attached {original}")
        db.session.commit()
    return redirect(url_for("issues.detail", issue_key=issue_key))


@bp.route("/attachment/<int:att_id>")
def download_attachment(att_id):
    att = Attachment.query.get_or_404(att_id)
    return send_from_directory(config.ATTACHMENTS_DIR, att.stored_name,
                               as_attachment=True, download_name=att.original_name)


# ---------------------------------------------------------------------------
# Kanban board
# ---------------------------------------------------------------------------
@bp.route("/kanban")
def kanban():
    f_project = request.args.get("project", "")
    query = Issue.query
    if f_project:
        query = query.filter(Issue.project_id == int(f_project))
    issues = query.all()

    columns = {status: [] for status in config.STATUSES}
    for issue in issues:
        columns.setdefault(issue.status, []).append(issue)

    return render_template(
        "kanban.html",
        columns=columns,
        statuses=config.STATUSES,
        projects=Project.query.order_by(Project.key).all(),
        selected_project=f_project,
    )
