import os
import secrets
from flask import Flask
from flask_session import Session
from flask_mail import Mail
from dotenv import load_dotenv

# Import utilities and extensions
from extensions import init_oauth, csrf, limiter
from routes.main import main_bp
from routes.auth import auth_bp
from routes.admin import admin_bp
from routes.booking import booking_bp

load_dotenv()
os.environ['AUTHLIB_INSECURE_TRANSPORT'] = '1'

from datetime import date, datetime, timedelta
from translations import TRANSLATIONS
from flask import session

app = Flask(__name__)
env_secret = os.getenv('SECRET_KEY')
if os.getenv('FLASK_ENV', 'development') == 'production' and not env_secret:
    raise RuntimeError("SECRET_KEY is required in production environment (ISO 27001 A.10)")
app.secret_key = env_secret or secrets.token_hex(32)


# Flask-Mail Configuration
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'True') == 'True'
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME', '')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD', '')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER', 'noreply@bhinekahotels.com')
mail = Mail(app)

@app.template_filter('format_date')
def format_date(value):
    if not value:
        return ""
    months_id = ["", "Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agt", "Sep", "Okt", "Nov", "Des"]
    try:
        if isinstance(value, (date, datetime)):
            dt = value
        else:
            dt = datetime.strptime(str(value), "%Y-%m-%d")
        return f"{dt.day} {months_id[dt.month]}"
    except Exception:
        return value

from utils import get_company_settings

@app.context_processor
def inject_globals():
    # Translation function
    def translate(text):
        lang = session.get('language', 'id')
        if lang == 'en':
            return TRANSLATIONS.get(text, text)
        return text
    
    return dict(
        _ = translate,
        current_theme = session.get('theme', 'light'),
        current_language = session.get('language', 'id'),
        settings = get_company_settings()
    )

# Setup File Uploads
HOTEL_UPLOAD_FOLDER = os.path.join('static', 'uploads', 'hotels')
ROOM_UPLOAD_FOLDER = os.path.join('static', 'uploads', 'rooms')
USER_UPLOAD_FOLDER = os.path.join('static', 'uploads', 'users')
os.makedirs(HOTEL_UPLOAD_FOLDER, exist_ok=True)
os.makedirs(ROOM_UPLOAD_FOLDER, exist_ok=True)
os.makedirs(USER_UPLOAD_FOLDER, exist_ok=True)
app.config['HOTEL_UPLOAD_FOLDER'] = HOTEL_UPLOAD_FOLDER
app.config['USER_UPLOAD_FOLDER'] = USER_UPLOAD_FOLDER
app.config['ROOM_UPLOAD_FOLDER'] = ROOM_UPLOAD_FOLDER
app.config['UPLOAD_FOLDER'] = HOTEL_UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# Session Setup
app.config["SESSION_PERMANENT"] = True
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(minutes=int(os.getenv('SESSION_LIFETIME_MINUTES', '60')))
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.getenv('FLASK_ENV', 'development') == 'production'
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_REFRESH_EACH_REQUEST"] = True
Session(app)

# Initialize Extensions
init_oauth(app)
csrf.init_app(app)
limiter.init_app(app)

import traceback
from werkzeug.exceptions import HTTPException
from flask import flash, redirect, url_for, request, jsonify

@app.errorhandler(Exception)
def handle_global_error(e):
    # Pass through standard HTTP errors like 404
    if isinstance(e, HTTPException):
        return e
    
    # Log the error for debugging
    app.logger.error(f"Global Error: {str(e)}")
    app.logger.error(traceback.format_exc())

    # Endpoint AJAX/JSON harus tetap menerima JSON. Mengembalikan redirect HTML
    # ke sini membuat infinite scroll, live search, dan fetch() lain gagal parse.
    if request.path.startswith('/api/') or request.path.startswith('/admin/api/'):
        return jsonify({'error': 'Terjadi masalah pada sistem. Mohon coba beberapa saat lagi.'}), 500

    # Show user-friendly SweetAlert flash message instead of ugly debugger
    flash("Terdapat masalah pada sistem atau tindakan tidak valid. Mohon coba beberapa saat lagi.", "danger")
    return redirect(url_for('main.index'))

# Context Processor for global user data
from flask import session
from db import get_db_connection, init_db_schema

# Ensure database schema is initialized and tables exist
init_db_schema()

@app.context_processor
def inject_user():
    if 'user_id' in session:
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM users WHERE id = %s", (session['user_id'],))
            current_user = cursor.fetchone()
            cursor.close()
            conn.close()
            return dict(current_user=current_user)
        except Exception:
            return dict(current_user=None)
    return dict(current_user=None)

@app.before_request
def auto_update_booking_statuses():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # If today is >= check_in and status is Booked -> Checked In
        cursor.execute("UPDATE bookings SET status = 'Checked In' WHERE status = 'Booked' AND check_in <= CURDATE() AND check_out > CURDATE()")
        # If today is >= check_out and status is Checked In -> Checked Out
        cursor.execute("UPDATE bookings SET status = 'Checked Out' WHERE status = 'Checked In' AND check_out <= CURDATE()")
        # Edge case: If today is >= check_out and status is still Booked (guest never checked in/out) -> Checked Out
        cursor.execute("UPDATE bookings SET status = 'Checked Out' WHERE status = 'Booked' AND check_out <= CURDATE()")
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        app.logger.error(f"Error auto-updating statuses: {e}")

@app.before_request
def validate_session():
    if 'user_id' in session:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users WHERE id = %s", (session['user_id'],))
            user = cursor.fetchone()
            cursor.close()
            conn.close()
            if not user:
                session.clear()
        except Exception:
            pass

@app.after_request
def apply_security_headers(response):
    # ISO 27001 HTTP Security Headers
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    # Base CSP allowing essential CDNs
    response.headers['Content-Security-Policy'] = "default-src 'self' 'unsafe-inline' 'unsafe-eval' https://fonts.googleapis.com https://fonts.gstatic.com https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://unpkg.com;"
    return response

# Register Blueprints
app.register_blueprint(main_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(booking_bp)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
