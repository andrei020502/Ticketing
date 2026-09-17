"""
database/db.py
SQLAlchemy database object + initialization helpers.

The database is created automatically on first launch. If it is empty,
a few sample projects are seeded so the app is usable immediately.
"""

import os
from flask_sqlalchemy import SQLAlchemy

# Single shared SQLAlchemy instance, imported by models and routes.
db = SQLAlchemy()


def init_db(app):
    """Create the data folders and all tables if they do not yet exist."""
    import config
    from database import models  # noqa: F401  (ensures models are registered)

    # Make sure data/, data/attachments/ and data/backups/ exist.
    os.makedirs(config.DATA_DIR, exist_ok=True)
    os.makedirs(config.ATTACHMENTS_DIR, exist_ok=True)
    os.makedirs(config.BACKUP_DIR, exist_ok=True)

    with app.app_context():
        db.create_all()
        _seed_defaults()


def _seed_defaults():
    """Insert a couple of starter projects on a brand-new database."""
    import config
    from database.models import Project

    if Project.query.count() > 0:
        return

    starters = [
        ("Personal Development", "DEV", "Software-development ideas, bugs, and features."),
        ("WFM Reporting Dashboard", "WFM", "Workforce-management reporting work."),
        ("Homelab", "HOME", "Homelab infrastructure and experiments."),
        ("IT Automation", "AUTO", "Scripts and automation for IT tasks."),
    ]
    for name, key, desc in starters:
        db.session.add(Project(name=name, key=key, description=desc))
    db.session.commit()
