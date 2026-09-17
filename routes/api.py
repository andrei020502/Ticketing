"""
routes/api.py
Simple REST API. All endpoints are local-only (served on 127.0.0.1).

    GET    /api/issues
    GET    /api/issues/<key>
    POST   /api/issues
    PUT    /api/issues/<key>
    DELETE /api/issues/<key>

    GET    /api/projects
    POST   /api/projects
"""

from flask import Blueprint, request, jsonify, abort

import config
from database.db import db
from database.models import Issue, Project
from database.helpers import (
    generate_issue_key, log_activity, resolve_labels, parse_date,
    parse_time_to_minutes
)

bp = Blueprint("api", __name__, url_prefix="/api")


# ---------------------------------------------------------------------------
# Issues
# ---------------------------------------------------------------------------
@bp.route("/issues", methods=["GET"])
def get_issues():
    query = Issue.query
    # Optional filters via query string.
    if request.args.get("status"):
        query = query.filter(Issue.status == request.args["status"])
    if request.args.get("project"):
        query = query.filter(Issue.project.has(key=request.args["project"]))
    if request.args.get("type"):
        query = query.filter(Issue.issue_type == request.args["type"])
    issues = query.order_by(Issue.created_date.desc()).all()
    return jsonify([i.to_dict() for i in issues])


@bp.route("/issues/<issue_key>", methods=["GET"])
def get_issue(issue_key):
    issue = Issue.query.filter_by(issue_key=issue_key).first()
    if not issue:
        abort(404, description="Issue not found")
    return jsonify(issue.to_dict(full=True))


@bp.route("/issues", methods=["POST"])
def create_issue():
    data = request.get_json(silent=True) or {}
    if not data.get("title"):
        abort(400, description="title is required")

    # Resolve project by key or id.
    project = None
    if data.get("project_key"):
        project = Project.query.filter_by(key=data["project_key"]).first()
    elif data.get("project_id"):
        project = Project.query.get(data["project_id"])
    if not project:
        abort(400, description="Valid project_key or project_id is required")

    issue = Issue(
        issue_key=generate_issue_key(project),
        title=data["title"],
        description=data.get("description", ""),
        issue_type=data.get("issue_type", "Task"),
        status=data.get("status", "Backlog"),
        priority=data.get("priority", "Medium"),
        project_id=project.id,
        assignee=data.get("assignee", config.DEFAULT_ASSIGNEE),
        due_date=parse_date(data.get("due_date")),
        estimated_minutes=parse_time_to_minutes(data.get("estimated_time")),
    )
    if data.get("labels"):
        issue.labels = resolve_labels(data["labels"])
    db.session.add(issue)
    db.session.flush()
    log_activity(issue, "Created (via API)")
    db.session.commit()
    return jsonify(issue.to_dict(full=True)), 201


@bp.route("/issues/<issue_key>", methods=["PUT"])
def update_issue(issue_key):
    issue = Issue.query.filter_by(issue_key=issue_key).first()
    if not issue:
        abort(404, description="Issue not found")
    data = request.get_json(silent=True) or {}

    for field in ["title", "description", "issue_type", "status",
                  "priority", "assignee", "resolution", "notes"]:
        if field in data:
            if field == "status" and data[field] != issue.status:
                log_activity(issue, f"Status changed to {data[field]}")
            setattr(issue, field, data[field])

    if "due_date" in data:
        issue.due_date = parse_date(data["due_date"])
    if "estimated_time" in data:
        issue.estimated_minutes = parse_time_to_minutes(data["estimated_time"])
    if "labels" in data:
        issue.labels = resolve_labels(data["labels"])

    db.session.commit()
    return jsonify(issue.to_dict(full=True))


@bp.route("/issues/<issue_key>", methods=["DELETE"])
def delete_issue(issue_key):
    issue = Issue.query.filter_by(issue_key=issue_key).first()
    if not issue:
        abort(404, description="Issue not found")
    db.session.delete(issue)
    db.session.commit()
    return jsonify({"deleted": issue_key})


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------
@bp.route("/projects", methods=["GET"])
def get_projects():
    return jsonify([p.to_dict() for p in Project.query.order_by(Project.key).all()])


@bp.route("/projects", methods=["POST"])
def create_project():
    data = request.get_json(silent=True) or {}
    if not data.get("name") or not data.get("key"):
        abort(400, description="name and key are required")
    key = data["key"].upper()
    if Project.query.filter_by(key=key).first():
        abort(409, description=f"Project key '{key}' already exists")
    project = Project(name=data["name"], key=key,
                      description=data.get("description", ""))
    db.session.add(project)
    db.session.commit()
    return jsonify(project.to_dict()), 201
