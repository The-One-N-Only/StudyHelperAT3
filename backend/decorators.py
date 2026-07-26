from functools import wraps

from flask import jsonify, request, session

import src.db as db

ROLE_HIERARCHY = {"viewer": 0, "editor": 1, "owner": 2}


def require_workspace_role(min_role="editor", optional=False):
    """Decorator: require minimum role on workspace.
    If `optional=True` and no workspace_id is found, passes through.
    Expects a `workspace_id` in the URL parameter, JSON body, or kwargs.
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            user_id = session.get("user_id")
            if not user_id:
                return jsonify({"status": False, "error": "Not logged in"}), 401

            workspace_id = (
                kwargs.get("workspace_id") or
                request.args.get("workspace_id") or
                (request.get_json(silent=True) or {}).get("workspace_id")
            )

            if not workspace_id:
                if optional:
                    return f(*args, **kwargs)
                return jsonify({"status": False, "error": "No workspace_id"}), 400

            # Check if workspace exists first - if not, let the endpoint handle 404
            ws = db.get_workspace(workspace_id, user_id)
            if ws:
                role = db.get_user_workspace_role(workspace_id, user_id)
                if not role:
                    return jsonify({"status": False, "error": "Not a member of this workspace"}), 403
                if ROLE_HIERARCHY.get(role, 0) < ROLE_HIERARCHY.get(min_role, 1):
                    return jsonify({"status": False, "error": f"Need {min_role} role, have {role}"}), 403
            elif not optional:
                # Workspace doesn't exist - let the endpoint handle 404
                pass

            return f(*args, **kwargs)
        return wrapper
    return decorator
