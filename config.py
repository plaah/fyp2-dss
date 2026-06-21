import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        'postgresql://localhost:5432/fyp2_db'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DEBUG = True
    RETRAIN_THRESHOLD = int(os.environ.get('RETRAIN_THRESHOLD', 50))
