import logging

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for

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
    },
    {
        "id": "major_work",
        "name": "Major Work / Depth Study",
        "description": "Structured scaffold for long-form projects: proposals, checkpoints, source logs, drafts, and reflections",
        "icon": "bi bi-journal-richtext",
        "structure": {
            "note_sections": [
                "Proposal & Planning",
                "Source Log & Annotations",
                "Checkpoint 1",
                "Draft",
                "Peer Feedback",
                "Final Reflection"
            ],
            "source_groups": ["Primary Sources", "Secondary Sources", "References"]
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
    return render_template('workspace.html', workspace_id=workspace_id, workspace_name=workspace['name'], course_id=workspace.get('course_id'), course_name=workspace.get('course_name'), course_kla=workspace.get('course_kla'))


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


# ── Workspace Members / Invite Endpoints ──

@workspace_bp.route('/workspace/<int:workspace_id>/invite', methods=['POST'])
def generate_invite(workspace_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    ws = db.get_workspace(user_id, workspace_id)
    if not ws:
        return jsonify({'status': False, 'error': 'Workspace not found'}), 404
    role = db.get_user_workspace_role(workspace_id, user_id)
    if role != 'owner':
        return jsonify({'status': False, 'error': 'Only the owner can generate invites'}), 403
    data = request.json or {}
    invite_role = data.get('role', 'viewer')
    token = db.generate_invite_token(workspace_id, invite_role)
    invite_url = url_for('workspace.accept_invite', token=token, _external=True)
    return jsonify({'status': True, 'invite_url': invite_url, 'token': token})


@workspace_bp.route('/workspace/join/<token>')
def accept_invite(token):
    if not session.get('user_id'):
        return redirect(url_for('auth.login'))
    user_id = session['user_id']
    result = db.verify_invite_token(token)
    if not result:
        return redirect(url_for('index'))
    workspace_id, role = result
    ws = db.get_workspace(user_id, workspace_id)
    if ws:
        return redirect(url_for('workspace.workspace', workspace_id=workspace_id))
    db.add_workspace_member(workspace_id, user_id, role=role)
    logging.info(f"User {user_id} joined workspace {workspace_id} via invite with role {role}")
    return redirect(url_for('workspace.workspace', workspace_id=workspace_id))


@workspace_bp.route('/workspace/<int:workspace_id>/members', methods=['GET'])
def list_members(workspace_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    ws = db.get_workspace(user_id, workspace_id)
    if not ws:
        return jsonify({'status': False, 'error': 'Workspace not found'}), 404
    members = db.get_workspace_members(workspace_id)
    return jsonify({'status': True, 'members': members})


@workspace_bp.route('/workspace/<int:workspace_id>/members/<int:member_id>/remove', methods=['POST'])
def remove_member(workspace_id, member_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    role = db.get_user_workspace_role(workspace_id, user_id)
    if role != 'owner':
        return jsonify({'status': False, 'error': 'Only owner can remove members'}), 403
    if db.remove_workspace_member(workspace_id, member_id):
        return jsonify({'status': True})
    return jsonify({'status': False, 'error': 'Member not found'}), 404


@workspace_bp.route('/workspace/<int:workspace_id>/members/<int:member_id>/role', methods=['POST'])
def update_member_role(workspace_id, member_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    role = db.get_user_workspace_role(workspace_id, user_id)
    if role != 'owner':
        return jsonify({'status': False, 'error': 'Only owner can update roles'}), 403
    data = request.json
    new_role = data.get('role', 'viewer')
    if new_role not in ('editor', 'viewer'):
        return jsonify({'status': False, 'error': 'Invalid role'}), 400
    if db.update_member_role(workspace_id, member_id, new_role):
        return jsonify({'status': True})
    return jsonify({'status': False, 'error': 'Member not found'}), 404


@workspace_bp.route('/workspace/<int:workspace_id>/add-member', methods=['POST'])
def add_member_by_username(workspace_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    role = db.get_user_workspace_role(workspace_id, user_id)
    if role != 'owner':
        return jsonify({'status': False, 'error': 'Only owner can add members'}), 403
    data = request.json
    username = data.get('username', '').strip()
    if not username:
        return jsonify({'status': False, 'error': 'Username required'}), 400
    user = db.get_user_by_username(username)
    if not user:
        return jsonify({'status': False, 'error': 'User not found'}), 404
    if db.add_workspace_member(workspace_id, user.id, role='viewer'):
        logging.info(f"User {user_id} added member {user.id} to workspace {workspace_id}")
        return jsonify({'status': True})
    return jsonify({'status': False, 'error': 'Already a member'}), 400


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
def get_note_versions(_workspace_id, note_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    versions = db.get_note_versions(note_id)
    return jsonify({'status': True, 'versions': versions})


@workspace_bp.route('/workspace/<int:workspace_id>/note/<int:note_id>/restore/<int:version_id>', methods=['POST'])
def restore_note_version(_workspace_id, note_id, version_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'status': False, 'error': 'Not logged in'}), 401
    result = db.restore_note_version(note_id, version_id, user_id)
    if not result:
        return jsonify({'status': False, 'error': 'Version or note not found'}), 404
    return jsonify({'status': True, 'note': result})
