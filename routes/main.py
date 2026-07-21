from flask import Blueprint, render_template, request, flash, redirect, url_for
from datetime import datetime
from db import get_db_connection, cleanup_expired_bookings

main_bp = Blueprint('main', __name__)

def get_available_rooms(hotel_id, check_in, check_out, min_price=None, max_price=None, sort_by=None):
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
    params = [hotel_id, check_out, check_in, check_in, check_out]
    
    if min_price:
        query += " AND r.price >= %s"
        params.append(min_price)
    if max_price:
        query += " AND r.price <= %s"
        params.append(max_price)
        
    if sort_by == 'cheapest':
        query += " ORDER BY r.price ASC"
    elif sort_by == 'expensive':
        query += " ORDER BY r.price DESC"
        
    cursor.execute(query, tuple(params))
    rooms = cursor.fetchall()
    
    cursor.close()
    conn.close()
    return rooms

def get_booked_rooms(hotel_id, check_in, check_out):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    query = """
        SELECT r.* FROM rooms r
        WHERE r.hotel_id = %s AND r.id IN (
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
    check_in = request.args.get('check_in')
    check_out = request.args.get('check_out')
    
    if city_id:
        return redirect(url_for('main.city_hotels', city_id=city_id, check_in=check_in, check_out=check_out))
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    base_query = """
        SELECT h.*, c.city_name, p.province 
        FROM hotels h 
        LEFT JOIN cities c ON h.city_id = c.city_id 
        LEFT JOIN provinces p ON h.province_id = p.province_id
    """
    
    # 1. Rekomendasi (Top 14 Rating)
    cursor.execute(base_query + " ORDER BY h.rating DESC LIMIT 14")
    rekomendasi = cursor.fetchall()
    
    for hotel in rekomendasi:
        cursor.execute("SELECT image_url FROM hotel_images WHERE hotel_id = %s", (hotel['id'],))
        hotel['images'] = [img['image_url'] for img in cursor.fetchall()]
        cursor.execute("SELECT MIN(price) as min_price FROM rooms WHERE hotel_id = %s", (hotel['id'],))
        res = cursor.fetchone()
        hotel['min_price'] = res['min_price'] if res and res['min_price'] else 0
        
    # 2. Get cities that have hotels
    cursor.execute("""
        SELECT DISTINCT c.city_id, c.city_name, p.province 
        FROM hotels h 
        JOIN cities c ON h.city_id = c.city_id 
        JOIN provinces p ON h.province_id = p.province_id
        ORDER BY c.city_name
    """)
    available_cities = cursor.fetchall()
    
    city_groups = []
    for city in available_cities:
        cursor.execute(base_query + " WHERE h.city_id = %s LIMIT 14", (city['city_id'],))
        city_hotels = cursor.fetchall()
        for hotel in city_hotels:
            cursor.execute("SELECT image_url FROM hotel_images WHERE hotel_id = %s", (hotel['id'],))
            hotel['images'] = [img['image_url'] for img in cursor.fetchall()]
            cursor.execute("SELECT MIN(price) as min_price FROM rooms WHERE hotel_id = %s", (hotel['id'],))
            res = cursor.fetchone()
            hotel['min_price'] = res['min_price'] if res and res['min_price'] else 0
        
        city_groups.append({
            'city': city,
            'hotels': city_hotels
        })
        
    cursor.close()
    conn.close()
    return render_template('index.html', rekomendasi=rekomendasi, city_groups=city_groups, available_cities=available_cities)

@main_bp.route('/city/<int:city_id>')
def city_hotels(city_id):
    check_in = request.args.get('check_in')
    check_out = request.args.get('check_out')
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT c.city_name, p.province 
        FROM cities c 
        JOIN provinces p ON c.province_id = p.province_id 
        WHERE c.city_id = %s
    """, (city_id,))
    city_info = cursor.fetchone()
    
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
    
    if not city_info:
        return redirect(url_for('main.index'))
        
    return render_template('city_hotels.html', city=city_info, city_id=city_id, available_cities=available_cities, check_in=check_in, check_out=check_out)

from flask import jsonify

@main_bp.route('/api/hotels')
def api_hotels():
    city_id = request.args.get('city_id')
    page = request.args.get('page', 1, type=int)
    per_page = 14
    offset = (page - 1) * per_page
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    base_query = """
        SELECT h.*, c.city_name, p.province 
        FROM hotels h 
        LEFT JOIN cities c ON h.city_id = c.city_id 
        LEFT JOIN provinces p ON h.province_id = p.province_id
        WHERE h.city_id = %s
        LIMIT %s OFFSET %s
    """
    cursor.execute(base_query, (city_id, per_page, offset))
    hotels = cursor.fetchall()
    
    for hotel in hotels:
        cursor.execute("SELECT image_url FROM hotel_images WHERE hotel_id = %s", (hotel['id'],))
        hotel['images'] = [img['image_url'] for img in cursor.fetchall()]
        cursor.execute("SELECT MIN(price) as min_price FROM rooms WHERE hotel_id = %s", (hotel['id'],))
        res = cursor.fetchone()
        hotel['min_price'] = res['min_price'] if res and res['min_price'] else 0
        
    cursor.close()
    conn.close()
    
    return jsonify({'hotels': hotels})

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
    
    # Filter parameters
    min_price = request.args.get('min_price', type=int)
    max_price = request.args.get('max_price', type=int)
    sort_by = request.args.get('sort_by')

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

    # Get available and booked rooms separately to prevent price-filtered rooms from showing as booked
    available_rooms_raw = get_available_rooms(hotel_id, check_in, check_out, min_price, max_price, sort_by)
    booked_rooms_raw = get_booked_rooms(hotel_id, check_in, check_out)
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT h.*, c.city_name, p.province 
        FROM hotels h 
        LEFT JOIN cities c ON h.city_id = c.city_id 
        LEFT JOIN provinces p ON h.province_id = p.province_id
        WHERE h.id = %s
    """, (hotel_id,))
    hotel = cursor.fetchone()
    
    if hotel:
        cursor.execute("SELECT image_url FROM hotel_images WHERE hotel_id = %s", (hotel_id,))
        hotel['images'] = [img['image_url'] for img in cursor.fetchall()]
    
    # Function to attach images to room list
    def attach_images(room_list):
        for r in room_list:
            cursor.execute("SELECT image_url FROM room_images WHERE room_id = %s", (r['id'],))
            r['images'] = [img['image_url'] for img in cursor.fetchall()]
        return room_list

    rooms = attach_images(available_rooms_raw)
    booked_rooms = attach_images(booked_rooms_raw)
        
    cursor.close()
    conn.close()

    return render_template('rooms.html', hotel=hotel, available_rooms=rooms, booked_rooms=booked_rooms, 
                           check_in=check_in, check_out=check_out, 
                           min_price=min_price if min_price else '', 
                           max_price=max_price if max_price else '', 
                           sort_by=sort_by)
