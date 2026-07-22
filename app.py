import os
from flask import Flask
from flask_session import Session
from flask_mail import Mail
from dotenv import load_dotenv

# Import utilities and extensions
from extensions import init_oauth
from routes.main import main_bp
from routes.auth import auth_bp
from routes.admin import admin_bp
from routes.booking import booking_bp

load_dotenv()
os.environ['AUTHLIB_INSECURE_TRANSPORT'] = '1'

from datetime import date, datetime, timedelta

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'default_secret_key')

# Flask-Mail Configuration
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'True') == 'True'
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME', '')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD', '')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER', 'noreply@antigravityhotels.com')
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

# Setup File Uploads
HOTEL_UPLOAD_FOLDER = os.path.join('static', 'uploads', 'hotels')
ROOM_UPLOAD_FOLDER = os.path.join('static', 'uploads', 'rooms')
os.makedirs(HOTEL_UPLOAD_FOLDER, exist_ok=True)
os.makedirs(ROOM_UPLOAD_FOLDER, exist_ok=True)
app.config['HOTEL_UPLOAD_FOLDER'] = HOTEL_UPLOAD_FOLDER
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

# Initialize OAuth
init_oauth(app)

import traceback
from werkzeug.exceptions import HTTPException
from flask import flash, redirect, url_for

@app.errorhandler(Exception)
def handle_global_error(e):
    # Pass through standard HTTP errors like 404
    if isinstance(e, HTTPException):
        return e
    
    # Log the error for debugging
    app.logger.error(f"Global Error: {str(e)}")
    app.logger.error(traceback.format_exc())
    
    # Show user-friendly SweetAlert flash message instead of ugly debugger
    flash("Terdapat masalah pada sistem atau tindakan tidak valid. Mohon coba beberapa saat lagi.", "danger")
    return redirect(url_for('main.index'))

# Register Blueprints
app.register_blueprint(main_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(booking_bp)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
