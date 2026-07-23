from flask import Flask, request, jsonify, render_template, session, redirect, url_for, send_file, flash, abort
from flask_session import Session
import os
from dotenv import load_dotenv
load_dotenv()
import io
import src.db as db
import src.search as search
import src.pubmed as pubmed
import src.summarise as summarise
import src.proxy as proxy
import src.citations as citations
import src.files as files
import src.export as export
import src.answer as answer
import json
import uuid
import mimetypes
import secrets
import time
import re
import concurrent.futures
import random
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
import logging
from flask import g

# Configure logging
logging.basicConfig(
    filename='user_activity.log',
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)
#kr
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret')
app.config['SESSION_TYPE'] = 'sqlalchemy'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///server.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['DEBUG'] = False
db_flask = SQLAlchemy(app)
app.config['SESSION_SQLALCHEMY'] = db_flask
Session(app)

db.setup_db()

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

app.jinja_env.globals['random_result_fallback'] = random_result_fallback

LOGIN_EXEMPT = {'login', 'register', 'static', 'not_found', 'internal_error', 'handle_exception'}
BROWSE_SERVER_TIMEOUT_SECONDS = 25

@app.before_request
def require_login():
    if request.endpoint and request.endpoint not in LOGIN_EXEMPT and not session.get('user_id'):
        return redirect(url_for('login'))

@app.route('/')
def index():
    user_id = session['user_id']
    logging.info(f"User {user_id} accessed home page")
    return render_template('index.html')

@app.route('/browse')
def browse():
    logging.info(f"User {session.get('user_id', 'anonymous')} accessed browse page")
    return render_template('browse.html')

@app.route('/workspace')
def workspace_redirect():
    return redirect(url_for('index'))

@app.route('/workspace/<int:workspace_id>')
def workspace(workspace_id):
    if not session.get('user_id'):
        return redirect(url_for('login'))
    user_id = session['user_id']
    workspace = db.get_workspace(user_id, workspace_id)
    if not workspace:
        logging.info(f"User {user_id} tried to access missing workspace {workspace_id}")
        return redirect(url_for('index'))

    logging.info(f"User {user_id} accessed workspace {workspace_id}")
    return render_template('workspace.html', workspace_id=workspace_id, workspace_name=workspace['name'])

def get_csrf_token():
    token = session.get('_csrf_token')
    if not token:
        token = secrets.token_urlsafe(16)
        session['_csrf_token'] = token
    return token

@app.context_processor
def inject_user():
    ctx = {
        'logged_in': bool(session.get('user_id')),
        'current_username': session.get('username'),
        'csrf_token': get_csrf_token()
    }
    if ctx['logged_in']:
        ctx['profile_picture'] = db.get_profile_picture_path(session.get('gender', 'gentleman'))
    return ctx

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Capture submitted form values so we can re-populate the form
        form_values = {
            'name': request.form.get('name', '').strip(),
            'email': request.form.get('email', '').strip(),
            'username': request.form.get('username', '').strip(),
            'gender': request.form.get('gender', 'gentleman')
        }
        if session.get('login_lockout_until') and time.time() < session['login_lockout_until']:
            flash('Too many registration attempts. Please try again later.', 'warning')
            return render_template('register.html', form_values=form_values)

        token = request.form.get('csrf_token')
        if not token or token != session.get('_csrf_token'):
            abort(400, 'Invalid CSRF token')

        email = request.form.get('email', '').strip()
        name = request.form.get('name', '').strip()
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        gender = request.form.get('gender', 'gentleman')

        if gender not in ('gentleman', 'lady', 'secret'):
            gender = 'gentleman'

        if not email or not username or not password:
            flash('Email, username and password are required.', 'danger')
            form_values = {'name': name, 'email': email, 'username': username, 'gender': gender}
            return render_template('register.html', form_values=form_values)

        if len(name) > 255 or len(email) > 255 or len(username) > 255 or len(password) > 255:
            flash('Fields must not exceed 255 characters.', 'danger')
            form_values = {'name': name, 'email': email, 'username': username, 'gender': gender}
            return render_template('register.html', form_values=form_values)

        if len(password) < 8:
            flash('Password must be at least 8 characters.', 'danger')
            form_values = {'name': name, 'email': email, 'username': username, 'gender': gender}
            return render_template('register.html', form_values=form_values)

        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            form_values = {'name': name, 'email': email, 'username': username, 'gender': gender}
            return render_template('register.html', form_values=form_values)

        if not re.match(r'^[A-Za-z0-9_.-]{3,30}$', username):
            flash('Username may only contain letters, numbers, dots, underscores, or hyphens.', 'danger')
            form_values = {'name': name, 'email': email, 'username': username, 'gender': gender}
            return render_template('register.html', form_values=form_values)

        if '@' not in email or len(email) > 254:
            flash('Please enter a valid email address.', 'danger')
            form_values = {'name': name, 'email': email, 'username': username, 'gender': gender}
            return render_template('register.html', form_values=form_values)

        existing_email = db.get_user_by_email(email)
        existing_username = db.get_user_by_username(username)
        if existing_email:
            flash('Email is already registered.', 'danger')
            form_values = {'name': name, 'email': email, 'username': username, 'gender': gender}
            return render_template('register.html', form_values=form_values)
        if existing_username:
            flash('Username already exists.', 'danger')
            form_values = {'name': name, 'email': email, 'username': username, 'gender': gender}
            return render_template('register.html', form_values=form_values)

        try:
            password_hash = generate_password_hash(password)
            user = db.create_local_user(email, username, password_hash, name=name, gender=gender)
        except Exception as e:
            logging.error(f"Registration error: {str(e)}")
            flash('An error occurred during registration. Please try again.', 'danger')
            form_values = {'name': name, 'email': email, 'username': username, 'gender': gender}
            return render_template('register.html', form_values=form_values)

        session.clear()
        session['user_id'] = user['id']
        session['username'] = user['username']
        session['gender'] = user.get('gender', 'gentleman')
        flash('Registration successful! You are now logged in.', 'success')
        logging.info(f"User {user['id']} registered with username {username}")
        return redirect(url_for('index'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if session.get('login_lockout_until') and time.time() < session['login_lockout_until']:
            flash('Too many login attempts. Please try again later.', 'warning')
            return render_template('login.html')

        token = request.form.get('csrf_token')
        if not token or token != session.get('_csrf_token'):
            abort(400, 'Invalid CSRF token')

        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash('Username and password are required.', 'danger')
            return render_template('login.html')

        user = db.get_user_by_username(username)
        if user and user.password_hash and check_password_hash(user.password_hash, password):
            session.clear()
            session['user_id'] = user.id
            session['username'] = user.username or user.email
            session['gender'] = user.gender or 'gentleman'
            session.pop('login_attempts', None)
            session.pop('login_lockout_until', None)
            flash('Logged in successfully.', 'success')
            logging.info(f"User {user.id} logged in")
            return redirect(url_for('index'))

        attempts = session.get('login_attempts', 0) + 1
        session['login_attempts'] = attempts
        if attempts >= 5:
            session['login_lockout_until'] = time.time() + 300
            flash('Too many login attempts. Please try again in 5 minutes.', 'warning')
        else:
            flash('Invalid username or password.', 'danger')
        return render_template('login.html')

    return render_template('login.html')

@app.route('/user', methods=['GET', 'POST'])
def user():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    user_obj = db.get_user_by_id(user_id)
    if not user_obj:
        flash('User not found.', 'danger')
        return redirect(url_for('logout'))

    if request.method == 'POST':
        token = request.form.get('csrf_token')
        if not token or token != session.get('_csrf_token'):
            abort(400, 'Invalid CSRF token')

        name = request.form.get('name', '').strip()
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        gender = request.form.get('gender', 'gentleman')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if gender not in ('gentleman', 'lady', 'secret'):
            gender = 'gentleman'

        if not email or not username:
            flash('Email and username are required.', 'danger')
            return render_template('user.html', user=user_obj, gender=gender, profile_picture=db.get_profile_picture_path(gender))

        if len(name) > 255 or len(email) > 255 or len(username) > 255 or len(new_password) > 255:
            flash('Fields must not exceed 255 characters.', 'danger')
            return render_template('user.html', user=user_obj, gender=gender, profile_picture=db.get_profile_picture_path(gender))

        if '@' not in email or len(email) > 254:
            flash('Please enter a valid email address.', 'danger')
            return render_template('user.html', user=user_obj, gender=gender, profile_picture=db.get_profile_picture_path(gender))

        existing_email = db.get_user_by_email(email)
        if existing_email and existing_email.id != user_id:
            flash('Email is already in use by another account.', 'danger')
            return render_template('user.html', user=user_obj, gender=gender, profile_picture=db.get_profile_picture_path(gender))

        existing_username = db.get_user_by_username(username)
        if existing_username and existing_username.id != user_id:
            flash('Username is already in use by another account.', 'danger')
            return render_template('user.html', user=user_obj, gender=gender, profile_picture=db.get_profile_picture_path(gender))

        password_hash = None
        if new_password:
            if len(new_password) < 8:
                flash('Password must be at least 8 characters.', 'danger')
                return render_template('user.html', user=user_obj, gender=gender, profile_picture=db.get_profile_picture_path(gender))
            if new_password != confirm_password:
                flash('Passwords do not match.', 'danger')
                return render_template('user.html', user=user_obj, gender=gender, profile_picture=db.get_profile_picture_path(gender))
            password_hash = generate_password_hash(new_password)

        try:
            updated = db.update_user(user_id, name, username, email, gender, password_hash=password_hash)
        except Exception as e:
            logging.error(f"Profile update error: {str(e)}")
            flash('An error occurred while updating your profile. Please try again.', 'danger')
            return redirect(url_for('user'))

        if updated:
            session['username'] = updated['username']
            session['gender'] = updated['gender']
            flash('Profile updated successfully.', 'success')
        else:
            flash('Failed to update profile.', 'danger')

        return redirect(url_for('user'))

    return render_template('user.html', user=user_obj, gender=user_obj.gender or 'gentleman', profile_picture=db.get_profile_picture_path(user_obj.gender or 'gentleman'))

@app.route('/logout')
def logout():
    user_id = session.get('user_id')
    session.clear()
    flash('Logged out successfully.', 'success')
    logging.info(f"User {user_id} logged out")
    return redirect(url_for('login'))

@app.route('/api/browse/search', methods=['POST'])
def browse_search():
    data = request.json
    query = data['query']
    source = data.get('source')
    sources = data.get('sources')  # New: array of sources
    num_results = data['num_results']
    filters = data.get('filters', {})
    user_id = session.get('user_id')

    if not search.SERP_API_KEY:
        return jsonify({
            'status': False,
            'error': 'Browse search is not configured. Add SERP_API_KEY and restart StudyLib.'
        }), 503

    requested_sources = [source] if source else list(dict.fromkeys(sources or []))
    results = []
    try:
        for requested_source in requested_sources:
            results.extend(search.browse_serpapi_search(
                query,
                num_results,
                requested_source,
                filters,
                user_id=user_id,
            ))
    except search.SerpApiProviderError:
        return jsonify({
            'status': False,
            'error': 'Browse search could not reach SerpAPI. Try again shortly.'
        }), 502

    logging.info(f"User {user_id} searched for '{query}' on sources: {requested_sources}")

    return jsonify({'status': True, 'results': results})

@app.route('/api/browse/search-all', methods=['POST'])
def browse_search_all():
    """Search all sources in parallel and return mixed results."""
    data = request.json
    query = data['query']
    num_results = data.get('num_results', 20)
    sources = data.get('sources', ['wikipedia', 'gbooks', 'scholar'])
    filters = data.get('filters', {})
    user_id = session.get('user_id')

    if not query or not sources:
        return jsonify({'status': False, 'error': 'Query and sources required'}), 400

    if not search.SERP_API_KEY:
        return jsonify({
            'status': False,
            'error': 'Browse search is not configured. Add SERP_API_KEY and restart StudyLib.'
        }), 503

    requested_sources = []
    seen_sources = set()
    for source in sources:
        if source in seen_sources:
            continue
        seen_sources.add(source)
        requested_sources.append(source)

    # An explicit domain is more precise than the generic whitelist fan-out.
    if any(source.startswith('whitelist_') for source in requested_sources):
        requested_sources = [
            source for source in requested_sources if source != 'whitelist'
        ]

    selected_sources = set(requested_sources)
    dedicated_source_by_domain = {
        domain: source
        for source, (domain, _source_name) in search.BROWSE_SOURCE_DOMAINS.items()
    }
    requested_sources = [
        source
        for source in requested_sources
        if not (
            source.startswith('whitelist_')
            and dedicated_source_by_domain.get(source.split('_', 1)[1])
            in selected_sources
        )
    ]

    grouped_results = {}
    source_counts = {}
    source_errors = {}

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=6)
    futures = {
        source: executor.submit(
            search.browse_serpapi_search,
            query,
            num_results,
            source,
            filters,
            user_id=user_id,
        )
        for source in requested_sources
    }
    try:
        done, not_done = concurrent.futures.wait(
            futures.values(),
            timeout=BROWSE_SERVER_TIMEOUT_SECONDS,
        )
        for source, future in futures.items():
            if future in not_done:
                future.cancel()
                logging.warning("SerpAPI Browse search timed out for source %s", source)
                source_errors[source] = 'Search timed out'
                grouped_results[source] = []
                source_counts[source] = 0
                continue
            try:
                source_results = future.result() or []
                grouped_results[source] = source_results
                source_counts[source] = len(source_results)
            except search.SerpApiProviderError:
                source_errors[source] = 'SerpAPI search failed'
                grouped_results[source] = []
                source_counts[source] = 0
            except Exception:
                logging.exception("Browse search failed for source %s", source)
                source_errors[source] = 'Search failed'
                grouped_results[source] = []
                source_counts[source] = 0
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    if futures and len(source_errors) == len(futures):
        return jsonify({
            'status': False,
            'error': 'Browse search could not reach SerpAPI. Try again shortly.',
            'source_errors': source_errors,
        }), 502

    flattened = [
        (source, item)
        for source, items in grouped_results.items()
        for item in items
    ]
    unique_items = iter(search.deduplicate_results([item for _, item in flattened]))
    next_unique = next(unique_items, None)
    deduplicated_groups = {source: [] for source in grouped_results}
    all_results = []
    for source, item in flattened:
        if item is not next_unique:
            continue
        response_item = search.with_response_dedupe_metadata(item)
        deduplicated_groups[source].append(response_item)
        all_results.append(response_item)
        next_unique = next(unique_items, None)

    logging.info(
        f"User {user_id} performed multi-source search for '{query}' "
        f"across {len(futures)} sources"
    )

    return jsonify({
        'status': True,
        'results': all_results,
        'grouped_results': deduplicated_groups,
        'source_counts': source_counts,
        'source_errors': source_errors,
    })

@app.route('/api/browse/summary', methods=['POST'])
def browse_summary():
    data = request.json
    query = data.get('query', '').strip()
    results = data.get('results', [])
    atn = data.get('atn')
    user_id = session.get('user_id')

    if not query:
        return jsonify({'status': False, 'error': 'Query required'}), 400

    try:
        summary = summarise.summarise_search_results(query, results, atn)
        logging.info(f"User {user_id} requested search summary for '{query}'")
        return jsonify(summary)
    except Exception as e:
        logging.error(f"Search summary failed for user {user_id}: {str(e)}")
        return jsonify({'status': False, 'error': 'Search summarisation failed'}), 500

@app.route('/api/filters')
def api_filters():
    return send_file(os.path.join(os.path.dirname(__file__), 'src', 'filters.json'), mimetype='application/json')

@app.route('/api/pubmed/mesh-suggestions')
def pubmed_mesh_suggestions():
    query = request.args.get('q', '')
    if not query or len(query) < 2:
        return jsonify({'status': False, 'error': 'Query too short'}), 400

    terms = pubmed.get_mesh_terms(query, num_results=10)
    logging.info(f"User {session.get('user_id', 'anonymous')} requested MeSH suggestions for '{query}'")
    return jsonify({'status': True, 'suggestions': terms})

@app.route('/api/proxy/source')
def proxy_source():
    url = request.args.get('url')
    user_id = session.get('user_id')
    if not url:
        return jsonify({'status': False, 'error': 'No URL'}), 400
    try:
        result = proxy.fetch_source(url)
        logging.info(f"User {user_id} proxied source for {url}")
        return jsonify(result)
    except ValueError:
        return jsonify({'status': False, 'error': 'URL not allowed'}), 403

@app.route('/api/summarise', methods=['POST'])
def api_summarise():
    data = request.json
    url = data.get('url')
    file_id = data.get('file_id')
    atn = data.get('atn')
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    
    if url:
        try:
            result = summarise.summarise_url(url, data.get('title', ''), atn)
        except ValueError:
            return jsonify({'status': False, 'error': 'URL not allowed'}), 403
    elif file_id:
        result = summarise.summarise_file(file_id, user_id, atn)
    else:
        return jsonify({'status': False, 'error': 'No URL or file_id'}), 400
    
    logging.info(f"User {user_id} requested AI summary for {url or f'file {file_id}'}")
    return jsonify(result)

@app.route('/api/workspace/add', methods=['POST'])
def workspace_add():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    
    data = request.json
    item_id = data.get('item_id')
    summary = data.get('summary')
    bullets = json.dumps(data.get('bullets', []))
    relevance = data.get('relevance')
    atn_used = data.get('atn_used')
    citation_apa = data.get('citation_apa', '')
    citation_harvard = data.get('citation_harvard', '')
    workspace_id = data.get('workspace_id')
    
    try:
        result = db.add_to_workspace(user_id, item_id, summary, bullets, relevance, atn_used, citation_apa, citation_harvard, workspace_id)
        logging.info(f"User {user_id} added item {item_id} to workspace {workspace_id or 'default'}")
        return jsonify({'status': True, 'item': result})
    except Exception as e:
        logging.error(f"Error adding to workspace: {str(e)}")
        return jsonify({'status': False, 'error': 'Failed to add item'}), 500

@app.route('/api/workspaces/<int:workspace_id>/add-file', methods=['POST'])
def add_file_to_workspace(workspace_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    
    data = request.json
    file_id = data.get('file_id')
    if not file_id:
        return jsonify({'status': False, 'error': 'file_id required'}), 400
    
    try:
        result = db.add_file_to_workspace(user_id, file_id, workspace_id)
        logging.info(f"User {user_id} added file {file_id} to workspace {workspace_id}")
        return jsonify({'status': True, 'item': result})
    except Exception as e:
        logging.error(f"Error adding file to workspace: {str(e)}")
        return jsonify({'status': False, 'error': 'Failed to add file to workspace'}), 500

@app.route('/api/workspaces', methods=['GET'])
def get_workspaces():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    
    workspaces = db.get_user_workspaces(user_id)
    return jsonify({'status': True, 'workspaces': workspaces})

@app.route('/api/workspaces/<int:workspace_id>', methods=['GET'])
def get_workspace(workspace_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    
    workspace = db.get_workspace(user_id, workspace_id)
    if not workspace:
        return jsonify({'status': False, 'error': 'Workspace not found'}), 404

    return jsonify({'status': True, 'workspace': workspace})

@app.route('/api/workspaces/<int:workspace_id>/chat', methods=['GET'])
def get_workspace_chat(workspace_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401

    workspace = db.get_workspace(user_id, workspace_id)
    if not workspace:
        return jsonify({'status': False, 'error': 'Workspace not found'}), 404

    messages = db.get_workspace_chat_messages(workspace_id, user_id)
    return jsonify({
        'status': True,
        'messages': messages,
        'ai_configured': answer.client is not None,
    })

@app.route('/api/workspaces', methods=['POST'])
def create_workspace():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    
    data = request.json
    name = data.get('name', 'New Workspace').strip()[:25]
    if not name:
        return jsonify({'status': False, 'error': 'Workspace name is required'}), 400
    workspace = db.create_workspace(user_id, name)
    logging.info(f"User {user_id} created workspace: {name}")
    return jsonify({'status': True, 'workspace': workspace})

@app.route('/api/workspaces/<int:workspace_id>', methods=['PUT'])
def update_workspace(workspace_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    
    data = request.json
    name = data.get('name')
    if not name:
        return jsonify({'status': False, 'error': 'Name required'}), 400
    
    workspace = db.rename_workspace(workspace_id, user_id, name)
    if not workspace:
        return jsonify({'status': False, 'error': 'Workspace not found'}), 404
    
    logging.info(f"User {user_id} renamed workspace {workspace_id} to: {name}")
    return jsonify({'status': True, 'workspace': workspace})

@app.route('/api/workspaces/<int:workspace_id>', methods=['DELETE'])
def delete_workspace(workspace_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    
    if db.delete_workspace(workspace_id, user_id):
        logging.info(f"User {user_id} deleted workspace {workspace_id}")
        return jsonify({'status': True})
    return jsonify({'status': False, 'error': 'Workspace not found'}), 404

@app.route('/api/workspaces/<int:workspace_id>/notes', methods=['GET'])
def get_workspace_notes(workspace_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    
    notes = db.get_workspace_notes(workspace_id, user_id)
    return jsonify({'status': True, 'notes': notes})

@app.route('/api/workspaces/<int:workspace_id>/notes', methods=['POST'])
def create_workspace_note(workspace_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    
    data = request.json
    title = data.get('title', 'New Note')
    content = data.get('content', '')
    
    note = db.create_workspace_note(user_id, workspace_id, title, content)
    logging.info(f"User {user_id} created note in workspace {workspace_id}")
    return jsonify({'status': True, 'note': note})


@app.route('/api/workspace/<int:item_id>', methods=['DELETE'])
def workspace_remove(item_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    
    result = db.remove_from_workspace(item_id, user_id)
    if result:
        logging.info(f"User {user_id} removed item {item_id} from workspace")
        return jsonify({'status': True})
    return jsonify({'status': False, 'error': 'Not found'}), 404

@app.route('/api/workspace/reorder', methods=['POST'])
def workspace_reorder():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    
    data = request.json
    ordered_ids = data['ordered_ids']
    db.reorder_workspace(user_id, ordered_ids)
    logging.info(f"User {user_id} reordered workspace")
    return jsonify({'status': True})

@app.route('/api/workspace/items')
def workspace_items():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    
    workspace_id = request.args.get('workspace_id', type=int)
    items = db.get_workspace_items(user_id, workspace_id) or []
    for item in items:
        source_name = (item.get('source_name') or '').lower()
        source_url = item.get('source_url') or ''
        if source_name in ('gbooks', 'google books') or 'books.google.com' in source_url:
            volume_id = search._google_books_volume_id(source_url)
            if not volume_id:
                source_id = item.get('source_id', '')
                volume_id = search._google_books_volume_id(source_id)
            if not volume_id:
                source_id = item.get('source_id', '')
                if isinstance(source_id, str) and search.GOOGLE_BOOKS_VOLUME_ID_PATTERN.fullmatch(source_id):
                    volume_id = source_id
            if volume_id:
                item['google_books_volume_id'] = volume_id
            item['accessInfo'] = {
                'embeddable': True,
                'webReaderLink': source_url,
                'viewability': 'UNKNOWN',
                'accessViewStatus': 'NONE',
            }
    logging.info(f"User {user_id} viewed workspace items for workspace {workspace_id or 'default'}")
    return jsonify({'status': True, 'items': items})

@app.route('/api/citations/generate', methods=['POST'])
def generate_citations():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    
    data = request.json
    items = data['items']
    format_type = data['format']
    
    citations_list = []
    for item in items:
        kwargs = dict(
            title=item['title'],
            source_name=item['source_name'],
            url=item['url'],
            author=item.get('author'),
            year=item.get('year'),
            authors=item.get('authors'),
            journal=item.get('journal'),
            volume=item.get('volume'),
            issue=item.get('issue'),
            doi=item.get('doi'),
        )
        if format_type == 'apa':
            cit = citations.format_apa(**kwargs)
        else:
            cit = citations.format_harvard(**kwargs)
        citations_list.append(cit)
    
    logging.info(f"User {user_id} generated {len(items)} citations in {format_type} format")
    return jsonify({'status': True, 'citations': citations_list})

@app.route('/api/files/upload', methods=['POST'])
def upload_file():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    
    file = request.files.get('file')
    if not file:
        return jsonify({'status': False, 'error': 'No file'}), 400
    
    # Validate
    allowed_mimes = [
        'application/pdf', 
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',  # .docx
        'text/plain',  # .txt
        'image/jpeg', 'image/png', 'image/gif', 'image/webp',  # Images
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',  # .xlsx
        'application/vnd.ms-excel',  # .xls
        'application/x-msexcel',  # .xls alternative
        'application/x-excel'  # .xls alternative
    ]
    if file.mimetype not in allowed_mimes:
        return jsonify({'status': False, 'error': 'Invalid file type'}), 400
    
    if file.content_length > 10 * 1024 * 1024:  # 10MB
        return jsonify({'status': False, 'error': 'File too large'}), 400
    
    # Determine type
    if file.mimetype == 'application/pdf':
        file_type = 'pdf'
    elif file.mimetype == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
        file_type = 'docx'
    elif file.mimetype == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':
        file_type = 'xlsx'
    elif file.mimetype in ['application/vnd.ms-excel', 'application/x-msexcel', 'application/x-excel']:
        file_type = 'xls'
    elif file.mimetype.startswith('image/'):
        file_type = 'image'
    else:
        file_type = 'txt'
    
    # Save
    filename = f"{uuid.uuid4()}_{file.filename}"
    stored_path = f"static/uploads/{user_id}/{filename}"
    os.makedirs(os.path.dirname(stored_path), exist_ok=True)
    file.save(stored_path)
    
    # Extract text
    extracted_text = files.extract_text(stored_path, file_type)
    
    # DB
    result = db.create_uploaded_file(user_id, file.filename, stored_path, file_type, extracted_text, file.content_length)
    logging.info(f"User {user_id} uploaded file {file.filename} ({file_type})")
    return jsonify({'status': True, 'file_id': result['id'], 'filename': result['filename'], 'url': f"/static/uploads/{user_id}/{result['id']}_{result['filename']}"})

@app.route('/api/files/<int:file_id>', methods=['DELETE'])
def delete_file(file_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    
    result = db.delete_uploaded_file(file_id, user_id)
    if result:
        # Also delete from disk
        files = db.get_uploaded_files(user_id)
        file_data = next((f for f in files if f['id'] == file_id), None)
        if file_data:
            os.remove(file_data['stored_path'])
        logging.info(f"User {user_id} deleted file {file_id}")
        return jsonify({'status': True})
    return jsonify({'status': False, 'error': 'Not found'}), 404

@app.route('/api/files/list')
def list_files():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    
    files = db.get_uploaded_files(user_id) or []
    logging.info(f"User {user_id} listed uploaded files")
    return jsonify({'status': True, 'files': files})

@app.route('/api/files/search')
def search_files():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    
    query = request.args.get('q', '')
    results = db.search_uploaded_files(user_id, query)
    logging.info(f"User {user_id} searched uploaded files for '{query}'")
    return jsonify({'status': True, 'results': results})

@app.route('/api/export/pdf', methods=['POST'])
def export_pdf():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    
    data = request.json
    items = data['items']
    atn = data.get('atn')
    citation_format = data.get('citation_format', 'apa')
    
    pdf_data = export.export_pdf(items, atn, citation_format)
    logging.info(f"User {user_id} exported workspace as PDF")
    return send_file(io.BytesIO(pdf_data), as_attachment=True, download_name='StudyLib_Compilation.pdf', mimetype='application/pdf')

@app.route('/api/export/docx', methods=['POST'])
def export_docx():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    
    data = request.json
    items = data['items']
    atn = data.get('atn')
    citation_format = data.get('citation_format', 'apa')
    
    docx_data = export.export_docx(items, atn, citation_format)
    logging.info(f"User {user_id} exported workspace as DOCX")
    return send_file(io.BytesIO(docx_data), as_attachment=True, download_name='StudyLib_Compilation.docx', mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document')

@app.route('/api/item/save', methods=['POST'])
def save_item():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    
    data = request.json
    item_id = data['item_id']
    query = data.get('query', '')
    result = db.save_item(item_id, user_id, query=query)
    logging.info(f"User {user_id} saved item {item_id} with query '{query}'")
    return jsonify({'status': result is not None})

@app.route('/api/item/unsave', methods=['POST'])
def unsave_item():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    
    data = request.json
    item_id = data['item_id']
    result = db.unsave_item(item_id, user_id)
    logging.info(f"User {user_id} unsaved item {item_id}")
    return jsonify({'status': result is not None})

@app.route('/saved')
def saved_page():
    if not session.get('user_id'):
        return redirect(url_for('login'))
    logging.info(f"User {session['user_id']} accessed saved sources page")
    return render_template('saved.html')

@app.route('/api/saved')
def api_saved():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    
    grouped = db.get_saved_items_grouped(user_id)
    logging.info(f"User {user_id} fetched saved items")
    return jsonify({'status': True, 'groups': grouped})

@app.route('/api/recent/viewed', methods=['POST'])
def add_recent_viewed():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    
    data = request.json
    item_id = data['item_id']
    db.append_to_recently_viewed(user_id, item_id)
    logging.info(f"User {user_id} added to recently viewed {item_id}")
    return jsonify({'status': True})

@app.route('/api/answer/prompt', methods=['POST'])
def answer_prompt():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    
    data = request.json
    prompt = data.get('prompt', '').strip()
    search_web = data.get('search_web', True)
    atn = data.get('atn')
    
    if not prompt:
        return jsonify({'status': False, 'error': 'No prompt provided'}), 400
    
    result = answer.answer_prompt(prompt, user_id, search_web=search_web, atn=atn)
    logging.info(f"User {user_id} asked prompt: {prompt[:50]}")
    return jsonify(result)

@app.route('/api/answer/chat', methods=['POST'])
def answer_chat():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    
    data = request.get_json(silent=True) or {}
    messages = data.get('messages', [])
    atn = data.get('atn')
    workspace_id = data.get('workspace_id')
    
    if not messages:
        return jsonify({'status': False, 'error': 'No messages provided'}), 400

    latest_user_content = None
    if workspace_id is not None:
        if isinstance(workspace_id, bool):
            return jsonify({'status': False, 'error': 'Invalid workspace ID'}), 400
        try:
            workspace_id = int(workspace_id)
        except (TypeError, ValueError):
            return jsonify({'status': False, 'error': 'Invalid workspace ID'}), 400

        workspace = db.get_workspace(user_id, workspace_id)
        if not workspace:
            return jsonify({'status': False, 'error': 'Workspace not found'}), 404

        latest_user_content = next((
            message.get('content')
            for message in reversed(messages)
            if isinstance(message, dict)
            and message.get('role') == 'user'
            and isinstance(message.get('content'), str)
            and message.get('content').strip()
        ), None)
        if latest_user_content is None:
            return jsonify({'status': False, 'error': 'No user message provided'}), 400
    
    result = answer.chat_with_sources(messages, user_id, atn=atn)
    if isinstance(result, str):
        result = {'status': True, 'response': result}
    elif not isinstance(result, dict):
        logging.error("AI chat returned an invalid response type for user %s", user_id)
        result = {'status': False, 'error': 'Alexander returned an invalid response.'}

    if workspace_id is not None and result.get('status') is True:
        assistant_content = result.get('response')
        if not isinstance(assistant_content, str) or not assistant_content.strip():
            logging.error("AI chat returned no response text for user %s", user_id)
            return jsonify({
                'status': False,
                'error': 'Alexander returned an invalid response.',
            }), 502
        try:
            persisted = db.append_workspace_chat_turn(
                user_id,
                workspace_id,
                latest_user_content,
                assistant_content,
            )
        except Exception:
            logging.exception(
                "Failed to persist chat turn for user %s workspace %s",
                user_id,
                workspace_id,
            )
            return jsonify({
                'status': False,
                'error': 'Alexander answered, but the conversation could not be saved.',
            }), 500
        if not persisted:
            return jsonify({'status': False, 'error': 'Workspace not found'}), 404

    logging.info(f"User {user_id} had multi-turn conversation")
    return jsonify(result)

@app.route('/api/notes', methods=['GET', 'POST'])
def api_notes():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    
    if request.method == 'POST':
        data = request.json
        title = data.get('title', '').strip()
        content = data.get('content', '')
        if not title:
            return jsonify({'status': False, 'error': 'Title required'}), 400
        note = db.create_note(user_id, title, content)
        logging.info(f"User {user_id} created note {note['id']}")
        return jsonify({'status': True, 'note': note})
    else:
        notes = db.get_notes(user_id)
        return jsonify({'status': True, 'notes': notes})

@app.route('/api/notes/<int:note_id>', methods=['GET', 'PUT', 'DELETE'])
def api_note(note_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    
    if request.method == 'GET':
        note = db.get_note(note_id, user_id)
        if not note:
            return jsonify({'status': False, 'error': 'Not found'}), 404
        return jsonify({'status': True, 'note': note})
    elif request.method == 'PUT':
        data = request.json
        title = data.get('title')
        content = data.get('content')
        note = db.update_note(note_id, user_id, title=title, content=content)
        if not note:
            return jsonify({'status': False, 'error': 'Not found'}), 404
        logging.info(f"User {user_id} updated note {note_id}")
        return jsonify({'status': True, 'note': note})
    elif request.method == 'DELETE':
        result = db.delete_note(note_id, user_id)
        if not result:
            return jsonify({'status': False, 'error': 'Not found'}), 404
        logging.info(f"User {user_id} deleted note {note_id}")
        return jsonify({'status': True})

@app.errorhandler(Exception)
def handle_exception(e):
    logging.error(f"Unhandled exception: {str(e)}")
    return render_template('error.html'), 500

@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8010)), debug=True)
