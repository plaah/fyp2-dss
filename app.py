"""
Flask Application Factory
===========================
Initialises the Flask app, SQLAlchemy database, and registers all blueprints.
Page routes for the frontend dashboard are also defined here.
"""

from pathlib import Path
from flask import Flask, send_from_directory, abort
from config import Config
from src.models.db_models import db
from src.api.routes import api_bp

REACT_DIST = Path(__file__).parent / 'frontend' / 'dist'


def create_app() -> Flask:
    app = Flask(__name__, static_folder=None)
    app.config.from_object(Config)

    db.init_app(app)
    app.register_blueprint(api_bp, url_prefix='/api/v1')

    # ── Serve React build ─────────────────────────────────────────────────────
    @app.route('/assets/<path:filename>')
    def react_assets(filename: str):
        return send_from_directory(REACT_DIST / 'assets', filename)

    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve_react(path: str):
        if path.startswith('api/'):
            abort(404)
        target = REACT_DIST / path
        if path and target.exists() and target.is_file():
            return send_from_directory(REACT_DIST, path)
        return send_from_directory(REACT_DIST, 'index.html')

    return app


if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        db.create_all()
        # Eager-load ML models at startup so first prediction is instant
        from src.api.routes import _grouper
        _grouper._load()
    app.run(debug=True, port=5001)
