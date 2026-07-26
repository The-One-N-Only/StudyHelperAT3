import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret')
    SESSION_TYPE = 'sqlalchemy'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///server.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DEBUG = False
    ALEMBIC_DB_URL = os.getenv('DATABASE_URL', 'sqlite:///server.db')
    REDIS_URL = os.getenv('REDIS_URL', '')


BROWSE_SERVER_TIMEOUT_SECONDS = 25
