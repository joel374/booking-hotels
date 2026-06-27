import os
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app, jsonify
from werkzeug.utils import secure_filename
from db import get_db_connection
from utils import admin_required, allowed_file, delete_image_file

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT COUNT(*) as count FROM bookings")
    total_bookings = cursor.fetchone()['count']
    
    cursor.execute("SELECT IFNULL(SUM(r.price), 0) as revenue FROM bookings b JOIN rooms r ON b.room_id = r.id WHERE b.status = 'Booked'")
    revenue = cursor.fetchone()['revenue']
    
    cursor.execute("SELECT COUNT(*) as count FROM users WHERE role = 'customer'")
    customers = cursor.fetchone()['count']
    
    cursor.execute("SELECT b.*, u.username, h.name as hotel_name, r.room_number FROM bookings b JOIN users u ON b.user_id = u.id JOIN rooms r ON b.room_id = r.id JOIN hotels h ON r.hotel_id = h.id ORDER BY b.created_at DESC LIMIT 5")
    recent_bookings = cursor.fetchall()
    
    cursor.close()
    conn.close()
    return render_template('admin/dashboard.html', 
                          total_bookings=total_bookings, 
                          revenue=revenue, 
                          customers=customers,
                          recent_bookings=recent_bookings)

@admin_bp.route('/hotels', methods=['GET', 'POST'])
@admin_required
def hotels():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        name = request.form['name']
        location = request.form['location']
        province_id = request.form.get('province_id')
        city_id = request.form.get('city_id')
        description = request.form['description']
        
        cursor.execute("INSERT INTO hotels (name, location, province_id, city_id, description) VALUES (%s, %s, %s, %s, %s)",
                      (name, location, province_id, city_id, description))
        hotel_id = cursor.lastrowid
        
        files = request.files.getlist('images')
        for file in files:
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                image_url = url_for('static', filename=f"uploads/hotels/{filename}")
                cursor.execute("INSERT INTO hotel_images (hotel_id, image_url) VALUES (%s, %s)", (hotel_id, image_url))
        
        conn.commit()
        flash("Hotel added successfully!", "success")
        return redirect(url_for('admin.hotels'))
        
    cursor.execute("SELECT h.*, p.province, c.city_name FROM hotels h LEFT JOIN provinces p ON h.province_id = p.province_id LEFT JOIN cities c ON h.city_id = c.city_id")
    hotel_list = cursor.fetchall()
    
    for hotel in hotel_list:
        cursor.execute("SELECT image_url FROM hotel_images WHERE hotel_id = %s", (hotel['id'],))
        imgs = cursor.fetchall()
        hotel['images'] = [img['image_url'] for img in imgs]
    
    cursor.execute("SELECT * FROM provinces ORDER BY province")
    provinces = cursor.fetchall()
    
    cursor.close()
    conn.close()
    return render_template('admin/hotels.html', hotels=hotel_list, provinces=provinces)

@admin_bp.route('/hotel/edit/<int:id>', methods=['POST'])
@admin_required
def edit_hotel(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    name = request.form['name']
    location = request.form['location']
    province_id = request.form.get('province_id')
    city_id = request.form.get('city_id')
    description = request.form['description']
    
    cursor.execute("UPDATE hotels SET name=%s, location=%s, province_id=%s, city_id=%s, description=%s WHERE id=%s",
                  (name, location, province_id, city_id, description, id))
                  
    files = request.files.getlist('images')
    if files and files[0].filename != '':
        cursor.execute("SELECT image_url FROM hotel_images WHERE hotel_id = %s", (id,))
        old_images = cursor.fetchall()
        for old in old_images:
            delete_image_file(old['image_url'], current_app.root_path)
            
        cursor.execute("DELETE FROM hotel_images WHERE hotel_id = %s", (id,))
        
        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                image_url = url_for('static', filename=f"uploads/hotels/{filename}")
                cursor.execute("INSERT INTO hotel_images (hotel_id, image_url) VALUES (%s, %s)", (id, image_url))
                
    conn.commit()
    cursor.close()
    conn.close()
    flash("Hotel updated successfully!", "success")
    return redirect(url_for('admin.hotels'))

@admin_bp.route('/api/cities/<province_id>')
def get_cities(province_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM cities WHERE province_id = %s ORDER BY city_name", (province_id,))
    cities = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(cities)
    
@admin_bp.route('/rooms', methods=['GET', 'POST'])
@admin_required
def rooms():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        hotel_id = request.form['hotel_id']
        room_number = request.form['room_number']
        room_type = request.form['room_type']
        price = request.form['price']
        
        cursor.execute("INSERT INTO rooms (hotel_id, room_number, room_type, price) VALUES (%s, %s, %s, %s)",
                      (hotel_id, room_number, room_type, price))
        room_id = cursor.lastrowid
        
        files = request.files.getlist('images')
        for file in files:
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                image_url = url_for('static', filename=f"uploads/hotels/{filename}")
                cursor.execute("INSERT INTO room_images (room_id, image_url) VALUES (%s, %s)", (room_id, image_url))
        
        conn.commit()
        flash("Room added successfully!", "success")
        return redirect(url_for('admin.rooms'))
        
    cursor.execute("SELECT r.*, h.name as hotel_name FROM rooms r JOIN hotels h ON r.hotel_id = h.id")
    room_list = cursor.fetchall()
    
    for room in room_list:
        cursor.execute("SELECT image_url FROM room_images WHERE room_id = %s", (room['id'],))
        imgs = cursor.fetchall()
        room['images'] = [img['image_url'] for img in imgs]
    
    cursor.execute("SELECT id, name FROM hotels")
    hotel_list = cursor.fetchall()
    
    cursor.close()
    conn.close()
    return render_template('admin/rooms.html', rooms=room_list, hotels=hotel_list)

@admin_bp.route('/room/edit/<int:id>', methods=['POST'])
@admin_required
def edit_room(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    room_number = request.form['room_number']
    room_type = request.form['room_type']
    price = request.form['price']
    
    cursor.execute("UPDATE rooms SET room_number=%s, room_type=%s, price=%s WHERE id=%s",
                  (room_number, room_type, price, id))
                  
    files = request.files.getlist('images')
    if files and files[0].filename != '':
        cursor.execute("SELECT image_url FROM room_images WHERE room_id = %s", (id,))
        old_images = cursor.fetchall()
        for old in old_images:
            delete_image_file(old['image_url'], current_app.root_path)
            
        cursor.execute("DELETE FROM room_images WHERE room_id = %s", (id,))
        
        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                image_url = url_for('static', filename=f"uploads/hotels/{filename}")
                cursor.execute("INSERT INTO room_images (room_id, image_url) VALUES (%s, %s)", (id, image_url))
                
    conn.commit()
    cursor.close()
    conn.close()
    flash("Room updated successfully!", "success")
    return redirect(url_for('admin.rooms'))

@admin_bp.route('/bookings', methods=['GET', 'POST'])
@admin_required
def bookings():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        booking_id = request.form.get('booking_id')
        cancel_reason = request.form.get('cancel_reason')
        if booking_id and cancel_reason:
            cursor.execute("UPDATE bookings SET status = 'Cancelled', cancel_reason = %s WHERE id = %s", 
                          (cancel_reason, booking_id))
            conn.commit()
            flash("Booking cancelled successfully.", "warning")
        return redirect(url_for('admin.bookings'))
        
    cursor.execute("""
        SELECT b.*, u.username, u.email, r.room_type, r.room_number, h.name as hotel_name 
        FROM bookings b 
        JOIN users u ON b.user_id = u.id 
        JOIN rooms r ON b.room_id = r.id
        JOIN hotels h ON r.hotel_id = h.id
        ORDER BY b.created_at DESC
    """)
    booking_list = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('admin/bookings.html', bookings=booking_list)
