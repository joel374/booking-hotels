from flask import Blueprint, render_template, request, flash, redirect, url_for
from datetime import datetime
from db import get_db_connection, cleanup_expired_bookings

main_bp = Blueprint('main', __name__)

def get_available_rooms(hotel_id, check_in, check_out):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cleanup_expired_bookings(cursor)
    conn.commit()
    
    query = """
        SELECT r.* FROM rooms r
        WHERE r.hotel_id = %s AND r.id NOT IN (
            SELECT b.room_id FROM bookings b
            WHERE b.status IN ('Booked', 'Pending') 
            AND (
                (b.check_in <= %s AND b.check_out >= %s) OR
                (b.check_in >= %s AND b.check_in < %s)
            )
        )
    """
    cursor.execute(query, (hotel_id, check_out, check_in, check_in, check_out))
    rooms = cursor.fetchall()
    cursor.close()
    conn.close()
    return rooms

@main_bp.route('/')
def index():
    city_id = request.args.get('city_id')
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if city_id:
        cursor.execute("SELECT * FROM hotels WHERE city_id = %s", (city_id,))
    else:
        cursor.execute("SELECT * FROM hotels")
    hotels = cursor.fetchall()
    
    for hotel in hotels:
        cursor.execute("SELECT image_url FROM hotel_images WHERE hotel_id = %s", (hotel['id'],))
        hotel['images'] = [img['image_url'] for img in cursor.fetchall()]
    
    cursor.execute("""
        SELECT DISTINCT c.city_id, c.city_name, p.province 
        FROM hotels h 
        JOIN cities c ON h.city_id = c.city_id 
        JOIN provinces p ON h.province_id = p.province_id
        ORDER BY c.city_name
    """)
    available_cities = cursor.fetchall()
    
    cursor.close()
    conn.close()
    return render_template('index.html', hotels=hotels, available_cities=available_cities, selected_city=city_id)

@main_bp.route('/about')
def about():
    return render_template('about.html')

@main_bp.route('/contact')
def contact():
    return render_template('contact.html')

@main_bp.route('/contact/submit', methods=['POST'])
def contact_submit():
    flash("Terima kasih! Pesan Anda telah kami terima dan akan segera kami balas.", "success")
    return redirect(url_for('main.contact'))

@main_bp.route('/hotel/<int:hotel_id>')
def hotel_rooms(hotel_id):
    check_in = request.args.get('check_in')
    check_out = request.args.get('check_out')

    if not check_in or not check_out:
        flash("Please select check-in and check-out dates.", "warning")
        return redirect(url_for('main.index'))

    try:
        ci_date = datetime.strptime(check_in, '%Y-%m-%d')
        co_date = datetime.strptime(check_out, '%Y-%m-%d')
        if ci_date >= co_date:
            flash("Check-out date must be after check-in date.", "danger")
            return redirect(url_for('main.index'))
        if ci_date.date() < datetime.now().date():
            flash("Check-in date cannot be in the past.", "danger")
            return redirect(url_for('main.index'))
    except ValueError:
        flash("Invalid date format.", "danger")
        return redirect(url_for('main.index'))

    rooms = get_available_rooms(hotel_id, check_in, check_out)
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM hotels WHERE id = %s", (hotel_id,))
    hotel = cursor.fetchone()
    
    if hotel:
        cursor.execute("SELECT image_url FROM hotel_images WHERE hotel_id = %s", (hotel_id,))
        hotel['images'] = [img['image_url'] for img in cursor.fetchall()]
    
    cursor.execute("SELECT * FROM rooms WHERE hotel_id = %s", (hotel_id,))
    all_rooms = cursor.fetchall()
    
    for r in all_rooms:
        cursor.execute("SELECT image_url FROM room_images WHERE room_id = %s", (r['id'],))
        r['images'] = [img['image_url'] for img in cursor.fetchall()]
        
    cursor.close()
    conn.close()

    available_room_ids = [r['id'] for r in rooms]
    # Update rooms list with the image data from all_rooms
    rooms = [r for r in all_rooms if r['id'] in available_room_ids]
    booked_rooms = [r for r in all_rooms if r['id'] not in available_room_ids]

    return render_template('rooms.html', hotel=hotel, available_rooms=rooms, booked_rooms=booked_rooms, check_in=check_in, check_out=check_out)
