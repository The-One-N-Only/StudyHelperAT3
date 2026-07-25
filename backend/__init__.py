import logging
import os
import random
import secrets
from flask import Flask, render_template, request, session, redirect, url_for
from flask_session import Session
from flask_sqlalchemy import SQLAlchemy
import src.db as db
from src.logging_config import setup_logging
from src.tasks import task_queue
from src.cache import cache

_root = os.path.dirname(os.path.dirname(__file__))

db_flask = SQLAlchemy()

RESULT_IMAGE_FALLBACKS = [
    '/static/img/illustrations/open-book.svg',
    '/static/img/illustrations/scrollwork-flourish.svg',
    '/static/img/illustrations/stacked-books.svg',
    '/static/img/illustrations/compass-rose.svg',
    '/static/img/illustrations/browse-scholar.svg',
    '/static/img/illustrations/sextant.svg',
    '/static/img/illustrations/victorian-man.svg',
]


def random_result_fallback():
    return random.choice(RESULT_IMAGE_FALLBACKS)


LOGIN_EXEMPT = {'auth.login', 'auth.register', 'static'}


def _get_csrf_token():
    token = session.get('_csrf_token')
    if not token:
        token = secrets.token_urlsafe(16)
        session['_csrf_token'] = token
    return token


def create_app():
    app = Flask(__name__,
                template_folder=os.path.join(_root, 'templates'),
                static_folder=os.path.join(_root, 'static'),
                static_url_path='/static')
    app.config.from_object('backend.config.Config')

    setup_logging(app)
    cache.init_app(app.config.get("REDIS_URL"))

    db_flask.init_app(app)
    app.config['SESSION_SQLALCHEMY'] = db_flask
    Session(app)

    from backend.auth_routes import auth_bp
    from backend.browse_routes import browse_bp
    from backend.workspace_routes import workspace_bp
    from backend.api_routes import api_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(browse_bp)
    app.register_blueprint(workspace_bp)
    app.register_blueprint(api_bp, url_prefix='/api')

    app.jinja_env.globals['random_result_fallback'] = random_result_fallback

    @app.route('/')
    def index():
        user_id = session['user_id']
        logging.info(f"User {user_id} accessed home page")
        return render_template('index.html')

    @app.before_request
    def require_login():
        if request.endpoint and request.endpoint not in LOGIN_EXEMPT and not session.get('user_id'):
            return redirect(url_for('auth.login'))

    @app.context_processor
    def inject_user():
        ctx = {
            'logged_in': bool(session.get('user_id')),
            'current_username': session.get('username'),
            'csrf_token': _get_csrf_token()
        }
        if ctx['logged_in']:
            ctx['profile_picture'] = db.get_profile_picture_path(session.get('gender', 'gentleman'))
        return ctx

    from backend.error_handlers import register_error_handlers
    register_error_handlers(app)

    db.setup_db()

    task_queue.start()

    return app
