import re
import os
from decimal import Decimal
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app, jsonify, session
from db import get_db_connection
from services.room_service import generate_rooms, edit_room_group, delete_room_group
from utils import admin_required, delete_image_file, save_file, add_notification, log_admin
from werkzeug.security import check_password_hash, generate_password_hash

import io
import datetime
import smtplib
from email.message import EmailMessage
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.platypus.flowables import HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from flask import Response


admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def fetch_images_by_parent(cursor, table_name, parent_field, values):
    if not values:
        return {}

    placeholders = ', '.join(['%s'] * len(values))
    query = f"SELECT {parent_field}, image_url FROM {table_name} WHERE {parent_field} IN ({placeholders})"
    cursor.execute(query, values)
    rows = cursor.fetchall()

    grouped = {}
    for row in rows:
        grouped.setdefault(row[parent_field], []).append(row['image_url'])
    return grouped


def validate_hotel_fields(name, location, province_id, city_id, description):
    if not name.strip() or not location.strip() or not province_id or not city_id or not description.strip():
        return False, 'Please fill in all required hotel fields.'
    return True, ''


def validate_room_fields(cursor, hotel_id, room_number, room_type, price, exclude_room_id=None):
    if not hotel_id:
        return False, 'Please select a hotel for this room.'
    if not room_number.strip() or not room_type.strip() or not price:
        return False, 'Please fill in all required room fields.'
    try:
        price_value = Decimal(price)
        if price_value <= 0:
            return False, 'Room price must be greater than zero.'
    except Exception:
        return False, 'Room price must be a valid number.'

    cursor.execute('SELECT id FROM hotels WHERE id = %s', (hotel_id,))
    if not cursor.fetchone():
        return False, 'Selected hotel does not exist.'

    duplicate_query = 'SELECT id FROM rooms WHERE hotel_id = %s AND room_number = %s AND is_deleted = 0'
    params = [hotel_id, room_number.strip()]
    if exclude_room_id:
        duplicate_query += ' AND id != %s'
        params.append(exclude_room_id)

    cursor.execute(duplicate_query, params)
    if cursor.fetchone():
        return False, 'This room number already exists for the selected hotel.'

    return True, ''

@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT COUNT(*) as count FROM bookings")
    total_bookings = cursor.fetchone()['count']
    
    cursor.execute("SELECT IFNULL(SUM(r.price * GREATEST(1, DATEDIFF(b.check_out, b.check_in))), 0) as revenue FROM bookings b JOIN rooms r ON b.room_id = r.id WHERE b.status IN ('Booked', 'Checked In', 'Checked Out')")
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
        name = request.form.get('name', '').strip()
        location = request.form.get('location', '').strip()
        province_id = request.form.get('province_id')
        city_id = request.form.get('city_id')
        description = request.form.get('description', '').strip()

        valid, message = validate_hotel_fields(name, location, province_id, city_id, description)
        if not valid:
            flash(message, 'danger')
            cursor.close()
            conn.close()
            return redirect(url_for('admin.hotels'))

        try:
            conn.start_transaction()
            cursor.execute("INSERT INTO hotels (name, location, province_id, city_id, description) VALUES (%s, %s, %s, %s, %s)",
                          (name, location, province_id, city_id, description))
            hotel_id = cursor.lastrowid

            files = request.files.getlist('images')
            saved_image_urls = []
            image_data = []
            for file in files:
                if file and file.filename != '':
                    image_url = save_file(file, current_app.config['HOTEL_UPLOAD_FOLDER'], 'uploads/hotels')
                    saved_image_urls.append(image_url)
                    image_data.append((hotel_id, image_url))
            if image_data:
                cursor.executemany("INSERT INTO hotel_images (hotel_id, image_url) VALUES (%s, %s)", image_data)
            
            conn.commit()
            saved_image_urls = [] # Clear so we do not delete committed images
            # Handle Room Groups
            room_types = request.form.getlist('room_type[]')
            quantities = request.form.getlist('quantity[]')
            start_numbers = request.form.getlist('start_number[]')
            prices = request.form.getlist('price[]')
            capacities = request.form.getlist('capacity[]')
            group_indices = request.form.getlist('group_index[]')
            
            for i in range(len(room_types)):
                r_type = room_types[i].strip()
                if not r_type: continue
                qty = int(quantities[i]) if quantities[i] else 1
                start_no = int(start_numbers[i]) if start_numbers[i] else 1
                price = float(prices[i]) if prices[i] else 0
                cap = int(capacities[i]) if capacities[i] else 2
                
                group_idx = group_indices[i] if i < len(group_indices) else i
                room_image_files = request.files.getlist(f'room_images_{group_idx}[]')
                
                r_img_urls = []
                for file in room_image_files:
                    if file and file.filename != '':
                        img_url = save_file(file, current_app.config['HOTEL_UPLOAD_FOLDER'], 'uploads/hotels')
                        r_img_urls.append(img_url)
                        
                generate_rooms(hotel_id, r_type, qty, start_no, price, cap, r_img_urls if r_img_urls else None)

            conn.commit()
            add_notification(
                title="Hotel Baru Ditambahkan",
                description=f"Hotel {name} berhasil ditambahkan ke sistem.",
                icon_type="hotel"
            )
            flash("Hotel and rooms added successfully!", "success")
            log_admin(session['user_id'], 'Hotel', 'Add Hotel', f'Added hotel: {name}')
        except ValueError as e:
            for image_url in saved_image_urls:
                delete_image_file(image_url, current_app.root_path)
            conn.rollback()
            flash(str(e), 'danger')
        except Exception as e:
            for image_url in saved_image_urls:
                delete_image_file(image_url, current_app.root_path)
            conn.rollback()
            flash(f"Error adding hotel: {str(e)}", 'danger')
        finally:
            cursor.close()
            conn.close()
            
        return redirect(url_for('admin.hotels'))

    cursor.execute("SELECT h.*, COUNT(DISTINCT r.id) as room_count, p.province, c.city_name, COALESCE(ROUND(AVG(rev.rating), 1), 0) as avg_rating, COUNT(DISTINCT rev.id) as review_count FROM hotels h LEFT JOIN provinces p ON h.province_id = p.province_id LEFT JOIN cities c ON h.city_id = c.city_id LEFT JOIN rooms r ON h.id = r.hotel_id AND r.is_deleted = 0 LEFT JOIN reviews rev ON h.id = rev.hotel_id WHERE h.is_deleted = 0 GROUP BY h.id, p.province, c.city_name")
    hotel_list = cursor.fetchall()
    hotel_ids = [hotel['id'] for hotel in hotel_list]
    images_by_hotel = fetch_images_by_parent(cursor, 'hotel_images', 'hotel_id', hotel_ids)

    import re
    for hotel in hotel_list:
        hotel['images'] = images_by_hotel.get(hotel['id'], [])
        
        # Room count fallback
        if hotel.get('room_count', 0) == 0 and hotel.get('description'):
            match = re.search(r'rooms:\s*(\d+)', hotel['description'])
            if match:
                hotel['room_count'] = int(match.group(1))

    cursor.execute("SELECT * FROM provinces ORDER BY province")
    provinces = cursor.fetchall()

    cursor.close()
    conn.close()
    return render_template('admin/hotels.html', hotels=hotel_list, provinces=provinces)


@admin_bp.route('/hotel/edit/<int:id>', methods=['GET', 'POST'])
@admin_required
def edit_hotel(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'GET':
        cursor.execute("SELECT * FROM hotels WHERE id = %s AND is_deleted = 0", (id,))
        hotel = cursor.fetchone()
        if not hotel:
            flash("Hotel not found.", "danger")
            return redirect(url_for('admin.hotels'))
            

        # JIT Auto-Migration for legacy hotels
        cursor.execute("SELECT COUNT(*) as c FROM rooms WHERE hotel_id = %s AND is_deleted = 0", (id,))
        room_count = cursor.fetchone()['c']
        
        if room_count == 0 and hotel.get('description'):
            desc = hotel['description']
            # Look for rooms:XX and type:YY
            import re
            rooms_match = re.search(r'rooms:(\d+)', desc)
            type_match = re.search(r'type:([^|]+)', desc)
            
            if rooms_match:
                legacy_qty = int(rooms_match.group(1))
                legacy_type = type_match.group(1).strip() if type_match else "Standard Room"
                if legacy_qty > 0:
                    try:
                        # Auto-generate rooms using default price 500k and capacity 2
                        # The start number will be 101
                        generate_rooms(id, legacy_type, legacy_qty, 101, 500000, 2, None)
                    except Exception as e:
                        print(f"JIT Auto-migration failed for hotel {id}: {str(e)}")

        cursor.execute("SELECT * FROM provinces ORDER BY province")
        provinces = cursor.fetchall()
        
        cursor.execute("SELECT * FROM cities WHERE province_id = %s ORDER BY city_name", (hotel['province_id'],))
        cities = cursor.fetchall()
        
        cursor.execute("SELECT * FROM hotel_images WHERE hotel_id = %s", (id,))
        hotel['images'] = cursor.fetchall()
        
        # Get Room Groups
        cursor.execute("""
            SELECT room_type, price, capacity, COUNT(*) as quantity, MIN(room_number) as start_number, MAX(CAST(room_number AS UNSIGNED)) as max_number 
            FROM rooms 
            WHERE hotel_id = %s AND is_deleted = 0 
            GROUP BY room_type, price, capacity
        """, (id,))
        room_groups = cursor.fetchall()
        
        # Get all images per room type
        for group in room_groups:
            cursor.execute("""
                SELECT MIN(i.id) as id, i.image_url 
                FROM rooms r
                JOIN room_images i ON r.id = i.room_id
                WHERE r.hotel_id = %s AND r.room_type = %s AND r.is_deleted = 0 AND i.image_url IS NOT NULL
                GROUP BY i.image_url
                ORDER BY MIN(i.id) ASC
            """, (id, group['room_type']))
            imgs = cursor.fetchall()
            group['images'] = imgs
            
            if imgs:
                group['image_url'] = imgs[0]['image_url']
            elif hotel.get('images'):
                group['image_url'] = hotel['images'][0]['image_url']
            else:
                group['image_url'] = None

        cursor.close()
        conn.close()
        return render_template('admin/edit_hotel.html', hotel=hotel, provinces=provinces, cities=cities, room_groups=room_groups)

    # POST method
    name = request.form.get('name', '').strip()
    location = request.form.get('location', '').strip()
    province_id = request.form.get('province_id')
    city_id = request.form.get('city_id')
    description = request.form.get('description', '').strip()

    valid, message = validate_hotel_fields(name, location, province_id, city_id, description)
    if not valid:
        flash(message, 'danger')
        cursor.close()
        conn.close()
        return redirect(url_for('admin.edit_hotel', id=id))

    cursor.execute("UPDATE hotels SET name=%s, location=%s, province_id=%s, city_id=%s, description=%s WHERE id=%s",
                  (name, location, province_id, city_id, description, id))

    files = request.files.getlist('images')
    if files and files[0].filename != '':
        cursor.execute("SELECT image_url FROM hotel_images WHERE hotel_id = %s", (id,))
        old_images = cursor.fetchall()
        for old in old_images:
            delete_image_file(old['image_url'], current_app.root_path)

        cursor.execute("DELETE FROM hotel_images WHERE hotel_id = %s", (id,))

        saved_image_urls = []
        try:
            image_data = []
            for file in files:
                if file and file.filename != '':
                    image_url = save_file(file, current_app.config['HOTEL_UPLOAD_FOLDER'], 'uploads/hotels')
                    saved_image_urls.append(image_url)
                    image_data.append((id, image_url))
            if image_data:
                cursor.executemany("INSERT INTO hotel_images (hotel_id, image_url) VALUES (%s, %s)", image_data)
        except ValueError as e:
            for image_url in saved_image_urls:
                delete_image_file(image_url, current_app.root_path)
            conn.rollback()
            cursor.close()
            conn.close()
            flash(str(e), 'danger')
            return redirect(url_for('admin.edit_hotel', id=id))

    conn.commit()
    cursor.close()
    conn.close()
    flash("Hotel updated successfully!", "success")
    log_admin(session['user_id'], 'Hotel', 'Edit Hotel', f'Edited hotel ID: {id}')
    return redirect(url_for('admin.edit_hotel', id=id))

@admin_bp.route('/hotel/edit/<int:hotel_id>/room_group/add', methods=['POST'])
@admin_required
def hotel_add_room_group(hotel_id):
    room_type = request.form.get('room_type', '').strip()
    quantity = int(request.form.get('quantity', 1))
    start_number = int(request.form.get('start_number', 1))
    price = float(request.form.get('price', 0))
    capacity = int(request.form.get('capacity', 2))
    
    file = request.files.get('room_image')
    image_url = None
    if file and file.filename != '':
        image_url = save_file(file, current_app.config['HOTEL_UPLOAD_FOLDER'], 'uploads/hotels')
    
    try:
        generate_rooms(hotel_id, room_type, quantity, start_number, price, capacity, image_url)
        flash(f"Berhasil menambahkan {quantity} kamar tipe {room_type}!", "success")
        log_admin(session['user_id'], 'Room Group', 'Add Room Group', f'Added room group {room_type} to hotel {hotel_id}')
    except ValueError as ve:
        flash(str(ve), "danger")
    except Exception as e:
        flash(f"Error menambahkan room group: {str(e)}", "danger")
        
    return redirect(url_for('admin.edit_hotel', id=hotel_id) + "#manage-rooms")


@admin_bp.route('/hotel/edit/<int:hotel_id>/room_group/add_more', methods=['POST'])
@admin_required
def hotel_add_more_rooms(hotel_id):
    room_type = request.form.get('room_type', '').strip()
    quantity = int(request.form.get('quantity', 1))
    start_number = int(request.form.get('start_number', 1))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Fetch existing price, capacity, and image
        cursor.execute("""
            SELECT r.price, r.capacity, i.image_url, (SELECT MAX(CAST(room_number AS UNSIGNED)) FROM rooms WHERE hotel_id = %s AND room_type = %s) as max_number
            FROM rooms r 
            LEFT JOIN room_images i ON r.id = i.room_id 
            WHERE r.hotel_id = %s AND r.room_type = %s AND r.is_deleted = 0
            LIMIT 1
            """, (hotel_id, room_type, hotel_id, room_type))
        existing = cursor.fetchone()
        
        if not existing:
            flash(f"Room Group '{room_type}' tidak ditemukan.", "danger")
            return redirect(url_for('admin.edit_hotel', id=hotel_id) + "#manage-rooms")
            
        price = existing['price']
        capacity = existing['capacity']
        image_url = existing['image_url']
        
        generate_rooms(hotel_id, room_type, quantity, start_number, price, capacity, image_url)
        flash(f"Berhasil menambahkan {quantity} kamar tambahan untuk tipe {room_type}!", "success")
        log_admin(session['user_id'], 'Room Group', 'Add More Room Group', f'Added {quantity} more rooms to {room_type} in hotel {hotel_id}')
    except ValueError as ve:
        flash(str(ve), "danger")
    except Exception as e:
        flash(f"Error menambahkan kamar tambahan: {str(e)}", "danger")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('admin.edit_hotel', id=hotel_id) + "#manage-rooms")

@admin_bp.route('/hotel/edit/<int:hotel_id>/room_group/edit', methods=['POST'])
@admin_required
def hotel_edit_room_group(hotel_id):
    old_room_type = request.form.get('old_room_type', '').strip()
    new_room_type = request.form.get('room_type', '').strip()
    price = float(request.form.get('price', 0))
    capacity = int(request.form.get('capacity', 2))
    
    files = request.files.getlist('room_image[]')
    image_urls = []
    for file in files:
        if file and file.filename != '':
            img_url = save_file(file, current_app.config['HOTEL_UPLOAD_FOLDER'], 'uploads/hotels')
            image_urls.append(img_url)
        
    try:
        edit_room_group(hotel_id, old_room_type, new_room_type, price, capacity, image_urls if image_urls else None)
        flash(f"Berhasil mengubah grup kamar {old_room_type}!", "success")
        log_admin(session['user_id'], 'Room Group', 'Edit Room Group', f'Edited room group {old_room_type} in hotel {hotel_id}')
    except Exception as e:
        flash(f"Error mengubah room group: {str(e)}", "danger")
        
    return redirect(url_for('admin.edit_hotel', id=hotel_id) + "#manage-rooms")

@admin_bp.route('/hotel/edit/<int:hotel_id>/room_group/delete_image', methods=['POST'])
@admin_required
def hotel_delete_room_image(hotel_id):
    image_id = request.form.get('image_id')
    if not image_id:
        return jsonify({'success': False, 'error': 'Image ID is required'}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT i.id, i.image_url 
            FROM room_images i
            JOIN rooms r ON i.room_id = r.id
            WHERE i.id = %s AND r.hotel_id = %s
        """, (image_id, hotel_id))
        img = cursor.fetchone()
        
        if img:
            cursor.execute("DELETE FROM room_images WHERE id = %s", (image_id,))
            conn.commit()
            log_admin(session.get('user_id'), 'Images', 'Delete Room Image', f'Deleted room image {image_id} for hotel {hotel_id}')
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Image not found or access denied'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@admin_bp.route('/hotel/edit/<int:hotel_id>/room_group/delete', methods=['POST'])
@admin_required
def hotel_delete_room_group(hotel_id):
    room_type = request.form.get('room_type', '').strip()
    try:
        delete_room_group(hotel_id, room_type)
        flash(f"Berhasil menghapus grup kamar {room_type}!", "success")
        log_admin(session['user_id'], 'Room Group', 'Delete Room Group', f'Deleted room group {room_type} in hotel {hotel_id}')
    except Exception as e:
        flash(f"Error menghapus room group: {str(e)}", "danger")
        
    return redirect(url_for('admin.edit_hotel', id=hotel_id) + "#manage-rooms")

    
    cursor.execute("UPDATE hotels SET name=%s, location=%s, province_id=%s, city_id=%s, description=%s WHERE id=%s",
                  (name, location, province_id, city_id, description, id))
                   
    files = request.files.getlist('images')
    if files and files[0].filename != '':
        cursor.execute("SELECT image_url FROM hotel_images WHERE hotel_id = %s", (id,))
        old_images = cursor.fetchall()
        for old in old_images:
            delete_image_file(old['image_url'], current_app.root_path)
            
        cursor.execute("DELETE FROM hotel_images WHERE hotel_id = %s", (id,))

        saved_image_urls = []
        try:
            image_data = []
            for file in files:
                if file and file.filename != '':
                    image_url = save_file(file, current_app.config['HOTEL_UPLOAD_FOLDER'], 'uploads/hotels')
                    saved_image_urls.append(image_url)
                    image_data.append((id, image_url))
            if image_data:
                cursor.executemany("INSERT INTO hotel_images (hotel_id, image_url) VALUES (%s, %s)", image_data)
        except ValueError as e:
            for image_url in saved_image_urls:
                delete_image_file(image_url, current_app.root_path)
            conn.rollback()
            cursor.close()
            conn.close()
            flash(str(e), 'danger')
            return redirect(url_for('admin.hotels'))
                
    conn.commit()
    cursor.close()
    conn.close()
    flash("Hotel updated successfully!", "success")
    log_admin(session['user_id'], 'Hotel', 'Edit Hotel', f'Edited hotel ID: {id}')
    return redirect(url_for('admin.hotels'))

@admin_bp.route('/hotel/delete/<int:id>', methods=['POST'])
@admin_required
def delete_hotel(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("UPDATE hotels SET is_deleted = 1 WHERE id = %s", (id,))
    cursor.execute("UPDATE rooms SET is_deleted = 1 WHERE hotel_id = %s", (id,))
    
    conn.commit()
    cursor.close()
    conn.close()
    flash('Hotel and related data deleted successfully.', 'success')
    log_admin(session['user_id'], 'Hotel', 'Delete Hotel', f'Deleted hotel ID: {id}')
    return redirect(url_for('admin.hotels'))

@admin_bp.route('/api/cities/<province_id>')
@admin_required
def get_cities(province_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM cities WHERE province_id = %s ORDER BY city_name", (province_id,))
    cities = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(cities)


@admin_bp.route('/search', methods=['GET'])
@admin_required
def search():
    query = request.args.get('q', '').strip()
    if len(query) < 2:
        return jsonify([])
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    results = []
    
    # 1. Search Hotels
    cursor.execute("SELECT id, name, location FROM hotels WHERE name LIKE %s OR location LIKE %s LIMIT 5", (f"%{query}%", f"%{query}%"))
    hotels = cursor.fetchall()
    if hotels:
        items = [{'title': h['name'], 'subtitle': h['location'] or 'Hotel', 'url': url_for('admin.hotels') + f"?q={h['name']}"} for h in hotels]
        results.append({'category': 'Hotels', 'items': items})
        
    # 2. Search Rooms
    cursor.execute("SELECT r.id, r.room_number, r.room_type, h.name as hotel_name FROM rooms r JOIN hotels h ON r.hotel_id = h.id WHERE r.room_number LIKE %s OR r.room_type LIKE %s LIMIT 5", (f"%{query}%", f"%{query}%"))
    rooms = cursor.fetchall()
    if rooms:
        items = [{'title': f"Room {r['room_number']} ({r['room_type']})", 'subtitle': r['hotel_name'], 'url': url_for('admin.rooms') + f"?q={r['room_number']}"} for r in rooms]
        results.append({'category': 'Rooms', 'items': items})
        
    # 3. Search Bookings
    cursor.execute("SELECT b.id, b.guest_name, b.status, r.room_number, h.name as hotel_name FROM bookings b JOIN rooms r ON b.room_id = r.id JOIN hotels h ON r.hotel_id = h.id WHERE b.guest_name LIKE %s OR b.id LIKE %s LIMIT 5", (f"%{query}%", f"%{query}%"))
    bookings = cursor.fetchall()
    if bookings:
        items = [{'title': f"Booking #{b['id']} - {b['guest_name']}", 'subtitle': f"{b['hotel_name']} • Room {b['room_number']} ({b['status']})", 'url': url_for('admin.bookings')} for b in bookings]
        results.append({'category': 'Bookings', 'items': items})
        
    # 4. Search Guests / Users
    cursor.execute("SELECT id, username, email, full_name, role FROM users WHERE username LIKE %s OR email LIKE %s OR full_name LIKE %s LIMIT 5", (f"%{query}%", f"%{query}%", f"%{query}%"))
    users = cursor.fetchall()
    
    guests = [u for u in users if u['role'] == 'customer']
    admins = [u for u in users if u['role'] == 'admin']
    
    if guests:
        items = [{'title': u['full_name'] or u['username'], 'subtitle': u['email'], 'url': url_for('admin.bookings')} for u in guests] # Typically guests relate to bookings
        results.append({'category': 'Guests', 'items': items})
        
    if admins:
        items = [{'title': u['full_name'] or u['username'], 'subtitle': f"Admin • {u['email']}", 'url': url_for('admin.dashboard')} for u in admins]
        results.append({'category': 'Users', 'items': items})
        
    cursor.close()
    conn.close()
    return jsonify(results)
    
@admin_bp.route('/rooms', methods=['GET', 'POST'])
@admin_required
def rooms():
    return redirect(url_for('admin.hotels'))
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        hotel_id = request.form.get('hotel_id')
        room_number = request.form.get('room_number', '').strip()
        room_type = request.form.get('room_type', '').strip()
        price = request.form.get('price', '')

        valid, message = validate_room_fields(cursor, hotel_id, room_number, room_type, price)
        if not valid:
            flash(message, 'danger')
            cursor.close()
            conn.close()
            return redirect(url_for('admin.rooms'))

        cursor.execute("INSERT INTO rooms (hotel_id, room_number, room_type, price) VALUES (%s, %s, %s, %s)",
                      (hotel_id, room_number, room_type, price))
        room_id = cursor.lastrowid
        
        saved_image_urls = []
        try:
            files = request.files.getlist('images')
            for file in files:
                if file and file.filename != '':
                    image_url = save_file(file, current_app.config['ROOM_UPLOAD_FOLDER'], 'uploads/rooms')
                    saved_image_urls.append(image_url)
                    cursor.execute("INSERT INTO room_images (room_id, image_url) VALUES (%s, %s)", (room_id, image_url))
        except ValueError as e:
            for image_url in saved_image_urls:
                delete_image_file(image_url, current_app.root_path)
            conn.rollback()
            cursor.close()
            conn.close()
            flash(str(e), 'danger')
            return redirect(url_for('admin.rooms'))
        
        conn.commit()
        add_notification(
            title="Room Baru Ditambahkan",
            description=f"Kamar {room_number} ({room_type}) berhasil ditambahkan.",
            icon_type="room"
        )
        flash("Room added successfully!", "success")
        return redirect(url_for('admin.rooms'))
        
    cursor.execute("SELECT r.*, h.name as hotel_name FROM rooms r JOIN hotels h ON r.hotel_id = h.id WHERE r.is_deleted = 0 AND h.is_deleted = 0")
    room_list = cursor.fetchall()
    room_ids = [room['id'] for room in room_list]
    images_by_room = fetch_images_by_parent(cursor, 'room_images', 'room_id', room_ids)
    
    for room in room_list:
        room['images'] = images_by_room.get(room['id'], [])
    
    cursor.execute("SELECT id, name FROM hotels WHERE is_deleted = 0")
    hotel_list = cursor.fetchall()
    
    cursor.close()
    conn.close()
    return render_template('admin/rooms.html', rooms=room_list, hotels=hotel_list)

@admin_bp.route('/room/edit/<int:id>', methods=['POST'])
@admin_required
def edit_room(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute('SELECT hotel_id FROM rooms WHERE id = %s', (id,))
    room_info = cursor.fetchone()
    if not room_info:
        flash('Room not found.', 'danger')
        cursor.close()
        conn.close()
        return redirect(url_for('admin.rooms'))

    hotel_id = room_info['hotel_id']
    room_number = request.form.get('room_number', '').strip()
    room_type = request.form.get('room_type', '').strip()
    price = request.form.get('price', '')

    valid, message = validate_room_fields(cursor, hotel_id, room_number, room_type, price, exclude_room_id=id)
    if not valid:
        flash(message, 'danger')
        cursor.close()
        conn.close()
        return redirect(url_for('admin.rooms'))

    cursor.execute("UPDATE rooms SET room_number=%s, room_type=%s, price=%s WHERE id=%s",
                  (room_number, room_type, price, id))
                  
    files = request.files.getlist('images')
    if files and files[0].filename != '':
        cursor.execute("SELECT image_url FROM room_images WHERE room_id = %s", (id,))
        old_images = cursor.fetchall()
        for old in old_images:
            delete_image_file(old['image_url'], current_app.root_path)
            
        cursor.execute("DELETE FROM room_images WHERE room_id = %s", (id,))

        saved_image_urls = []
        try:
            for file in files:
                if file and file.filename != '':
                    image_url = save_file(file, current_app.config['ROOM_UPLOAD_FOLDER'], 'uploads/rooms')
                    saved_image_urls.append(image_url)
                    cursor.execute("INSERT INTO room_images (room_id, image_url) VALUES (%s, %s)", (id, image_url))
        except ValueError as e:
            for image_url in saved_image_urls:
                delete_image_file(image_url, current_app.root_path)
            conn.rollback()
            cursor.close()
            conn.close()
            flash(str(e), 'danger')
            return redirect(url_for('admin.rooms'))
                
    conn.commit()
    cursor.close()
    conn.close()
    flash("Room updated successfully!", "success")
    return redirect(url_for('admin.rooms'))

@admin_bp.route('/room/delete/<int:id>', methods=['POST'])
@admin_required
def delete_room(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("UPDATE rooms SET is_deleted = 1 WHERE id = %s", (id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash('Room deleted successfully.', 'success')
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
            cursor.execute("UPDATE bookings SET status = 'Cancelled', cancel_reason = %s WHERE id = %s AND status = 'Booked'", 
                          (cancel_reason, booking_id))
            conn.commit()
            add_notification(
                title="Booking Dibatalkan",
                description=f"Booking #{booking_id} telah dibatalkan.",
                icon_type="cancel"
            )
            flash("Booking cancelled successfully.", "warning")
            log_admin(session['user_id'], 'Bookings', 'Cancel Booking', f'Cancelled booking ID: {booking_id}')
        return redirect(url_for('admin.bookings'))
        
    cursor.execute("""
        SELECT b.*, u.username, u.email, r.room_type, r.room_number, h.name as hotel_name,
               (r.price * GREATEST(1, DATEDIFF(b.check_out, b.check_in))) as total_price
        FROM bookings b 
        JOIN users u ON b.user_id = u.id 
        JOIN rooms r ON b.room_id = r.id
        JOIN hotels h ON r.hotel_id = h.id
        ORDER BY b.created_at DESC
    """)
    booking_list = cursor.fetchall()
    
    # Format total_price to be an integer (remove decimals)
    for booking in booking_list:
        if booking.get('total_price'):
            booking['total_price'] = int(booking['total_price'])

    cursor.close()
    conn.close()
    return render_template('admin/bookings.html', bookings=booking_list)

@admin_bp.route('/booking/delete/<int:id>', methods=['POST'])
@admin_required
def delete_booking(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("DELETE FROM bookings WHERE id = %s", (id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash('Booking deleted successfully.', 'success')
    log_admin(session['user_id'], 'Bookings', 'Soft Delete Booking', f'Soft deleted booking ID: {id}')
    return redirect(url_for('admin.bookings'))

@admin_bp.route('/api/bookings/filter', methods=['GET'])
@admin_required
def api_bookings_filter():
    search = request.args.get('search', '').strip()
    status = request.args.get('status', '').strip()
    date_filter = request.args.get('date', '').strip()
    sort_filter = request.args.get('sort', 'newest').strip()
    user_filter = request.args.get('user', '').strip()
    view = request.args.get('view', '').strip()

    query = """
        SELECT b.*, u.username, u.email, r.room_type, r.room_number, h.name as hotel_name,
               (r.price * GREATEST(1, DATEDIFF(b.check_out, b.check_in))) as total_price
        FROM bookings b 
        JOIN users u ON b.user_id = u.id 
        JOIN rooms r ON b.room_id = r.id
        JOIN hotels h ON r.hotel_id = h.id
        WHERE 1=1
    """
    params = []

    if search:
        query += " AND (b.guest_name LIKE %s OR b.id LIKE %s OR u.username LIKE %s OR r.room_number LIKE %s OR h.name LIKE %s)"
        search_term = '%' + search + '%'
        params.extend([search_term, search_term, search_term, search_term, search_term])
    
    if user_filter:
        query += " AND u.username = %s"
        params.append(user_filter)
    
    if status:
        query += " AND b.status = %s"
        params.append(status)

    if date_filter == 'today':
        query += " AND DATE(b.created_at) = CURDATE()"
    elif date_filter == 'yesterday':
        query += " AND DATE(b.created_at) = CURDATE() - INTERVAL 1 DAY"
    elif date_filter == 'week':
        query += " AND b.created_at >= CURDATE() - INTERVAL 7 DAY"
    elif date_filter == 'month' or date_filter == 'this_month':
        query += " AND YEAR(b.created_at) = YEAR(CURDATE()) AND MONTH(b.created_at) = MONTH(CURDATE())"
    elif date_filter == 'last_30':
        query += " AND b.created_at >= CURDATE() - INTERVAL 30 DAY"

    if sort_filter == 'oldest':
        query += " ORDER BY b.created_at ASC"
    elif sort_filter == 'guest_asc':
        query += " ORDER BY b.guest_name ASC"
    elif sort_filter == 'guest_desc':
        query += " ORDER BY b.guest_name DESC"
    elif sort_filter == 'checkin_new':
        query += " ORDER BY b.check_in DESC"
    elif sort_filter == 'checkin_old':
        query += " ORDER BY b.check_in ASC"
    elif sort_filter == 'price_desc':
        query += " ORDER BY total_price DESC"
    elif sort_filter == 'price_asc':
        query += " ORDER BY total_price ASC"
    else: # newest
        query += " ORDER BY b.created_at DESC"

    if view == 'audit' and user_filter == 'admin':
        # Fetch directly from audit_logs for Admin
        audit_query = """
            SELECT a.*, u.username, 1 as is_audit, a.created_at, 'Admin' as status
            FROM audit_logs a
            JOIN users u ON a.admin_id = u.id
            WHERE 1=1
        """
        audit_params = []
        
        if search:
            audit_query += " AND (a.module LIKE %s OR a.action LIKE %s OR a.description LIKE %s)"
            search_term = '%' + search + '%'
            audit_params.extend([search_term, search_term, search_term])
            
        if date_filter == 'today':
            audit_query += " AND DATE(a.created_at) = CURDATE()"
        elif date_filter == 'yesterday':
            audit_query += " AND DATE(a.created_at) = CURDATE() - INTERVAL 1 DAY"
        elif date_filter == 'week':
            audit_query += " AND a.created_at >= CURDATE() - INTERVAL 7 DAY"
        elif date_filter == 'month' or date_filter == 'this_month':
            audit_query += " AND YEAR(a.created_at) = YEAR(CURDATE()) AND MONTH(a.created_at) = MONTH(CURDATE())"
        elif date_filter == 'last_30':
            audit_query += " AND a.created_at >= CURDATE() - INTERVAL 30 DAY"
            
        if sort_filter == 'oldest':
            audit_query += " ORDER BY a.created_at ASC"
        else:
            audit_query += " ORDER BY a.created_at DESC"
            
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(audit_query, tuple(audit_params))
        audit_list = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return render_template('admin/partials/timeline_rows.html', bookings=audit_list)

    else:
        # Original bookings query
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(query, tuple(params))
        booking_list = cursor.fetchall()
        
        for booking in booking_list:
            if booking.get('total_price'):
                booking['total_price'] = int(booking['total_price'])
                
        cursor.close()
        conn.close()
        
        if view == 'audit':
            return render_template('admin/partials/timeline_rows.html', bookings=booking_list)
        else:
            return render_template('admin/partials/booking_rows.html', bookings=booking_list)


@admin_bp.route('/reports', methods=['GET'])
@admin_required
def reports():
    return render_template('admin/reports.html')


def get_report_data(report_type, period, search_term='', sort_by='', page=1, limit=None):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    import datetime
    now = datetime.datetime.now()
    start_date = None
    end_date = now
    
    if period == 'Today':
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == 'Yesterday':
        start_date = (now - datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + datetime.timedelta(days=1) - datetime.timedelta(microseconds=1)
    elif period == 'Last 7 Days':
        start_date = now - datetime.timedelta(days=7)
    elif period == 'Last 30 Days':
        start_date = now - datetime.timedelta(days=30)
    elif period == 'This Week':
        start_date = now - datetime.timedelta(days=now.weekday())
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == 'This Month':
        start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif period == 'This Year':
        start_date = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    elif ' to ' in period:
        try:
            parts = period.split(' to ')
            start_date = datetime.datetime.strptime(parts[0], '%Y-%m-%d')
            end_date = datetime.datetime.strptime(parts[1], '%Y-%m-%d').replace(hour=23, minute=59, second=59)
        except ValueError:
            pass
            
    cursor.execute("SELECT COUNT(*) as total FROM hotels WHERE is_deleted = 0")
    total_hotels = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as total FROM rooms WHERE is_deleted = 0")
    total_rooms = cursor.fetchone()['total']
    
    query_b = "SELECT COUNT(*) as total FROM bookings WHERE 1=1"
    params_b = []
    if start_date:
        query_b += " AND created_at >= %s AND created_at <= %s"
        params_b.extend([start_date, end_date])
    cursor.execute(query_b, params_b)
    total_bookings = cursor.fetchone()['total']
    
    query_r = "SELECT IFNULL(SUM(r.price * GREATEST(1, DATEDIFF(b.check_out, b.check_in))), 0) as revenue FROM bookings b JOIN rooms r ON b.room_id = r.id WHERE b.status IN ('Booked', 'Checked In', 'Checked Out')"
    params_r = []
    if start_date:
        query_r += " AND b.created_at >= %s AND b.created_at <= %s"
        params_r.extend([start_date, end_date])
    cursor.execute(query_r, params_r)
    total_revenue = float(cursor.fetchone()['revenue'])
    
    query_s = "SELECT status, COUNT(*) as cnt FROM bookings WHERE 1=1"
    params_s = []
    if start_date:
        query_s += " AND created_at >= %s AND created_at <= %s"
        params_s.extend([start_date, end_date])
    query_s += " GROUP BY status"
    cursor.execute(query_s, params_s)
    status_counts = {'Booked': 0, 'Checked In': 0, 'Checked Out': 0, 'Cancelled': 0}
    for row in cursor.fetchall():
        if row['status'] in status_counts:
            status_counts[row['status']] = row['cnt']
            
    occupancy_rate = 0.0
    if total_rooms > 0:
        occupancy_rate = ((status_counts['Booked'] + status_counts['Checked In']) / total_rooms) * 100
    
    # Calculate new data without breaking existing structure
    cursor.execute("SELECT COUNT(*) as total FROM rooms WHERE is_deleted = 0 AND id NOT IN (SELECT room_id FROM bookings WHERE status IN ('Booked', 'Checked In'))")
    row_ar = cursor.fetchone()
    available_rooms = row_ar['total'] if row_ar else 0
    
    query_trx = "SELECT COUNT(id) as cnt FROM bookings WHERE status IN ('Booked', 'Checked In', 'Checked Out')"
    params_trx = []
    if start_date:
        query_trx += " AND created_at >= %s AND created_at <= %s"
        params_trx.extend([start_date, end_date])
    cursor.execute(query_trx, params_trx)
    row_trx = cursor.fetchone()
    total_transactions = row_trx['cnt'] if row_trx else 0
    avg_revenue = total_revenue / total_transactions if total_transactions > 0 else 0.0

    query_top = "SELECT h.name, SUM(r.price * GREATEST(1, DATEDIFF(b.check_out, b.check_in))) as revenue FROM bookings b JOIN rooms r ON b.room_id = r.id JOIN hotels h ON h.id = r.hotel_id WHERE b.status IN ('Booked', 'Checked In', 'Checked Out') GROUP BY h.id ORDER BY revenue DESC LIMIT 1"
    cursor.execute(query_top)
    top_hotel_data = cursor.fetchone()
    highest_revenue_hotel = top_hotel_data['name'] if top_hotel_data else "-"
    
    query_logs = "SELECT COUNT(*) as total FROM bookings WHERE 1=1"
    params_logs = []
    if start_date:
        query_logs += " AND created_at >= %s AND created_at <= %s"
        params_logs.extend([start_date, end_date])
    cursor.execute(query_logs, params_logs)
    row_logs = cursor.fetchone()
    total_audit_logs = row_logs['total'] if row_logs else 0
    
    cursor.execute("SELECT COUNT(*) as today FROM bookings WHERE DATE(created_at) = CURDATE()")
    row_today = cursor.fetchone()
    today_logs = row_today['today'] if row_today else 0

    summary = {
        'total_hotels': total_hotels,
        'total_rooms': total_rooms,
        'total_bookings': total_bookings,
        'total_revenue': total_revenue,
        'status_booked': status_counts['Booked'],
        'status_checked_in': status_counts['Checked In'],
        'status_checked_out': status_counts['Checked Out'],
        'status_cancelled': status_counts['Cancelled'],
        'occupancy_rate': round(occupancy_rate, 1),
        
        # New enriched data
        'available_rooms': available_rooms,
        'avg_revenue': avg_revenue,
        'total_transactions': total_transactions,
        'highest_revenue_hotel': highest_revenue_hotel,
        'total_audit_logs': total_audit_logs,
        'today_logs': today_logs,
        'admin_actions': total_audit_logs,
        'system_actions': 0
    }
    
    details = []
    total_records = 0
    if report_type == 'Hotels':
        q_count = "SELECT COUNT(DISTINCT h.id) as total FROM hotels h LEFT JOIN rooms r ON h.id = r.hotel_id AND r.is_deleted = 0 WHERE h.is_deleted = 0"
        p_count = []
        if search_term:
            q_count += " AND (h.name LIKE %s OR h.location LIKE %s)"
            p_count.extend([f"%{search_term}%", f"%{search_term}%"])
        cursor.execute(q_count, p_count)
        total_records = cursor.fetchone()['total']

        q = "SELECT h.name as hotel, h.location, COUNT(r.id) as rooms, 'Available' as status FROM hotels h LEFT JOIN rooms r ON h.id = r.hotel_id AND r.is_deleted = 0 WHERE h.is_deleted = 0"
        p = []
        if search_term:
            q += " AND (h.name LIKE %s OR h.location LIKE %s)"
            p.extend([f"%{search_term}%", f"%{search_term}%"])
        q += " GROUP BY h.id"
        if sort_by == 'name_asc':
            q += " ORDER BY h.name ASC"
        else:
            q += " ORDER BY h.id DESC"
            
        if limit is not None:
            q += " LIMIT %s OFFSET %s"
            p.extend([limit, (page - 1) * limit])
            
        cursor.execute(q, p)
        for r in cursor.fetchall():
            details.append({
                'hotel': r['hotel'],
                'location': r['location'],
                'rooms': r['rooms'],
                'status': r['status']
            })
    elif report_type == 'Rooms':
        q_count = "SELECT COUNT(*) as total FROM (SELECT h.id FROM rooms r JOIN hotels h ON r.hotel_id = h.id WHERE r.is_deleted = 0"
        p_count = []
        if search_term:
            q_count += " AND (r.room_type LIKE %s OR h.name LIKE %s)"
            p_count.extend([f"%{search_term}%", f"%{search_term}%"])
        q_count += " GROUP BY h.id, r.room_type) as tmp"
        cursor.execute(q_count, p_count)
        total_records = cursor.fetchone()['total']

        q = """
        SELECT h.name as hotel, r.room_type, COUNT(r.id) as total_rooms, 
        SUM(CASE WHEN r.id IN (SELECT room_id FROM bookings WHERE status IN ('Booked', 'Checked In')) THEN 1 ELSE 0 END) as booked
        FROM rooms r JOIN hotels h ON r.hotel_id = h.id 
        WHERE r.is_deleted = 0
        """
        p = []
        if search_term:
            q += " AND (r.room_type LIKE %s OR h.name LIKE %s)"
            p.extend([f"%{search_term}%", f"%{search_term}%"])
        q += " GROUP BY h.id, r.room_type"
        if sort_by == 'name_asc':
            q += " ORDER BY r.room_type ASC"
        else:
            q += " ORDER BY h.name ASC"
            
        if limit is not None:
            q += " LIMIT %s OFFSET %s"
            p.extend([limit, (page - 1) * limit])
            
        cursor.execute(q, p)
        for r in cursor.fetchall():
            tr = r['total_rooms'] or 0
            br = int(r['booked']) or 0
            ar = tr - br
            occ_rate = (br / tr) * 100 if tr > 0 else 0
            details.append({
                'hotel': r['hotel'],
                'room_type': r['room_type'],
                'total_rooms': tr,
                'booked': br,
                'available': ar,
                'occupancy': f"{occ_rate:.0f}%"
            })
    elif report_type == 'Bookings':
        q_count = "SELECT COUNT(*) as total FROM bookings b JOIN rooms r ON b.room_id = r.id JOIN hotels h ON r.hotel_id = h.id WHERE 1=1"
        p_count = []
        if start_date:
            q_count += " AND b.created_at >= %s AND b.created_at <= %s"
            p_count.extend([start_date, end_date])
        if search_term:
            q_count += " AND (b.guest_name LIKE %s OR h.name LIKE %s)"
            p_count.extend([f"%{search_term}%", f"%{search_term}%"])
        cursor.execute(q_count, p_count)
        total_records = cursor.fetchone()['total']

        q = "SELECT b.id as booking_id, b.guest_name as guest, h.name as hotel, b.created_at as date, b.status FROM bookings b JOIN rooms r ON b.room_id = r.id JOIN hotels h ON r.hotel_id = h.id WHERE 1=1"
        p = []
        if start_date:
            q += " AND b.created_at >= %s AND b.created_at <= %s"
            p.extend([start_date, end_date])
        if search_term:
            q += " AND (b.guest_name LIKE %s OR h.name LIKE %s)"
            p.extend([f"%{search_term}%", f"%{search_term}%"])
        if sort_by == 'name_asc':
            q += " ORDER BY b.guest_name ASC"
        else:
            q += " ORDER BY b.created_at DESC"
            
        if limit is not None:
            q += " LIMIT %s OFFSET %s"
            p.extend([limit, (page - 1) * limit])
            
        cursor.execute(q, p)
        for r in cursor.fetchall():
            details.append({
                'booking_id': r['booking_id'],
                'guest': r['guest'],
                'hotel': r['hotel'],
                'date': r['date'].strftime('%Y-%m-%d'),
                'status': r['status']
            })
    elif report_type == 'Revenue Report':
        q_count = "SELECT COUNT(*) as total FROM (SELECT h.id FROM bookings b JOIN rooms r ON b.room_id = r.id JOIN hotels h ON r.hotel_id = h.id WHERE b.status IN ('Booked', 'Checked In', 'Checked Out')"
        p_count = []
        if start_date:
            q_count += " AND b.created_at >= %s AND b.created_at <= %s"
            p_count.extend([start_date, end_date])
        if search_term:
            q_count += " AND (h.name LIKE %s OR r.room_type LIKE %s)"
            p_count.extend([f"%{search_term}%", f"%{search_term}%"])
        q_count += " GROUP BY h.id, r.room_type) as tmp"
        cursor.execute(q_count, p_count)
        total_records = cursor.fetchone()['total']

        q = "SELECT h.name as hotel, r.room_type, COUNT(b.id) as total_bookings, IFNULL(SUM(r.price * GREATEST(1, DATEDIFF(b.check_out, b.check_in))), 0) as total_revenue FROM bookings b JOIN rooms r ON b.room_id = r.id JOIN hotels h ON r.hotel_id = h.id WHERE b.status IN ('Booked', 'Checked In', 'Checked Out')"
        p = []
        if start_date:
            q += " AND b.created_at >= %s AND b.created_at <= %s"
            p.extend([start_date, end_date])
        if search_term:
            q += " AND (h.name LIKE %s OR r.room_type LIKE %s)"
            p.extend([f"%{search_term}%", f"%{search_term}%"])
        q += " GROUP BY h.id, r.room_type"
        if sort_by == 'highest_revenue':
            q += " ORDER BY total_revenue DESC"
        else:
            q += " ORDER BY total_revenue DESC"
            
        if limit is not None:
            q += " LIMIT %s OFFSET %s"
            p.extend([limit, (page - 1) * limit])
            
        cursor.execute(q, p)
        for r in cursor.fetchall():
            details.append({
                'hotel': r['hotel'],
                'room_type': r['room_type'],
                'total_bookings': r['total_bookings'],
                'total_revenue': float(r['total_revenue'])
            })
    elif report_type == 'Audit Report':
        q_count = "SELECT COUNT(*) as total FROM bookings b JOIN rooms r ON b.room_id = r.id JOIN hotels h ON r.hotel_id = h.id WHERE 1=1"
        p_count = []
        if start_date:
            q_count += " AND b.created_at >= %s AND b.created_at <= %s"
            p_count.extend([start_date, end_date])
        if search_term:
            q_count += " AND (b.guest_name LIKE %s OR h.name LIKE %s)"
            p_count.extend([f"%{search_term}%", f"%{search_term}%"])
        cursor.execute(q_count, p_count)
        total_records = cursor.fetchone()['total']

        # Simulate audit log from bookings since audit_logs table does not exist
        q = "SELECT b.id as log_id, b.guest_name as admin, CONCAT('Booking ', b.status) as action, CONCAT('Room ', r.room_number, ' at ', h.name) as details, b.created_at as date FROM bookings b JOIN rooms r ON b.room_id = r.id JOIN hotels h ON r.hotel_id = h.id WHERE 1=1"
        p = []
        if start_date:
            q += " AND b.created_at >= %s AND b.created_at <= %s"
            p.extend([start_date, end_date])
        if search_term:
            q += " AND (b.guest_name LIKE %s OR h.name LIKE %s)"
            p.extend([f"%{search_term}%", f"%{search_term}%"])
        q += " ORDER BY b.created_at DESC"
        
        if limit is not None:
            q += " LIMIT %s OFFSET %s"
            p.extend([limit, (page - 1) * limit])
            
        cursor.execute(q, p)
        for r in cursor.fetchall():
            details.append({
                'booking_id': r['log_id'],
                'guest': r['details'][:30] + '...' if r['details'] and len(r['details']) > 30 else (r['details'] or '-'),
                'admin': 'System',
                'action': r['action'],
                'date': r['date'].strftime('%Y-%m-%d %H:%M')
            })

    cursor.close()
    conn.close()
    return summary, details, total_records




@admin_bp.route('/api/reports/preview', methods=['POST'])
@admin_required
def api_reports_preview():
    print("Preview endpoint called")
    data = request.json
    report_type = data.get('type', 'Dashboard Summary')
    period = data.get('period', 'This Month')
    search_term = data.get('search', '').strip()
    sort_by = data.get('sort', '').strip()
    page = int(data.get('page', 1))
    limit = int(data.get('limit', 20))
    
    summary, details, total_records = get_report_data(report_type, period, search_term, sort_by, page, limit)
    return jsonify({
        'summary': summary,
        'details': details,
        'pagination': {
            'page': page,
            'limit': limit,
            'total_records': total_records
        }
    })



def generate_pdf_bytes(report_type, period, summary, details):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    elements = []
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'MainTitle', parent=styles['Title'], fontName='Helvetica-Bold', fontSize=24,
        textColor=colors.HexColor('#0F172A'), spaceAfter=6, alignment=1
    )
    subtitle_style = ParagraphStyle(
        'SubTitle', parent=styles['Normal'], fontName='Helvetica', fontSize=12,
        textColor=colors.HexColor('#64748B'), spaceAfter=20, alignment=1
    )
    heading_style = ParagraphStyle(
        'CustomHeading', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=14,
        textColor=colors.HexColor('#1E293B'), spaceBefore=20, spaceAfter=10
    )
    normal_style = ParagraphStyle(
        'CustomNormal', parent=styles['Normal'], fontName='Helvetica', fontSize=10,
        textColor=colors.HexColor('#334155'), spaceAfter=6
    )
    
    # --- HEADER ---
    elements.append(Paragraph("BHINEKA HOTELS", title_style))
    elements.append(Paragraph("Property Management System", subtitle_style))
    
    # Separator Line
    from reportlab.platypus import HRFlowable
    elements.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#E2E8F0'), spaceBefore=10, spaceAfter=20))
    
    # --- REPORT INFORMATION ---
    elements.append(Paragraph("REPORT INFORMATION", heading_style))
    gen_time = datetime.datetime.now()
    info_data = [
        [Paragraph("<b>Generated Date:</b>", normal_style), Paragraph(gen_time.strftime('%Y-%m-%d'), normal_style),
         Paragraph("<b>Selected Period:</b>", normal_style), Paragraph(period, normal_style)],
        [Paragraph("<b>Generated Time:</b>", normal_style), Paragraph(gen_time.strftime('%H:%M:%S'), normal_style),
         Paragraph("<b>Report Type:</b>", normal_style), Paragraph(report_type.upper(), normal_style)],
        [Paragraph("<b>Administrator:</b>", normal_style), Paragraph("System Admin", normal_style), "", ""]
    ]
    t_info = Table(info_data, colWidths=['20%', '30%', '20%', '30%'])
    t_info.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
    ]))
    elements.append(t_info)
    elements.append(Spacer(1, 20))
    
    # --- SUMMARY ---
    elements.append(Paragraph("EXECUTIVE SUMMARY", heading_style))
    if report_type == 'Dashboard Summary':
        summary_data = [
            ['Total Hotels', 'Total Rooms', 'Total Bookings', 'Total Revenue'],
            [str(summary.get('total_hotels', 0)), str(summary.get('total_rooms', 0)),
             str(summary.get('total_bookings', 0)), f"Rp {summary.get('total_revenue', 0):,.0f}".replace(',', '.')]
        ]
    elif report_type == 'Hotels':
        summary_data = [
            ['Total Hotels', 'Total Rooms', 'Available Rooms', 'Occupancy Rate'],
            [str(summary.get('total_hotels', 0)), str(summary.get('total_rooms', 0)),
             str(summary.get('available_rooms', 0)), f"{summary.get('occupancy_rate', 0)}%"]
        ]
    elif report_type == 'Rooms':
        booked_rooms = summary.get('total_rooms', 0) - summary.get('available_rooms', 0)
        summary_data = [
            ['Total Rooms', 'Booked Rooms', 'Available Rooms', 'Occupancy Rate'],
            [str(summary.get('total_rooms', 0)), str(booked_rooms),
             str(summary.get('available_rooms', 0)), f"{summary.get('occupancy_rate', 0)}%"]
        ]
    elif report_type == 'Bookings':
        summary_data = [
            ['Total Bookings', 'Booked', 'Checked In', 'Cancelled'],
            [str(summary.get('total_bookings', 0)), str(summary.get('status_booked', 0)),
             str(summary.get('status_checked_in', 0)), str(summary.get('status_cancelled', 0))]
        ]
    elif report_type == 'Revenue Report':
        summary_data = [
            ['Total Revenue', 'Avg Revenue', 'Transactions', 'Top Hotel'],
            [f"Rp {summary.get('total_revenue', 0):,.0f}".replace(',', '.'), 
             f"Rp {summary.get('avg_revenue', 0):,.0f}".replace(',', '.'),
             str(summary.get('total_transactions', 0)), 
             str(summary.get('highest_revenue_hotel', '-'))]
        ]
    elif report_type == 'Audit Report':
        summary_data = [
            ['Total Audit Logs', "Today's Logs", 'Admin Actions', 'System Actions'],
            [str(summary.get('total_audit_logs', 0)), str(summary.get('today_logs', 0)),
             str(summary.get('admin_actions', 0)), str(summary.get('system_actions', 0))]
        ]
    else:
        summary_data = [
            ['Total Hotels', 'Total Rooms', 'Total Bookings', 'Total Revenue'],
            [str(summary.get('total_hotels', 0)), str(summary.get('total_rooms', 0)),
             str(summary.get('total_bookings', 0)), f"Rp {summary.get('total_revenue', 0):,.0f}".replace(',', '.')]
        ]
    
    t_sum = Table(summary_data, colWidths=['25%', '25%', '25%', '25%'])
    t_sum.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#4F46E5')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('TOPPADDING', (0,0), (-1,0), 12),
        ('BOTTOMPADDING', (0,0), (-1,0), 12),
        ('BACKGROUND', (0,1), (-1,-1), colors.HexColor('#F8FAFC')),
        ('TEXTCOLOR', (0,1), (-1,-1), colors.HexColor('#0F172A')),
        ('TOPPADDING', (0,1), (-1,-1), 16),
        ('BOTTOMPADDING', (0,1), (-1,-1), 16),
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,1), (-1,-1), 12),
        ('GRID', (0,0), (-1,-1), 1, colors.HexColor('#E2E8F0'))
    ]))
    elements.append(t_sum)
    elements.append(Spacer(1, 20))
    
    # --- DETAIL ANALYTICS OR TABLE ---
    if report_type == 'Business Analytics':
        elements.append(Paragraph("DETAIL ANALYTICS", heading_style))
        
        detail_data = [
            [Paragraph("<b>Revenue</b>", normal_style), Paragraph("Consistent growth detected based on available bookings.", normal_style)],
            [Paragraph("<b>Bookings</b>", normal_style), Paragraph(f"{summary.get('total_bookings', 0)} total historical bookings recorded in the system.", normal_style)],
            [Paragraph("<b>Top Hotel</b>", normal_style), Paragraph("Based on aggregated data.", normal_style)],
            [Paragraph("<b>Popular Room</b>", normal_style), Paragraph("Based on highest booking volume.", normal_style)],
        ]
        t_det = Table(detail_data, colWidths=['30%', '70%'])
        t_det.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')),
            ('GRID', (0,0), (-1,-1), 1, colors.HexColor('#E2E8F0')),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('TOPPADDING', (0,0), (-1,-1), 12),
            ('BOTTOMPADDING', (0,0), (-1,-1), 12),
        ]))
        elements.append(t_det)
        
    elif report_type != 'Dashboard Summary' and details:
        elements.append(Paragraph(f"{report_type.upper()} DETAILS", heading_style))
        
        if report_type == 'Hotels':
            headers = ['Hotel', 'Location', 'Rooms', 'Status']
            table_data = [headers]
            for row in details:
                table_data.append([row['hotel'], row['location'], str(row['rooms']), row['status']])
        elif report_type == 'Rooms':
            headers = ['Hotel', 'Room Type', 'Total Rooms', 'Available', 'Booked', 'Occupancy']
            table_data = [headers]
            last_hotel = None
            for row in details:
                hotel_name = "" if row['hotel'] == last_hotel else row['hotel']
                last_hotel = row['hotel']
                table_data.append([hotel_name, row['room_type'], str(row['total_rooms']), str(row['available']), str(row['booked']), row['occupancy']])
        elif report_type == 'Bookings':
            headers = ['Booking ID', 'Guest', 'Hotel', 'Date', 'Status']
            table_data = [headers]
            for row in details:
                table_data.append([str(row['booking_id']), row['guest'], row['hotel'], row['date'], row['status']])
        elif report_type == 'Revenue Report':
            headers = ['Hotel', 'Room Type', 'Bookings', 'Total Revenue']
            table_data = [headers]
            for row in details:
                table_data.append([row['hotel'], row['room_type'], str(row['total_bookings']), f"Rp {row['total_revenue']:,.0f}".replace(',', '.')])
        elif report_type == 'Audit Report':
            headers = ['Booking ID', 'Guest', 'Admin', 'Action/Status', 'Date']
            table_data = [headers]
            for row in details:
                table_data.append([str(row['booking_id']), row['guest'], row['admin'], row['action'], row['date']])
                
        t_details = Table(table_data)
        t_details.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#4F46E5')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('TOPPADDING', (0,0), (-1,-1), 10),
            ('BOTTOMPADDING', (0,0), (-1,-1), 10),
            ('GRID', (0,0), (-1,-1), 1, colors.HexColor('#E2E8F0'))
        ]))
        elements.append(t_details)
        
    else:
        if report_type != 'Dashboard Summary':
            elements.append(Paragraph("No detailed data available for the selected period.", normal_style))
        
    elements.append(Spacer(1, 40))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#E2E8F0'), spaceBefore=10, spaceAfter=10))
    elements.append(Paragraph("Generated automatically by Bhineka Hotels Property Management System", ParagraphStyle(
        'Footer', parent=styles['Italic'], fontName='Helvetica-Oblique', fontSize=8, textColor=colors.HexColor('#94A3B8'), alignment=1
    )))
    
    doc.build(elements)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


@admin_bp.route('/api/reports/download_pdf', methods=['POST'])
@admin_required
def api_reports_download_pdf():
    report_type = request.form.get('type', 'Dashboard Summary')
    period = request.form.get('period', 'This Month')
    search_term = request.form.get('search', '').strip()
    sort_by = request.form.get('sort', '').strip()
    
    summary, details, _ = get_report_data(report_type, period, search_term, sort_by, 1, None)
    pdf_bytes = generate_pdf_bytes(report_type, period, summary, details)
    
    add_notification(
        title="Report Diekspor",
        description=f"Laporan {report_type} periode {period} berhasil diekspor ke PDF.",
        icon_type="report"
    )
    
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-disposition": f"attachment; filename=Report_{report_type}_{period}.pdf"}
    )


@admin_bp.route('/api/reports/send_email', methods=['POST'])
@admin_required
def api_reports_send_email():
    data = request.json
    report_type = data.get('type', 'Dashboard Summary')
    period = data.get('period', 'This Month')
    search_term = data.get('search', '').strip()
    sort_by = data.get('sort', '').strip()
    email = data.get('email')
    subject = data.get('subject', 'Bhineka Hotels Report')
    message_body = data.get('message', '')
    
    if not email:
        return jsonify({'error': 'Recipient email is required.'}), 400
        
    summary, details, _ = get_report_data(report_type, period, search_term, sort_by, 1, None)
    pdf_bytes = generate_pdf_bytes(report_type, period, summary, details)
    
    try:
        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = os.getenv('MAIL_USERNAME', 'no-reply@bhinekahotels.com')
        msg['To'] = email
        msg.set_content(message_body)
        
        msg.add_attachment(pdf_bytes, maintype='application', subtype='pdf', filename=f"Report_{report_type}_{period}.pdf")
        
        smtp_server = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
        smtp_port = int(os.getenv('MAIL_PORT', 587))
        smtp_user = os.getenv('MAIL_USERNAME')
        smtp_pass = os.getenv('MAIL_PASSWORD')
        
        if not smtp_user or not smtp_pass:
            # For testing purposes if no SMTP is configured, we simulate success
            print(f"Simulating email send to {email} (No SMTP configured)")
            return jsonify({'success': True, 'message': 'Email sent successfully (simulated).'})
            
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        
        add_notification(
            title="Report Dikirim",
            description=f"Laporan {report_type} berhasil dikirim ke email {email}.",
            icon_type="report"
        )
        
        return jsonify({'status': 'success', 'message': 'Email sent successfully!'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500



@admin_bp.route('/analytics')
@admin_required
def analytics():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, name FROM hotels WHERE is_deleted = 0")
    hotels = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('admin/analytics.html', hotels=hotels)


@admin_bp.route('/api/analytics_data')
@admin_required
def api_analytics_data():
    period = request.args.get('period', 'This Month')
    hotel_id = request.args.get('hotel_id', '')
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    now = datetime.datetime.now()
    start_date = None
    end_date = now
    
    prev_start_date = None
    prev_end_date = None
    
    if period == 'Today':
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        prev_start_date = start_date - datetime.timedelta(days=1)
        prev_end_date = start_date
    elif period == 'This Week':
        start_date = now - datetime.timedelta(days=now.weekday())
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        prev_start_date = start_date - datetime.timedelta(weeks=1)
        prev_end_date = start_date
    elif period == 'This Month':
        start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        first_day_prev_month = (start_date - datetime.timedelta(days=1)).replace(day=1)
        prev_start_date = first_day_prev_month
        prev_end_date = start_date
    elif period == 'This Year':
        start_date = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        prev_start_date = start_date.replace(year=start_date.year - 1)
        prev_end_date = start_date
    
    hotel_filter = ""
    params = []
    if hotel_id and hotel_id != 'all':
        hotel_filter = " AND h.id = %s "
        params.append(hotel_id)
        
    date_filter = ""
    date_params = []
    prev_date_filter = ""
    prev_date_params = []
    
    if start_date:
        date_filter = " AND b.created_at >= %s AND b.created_at <= %s "
        date_params = [start_date, end_date]
        prev_date_filter = " AND b.created_at >= %s AND b.created_at < %s "
        prev_date_params = [prev_start_date, prev_end_date]
        
    cursor.execute("SELECT COUNT(*) as total FROM hotels h WHERE h.is_deleted = 0" + hotel_filter, params)
    total_hotels = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as total FROM rooms r JOIN hotels h ON r.hotel_id = h.id WHERE r.is_deleted = 0 AND h.is_deleted = 0" + hotel_filter, params)
    total_rooms = cursor.fetchone()['total']
    
    b_join = " FROM bookings b JOIN rooms r ON b.room_id = r.id JOIN hotels h ON r.hotel_id = h.id WHERE r.is_deleted = 0 AND h.is_deleted = 0 "
    
    cursor.execute("SELECT IFNULL(SUM(r.price), 0) as revenue " + b_join + " AND b.status IN ('Booked', 'Checked In', 'Checked Out') " + hotel_filter, params)
    total_revenue_lifetime = float(cursor.fetchone()['revenue'])
    
    cursor.execute("SELECT IFNULL(SUM(r.price), 0) as revenue " + b_join + " AND b.status IN ('Booked', 'Checked In', 'Checked Out') " + hotel_filter + date_filter, params + date_params)
    period_revenue = float(cursor.fetchone()['revenue'])
    
    prev_revenue = 0
    if start_date:
        cursor.execute("SELECT IFNULL(SUM(r.price), 0) as revenue " + b_join + " AND b.status IN ('Booked', 'Checked In', 'Checked Out') " + hotel_filter + prev_date_filter, params + prev_date_params)
        prev_revenue = float(cursor.fetchone()['revenue'])
    
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    cursor.execute("SELECT COUNT(*) as total " + b_join + " AND b.created_at >= %s " + hotel_filter, [today_start] + params)
    todays_bookings = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as total " + b_join + hotel_filter + date_filter, params + date_params)
    period_bookings = cursor.fetchone()['total']
    
    prev_bookings = 0
    if start_date:
        cursor.execute("SELECT COUNT(*) as total " + b_join + hotel_filter + prev_date_filter, params + prev_date_params)
        prev_bookings = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(DISTINCT r.id) as occupied FROM rooms r JOIN bookings b ON r.id = b.room_id JOIN hotels h ON r.hotel_id = h.id WHERE b.status IN ('Booked', 'Checked In', 'Checked Out') AND DATE(b.created_at) = CURDATE() " + hotel_filter, params)
    occupied_rooms = cursor.fetchone()['occupied']
    
    available_rooms = max(0, total_rooms - occupied_rooms)
    occupancy_rate = round((occupied_rooms / total_rooms * 100) if total_rooms > 0 else 0)
    
    cursor.execute("SELECT IFNULL(AVG(r.price), 0) as avg_price FROM rooms r JOIN hotels h ON r.hotel_id = h.id WHERE r.is_deleted = 0 " + hotel_filter, params)
    avg_price = float(cursor.fetchone()['avg_price'])
    
    cursor.execute("SELECT DATE_FORMAT(b.created_at, '%b') as label, IFNULL(SUM(r.price), 0) as value " + b_join + " AND b.status IN ('Booked', 'Checked In', 'Checked Out') AND b.created_at >= DATE_SUB(NOW(), INTERVAL 6 MONTH) " + hotel_filter + " GROUP BY label ORDER BY MIN(b.created_at)", params)
    revenue_trend = cursor.fetchall()
    
    cursor.execute("SELECT DATE_FORMAT(b.created_at, '%b') as label, COUNT(*) as value " + b_join + " AND b.created_at >= DATE_SUB(NOW(), INTERVAL 6 MONTH) " + hotel_filter + " GROUP BY label ORDER BY MIN(b.created_at)", params)
    booking_trend = cursor.fetchall()
    
    room_status = [
        {'label': 'Available', 'value': available_rooms},
        {'label': 'Booked', 'value': occupied_rooms},
        {'label': 'Maintenance', 'value': 0}
    ]
    
    cursor.execute("SELECT h.name as label, COUNT(b.id) as value " + b_join + hotel_filter + date_filter + " GROUP BY h.id ORDER BY value DESC LIMIT 5", params + date_params)
    top_performing_hotels = cursor.fetchall()
    
    cursor.execute("SELECT r.room_type as label, COUNT(b.id) as value " + b_join + hotel_filter + date_filter + " GROUP BY r.room_type ORDER BY value DESC", params + date_params)
    room_types = cursor.fetchall()
    
    cursor.execute("SELECT b.guest_name, h.name as hotel, DATE_FORMAT(b.check_in, '%Y-%m-%d') as check_in, DATE_FORMAT(b.check_out, '%Y-%m-%d') as check_out, b.status " + b_join + hotel_filter + " ORDER BY b.created_at DESC LIMIT 5", params)
    recent_bookings = cursor.fetchall()
    
    top_hotel_name = top_performing_hotels[0]['label'] if top_performing_hotels else "No hotel ranking available yet."
    top_room_name = room_types[0]['label'] if room_types else "No room popularity data yet."
    
    insights = []
    if period_revenue > prev_revenue and prev_revenue > 0:
        pct = round((period_revenue - prev_revenue) / prev_revenue * 100)
        insights.append({'text': f"Revenue meningkat {pct}% dibanding periode sebelumnya.", 'status': 'up'})
    elif period_revenue < prev_revenue and prev_revenue > 0:
        pct = round((prev_revenue - period_revenue) / prev_revenue * 100)
        insights.append({'text': f"Revenue menurun {pct}% dibanding periode sebelumnya.", 'status': 'down'})
    elif period_revenue > 0:
        insights.append({'text': f"Revenue mencapai Rp {period_revenue:,.0f} periode ini.", 'status': 'up'})
        
    if todays_bookings > 0:
        insights.append({'text': f"{todays_bookings} booking berhasil dibuat hari ini.", 'status': 'up'})
    
    if occupancy_rate == 0:
        insights.append({'text': "Semua kamar masih tersedia (Tingkat hunian 0%).", 'status': 'neutral'})
    elif occupancy_rate >= 80:
        insights.append({'text': f"Hotel memiliki tingkat hunian tinggi ({occupancy_rate}%).", 'status': 'up'})
    else:
        insights.append({'text': f"Tingkat hunian berada pada {occupancy_rate}%.", 'status': 'neutral'})
        
    if not insights:
        insights.append({'text': "Belum ada cukup data untuk menghasilkan insight.", 'status': 'neutral'})
        
    def get_trend(curr, prev):
        if not start_date:
            return {'text': 'No comparison available', 'status': 'neutral'}
        if prev == 0 and curr > 0:
            return {'text': '100% increase', 'status': 'up'}
        if prev == 0 and curr == 0:
            return {'text': '0% change', 'status': 'neutral'}
        pct = round((curr - prev) / prev * 100, 1)
        if pct > 0:
            return {'text': f"+{pct}% from prev period", 'status': 'up'}
        elif pct < 0:
            return {'text': f"{pct}% from prev period", 'status': 'down'}
        else:
            return {'text': "0% change", 'status': 'neutral'}
    
    cursor.close()
    conn.close()
    
    return jsonify({
        'summary': {
            'total_hotels': total_hotels,
            'total_rooms': total_rooms,
            'available_rooms': available_rooms,
            'occupied_rooms': occupied_rooms,
            'occupancy_rate': occupancy_rate,
            'todays_bookings': todays_bookings,
            'period_bookings': period_bookings,
            'period_bookings_trend': get_trend(period_bookings, prev_bookings),
            'total_revenue': total_revenue_lifetime,
            'period_revenue': period_revenue,
            'period_revenue_trend': get_trend(period_revenue, prev_revenue),
            'avg_price': avg_price
        },
        'charts': {
            'revenue_trend': revenue_trend,
            'booking_trend': booking_trend,
            'room_status': room_status,
            'top_hotels': top_performing_hotels,
            'room_types': room_types
        },
        'panels': {
            'recent_bookings': recent_bookings,
            'top_hotel': top_hotel_name,
            'popular_room': top_room_name,
            'quick_insights': insights
        }
    })

@admin_bp.route('/api/notifications', methods=['GET'])
@admin_required
def api_get_notifications():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM notifications ORDER BY created_at DESC LIMIT 15")
    notifications = cursor.fetchall()
    
    cursor.execute("SELECT COUNT(*) as unread FROM notifications WHERE is_read = FALSE")
    unread_count = cursor.fetchone()['unread']
    
    cursor.close()
    conn.close()
    
    # format datetime for JSON response
    for notif in notifications:
        notif['created_at'] = notif['created_at'].strftime('%Y-%m-%d %H:%M:%S')
    
    return jsonify({
        'notifications': notifications,
        'unread_count': unread_count
    })

@admin_bp.route('/api/notifications/read/<int:notif_id>', methods=['POST'])
@admin_required
def api_read_notification(notif_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE notifications SET is_read = TRUE WHERE id = %s", (notif_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({'status': 'success'})

@admin_bp.route('/api/notifications/read_all', methods=['POST'])
@admin_required
def api_read_all_notifications():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE notifications SET is_read = TRUE WHERE is_read = FALSE")
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({'status': 'success'})

@admin_bp.route('/profile', methods=['GET'])
@admin_required
def profile():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    from flask import session
    cursor.execute("SELECT * FROM users WHERE id = %s", (session['user_id'],))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    return render_template('admin/profile.html', user=user)

@admin_bp.route('/profile/edit', methods=['POST'])
@admin_required
def profile_edit():
    full_name = request.form.get('full_name', '').strip()
    email = request.form.get('email', '').strip()
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    from flask import session
    
    file = request.files.get('photo')
    photo_url = None
    if file and file.filename != '':
        try:
            photo_url = save_file(file, current_app.config['USER_UPLOAD_FOLDER'], 'uploads/users')
            cursor.execute("SELECT photo_url FROM users WHERE id = %s", (session['user_id'],))
            old_photo = cursor.fetchone().get('photo_url')
            if old_photo:
                delete_image_file(old_photo, current_app.root_path)
        except Exception as e:
            flash(f"Error uploading photo: {e}", 'danger')
            cursor.close()
            conn.close()
            return redirect(url_for('admin.profile'))
            
    if photo_url:
        cursor.execute("UPDATE users SET full_name = %s, email = %s, photo_url = %s WHERE id = %s", 
                       (full_name, email, photo_url, session['user_id']))
    else:
        cursor.execute("UPDATE users SET full_name = %s, email = %s WHERE id = %s", 
                       (full_name, email, session['user_id']))
                       
    conn.commit()
    cursor.close()
    conn.close()
    
    flash("Profile updated successfully.", "success")
    return redirect(url_for('admin.profile'))

@admin_bp.route('/profile/password', methods=['POST'])
@admin_required
def profile_password():
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    if new_password != confirm_password:
        flash("New passwords do not match.", "danger")
        return redirect(url_for('admin.profile'))
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    from flask import session
    cursor.execute("SELECT password_hash FROM users WHERE id = %s", (session['user_id'],))
    user = cursor.fetchone()
    
    if user.get('password_hash'):
        if not current_password or not check_password_hash(user['password_hash'], current_password):
            flash("Incorrect current password.", "danger")
            cursor.close()
            conn.close()
            return redirect(url_for('admin.profile'))
            
    new_hash = generate_password_hash(new_password)
    cursor.execute("UPDATE users SET password_hash = %s WHERE id = %s", (new_hash, session['user_id']))
    conn.commit()
    cursor.close()
    conn.close()
    
    flash("Password updated successfully.", "success")
    return redirect(url_for('admin.profile'))

@admin_bp.route('/settings', methods=['GET'])
@admin_required
def settings():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    from flask import session
    cursor.execute("SELECT * FROM users WHERE id = %s", (session['user_id'],))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    return render_template('admin/settings.html', user=user)

@admin_bp.route('/settings/update', methods=['POST'])
@admin_required
def settings_update():
    theme = request.form.get('theme', 'light')
    language = request.form.get('language', 'en')
    notification_preference = request.form.get('notification_preference', 'all')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    from flask import session
    cursor.execute("""
        UPDATE users 
        SET theme = %s, language = %s, notification_preference = %s 
        WHERE id = %s
    """, (theme, language, notification_preference, session['user_id']))
    
    conn.commit()
    cursor.close()
    conn.close()
    
    flash("Settings updated successfully.", "success")
    return redirect(url_for('admin.settings'))


@admin_bp.route('/company-settings', methods=['GET', 'POST'])
@admin_required
def company_settings():
    from utils import get_company_settings
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        company_name = request.form.get('company_name', '').strip()
        tagline = request.form.get('tagline', '').strip()
        phone = request.form.get('phone', '').strip()
        whatsapp = request.form.get('whatsapp', '').strip()
        email = request.form.get('email', '').strip()
        website = request.form.get('website', '').strip()
        street_address = request.form.get('street_address', '').strip()
        city = request.form.get('city', '').strip()
        province = request.form.get('province', '').strip()
        postal_code = request.form.get('postal_code', '').strip()
        country = request.form.get('country', '').strip()
        business_hours = request.form.get('business_hours', '').strip()
        
        cursor.execute("SELECT id FROM company_settings LIMIT 1")
        row = cursor.fetchone()
        
        if row:
            cursor.execute("""
                UPDATE company_settings 
                SET company_name=%s, tagline=%s, phone=%s, whatsapp=%s, email=%s, website=%s, 
                    street_address=%s, city=%s, province=%s, postal_code=%s, country=%s, business_hours=%s
                WHERE id=%s
            """, (company_name, tagline, phone, whatsapp, email, website, street_address, city, province, postal_code, country, business_hours, row['id']))
        else:
            cursor.execute("""
                INSERT INTO company_settings (
                    company_name, tagline, phone, whatsapp, email, website, 
                    street_address, city, province, postal_code, country, business_hours
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (company_name, tagline, phone, whatsapp, email, website, street_address, city, province, postal_code, country, business_hours))
            
        conn.commit()
        add_notification(title="Pengaturan Diperbarui", description="Profil perusahaan berhasil diperbarui.", icon_type="settings")
        flash("Pengaturan perusahaan berhasil disimpan.", "success")
        log_admin(session['user_id'], 'Company', 'Update Company Settings', 'Updated company settings')
        return redirect(url_for('admin.company_settings'))
        
    settings = get_company_settings()
    cursor.close()
    conn.close()
    return render_template('admin/company_settings.html', active_page='settings', settings=settings)
