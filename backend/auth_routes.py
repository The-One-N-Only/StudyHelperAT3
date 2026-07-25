import logging
import re
import secrets
import time
from flask import Blueprint, request, render_template, session, redirect, url_for, flash, abort
from werkzeug.security import generate_password_hash, check_password_hash
import src.db as db

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
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


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
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


@auth_bp.route('/logout')
def logout():
    user_id = session.get('user_id')
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

    if request.method == 'POST':
        token = request.form.get('csrf_token')
        if not token or token != session.get('_csrf_token'):
            abort(400, 'Invalid CSRF token')

        name = request.form.get('name', '').strip()
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        gender = request.form.get('gender', 'gentleman')
        old_password = request.form.get('old_password', '')
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
            if not old_password:
                flash('Current password is required to set a new password.', 'danger')
                return render_template('user.html', user=user_obj, gender=gender, profile_picture=db.get_profile_picture_path(gender))
            if not check_password_hash(user_obj.password_hash, old_password):
                flash('Current password is incorrect.', 'danger')
                return render_template('user.html', user=user_obj, gender=gender, profile_picture=db.get_profile_picture_path(gender))
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
            return redirect(url_for('auth.user'))

        if updated:
            session['username'] = updated['username']
            session['gender'] = updated['gender']
            flash('Profile updated successfully.', 'success')
        else:
            flash('Failed to update profile.', 'danger')

        return redirect(url_for('auth.user'))

    return render_template('user.html', user=user_obj, gender=user_obj.gender or 'gentleman', profile_picture=db.get_profile_picture_path(user_obj.gender or 'gentleman'))

