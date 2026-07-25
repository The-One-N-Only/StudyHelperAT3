import json
import logging
from flask import Blueprint, render_template, session, redirect, url_for, request, jsonify
import src.db as db

workspace_bp = Blueprint('workspace', __name__)

# ── Template definitions ──

WORKSPACE_TEMPLATES = [
    {
        "id": "essay",
        "name": "Essay",
        "description": "Default structure with source groups and intro/body/conclusion note areas",
        "icon": "bi bi-pencil-square",
        "structure": {
            "note_sections": ["Introduction", "Body", "Conclusion"],
            "source_groups": ["Primary Sources", "Secondary Sources", "References"]
        }
    },
    {
        "id": "lab_report",
        "name": "Lab Report",
        "description": "Structure with sections: Aim, Hypothesis, Method, Results, Discussion, Conclusion",
        "icon": "bi bi-flask",
        "structure": {
            "note_sections": ["Aim", "Hypothesis", "Method", "Results", "Discussion", "Conclusion"],
            "source_groups": ["Method Sources", "Reference Sources"]
        }
    },
    {
        "id": "literature_review",
        "name": "Literature Review",
        "description": "Theme-based groups with comparison notes",
        "icon": "bi bi-journal-text",
        "structure": {
            "note_sections": ["Theme 1", "Theme 2", "Theme 3", "Comparison Notes", "Synthesis"],
            "source_groups": ["Theme 1 Sources", "Theme 2 Sources", "Theme 3 Sources"]
        }
    }
]


@workspace_bp.route('/workspace')
def workspace_redirect():
    return redirect(url_for('index'))


@workspace_bp.route('/workspace/<int:workspace_id>')
def workspace(workspace_id):
    if not session.get('user_id'):
        return redirect(url_for('auth.login'))
    user_id = session['user_id']
    workspace = db.get_workspace(user_id, workspace_id)
    if not workspace:
        logging.info(f"User {user_id} tried to access missing workspace {workspace_id}")
        return redirect(url_for('index'))

    logging.info(f"User {user_id} accessed workspace {workspace_id}")
    return render_template('workspace.html', workspace_id=workspace_id, workspace_name=workspace['name'])


# ── Folder Endpoints ──

@workspace_bp.route('/workspace/create-folder', methods=['POST'])
def create_folder():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    data = request.json
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'status': False, 'error': 'Name required'}), 400
    parent_id = data.get('parent_id')
    folder = db.create_folder(name, user_id, parent_id)
    return jsonify({'status': True, 'folder': folder})


@workspace_bp.route('/workspace/rename-folder', methods=['POST'])
def rename_folder():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    data = request.json
    folder_id = data.get('folder_id')
    name = data.get('name', '').strip()
    if not folder_id or not name:
        return jsonify({'status': False, 'error': 'folder_id and name required'}), 400
    result = db.rename_folder(folder_id, name, user_id)
    if not result:
        return jsonify({'status': False, 'error': 'Folder not found'}), 404
    return jsonify({'status': True, 'folder': result})


@workspace_bp.route('/workspace/delete-folder', methods=['POST'])
def delete_folder():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    data = request.json
    folder_id = data.get('folder_id')
    if not folder_id:
        return jsonify({'status': False, 'error': 'folder_id required'}), 400
    if db.delete_folder(folder_id, user_id):
        return jsonify({'status': True})
    return jsonify({'status': False, 'error': 'Folder not found'}), 404


@workspace_bp.route('/workspace/move-to-folder', methods=['POST'])
def move_to_folder():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    data = request.json
    workspace_id = data.get('workspace_id')
    folder_id = data.get('folder_id')
    if not workspace_id:
        return jsonify({'status': False, 'error': 'workspace_id required'}), 400
    if db.move_to_folder(workspace_id, folder_id, user_id):
        return jsonify({'status': True})
    return jsonify({'status': False, 'error': 'Workspace not found'}), 404


@workspace_bp.route('/workspace/tree')
def workspace_tree():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    tree = db.get_folder_tree(user_id)
    return jsonify({'status': True, 'tree': tree})


# ── Template Endpoints ──

@workspace_bp.route('/workspace/templates')
def list_templates():
    return jsonify({'status': True, 'templates': WORKSPACE_TEMPLATES})


@workspace_bp.route('/workspace/<int:workspace_id>/apply-template', methods=['POST'])
def apply_template(workspace_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    data = request.json
    template_id = data.get('template_id')
    if not template_id:
        return jsonify({'status': False, 'error': 'template_id required'}), 400
    template = next((t for t in WORKSPACE_TEMPLATES if t['id'] == template_id), None)
    if not template:
        return jsonify({'status': False, 'error': 'Template not found'}), 404
    ws = db.get_workspace(user_id, workspace_id)
    if not ws:
        return jsonify({'status': False, 'error': 'Workspace not found'}), 404
    structure = template['structure']
    # Create note sections as notes
    for section in structure.get('note_sections', []):
        db.create_workspace_note(user_id, workspace_id, section, f"<h3>{section}</h3><p>Your notes here...</p>")
    logging.info(f"User {user_id} applied template '{template_id}' to workspace {workspace_id}")
    return jsonify({'status': True, 'template': template})


# ── Archive / Trash Endpoints ──

@workspace_bp.route('/workspace/<int:workspace_id>/archive', methods=['POST'])
def archive_workspace(workspace_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    if db.archive_workspace(workspace_id, user_id):
        return jsonify({'status': True})
    return jsonify({'status': False, 'error': 'Workspace not found'}), 404


@workspace_bp.route('/workspace/<int:workspace_id>/unarchive', methods=['POST'])
def unarchive_workspace(workspace_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    if db.unarchive_workspace(workspace_id, user_id):
        return jsonify({'status': True})
    return jsonify({'status': False, 'error': 'Workspace not found'}), 404


@workspace_bp.route('/workspace/archived')
def get_archived():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    workspaces = db.get_archived_workspaces(user_id)
    return jsonify({'status': True, 'workspaces': workspaces})


@workspace_bp.route('/workspace/trash')
def get_trash():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    workspaces = db.get_trash(user_id)
    return jsonify({'status': True, 'workspaces': workspaces})


@workspace_bp.route('/workspace/<int:workspace_id>/set-persona', methods=['POST'])
def set_persona(workspace_id):
    if not session.get('user_id'):
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    data = request.json
    persona = data.get('persona', 'formal')
    result = db.set_workspace_persona(workspace_id, session['user_id'], persona)
    if not result:
        return jsonify({'status': False, 'error': 'Invalid persona or workspace not found'}), 400
    logging.info(f"User {session['user_id']} set persona '{persona}' for workspace {workspace_id}")
    return jsonify({'status': True, 'persona': result['persona']})


@workspace_bp.route('/workspace/<int:workspace_id>/restore', methods=['POST'])
def restore_from_trash(workspace_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    if db.restore_from_trash(workspace_id, user_id):
        return jsonify({'status': True})
    return jsonify({'status': False, 'error': 'Workspace not found'}), 404


# ── Note Version History Endpoints ──

@workspace_bp.route('/workspace/<int:workspace_id>/note/<int:note_id>/versions')
def get_note_versions(workspace_id, note_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    versions = db.get_note_versions(note_id)
    return jsonify({'status': True, 'versions': versions})


@workspace_bp.route('/workspace/<int:workspace_id>/note/<int:note_id>/restore/<int:version_id>', methods=['POST'])
def restore_note_version(workspace_id, note_id, version_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    result = db.restore_note_version(note_id, version_id, user_id)
    if not result:
        return jsonify({'status': False, 'error': 'Version or note not found'}), 404
    return jsonify({'status': True, 'note': result})
