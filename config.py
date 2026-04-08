import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-fyp2')
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        'postgresql://postgres:postgres@localhost:5432/fyp2_db'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DEBUG = True
