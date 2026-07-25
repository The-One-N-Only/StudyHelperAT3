import logging
import re
import secrets
import time
from flask import Blueprint, request, render_template, session, redirect, url_for, flash, abort, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
import src.db as db
import src.oauth as oauth
import src.email as email
from src.ratelimit import check_login_rate_limit, record_login_attempt

auth_bp = Blueprint('auth', __name__)

_serializer = URLSafeTimedSerializer(secrets.token_urlsafe(32))


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        allowed, retry_after = check_login_rate_limit()
        if not allowed:
            flash(f"Too many login attempts. Try again in {retry_after} seconds.", 'warning')
            return render_template('login.html')

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

        record_login_attempt()

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


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        form_values = {
            'name': request.form.get('name', '').strip(),
            'email': request.form.get('email', '').strip(),
            'username': request.form.get('username', '').strip(),
            'gender': request.form.get('gender', 'gentleman')
        }

        allowed, retry_after = check_login_rate_limit()
        if not allowed:
            flash(f"Too many registration attempts. Try again in {retry_after} seconds.", 'warning')
            return render_template('register.html', form_values=form_values)

        if session.get('login_lockout_until') and time.time() < session['login_lockout_until']:
            flash('Too many registration attempts. Please try again later.', 'warning')
            return render_template('register.html', form_values=form_values)

        token = request.form.get('csrf_token')
        if not token or token != session.get('_csrf_token'):
            abort(400, 'Invalid CSRF token')

        email_val = request.form.get('email', '').strip()
        name = request.form.get('name', '').strip()
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        gender = request.form.get('gender', 'gentleman')

        if gender not in ('gentleman', 'lady', 'secret'):
            gender = 'gentleman'

        if not email_val or not username or not password:
            flash('Email, username and password are required.', 'danger')
            form_values = {'name': name, 'email': email_val, 'username': username, 'gender': gender}
            return render_template('register.html', form_values=form_values)

        if len(name) > 255 or len(email_val) > 255 or len(username) > 255 or len(password) > 255:
            flash('Fields must not exceed 255 characters.', 'danger')
            form_values = {'name': name, 'email': email_val, 'username': username, 'gender': gender}
            return render_template('register.html', form_values=form_values)

        if len(password) < 8:
            flash('Password must be at least 8 characters.', 'danger')
            form_values = {'name': name, 'email': email_val, 'username': username, 'gender': gender}
            return render_template('register.html', form_values=form_values)

        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            form_values = {'name': name, 'email': email_val, 'username': username, 'gender': gender}
            return render_template('register.html', form_values=form_values)

        if not re.match(r'^[A-Za-z0-9_.-]{3,30}$', username):
            flash('Username may only contain letters, numbers, dots, underscores, or hyphens.', 'danger')
            form_values = {'name': name, 'email': email_val, 'username': username, 'gender': gender}
            return render_template('register.html', form_values=form_values)

        if '@' not in email_val or len(email_val) > 254:
            flash('Please enter a valid email address.', 'danger')
            form_values = {'name': name, 'email': email_val, 'username': username, 'gender': gender}
            return render_template('register.html', form_values=form_values)

        record_login_attempt()

        existing_email = db.get_user_by_email(email_val)
        existing_username = db.get_user_by_username(username)
        if existing_email:
            flash('Email is already registered.', 'danger')
            form_values = {'name': name, 'email': email_val, 'username': username, 'gender': gender}
            return render_template('register.html', form_values=form_values)
        if existing_username:
            flash('Username already exists.', 'danger')
            form_values = {'name': name, 'email': email_val, 'username': username, 'gender': gender}
            return render_template('register.html', form_values=form_values)

        try:
            password_hash = generate_password_hash(password)
            user = db.create_local_user(email_val, username, password_hash, name=name, gender=gender)
        except Exception as e:
            logging.error(f"Registration error: {str(e)}")
            flash('An error occurred during registration. Please try again.', 'danger')
            form_values = {'name': name, 'email': email_val, 'username': username, 'gender': gender}
            return render_template('register.html', form_values=form_values)

        session.clear()
        session['user_id'] = user['id']
        session['username'] = user['username']
        session['gender'] = user.get('gender', 'gentleman')
        flash('Registration successful! You are now logged in.', 'success')
        logging.info(f"User {user['id']} registered with username {username}")
        return redirect(url_for('index'))

    return render_template('register.html')


@auth_bp.route('/logout')
def logout():
    user_id = session.get('user_id')
    sid = request.cookies.get("session")
    if sid:
        db.delete_session(sid)
    session.clear()
    flash('Logged out successfully.', 'success')
    logging.info(f"User {user_id} logged out")
    return redirect(url_for('auth.login'))


@auth_bp.route('/user', methods=['GET', 'POST'])
def user():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('auth.login'))

    user_obj = db.get_user_by_id(user_id)
    if not user_obj:
        flash('User not found.', 'danger')
        return redirect(url_for('auth.logout'))

    deletion_scheduled = user_obj.deleted_at is not None

    if request.method == 'POST':
        token = request.form.get('csrf_token')
        if not token or token != session.get('_csrf_token'):
            abort(400, 'Invalid CSRF token')

        name = request.form.get('name', '').strip()
        username = request.form.get('username', '').strip()
        email_val = request.form.get('email', '').strip()
        gender = request.form.get('gender', 'gentleman')
        old_password = request.form.get('old_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if gender not in ('gentleman', 'lady', 'secret'):
            gender = 'gentleman'

        if not email_val or not username:
            flash('Email and username are required.', 'danger')
            return render_template('user.html', user=user_obj, gender=gender, profile_picture=db.get_profile_picture_path(gender), deletion_scheduled=deletion_scheduled)

        if len(name) > 255 or len(email_val) > 255 or len(username) > 255 or len(new_password) > 255:
            flash('Fields must not exceed 255 characters.', 'danger')
            return render_template('user.html', user=user_obj, gender=gender, profile_picture=db.get_profile_picture_path(gender), deletion_scheduled=deletion_scheduled)

        if '@' not in email_val or len(email_val) > 254:
            flash('Please enter a valid email address.', 'danger')
            return render_template('user.html', user=user_obj, gender=gender, profile_picture=db.get_profile_picture_path(gender), deletion_scheduled=deletion_scheduled)

        existing_email = db.get_user_by_email(email_val)
        if existing_email and existing_email.id != user_id:
            flash('Email is already in use by another account.', 'danger')
            return render_template('user.html', user=user_obj, gender=gender, profile_picture=db.get_profile_picture_path(gender), deletion_scheduled=deletion_scheduled)

        existing_username = db.get_user_by_username(username)
        if existing_username and existing_username.id != user_id:
            flash('Username is already in use by another account.', 'danger')
            return render_template('user.html', user=user_obj, gender=gender, profile_picture=db.get_profile_picture_path(gender), deletion_scheduled=deletion_scheduled)

        password_hash = None
        if new_password:
            if not old_password:
                flash('Current password is required to set a new password.', 'danger')
                return render_template('user.html', user=user_obj, gender=gender, profile_picture=db.get_profile_picture_path(gender), deletion_scheduled=deletion_scheduled)
            if not check_password_hash(user_obj.password_hash, old_password):
                flash('Current password is incorrect.', 'danger')
                return render_template('user.html', user=user_obj, gender=gender, profile_picture=db.get_profile_picture_path(gender), deletion_scheduled=deletion_scheduled)
            if len(new_password) < 8:
                flash('Password must be at least 8 characters.', 'danger')
                return render_template('user.html', user=user_obj, gender=gender, profile_picture=db.get_profile_picture_path(gender), deletion_scheduled=deletion_scheduled)
            if new_password != confirm_password:
                flash('Passwords do not match.', 'danger')
                return render_template('user.html', user=user_obj, gender=gender, profile_picture=db.get_profile_picture_path(gender), deletion_scheduled=deletion_scheduled)
            password_hash = generate_password_hash(new_password)

        try:
            updated = db.update_user(user_id, name, username, email_val, gender, password_hash=password_hash)
        except Exception as e:
            logging.error(f"Profile update error: {str(e)}")
            flash('An error occurred while updating your profile. Please try again.', 'danger')
            return redirect(url_for('auth.user'))

        if updated:
            session['username'] = updated['username']
            session['gender'] = updated['gender']
            flash('Profile updated successfully.', 'success')
        else:
            flash('Failed to update profile.', 'danger')

        return redirect(url_for('auth.user'))

    return render_template('user.html', user=user_obj, gender=user_obj.gender or 'gentleman', profile_picture=db.get_profile_picture_path(user_obj.gender or 'gentleman'), deletion_scheduled=deletion_scheduled)


# ========== Google OAuth ==========

@auth_bp.route('/login/google')
def google_login():
    if not oauth.GOOGLE_CLIENT_ID or not oauth.GOOGLE_CLIENT_SECRET:
        flash('Google sign-in is not configured.', 'warning')
        return redirect(url_for('auth.login'))
    auth_url = oauth.get_google_auth_url()
    return redirect(auth_url)


@auth_bp.route('/login/google/callback')
def google_callback():
    code = request.args.get('code')
    state = request.args.get('state')
    if not code or not state:
        flash('Google sign-in failed: missing parameters.', 'danger')
        return redirect(url_for('auth.login'))

    user_info = oauth.handle_google_callback(code, state)
    if not user_info:
        flash('Google sign-in failed. Please try again.', 'danger')
        return redirect(url_for('auth.login'))

    email_val = user_info.get('email', '')
    if not email_val:
        flash('Google account has no email address.', 'danger')
        return redirect(url_for('auth.login'))

    name = user_info.get('name', '')
    google_id = str(user_info.get('id', ''))

    result = db.get_or_create_user(
        email=email_val,
        platform='google',
        platform_id={'id': google_id, 'email': email_val},
        name=name,
    )

    session.clear()
    session['user_id'] = result['id']
    session['username'] = result.get('username') or result.get('name') or result['email']
    session['gender'] = result.get('gender', 'gentleman')
    flash('Signed in with Google successfully.', 'success')
    logging.info(f"User {result['id']} logged in via Google")
    return redirect(url_for('index'))


# ========== Forgot / Reset Password ==========

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        token = request.form.get('csrf_token')
        if not token or token != session.get('_csrf_token'):
            abort(400, 'Invalid CSRF token')

        email_val = request.form.get('email', '').strip()
        if not email_val or '@' not in email_val:
            flash('Please enter a valid email address.', 'danger')
            return render_template('forgot_password.html')

        user = db.get_user_by_email(email_val)
        if user:
            reset_token = _serializer.dumps(user.id, salt='password-reset')
            reset_url = url_for('auth.reset_password', token=reset_token, _external=True)
            subject = "StudyLib - Password Reset Request"
            body = f"""Hello {user.username or user.email},

We received a request to reset your password. Click the link below to set a new password:

{reset_url}

This link expires in 1 hour.

If you did not request this, please ignore this email.

- StudyLib Team
"""
            email.send_email(user.email, subject, body)

        flash('If an account with that email exists, a password reset link has been sent.', 'info')
        return redirect(url_for('auth.login'))

    return render_template('forgot_password.html')


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        user_id = _serializer.loads(token, salt='password-reset', max_age=3600)
    except SignatureExpired:
        flash('The reset link has expired. Please request a new one.', 'danger')
        return redirect(url_for('auth.forgot_password'))
    except BadSignature:
        flash('Invalid reset link.', 'danger')
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        token_csrf = request.form.get('csrf_token')
        if not token_csrf or token_csrf != session.get('_csrf_token'):
            abort(400, 'Invalid CSRF token')

        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        if len(password) < 8:
            flash('Password must be at least 8 characters.', 'danger')
            return render_template('reset_password.html', token=token)

        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('reset_password.html', token=token)

        password_hash = generate_password_hash(password)
        user = db.get_user_by_id(user_id)
        if not user:
            flash('User not found.', 'danger')
            return redirect(url_for('auth.login'))

        db.update_user(user_id, user.name or '', user.username or '', user.email, user.gender or 'gentleman', password_hash=password_hash)

        flash('Password has been reset successfully. Please log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('reset_password.html', token=token)


# ========== Account Deletion ==========

@auth_bp.route('/account/delete', methods=['POST'])
def account_delete():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('auth.login'))

    token = request.form.get('csrf_token')
    if not token or token != session.get('_csrf_token'):
        abort(400, 'Invalid CSRF token')

    user = db.get_user_by_id(user_id)
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('auth.logout'))

    db.schedule_account_deletion(user_id, grace_days=30)

    confirm_token = _serializer.dumps(user_id, salt='account-delete')
    confirm_url = url_for('auth.account_delete_confirm', token=confirm_token, _external=True)
    subject = "StudyLib - Account Deletion Scheduled"
    body = f"""Hello {user.username or user.email},

Your account has been scheduled for deletion. It will be permanently deleted in 30 days.

To cancel this request, visit your profile page and click "Cancel Deletion".

To confirm and delete immediately, click:
{confirm_url}

If you did not request this, please secure your account.

- StudyLib Team
"""
    email.send_email(user.email, subject, body)

    flash('Your account has been scheduled for deletion. You have 30 days to change your mind.', 'warning')
    return redirect(url_for('auth.user'))


@auth_bp.route('/account/undelete', methods=['POST'])
def account_undelete():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('auth.login'))

    token = request.form.get('csrf_token')
    if not token or token != session.get('_csrf_token'):
        abort(400, 'Invalid CSRF token')

    db.cancel_account_deletion(user_id)
    flash('Account deletion has been cancelled.', 'success')
    return redirect(url_for('auth.user'))


@auth_bp.route('/account/delete/confirm/<token>')
def account_delete_confirm(token):
    try:
        user_id = _serializer.loads(token, salt='account-delete', max_age=86400)
    except (SignatureExpired, BadSignature):
        flash('Invalid or expired confirmation link.', 'danger')
        return redirect(url_for('auth.login'))

    user = db.get_user_by_id(user_id)
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('auth.login'))

    db.permanently_delete_user(user_id)
    session.clear()
    flash('Your account has been permanently deleted.', 'info')
    logging.info(f"User {user_id} account permanently deleted")
    return redirect(url_for('auth.login'))


# ========== Session Management ==========

@auth_bp.route('/sessions')
def sessions():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('auth.login'))

    current_token = request.cookies.get("session", "")
    user_sessions = db.get_user_sessions(user_id)

    for s in user_sessions:
        s['is_current'] = (s['session_token'] == current_token)

    return render_template('sessions.html', sessions=user_sessions)


@auth_bp.route('/sessions/<token>/revoke', methods=['POST'])
def revoke_session(token):
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('auth.login'))

    form_token = request.form.get('csrf_token')
    if not form_token or form_token != session.get('_csrf_token'):
        abort(400, 'Invalid CSRF token')

    current_token = request.cookies.get("session", "")
    if token == current_token:
        flash('Cannot revoke your current session.', 'danger')
        return redirect(url_for('auth.sessions'))

    db.delete_session(token)
    flash('Session revoked.', 'success')
    return redirect(url_for('auth.sessions'))


@auth_bp.route('/sessions/revoke-all', methods=['POST'])
def revoke_all_sessions():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('auth.login'))

    form_token = request.form.get('csrf_token')
    if not form_token or form_token != session.get('_csrf_token'):
        abort(400, 'Invalid CSRF token')

    current_token = request.cookies.get("session", "")
    db.delete_all_user_sessions(user_id, except_token=current_token)
    flash('All other sessions have been revoked.', 'success')
    return redirect(url_for('auth.sessions'))
