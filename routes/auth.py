import os
import re
import secrets
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from db import get_db_connection
from extensions import oauth
from utils import login_required, add_notification

auth_bp = Blueprint('auth', __name__)


def valid_email(address):
    return re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', address)


def send_welcome_email(email, username):
    """Send welcome email after successful registration"""
    try:
        html_content = f'''
        <html>
        <body style="font-family: Arial, sans-serif; background-color: #f5f5f5;">
            <div style="max-width: 600px; margin: 20px auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                <h2 style="color: #0a192f;">Selamat Datang di Antigravity Hotels! 🎉</h2>
                <p style="color: #333; line-height: 1.6;">Halo <strong>{username}</strong>,</p>
                
                <p style="color: #333; line-height: 1.6;">Terima kasih telah mendaftar di platform kami. Akun Anda telah berhasil dibuat!</p>
                
                <div style="background-color: #f9f9f9; padding: 20px; border-left: 4px solid #e67e22; margin: 20px 0;">
                    <p style="margin: 0; color: #333;"><strong>✓ Akun Anda siap digunakan</strong></p>
                    <p style="margin: 10px 0 0 0; color: #666; font-size: 14px;">Username: {username}</p>
                    <p style="margin: 5px 0 0 0; color: #666; font-size: 14px;">Email: {email}</p>
                </div>
                
                <p style="color: #333; line-height: 1.6;"><strong>Apa yang bisa Anda lakukan sekarang:</strong></p>
                <ul style="color: #333; line-height: 1.8;">
                    <li>Browse berbagai pilihan hotel eksklusif</li>
                    <li>Buat reservasi dengan mudah dan cepat</li>
                    <li>Manage booking Anda di "My Bookings"</li>
                    <li>Dapatkan penawaran khusus dan diskon menarik</li>
                </ul>
                
                <p style="margin-top: 30px; color: #333;">
                    <a href="{url_for('main.index', _external=True)}" style="background-color: #e67e22; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold;">
                        Mulai Jelajahi Hotel
                    </a>
                </p>
                
                <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
                <p style="color: #999; font-size: 12px;">
                    Pertanyaan? Hubungi kami di support@antigravityhotels.com<br>
                    © 2026 Antigravity Hotels. All rights reserved.
                </p>
            </div>
        </body>
        </html>
        '''
        
        msg = Message(
            subject='Selamat Datang! Akun Anda Berhasil Dibuat - Antigravity Hotels',
            recipients=[email],
            html=html_content
        )
        current_app.extensions.get('mail').send(msg)
        return True
    except Exception as e:
        print(f"Error sending welcome email to {email}: {str(e)}")
        return False


def send_login_notification(email, username, ip_address="Unknown"):
    """Send login notification email"""
    try:
        login_time = datetime.now().strftime("%d %B %Y, %H:%M:%S")
        
        html_content = f'''
        <html>
        <body style="font-family: Arial, sans-serif; background-color: #f5f5f5;">
            <div style="max-width: 600px; margin: 20px auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                <h2 style="color: #0a192f;">Notifikasi Login - Antigravity Hotels 🔐</h2>
                <p style="color: #333; line-height: 1.6;">Halo <strong>{username}</strong>,</p>
                
                <p style="color: #333; line-height: 1.6;">Akun Anda baru saja berhasil login.</p>
                
                <div style="background-color: #f0f8ff; padding: 20px; border-left: 4px solid #0a192f; margin: 20px 0;">
                    <p style="margin: 0; color: #0a192f;"><strong>📍 Detail Login</strong></p>
                    <p style="margin: 10px 0 0 0; color: #333; font-size: 14px;">Waktu: {login_time} WIB</p>
                    <p style="margin: 5px 0 0 0; color: #333; font-size: 14px;">Perangkat: Browser</p>
                    <p style="margin: 5px 0 0 0; color: #333; font-size: 14px;">IP Address: {ip_address}</p>
                </div>
                
                <p style="color: #333; line-height: 1.6;">
                    <strong>⚠️ Jika Anda tidak melakukan login ini,</strong> silakan amankan akun Anda sekarang dengan mengganti password.
                </p>
                
                <p style="margin-top: 30px; color: #333;">
                    <a href="{url_for('auth.profile', _external=True)}" style="background-color: #0a192f; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold;">
                        Manage Account
                    </a>
                </p>
                
                <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
                <p style="color: #999; font-size: 12px;">
                    Pertanyaan atau kekhawatiran keamanan? Hubungi kami di support@antigravityhotels.com<br>
                    © 2026 Antigravity Hotels. All rights reserved.
                </p>
            </div>
        </body>
        </html>
        '''
        
        msg = Message(
            subject=f'Login Terdeteksi - {username} - Antigravity Hotels',
            recipients=[email],
            html=html_content
        )
        current_app.extensions.get('mail').send(msg)
        return True
    except Exception as e:
        print(f"Error sending login notification to {email}: {str(e)}")
        return False

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
            
            # Send welcome email
            send_welcome_email(email, username)
            
            flash("Registration successful. Please check your email for welcome message. You can now login.", "success")
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
            
            cursor.execute("UPDATE users SET last_login = NOW() WHERE id = %s", (user['id'],))
            conn.commit()
            
            # Get user IP address
            user_ip = request.remote_addr or request.headers.get('X-Forwarded-For', 'Unknown')
            
            # Send login notification email
            send_login_notification(user['email'], user['username'], user_ip)
            
            flash("Berhasil masuk.", "success")
            
            role = user.get('role')
            cursor.close()
            conn.close()
            if role == 'admin':
                add_notification(
                    title="Admin Login",
                    description=f"Admin {user['username']} logged in.",
                    icon_type="login"
                )
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
        is_new_user = False
        
        if user:
            if 'google_id' in user and not user.get('google_id'):
                cursor.execute("UPDATE users SET google_id = %s, auth_provider = 'google' WHERE id = %s", (google_id, user['id']))
                conn.commit()
            session.permanent = True
            session['user_id'] = user['id']
            session['username'] = user['username']
            
            cursor.execute("UPDATE users SET last_login = NOW() WHERE id = %s", (user['id'],))
            conn.commit()
            
            # Send login notification for existing user
            user_ip = request.remote_addr or request.headers.get('X-Forwarded-For', 'Unknown')
            send_login_notification(user['email'], user['username'], user_ip)
            
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
            is_new_user = True
            
            session.permanent = True
            session['user_id'] = user['id']
            session['username'] = user['username']
            
            cursor.execute("UPDATE users SET last_login = NOW() WHERE id = %s", (user['id'],))
            conn.commit()
            
            # Send welcome email for new Google user
            send_welcome_email(email, username)
            
            flash("Account created successfully via Google! Check your email for welcome message.", "success")
            
        role = user.get('role', 'customer')
        cursor.close()
        conn.close()
        if role == 'admin':
            add_notification(
                title="Admin Login (Google)",
                description=f"Admin {user['username']} logged in via Google.",
                icon_type="login"
            )
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
        cursor.execute("SELECT id, auth_provider FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()

        if user and user.get('auth_provider') == 'google':
            cursor.close()
            conn.close()
            flash("Akun ini terdaftar melalui Google. Silakan masuk dengan Google atau gunakan pemulihan akun Google.", "info")
            return redirect(url_for('auth.login'))

        if user:
            reset_token = secrets.token_urlsafe(32)
            expires_at = datetime.utcnow() + timedelta(hours=1)
            cursor.execute(
                "UPDATE users SET password_reset_token = %s, password_reset_expires = %s WHERE id = %s",
                (reset_token, expires_at, user['id'])
            )
            conn.commit()
            
            reset_link = url_for('auth.reset_password', token=reset_token, _external=True)
            html_content = '<html><body style="font-family: Arial, sans-serif;"><div style="max-width: 600px; margin: 20px auto; background: white; padding: 30px; border-radius: 8px;"><h2>Reset Password</h2><p>Klik link di bawah untuk reset password Anda:</p><p><a href="' + reset_link + '" style="background-color: #e67e22; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block;">Reset Password</a></p><p>Link ini berlaku 1 jam.</p></div></body></html>'
            
            try:
                msg = Message(
                    subject='Reset Password - Antigravity Hotels',
                    recipients=[email],
                    html=html_content
                )
                current_app.extensions.get('mail').send(msg)
                flash("Email reset password telah dikirim. Periksa inbox Anda.", "success")
            except Exception as e:
                flash("Gagal mengirim email. Coba lagi nanti.", "warning")
        else:
            flash("Jika email terdaftar, instruksi reset telah dikirim.", "info")
        
        cursor.close()
        conn.close()
        return redirect(url_for('auth.login'))

    return render_template('forgot_password.html')


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT id FROM users WHERE password_reset_token = %s AND password_reset_expires > %s",
        (token, datetime.utcnow())
    )
    user = cursor.fetchone()
    
    if not user:
        flash("Link reset password tidak valid atau sudah kadaluarsa.", "danger")
        cursor.close()
        conn.close()
        return redirect(url_for('auth.forgot_password'))
    
    if request.method == 'POST':
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        if new_password != confirm_password:
            flash("Password tidak cocok.", "danger")
            return render_template('reset_password.html', token=token)
        
        if len(new_password) < 8:
            flash("Password minimal 8 karakter.", "danger")
            return render_template('reset_password.html', token=token)
        
        new_password_hash = generate_password_hash(new_password)
        cursor.execute(
            "UPDATE users SET password_hash = %s, password_reset_token = NULL, password_reset_expires = NULL WHERE id = %s",
            (new_password_hash, user['id'])
        )
        conn.commit()
        cursor.close()
        conn.close()
        
        flash("Password berhasil direset. Silakan login.", "success")
        return redirect(url_for('auth.login'))
    
    cursor.close()
    conn.close()
    return render_template('reset_password.html', token=token)


@auth_bp.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('main.index'))
