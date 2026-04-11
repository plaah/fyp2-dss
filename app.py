"""
Flask Application Factory
===========================
Initialises the Flask app, SQLAlchemy database, and registers all blueprints.
Page routes for the frontend dashboard are also defined here.
"""

from flask import Flask, render_template
from config import Config
from src.models.db_models import db
from src.api.routes import api_bp


def create_app() -> Flask:
    """
    Create and configure the Flask application.

    Returns:
        Flask: Fully configured application instance.
    """
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialise SQLAlchemy with this app
    db.init_app(app)

    # Register API blueprint under /api/v1
    app.register_blueprint(api_bp, url_prefix='/api/v1')

    # ── Frontend page routes ───────────────────────────────────────────────────
    @app.route('/')
    def index():
        """Serve the main ICD Grouping Prediction tool."""
        return render_template('index.html')

    @app.route('/dashboard')
    def dashboard():
        """Serve the Analytics Overview dashboard."""
        return render_template('dashboard.html')

    return app


if __name__ == '__main__':
    app = create_app()
    # Create tables on first run (idempotent)
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5001)
