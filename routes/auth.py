from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
import os
from db import get_db_connection
from extensions import oauth

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        phone = request.form['phone']
        password = generate_password_hash(request.form['password'])

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO users (username, password_hash, email, phone) VALUES (%s, %s, %s, %s)",
                           (username, password, email, phone))
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
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()

        if user and user.get('password_hash') and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            flash("Logged in successfully.", "success")
            
            role = user.get('role')
            cursor.close()
            conn.close()
            if role == 'admin':
                return redirect(url_for('admin.dashboard'))
            return redirect(url_for('main.index'))
        
        flash("Invalid username or password.", "danger")
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

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('main.index'))
