import logging

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for

import src.db as db
import src.pubmed as pubmed

browse_bp = Blueprint('browse', __name__)


@browse_bp.route('/browse')
def browse():
    logging.info(f"User {session.get('user_id', 'anonymous')} accessed browse page")
    return render_template('browse.html')


@browse_bp.route('/saved')
def saved_page():
    if not session.get('user_id'):
        return redirect(url_for('auth.login'))
    logging.info(f"User {session['user_id']} accessed saved sources page")
    return render_template('saved.html')


@browse_bp.route('/browse/autocomplete-mesh')
def autocomplete_mesh():
    q = request.args.get('q', '')
    if not q or len(q) < 1:
        return jsonify({'status': False, 'suggestions': []})
    terms = pubmed.get_mesh_terms(q, num_results=10)
    return jsonify({'status': True, 'suggestions': terms})


@browse_bp.route('/usage')
def usage_page():
    if not session.get('user_id'):
        return redirect(url_for('auth.login'))
    logging.info(f"User {session['user_id']} accessed usage dashboard")
    return render_template('usage.html')


@browse_bp.route('/classes')
def classes_page():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('auth.login'))
    logging.info(f"User {user_id} accessed classes page")
    return render_template('classes.html')


@browse_bp.route('/browse/global-search')
def global_search():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('auth.login'))
    q = request.args.get('q', '').strip()
    if not q:
        return render_template('global_results.html', query='', results={})

    results = {
        'sources': [],
        'files': [],
        'notes': [],
        'workspaces': []
    }

    # Search saved items by title/source
    saved_items = db.get_saved_items(user_id) or []
    for item in saved_items:
        if q.lower() in (item.get('title', '') or '').lower() or q.lower() in (item.get('source_name', '') or '').lower():
            results['sources'].append(item)

    # Search uploaded files by filename
    files = db.get_uploaded_files(user_id) or []
    for f in files:
        if q.lower() in (f.get('filename', '') or '').lower():
            results['files'].append(f)

    # Search notes content
    notes = db.get_notes(user_id) or []
    for note in notes:
        if q.lower() in (note.get('title', '') or '').lower() or q.lower() in (note.get('content', '') or '').lower():
            results['notes'].append(note)

    # Search workspace names
    workspaces = db.get_user_workspaces(user_id) or []
    for ws in workspaces:
        if q.lower() in (ws.get('name', '') or '').lower():
            results['workspaces'].append(ws)

    logging.info(f"User {user_id} performed global search for '{q}'")
    return render_template('global_results.html', query=q, results=results)


@browse_bp.route('/dashboard')
def dashboard_page():
    if not session.get('user_id'):
        return redirect(url_for('auth.login'))
    logging.info(f"User {session['user_id']} accessed dashboard page")
    return render_template('dashboard.html')
