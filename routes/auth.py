import os
import re
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from db import get_db_connection
from extensions import oauth
from utils import login_required

auth_bp = Blueprint('auth', __name__)


def valid_email(address):
    return re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', address)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        email = request.form['email'].strip()
        phone = request.form['phone'].strip()
        password = request.form['password']
        confirm_password = request.form.get('confirm_password', '')

        if not username or not email or not password:
            flash("Username, email, and password are required.", "danger")
            return render_template('register.html')

        if password != confirm_password:
            flash("Password and confirmation do not match.", "danger")
            return render_template('register.html')

        if len(password) < 8:
            flash("Password must be at least 8 characters long.", "danger")
            return render_template('register.html')

        if not valid_email(email):
            flash("Please enter a valid email address.", "danger")
            return render_template('register.html')

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT id FROM users WHERE username = %s OR email = %s", (username, email))
            if cursor.fetchone():
                flash("Username or email already in use.", "danger")
                return render_template('register.html')

            hashed_password = generate_password_hash(password)
            cursor.execute("INSERT INTO users (username, password_hash, email, phone) VALUES (%s, %s, %s, %s)",
                           (username, hashed_password, email, phone))
            conn.commit()
            flash("Registration successful. Please login.", "success")
            return redirect(url_for('auth.login'))
        except Exception as err:
            flash(f"Error: {err}", "danger")
        finally:
            cursor.close()
            conn.close()
    return render_template('register.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identifier = request.form['identifier'].strip()
        password = request.form['password']
        remember_me = request.form.get('remember_me') == 'on'

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT * FROM users WHERE username = %s OR email = %s OR phone = %s",
            (identifier, identifier, identifier)
        )
        user = cursor.fetchone()

        if user and user.get('password_hash') and check_password_hash(user['password_hash'], password):
            session.permanent = remember_me
            session['user_id'] = user['id']
            session['username'] = user['username']
            flash("Berhasil masuk.", "success")
            
            role = user.get('role')
            cursor.close()
            conn.close()
            if role == 'admin':
                return redirect(url_for('admin.dashboard'))
            return redirect(url_for('main.index'))

        if user and user.get('auth_provider') == 'google':
            flash("Akun ini terdaftar dengan Google. Silakan masuk melalui Google.", "warning")
        else:
            flash("Email, nomor telepon, username, atau password salah.", "danger")
        cursor.close()
        conn.close()
    return render_template('login.html')

@auth_bp.route('/login/google')
def login_google():
    if not os.getenv('GOOGLE_CLIENT_ID'):
        flash("Google Login is not configured yet. Please add GOOGLE_CLIENT_ID to .env", "warning")
        return redirect(url_for('auth.login'))
    redirect_uri = url_for('auth.authorize_google', _external=True)
    google = oauth.create_client('google')
    return google.authorize_redirect(redirect_uri)

@auth_bp.route('/login/google/authorize')
def authorize_google():
    try:
        google = oauth.create_client('google')
        token = google.authorize_access_token()
        user_info = token.get('userinfo')
        if not user_info:
            flash("Failed to get user info from Google.", "danger")
            return redirect(url_for('auth.login'))
            
        email = user_info.get('email')
        name = user_info.get('name')
        google_id = user_info.get('sub')
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        
        if user:
            if 'google_id' in user and not user.get('google_id'):
                cursor.execute("UPDATE users SET google_id = %s, auth_provider = 'google' WHERE id = %s", (google_id, user['id']))
                conn.commit()
            session.permanent = True
            session['user_id'] = user['id']
            session['username'] = user['username']
            flash(f"Welcome back, {user['username']}!", "success")
        else:
            base_username = name.replace(" ", "").lower() if name else email.split('@')[0]
            username = base_username
            cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
            counter = 1
            while cursor.fetchone():
                username = f"{base_username}{counter}"
                cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
                counter += 1
                
            cursor.execute("""
                INSERT INTO users (username, email, google_id, auth_provider) 
                VALUES (%s, %s, %s, 'google')
            """, (username, email, google_id))
            conn.commit()
            
            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()
            
            session.permanent = True
            session['user_id'] = user['id']
            session['username'] = user['username']
            flash("Account created successfully via Google!", "success")
            
        role = user.get('role', 'customer')
        cursor.close()
        conn.close()
        if role == 'admin':
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('main.index'))
        
    except Exception as e:
        flash(f"Google login failed: {str(e)}", "danger")
        return redirect(url_for('auth.login'))

@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        username = request.form['username'].strip()
        email = request.form['email'].strip()
        phone = request.form['phone'].strip()
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not username or not email:
            flash("Username and email cannot be empty.", "danger")
            return redirect(url_for('auth.profile'))

        if not valid_email(email):
            flash("Please enter a valid email address.", "danger")
            return redirect(url_for('auth.profile'))

        cursor.execute("SELECT id FROM users WHERE (username = %s OR email = %s) AND id != %s", (username, email, session['user_id']))
        if cursor.fetchone():
            flash("Username or email already in use.", "danger")
            return redirect(url_for('auth.profile'))

        if new_password or confirm_password:
            if new_password != confirm_password:
                flash("New password and confirmation do not match.", "danger")
                return redirect(url_for('auth.profile'))
            if len(new_password) < 8:
                flash("New password must be at least 8 characters long.", "danger")
                return redirect(url_for('auth.profile'))
            if not current_password:
                flash("Current password is required to change your password.", "danger")
                return redirect(url_for('auth.profile'))
            cursor.execute("SELECT password_hash FROM users WHERE id = %s", (session['user_id'],))
            user = cursor.fetchone()
            if not user or not user.get('password_hash') or not check_password_hash(user['password_hash'], current_password):
                flash("Current password is incorrect.", "danger")
                return redirect(url_for('auth.profile'))
            new_password_hash = generate_password_hash(new_password)
            cursor.execute("UPDATE users SET password_hash = %s WHERE id = %s", (new_password_hash, session['user_id']))

        cursor.execute("UPDATE users SET username = %s, email = %s, phone = %s WHERE id = %s", (username, email, phone, session['user_id']))
        conn.commit()
        session['username'] = username
        flash("Profile updated successfully.", "success")
        cursor.close()
        conn.close()
        return redirect(url_for('auth.profile'))

    cursor.execute("SELECT username, email, phone FROM users WHERE id = %s", (session['user_id'],))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    return render_template('profile.html', user=user)


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email'].strip()
        if not email or not valid_email(email):
            flash("Please enter a valid email address.", "danger")
            return render_template('forgot_password.html')

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT auth_provider FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user and user.get('auth_provider') == 'google':
            flash("Akun ini terdaftar melalui Google. Silakan masuk dengan Google, atau gunakan pemulihan akun Google.", "info")
            return redirect(url_for('auth.login'))

        flash("If this email is registered, password reset instructions have been sent.", "info")
        return redirect(url_for('auth.login'))

    return render_template('forgot_password.html')


@auth_bp.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('main.index'))
