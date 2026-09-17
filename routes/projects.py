"""
routes/projects.py
HTML views for managing projects.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from database.db import db
from database.models import Project, Issue

bp = Blueprint("projects", __name__)


@bp.route("/projects")
def list_projects():
    return render_template(
        "projects.html",
        projects=Project.query.order_by(Project.key).all(),
    )


@bp.route("/projects/new", methods=["POST"])
def create():
    name = request.form["name"].strip()
    key = request.form["key"].strip().upper()

    if not name or not key:
        flash("Project name and key are required.", "error")
        return redirect(url_for("projects.list_projects"))

    if Project.query.filter_by(key=key).first():
        flash(f"Project key '{key}' already exists.", "error")
        return redirect(url_for("projects.list_projects"))

    db.session.add(Project(
        name=name, key=key, description=request.form.get("description", "").strip()
    ))
    db.session.commit()
    flash(f"Created project {key}", "success")
    return redirect(url_for("projects.list_projects"))


@bp.route("/projects/<int:project_id>/delete", methods=["POST"])
def delete(project_id):
    project = Project.query.get_or_404(project_id)
    key = project.key
    db.session.delete(project)  # cascades to issues
    db.session.commit()
    flash(f"Deleted project {key} and its issues.", "success")
    return redirect(url_for("projects.list_projects"))
