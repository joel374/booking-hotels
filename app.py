import os
from flask import Flask
from flask_session import Session
from dotenv import load_dotenv

# Import utilities and extensions
from extensions import init_oauth
from routes.main import main_bp
from routes.auth import auth_bp
from routes.admin import admin_bp
from routes.booking import booking_bp

load_dotenv()
os.environ['AUTHLIB_INSECURE_TRANSPORT'] = '1'

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'default_secret_key')

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
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Initialize OAuth
init_oauth(app)

# Register Blueprints
app.register_blueprint(main_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(booking_bp)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
