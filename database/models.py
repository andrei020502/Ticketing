"""
database/models.py
SQLAlchemy ORM models for the ticketing application.

Tables:
    projects        - top-level containers, provide the ID prefix (DEV, HOME...)
    issues          - the core work items (issue is the umbrella term)
    comments        - threaded notes on an issue
    labels          - reusable tags
    issue_labels    - many-to-many join between issues and labels
    attachments     - local file attachments, stored under data/attachments/
    activity_log    - history of important changes per issue
    time_entries    - recorded time (manual or timer) per issue
"""

from datetime import datetime, timezone
from database.db import db


def _utcnow():
    """Timezone-aware UTC timestamp (stored naive for SQLite simplicity)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# Many-to-many join: issues <-> labels
# ---------------------------------------------------------------------------
issue_labels = db.Table(
    "issue_labels",
    db.Column("issue_id", db.Integer, db.ForeignKey("issues.id", ondelete="CASCADE"), primary_key=True),
    db.Column("label_id", db.Integer, db.ForeignKey("labels.id", ondelete="CASCADE"), primary_key=True),
)


class Project(db.Model):
    __tablename__ = "projects"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    key = db.Column(db.String(20), nullable=False, unique=True)  # e.g. DEV, HOME
    description = db.Column(db.Text, default="")
    created_date = db.Column(db.DateTime, default=_utcnow)

    # Running counter used to build readable IDs like DEV-1, DEV-2 ...
    issue_counter = db.Column(db.Integer, default=0)

    issues = db.relationship(
        "Issue", back_populates="project", cascade="all, delete-orphan"
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "key": self.key,
            "description": self.description,
            "created_date": self.created_date.isoformat() if self.created_date else None,
            "issue_count": len(self.issues),
        }


class Issue(db.Model):
    __tablename__ = "issues"

    id = db.Column(db.Integer, primary_key=True)
    # Human-readable key, e.g. DEV-42. Generated on creation.
    issue_key = db.Column(db.String(40), nullable=False, unique=True, index=True)

    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text, default="")
    issue_type = db.Column(db.String(30), nullable=False, default="Task")
    status = db.Column(db.String(30), nullable=False, default="Backlog", index=True)
    priority = db.Column(db.String(20), nullable=False, default="Medium")

    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    project = db.relationship("Project", back_populates="issues")

    assignee = db.Column(db.String(100), default="Me")

    created_date = db.Column(db.DateTime, default=_utcnow)
    updated_date = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow)
    due_date = db.Column(db.DateTime, nullable=True)

    # Self-referential parent (Epic -> Story -> Subtask, etc.).
    parent_id = db.Column(db.Integer, db.ForeignKey("issues.id"), nullable=True)
    children = db.relationship(
        "Issue", backref=db.backref("parent", remote_side=[id]), lazy="select"
    )

    estimated_minutes = db.Column(db.Integer, default=0)  # stored in minutes
    actual_minutes = db.Column(db.Integer, default=0)      # rolled up from time_entries
    resolution = db.Column(db.String(40), nullable=True)

    # Private personal notes, local only.
    notes = db.Column(db.Text, default="")

    labels = db.relationship("Label", secondary=issue_labels, back_populates="issues")
    comments = db.relationship(
        "Comment", back_populates="issue", cascade="all, delete-orphan",
        order_by="Comment.created_date"
    )
    attachments = db.relationship(
        "Attachment", back_populates="issue", cascade="all, delete-orphan"
    )
    activities = db.relationship(
        "ActivityLog", back_populates="issue", cascade="all, delete-orphan",
        order_by="ActivityLog.created_date.desc()"
    )
    time_entries = db.relationship(
        "TimeEntry", back_populates="issue", cascade="all, delete-orphan",
        order_by="TimeEntry.started_at.desc()"
    )

    def to_dict(self, full=False):
        data = {
            "id": self.id,
            "issue_key": self.issue_key,
            "title": self.title,
            "issue_type": self.issue_type,
            "status": self.status,
            "priority": self.priority,
            "project_id": self.project_id,
            "project_key": self.project.key if self.project else None,
            "assignee": self.assignee,
            "created_date": self.created_date.isoformat() if self.created_date else None,
            "updated_date": self.updated_date.isoformat() if self.updated_date else None,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "parent_id": self.parent_id,
            "estimated_minutes": self.estimated_minutes,
            "actual_minutes": self.actual_minutes,
            "resolution": self.resolution,
            "labels": [l.name for l in self.labels],
        }
        if full:
            data.update({
                "description": self.description,
                "notes": self.notes,
                "comments": [c.to_dict() for c in self.comments],
                "attachments": [a.to_dict() for a in self.attachments],
                "activities": [a.to_dict() for a in self.activities],
                "time_entries": [t.to_dict() for t in self.time_entries],
            })
        return data


class Comment(db.Model):
    __tablename__ = "comments"

    id = db.Column(db.Integer, primary_key=True)
    issue_id = db.Column(db.Integer, db.ForeignKey("issues.id"), nullable=False)
    issue = db.relationship("Issue", back_populates="comments")

    author = db.Column(db.String(100), default="Me")
    body = db.Column(db.Text, nullable=False)
    created_date = db.Column(db.DateTime, default=_utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "author": self.author,
            "body": self.body,
            "created_date": self.created_date.isoformat() if self.created_date else None,
        }


class Label(db.Model):
    __tablename__ = "labels"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), nullable=False, unique=True)
    color = db.Column(db.String(20), default="#6b7280")

    issues = db.relationship("Issue", secondary=issue_labels, back_populates="labels")

    def to_dict(self):
        return {"id": self.id, "name": self.name, "color": self.color}


class Attachment(db.Model):
    __tablename__ = "attachments"

    id = db.Column(db.Integer, primary_key=True)
    issue_id = db.Column(db.Integer, db.ForeignKey("issues.id"), nullable=False)
    issue = db.relationship("Issue", back_populates="attachments")

    original_name = db.Column(db.String(300), nullable=False)
    stored_name = db.Column(db.String(300), nullable=False)  # unique name on disk
    size_bytes = db.Column(db.Integer, default=0)
    uploaded_date = db.Column(db.DateTime, default=_utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "original_name": self.original_name,
            "stored_name": self.stored_name,
            "size_bytes": self.size_bytes,
            "uploaded_date": self.uploaded_date.isoformat() if self.uploaded_date else None,
        }


class ActivityLog(db.Model):
    __tablename__ = "activity_log"

    id = db.Column(db.Integer, primary_key=True)
    issue_id = db.Column(db.Integer, db.ForeignKey("issues.id"), nullable=False)
    issue = db.relationship("Issue", back_populates="activities")

    action = db.Column(db.String(300), nullable=False)  # human-readable text
    created_date = db.Column(db.DateTime, default=_utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "action": self.action,
            "created_date": self.created_date.isoformat() if self.created_date else None,
        }


class TimeEntry(db.Model):
    __tablename__ = "time_entries"

    id = db.Column(db.Integer, primary_key=True)
    issue_id = db.Column(db.Integer, db.ForeignKey("issues.id"), nullable=False)
    issue = db.relationship("Issue", back_populates="time_entries")

    minutes = db.Column(db.Integer, default=0)
    note = db.Column(db.String(300), default="")
    started_at = db.Column(db.DateTime, default=_utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "minutes": self.minutes,
            "note": self.note,
            "started_at": self.started_at.isoformat() if self.started_at else None,
        }
