from flask import Flask
from config import Config
from src.api.routes import api_bp

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.register_blueprint(api_bp, url_prefix='/api/v1')
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)