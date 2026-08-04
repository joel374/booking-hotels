from utils import get_company_settings
from flask import Blueprint, render_template, request, flash, redirect, url_for, session
from datetime import datetime, timedelta
from db import get_db_connection, cleanup_expired_bookings

main_bp = Blueprint('main', __name__)

def get_available_rooms(hotel_id, check_in, check_out, min_price=None, max_price=None, sort_by=None):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cleanup_expired_bookings(cursor)
    conn.commit()

    query = """
        SELECT r.room_type, r.price, r.capacity, MIN(r.room_number) as start_number,
               SUM(CASE WHEN r.id NOT IN (
                   SELECT b.room_id FROM bookings b
                   WHERE b.status IN ('Booked', 'Checked In')
                   AND (b.check_in < %s AND b.check_out > %s)
               ) THEN 1 ELSE 0 END) as quantity
        FROM rooms r
        WHERE r.hotel_id = %s AND r.is_deleted = 0
    """
    params = [check_out, check_in, hotel_id]

    if min_price:
        query += " AND r.price >= %s"
        params.append(min_price)
    if max_price:
        query += " AND r.price <= %s"
        params.append(max_price)

    query += " GROUP BY r.room_type, r.price, r.capacity"

    if sort_by == 'cheapest':
        query += " ORDER BY r.price ASC"
    elif sort_by == 'expensive':
        query += " ORDER BY r.price DESC"

    cursor.execute(query, tuple(params))
    rooms = cursor.fetchall()
    
    for group in rooms:
        cursor.execute("""
            SELECT MIN(i.id) as id, i.image_url
            FROM rooms r
            JOIN room_images i ON r.id = i.room_id
            WHERE r.hotel_id = %s AND r.room_type = %s AND r.is_deleted = 0 AND i.image_url IS NOT NULL
            GROUP BY i.image_url
            ORDER BY MIN(i.id) ASC
        """, (hotel_id, group['room_type']))
        imgs = cursor.fetchall()
        group['images'] = imgs
        
        if imgs:
            group['image_url'] = imgs[0]['image_url']
        else:
            group['image_url'] = None

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
    cursor.execute(base_query + " WHERE h.is_deleted = 0 ORDER BY h.rating DESC LIMIT 14")
    rekomendasi = cursor.fetchall()
    
    for hotel in rekomendasi:
        cursor.execute("SELECT image_url FROM hotel_images WHERE hotel_id = %s", (hotel['id'],))
        hotel['images'] = [img['image_url'] for img in cursor.fetchall()]
        cursor.execute("SELECT MIN(price) as min_price FROM rooms WHERE hotel_id = %s AND is_deleted = 0", (hotel['id'],))
        res = cursor.fetchone()
        hotel['min_price'] = res['min_price'] if res and res['min_price'] else 0
        
    # 2. Get cities that have hotels
    cursor.execute("""
        SELECT DISTINCT c.city_id, c.city_name, p.province 
        FROM hotels h 
        JOIN cities c ON h.city_id = c.city_id 
        JOIN provinces p ON h.province_id = p.province_id
        WHERE h.is_deleted = 0
        ORDER BY c.city_name
    """)
    available_cities = cursor.fetchall()
    
    city_groups = []
    for city in available_cities:
        cursor.execute(base_query + " WHERE h.is_deleted = 0 AND h.city_id = %s LIMIT 14", (city['city_id'],))
        city_hotels = cursor.fetchall()
        for hotel in city_hotels:
            cursor.execute("SELECT image_url FROM hotel_images WHERE hotel_id = %s", (hotel['id'],))
            hotel['images'] = [img['image_url'] for img in cursor.fetchall()]
            cursor.execute("SELECT MIN(price) as min_price FROM rooms WHERE hotel_id = %s AND is_deleted = 0", (hotel['id'],))
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
        WHERE h.is_deleted = 0
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
    min_price = request.args.get('min_price', type=int)
    max_price = request.args.get('max_price', type=int)
    sort_by = request.args.get('sort_by')
    
    per_page = 14
    # Cegah OFFSET negatif (?page=0 atau page negatif) yang membuat MySQL error
    if not page or page < 1:
        page = 1
    offset = (page - 1) * per_page
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    base_query = """
        SELECT h.*, c.city_name, p.province, (SELECT MIN(price) FROM rooms WHERE hotel_id = h.id AND is_deleted = 0) as min_price
        FROM hotels h 
        LEFT JOIN cities c ON h.city_id = c.city_id 
        LEFT JOIN provinces p ON h.province_id = p.province_id
        WHERE h.city_id = %s AND h.is_deleted = 0
        HAVING 1=1
    """
    params = [city_id]
    
    if min_price:
        base_query += " AND min_price >= %s"
        params.append(min_price)
    if max_price:
        base_query += " AND min_price <= %s"
        params.append(max_price)
        
    if sort_by == 'cheapest':
        base_query += " ORDER BY min_price ASC"
    elif sort_by == 'expensive':
        base_query += " ORDER BY min_price DESC"
    else:
        # Default sort by rating if available, or just ID
        base_query += " ORDER BY h.rating DESC"
        
    base_query += " LIMIT %s OFFSET %s"
    params.extend([per_page, offset])
    
    cursor.execute(base_query, tuple(params))
    hotels = cursor.fetchall()
    
    for hotel in hotels:
        cursor.execute("SELECT image_url FROM hotel_images WHERE hotel_id = %s", (hotel['id'],))
        hotel['images'] = [img['image_url'] for img in cursor.fetchall()]
        if not hotel.get('min_price'):
            hotel['min_price'] = 0
        
    cursor.close()
    conn.close()
    
    return jsonify({'hotels': hotels})

@main_bp.route('/api/search')
def live_search():
    query = request.args.get('q', '').strip()
    if len(query) < 4:
        return jsonify({'hotels': [], 'cities': []})
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Search Hotels
    cursor.execute("""
        SELECT h.id, h.name, c.city_name, p.province 
        FROM hotels h
        LEFT JOIN cities c ON h.city_id = c.city_id
        LEFT JOIN provinces p ON h.province_id = p.province_id
        WHERE h.name LIKE %s AND h.is_deleted = 0
        LIMIT 5
    """, (f'%{query}%',))
    hotels = cursor.fetchall()
    
    # Search Cities
    cursor.execute("""
        SELECT c.city_id, c.city_name, p.province 
        FROM cities c
        JOIN provinces p ON c.province_id = p.province_id
        WHERE c.city_name LIKE %s
        AND EXISTS (SELECT 1 FROM hotels h WHERE h.city_id = c.city_id AND h.is_deleted = 0)
        LIMIT 5
    """, (f'%{query}%',))
    cities = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return jsonify({
        'hotels': hotels,
        'cities': cities
    })

@main_bp.route('/about')
def about():
    return render_template('about.html')

@main_bp.route('/contact')
def contact():
    return render_template('contact.html', settings=get_company_settings())

@main_bp.route('/contact/submit', methods=['POST'])
def contact_submit():
    name = request.form.get('name')
    email = request.form.get('email')
    message = request.form.get('message')
    
    settings = get_company_settings()
    company_email = settings.get('email')
    
    if company_email:
        try:
            from services.email_service import send_email
            html_content = f"""
            <h3>Pesan Baru dari {name}</h3>
            <p><strong>Email Pengirim:</strong> {email}</p>
            <p><strong>Pesan:</strong><br/>{message}</p>
            """
            send_email(company_email, f"Kontak Form: Pesan dari {name}", html_content)
        except Exception as e:
            print(f"Error sending contact email: {e}")
            
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
        check_in = datetime.now().strftime('%Y-%m-%d')
        check_out = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')

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

    available_rooms = get_available_rooms(hotel_id, check_in, check_out, min_price, max_price, sort_by)
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT h.*, c.city_name, p.province 
        FROM hotels h 
        LEFT JOIN cities c ON h.city_id = c.city_id 
        LEFT JOIN provinces p ON h.province_id = p.province_id
        WHERE h.id = %s AND h.is_deleted = 0
    """, (hotel_id,))
    hotel = cursor.fetchone()

    # Hotel yang sudah di-soft-delete tetap memiliki baris rooms dengan is_deleted = 0,
    # sehingga available_rooms bisa terisi walau hotel-nya None. Tanpa guard ini,
    # pemanggilan hotel.get('images') di bawah melempar AttributeError (HTTP 500).
    if not hotel:
        cursor.close()
        conn.close()
        flash("Hotel tidak ditemukan atau sudah tidak tersedia.", "warning")
        return redirect(url_for('main.index'))

    if hotel:
        cursor.execute("SELECT image_url FROM hotel_images WHERE hotel_id = %s", (hotel_id,))
        hotel['images'] = [img['image_url'] for img in cursor.fetchall()]
        
        cursor.execute("SELECT MIN(price) as min_price FROM rooms WHERE hotel_id = %s AND is_deleted = 0", (hotel_id,))
        res = cursor.fetchone()
        hotel['min_price'] = res['min_price'] if res and res['min_price'] else 0
        
        cursor.execute("""
            SELECT r.*, u.username as user_name 
            FROM reviews r 
            JOIN users u ON r.user_id = u.id 
            WHERE r.hotel_id = %s 
            ORDER BY r.created_at DESC
        """, (hotel_id,))
        reviews = cursor.fetchall()
        
        if reviews:
            hotel['average_rating'] = round(sum(r['rating'] for r in reviews) / len(reviews), 1)
            hotel['review_count'] = len(reviews)
        else:
            hotel['average_rating'] = hotel['rating']
            hotel['review_count'] = 0
    else:
        reviews = []
    
    # Set fallback images
    for r in available_rooms:
        if not r['image_url']:
            r['image_url'] = hotel['images'][0] if hotel.get('images') else None

    cursor.close()
    conn.close()

    return render_template('rooms.html', hotel=hotel, available_rooms=available_rooms, booked_rooms=[], 
                           check_in=check_in, check_out=check_out, 
                           min_price=min_price if min_price else '', 
                           max_price=max_price if max_price else '', 
                           sort_by=sort_by,
                           reviews=reviews)

from extensions import csrf

@main_bp.route('/api/set-theme', methods=['POST'])
@csrf.exempt
def set_theme():
    data = request.get_json(silent=True) or {}
    theme = data.get('theme', 'light')
    session['theme'] = theme
    if 'user_id' in session:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET theme = %s WHERE id = %s", (theme, session['user_id']))
        conn.commit()
        cursor.close()
        conn.close()
    return {"status": "success", "theme": theme}

@main_bp.route('/api/set-language', methods=['POST'])
@csrf.exempt
def set_language():
    data = request.get_json(silent=True) or {}
    language = data.get('language', 'id')
    session['language'] = language
    if 'user_id' in session:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET language = %s WHERE id = %s", (language, session['user_id']))
        conn.commit()
        cursor.close()
        conn.close()
    return {"status": "success", "language": language}

@main_bp.route('/api/reviews/<int:hotel_id>')
def api_reviews(hotel_id):
    page = request.args.get('page', 1, type=int)
    per_page = 5
    # Cegah OFFSET negatif (?page=0 atau page negatif) yang membuat MySQL error
    if not page or page < 1:
        page = 1
    offset = (page - 1) * per_page
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT r.*, u.username as user_name 
        FROM reviews r 
        JOIN users u ON r.user_id = u.id 
        WHERE r.hotel_id = %s 
        ORDER BY r.created_at DESC
        LIMIT %s OFFSET %s
    """, (hotel_id, per_page, offset))
    reviews = cursor.fetchall()
    
    # Convert dates to string for JSON serialization
    for r in reviews:
        if r.get('created_at'):
            r['created_at_str'] = r['created_at'].strftime('%d %b %Y')
            del r['created_at'] # Remove datetime object
            
    cursor.close()
    conn.close()
    
    return jsonify({'reviews': reviews})
