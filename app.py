"""
app.py
Entry point for the local personal ticketing application.

Run with:
    python app.py

Then open:
    http://127.0.0.1:5000

The database and data folders are created automatically on first launch.
The server binds ONLY to 127.0.0.1 (localhost). It is never exposed to the
LAN or the internet.
"""

import webbrowser
import threading
from flask import Flask, render_template, jsonify, request

import config
from database.db import db, init_db


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = config.SECRET_KEY
    app.config["SQLALCHEMY_DATABASE_URI"] = config.SQLALCHEMY_DATABASE_URI
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = config.SQLALCHEMY_TRACK_MODIFICATIONS
    app.config["MAX_CONTENT_LENGTH"] = config.MAX_CONTENT_LENGTH

    # Bind the SQLAlchemy instance to this app and create tables/seed data.
    db.init_app(app)
    init_db(app)

    # Register blueprints.
    from routes.main import bp as main_bp
    from routes.issues import bp as issues_bp
    from routes.projects import bp as projects_bp
    from routes.api import bp as api_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(issues_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(api_bp)

    # Kanban drag-and-drop endpoint (AJAX). Kept here so it can use the
    # app context cleanly; delegates to the same status-change logic.
    @app.route("/api/kanban/move", methods=["POST"])
    def kanban_move():
        from database.models import Issue
        from database.helpers import log_activity
        data = request.get_json(silent=True) or {}
        issue = Issue.query.filter_by(issue_key=data.get("issue_key")).first()
        if not issue:
            return jsonify({"error": "not found"}), 404
        new_status = data.get("status")
        if new_status and new_status != issue.status:
            log_activity(issue, f"Status changed to {new_status}")
            issue.status = new_status
            db.session.commit()
        return jsonify({"ok": True, "issue_key": issue.issue_key, "status": issue.status})

    # Make config values (types, statuses, priorities) available to all templates.
    @app.context_processor
    def inject_globals():
        return {
            "APP_NAME": "Ticketing",
            "NAV_STATUSES": config.STATUSES,
            "NAV_TYPES": config.ISSUE_TYPES,
            "NAV_PRIORITIES": config.PRIORITIES,
        }

    # Template filter to render minutes as "2h 30m".
    from database.helpers import format_minutes
    app.jinja_env.filters["duration"] = format_minutes

    # Friendly error pages for the API (JSON) vs HTML.
    @app.errorhandler(404)
    def not_found(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": str(e.description)}), 404
        return render_template("404.html"), 404

    return app


def _open_browser():
    """Open the default browser once the server is up (used when run directly)."""
    webbrowser.open(f"http://{config.HOST}:{config.PORT}")


if __name__ == "__main__":
    app = create_app()
    # Open the browser shortly after startup (only in the main process,
    # not the reloader's child process).
    import os
    if os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        threading.Timer(1.2, _open_browser).start()

    # debug=False keeps it quiet and avoids the reloader opening two tabs.
    app.run(host=config.HOST, port=config.PORT, debug=False)
