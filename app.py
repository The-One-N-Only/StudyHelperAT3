from flask import Flask, request, jsonify, render_template, session, redirect, url_for, send_file, flash, abort
from flask_session import Session
import os
from dotenv import load_dotenv
import io
import src.db as db
import src.search as search
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
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
import logging
from flask import g

load_dotenv()

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

LOGIN_EXEMPT = {'login', 'register', 'static', 'not_found', 'internal_error', 'handle_exception'}

@app.before_request
def require_login():
    if request.endpoint and request.endpoint not in LOGIN_EXEMPT and not session.get('user_id'):
        return redirect(url_for('login'))

@app.route('/')
def index():
    user_id = session['user_id']
    saved = db.get_saved_items(user_id) or []
    recently_viewed = db.get_recently_viewed(user_id) or []
    recently_searched = db.get_recently_searched(user_id) or []
    for item in saved:
        item['saved'] = True
    user_data = {
        'saved': saved,
        'recently_viewed': recently_viewed,
        'recently_searched': recently_searched
    }
    logging.info(f"User {user_id} accessed home page")
    return render_template('index.html', user_data=user_data)

@app.route('/browse')
def browse():
    logging.info(f"User {session.get('user_id', 'anonymous')} accessed browse page")
    return render_template('browse.html')

@app.route('/workspace')
def workspace():
    if not session.get('user_id'):
        return redirect('/')
    user_id = session['user_id']
    workspace_items = db.get_workspace_items(user_id) or []
    logging.info(f"User {user_id} accessed workspace page")
    return render_template('workspace.html', workspace_items=workspace_items)

@app.route('/upload')
def upload():
    if not session.get('user_id'):
        return redirect('/')
    logging.info(f"User {session['user_id']} accessed upload page")
    return render_template('upload.html')

@app.route('/saved')
def saved():
    if not session.get('user_id'):
        return redirect('/')
    user_id = session['user_id']
    saved_items = db.get_saved_items(user_id) or []
    for item in saved_items:
        item['saved'] = True
    logging.info(f"User {user_id} accessed saved page")
    return render_template('saved.html', saved_items=saved_items)

def get_csrf_token():
    token = session.get('_csrf_token')
    if not token:
        token = secrets.token_urlsafe(16)
        session['_csrf_token'] = token
    return token

@app.context_processor
def inject_user():
    return {
        'logged_in': bool(session.get('user_id')),
        'current_username': session.get('username'),
        'csrf_token': get_csrf_token()
    }

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        if session.get('login_lockout_until') and time.time() < session['login_lockout_until']:
            flash('Too many registration attempts. Please try again later.', 'warning')
            return render_template('register.html')

        token = request.form.get('csrf_token')
        if not token or token != session.get('_csrf_token'):
            abort(400, 'Invalid CSRF token')

        email = request.form.get('email', '').strip()
        name = request.form.get('name', '').strip()
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not email or not username or not password:
            flash('Email, username and password are required.', 'danger')
            return render_template('register.html')

        if len(password) < 8:
            flash('Password must be at least 8 characters.', 'danger')
            return render_template('register.html')

        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('register.html')

        if not re.match(r'^[A-Za-z0-9_.-]{3,30}$', username):
            flash('Username may only contain letters, numbers, dots, underscores, or hyphens.', 'danger')
            return render_template('register.html')

        if '@' not in email or len(email) > 254:
            flash('Please enter a valid email address.', 'danger')
            return render_template('register.html')

        existing_email = db.get_user_by_email(email)
        existing_username = db.get_user_by_username(username)
        if existing_email:
            flash('Email is already registered.', 'danger')
            return render_template('register.html')
        if existing_username:
            flash('Username already exists.', 'danger')
            return render_template('register.html')

        password_hash = generate_password_hash(password)
        user = db.create_local_user(email, username, password_hash, name=name)
        session.clear()
        session['user_id'] = user['id']
        session['username'] = user['username']
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
    source = data['source']
    num_results = data['num_results']
    filters = data.get('filters', {})
    user_id = session.get('user_id')
    
    if source == 'wikipedia':
        results = search.wikipedia(query, num_results, user_id=user_id)
    elif source == 'gbooks':
        results = search.gbooks(query, num_results, filters, user_id=user_id)
    else:
        results = []
    
    logging.info(f"User {user_id} searched for '{query}' on {source}")
    return jsonify({'status': True, 'results': results})

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
            result = summarise.summarise_url(url, data.get('title', ''), atn, user_id)
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
    item_id = data['item_id']
    summary = data['summary']
    bullets = json.dumps(data['bullets'])
    relevance = data.get('relevance')
    atn_used = data.get('atn_used')
    citation_apa = data['citation_apa']
    citation_harvard = data['citation_harvard']
    
    result = db.add_to_workspace(user_id, item_id, summary, bullets, relevance, atn_used, citation_apa, citation_harvard)
    logging.info(f"User {user_id} added item {item_id} to workspace")
    return jsonify({'status': True, 'item': result})

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
    
    items = db.get_workspace_items(user_id) or []
    logging.info(f"User {user_id} viewed workspace items")
    return jsonify({'status': True, 'items': items})

@app.route('/api/citations/generate', methods=['POST'])
def generate_citations():
    data = request.json
    items = data['items']
    format_type = data['format']
    
    citations_list = []
    for item in items:
        if format_type == 'apa':
            cit = citations.format_apa(item['title'], item['source_name'], item['url'], item.get('author'), item.get('year'))
        else:
            cit = citations.format_harvard(item['title'], item['source_name'], item['url'], item.get('author'), item.get('year'))
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
    result = db.save_item(item_id, user_id)
    logging.info(f"User {user_id} saved item {item_id}")
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
    
    data = request.json
    messages = data.get('messages', [])
    atn = data.get('atn')
    
    if not messages:
        return jsonify({'status': False, 'error': 'No messages provided'}), 400
    
    result = answer.chat_with_sources(messages, user_id, atn=atn)
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

@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500

@app.errorhandler(Exception)
def handle_exception(e):
    logging.error(f"Unhandled exception: {str(e)}")
    return render_template('500.html'), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8010, debug=False)