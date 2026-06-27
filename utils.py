from functools import wraps
from flask import session, flash, redirect, url_for
from db import get_db_connection

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def delete_image_file(image_url, app_root):
    if not image_url: return
    # image_url looks like /static/uploads/hotels/filename.jpg
    # we need to remove the leading slash or URL parts to get local path
    import os
    if image_url.startswith('/'):
        image_url = image_url[1:]
    
    filepath = os.path.join(app_root, image_url.replace('/', os.sep))
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
        except Exception as e:
            print(f"Error deleting file {filepath}: {e}")

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please login first.", "warning")
            return redirect(url_for('auth.login'))
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT role FROM users WHERE id = %s", (session['user_id'],))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not user or user.get('role') != 'admin':
            flash("Access denied. Admin privileges required.", "danger")
            return redirect(url_for('main.index'))
            
        return f(*args, **kwargs)
    return decorated_function
