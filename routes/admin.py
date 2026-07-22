import os
from decimal import Decimal
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app, jsonify
from db import get_db_connection
from utils import admin_required, delete_image_file, save_file

import io
import datetime
import smtplib
from email.message import EmailMessage
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
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

    duplicate_query = 'SELECT id FROM rooms WHERE hotel_id = %s AND room_number = %s'
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
        
        cursor.execute("INSERT INTO hotels (name, location, province_id, city_id, description) VALUES (%s, %s, %s, %s, %s)",
                      (name, location, province_id, city_id, description))
        hotel_id = cursor.lastrowid
        
        files = request.files.getlist('images')
        saved_image_urls = []
        try:
            for file in files:
                if file and file.filename != '':
                    image_url = save_file(file, current_app.config['HOTEL_UPLOAD_FOLDER'], 'uploads/hotels')
                    saved_image_urls.append(image_url)
                    cursor.execute("INSERT INTO hotel_images (hotel_id, image_url) VALUES (%s, %s)", (hotel_id, image_url))
        except ValueError as e:
            for image_url in saved_image_urls:
                delete_image_file(image_url, current_app.root_path)
            conn.rollback()
            cursor.close()
            conn.close()
            flash(str(e), 'danger')
            return redirect(url_for('admin.hotels'))

        conn.commit()
        flash("Hotel added successfully!", "success")
        return redirect(url_for('admin.hotels'))
        
    cursor.execute("SELECT h.*, p.province, c.city_name FROM hotels h LEFT JOIN provinces p ON h.province_id = p.province_id LEFT JOIN cities c ON h.city_id = c.city_id")
    hotel_list = cursor.fetchall()
    hotel_ids = [hotel['id'] for hotel in hotel_list]
    images_by_hotel = fetch_images_by_parent(cursor, 'hotel_images', 'hotel_id', hotel_ids)

    for hotel in hotel_list:
        hotel['images'] = images_by_hotel.get(hotel['id'], [])
    
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
            for file in files:
                if file and file.filename != '':
                    image_url = save_file(file, current_app.config['HOTEL_UPLOAD_FOLDER'], 'uploads/hotels')
                    saved_image_urls.append(image_url)
                    cursor.execute("INSERT INTO hotel_images (hotel_id, image_url) VALUES (%s, %s)", (id, image_url))
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
    return redirect(url_for('admin.hotels'))

@admin_bp.route('/hotel/delete/<int:id>', methods=['POST'])
@admin_required
def delete_hotel(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT ri.image_url FROM room_images ri JOIN rooms r ON ri.room_id = r.id WHERE r.hotel_id = %s", (id,))
    room_images = cursor.fetchall()
    for img in room_images:
        delete_image_file(img['image_url'], current_app.root_path)

    cursor.execute("SELECT image_url FROM hotel_images WHERE hotel_id = %s", (id,))
    hotel_images = cursor.fetchall()
    for img in hotel_images:
        delete_image_file(img['image_url'], current_app.root_path)

    cursor.execute("DELETE FROM hotels WHERE id = %s", (id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash('Hotel and related data deleted successfully.', 'success')
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
        flash("Room added successfully!", "success")
        return redirect(url_for('admin.rooms'))
        
    cursor.execute("SELECT r.*, h.name as hotel_name FROM rooms r JOIN hotels h ON r.hotel_id = h.id")
    room_list = cursor.fetchall()
    room_ids = [room['id'] for room in room_list]
    images_by_room = fetch_images_by_parent(cursor, 'room_images', 'room_id', room_ids)
    
    for room in room_list:
        room['images'] = images_by_room.get(room['id'], [])
    
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

    cursor.execute("SELECT image_url FROM room_images WHERE room_id = %s", (id,))
    room_images = cursor.fetchall()
    for img in room_images:
        delete_image_file(img['image_url'], current_app.root_path)

    cursor.execute("DELETE FROM rooms WHERE id = %s", (id,))
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


@admin_bp.route('/reports', methods=['GET'])
@admin_required
def reports():
    return render_template('admin/reports.html')


def get_report_data(report_type, period):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    now = datetime.datetime.now()
    start_date = None
    end_date = now
    
    if period == 'Today':
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == 'This Week':
        start_date = now - datetime.timedelta(days=now.weekday())
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == 'This Month':
        start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif period == 'This Year':
        start_date = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        
    cursor.execute("SELECT COUNT(*) as total FROM hotels")
    total_hotels = cursor.fetchone()['total']
    cursor.execute("SELECT COUNT(*) as total FROM rooms")
    total_rooms = cursor.fetchone()['total']
    cursor.execute("SELECT COUNT(*) as total FROM bookings")
    total_bookings = cursor.fetchone()['total']
    cursor.execute("SELECT IFNULL(SUM(r.price), 0) as revenue FROM bookings b JOIN rooms r ON b.room_id = r.id WHERE b.status = 'Booked'")
    total_revenue = float(cursor.fetchone()['revenue'])
    
    summary = {
        'total_hotels': total_hotels,
        'total_rooms': total_rooms,
        'total_bookings': total_bookings,
        'total_revenue': total_revenue
    }
    
    details = []
    if report_type == 'Hotels':
        query = """
            SELECT h.name as hotel, CONCAT(IFNULL(c.city_name, ''), ', ', IFNULL(p.province, '')) as location,
                   (SELECT COUNT(*) FROM rooms r WHERE r.hotel_id = h.id) as rooms,
                   'Active' as status
            FROM hotels h
            LEFT JOIN cities c ON h.city_id = c.city_id
            LEFT JOIN provinces p ON h.province_id = p.province_id
        """
        cursor.execute(query)
        details = cursor.fetchall()
    elif report_type == 'Rooms':
        query = """
            SELECT r.room_type as room, h.name as hotel, r.room_number, r.price, 'Available' as status
            FROM rooms r
            JOIN hotels h ON r.hotel_id = h.id
        """
        cursor.execute(query)
        details = cursor.fetchall()
        for d in details:
            d['price'] = float(d['price'])
    elif report_type == 'Bookings':
        query = """
            SELECT b.id as booking_id, b.guest_name as guest, h.name as hotel, 
                   b.created_at as date, b.status
            FROM bookings b
            JOIN rooms r ON b.room_id = r.id
            JOIN hotels h ON r.hotel_id = h.id
        """
        params = []
        if start_date:
            query += " WHERE b.created_at >= %s AND b.created_at <= %s"
            params = [start_date, end_date]
        query += " ORDER BY b.created_at DESC"
            
        cursor.execute(query, params)
        details = cursor.fetchall()
        for d in details:
            d['date'] = d['date'].strftime('%Y-%m-%d')
            
    cursor.close()
    conn.close()
    return summary, details


@admin_bp.route('/api/reports/preview', methods=['POST'])
@admin_required
def api_reports_preview():
    data = request.json
    report_type = data.get('type', 'Dashboard Summary')
    period = data.get('period', 'This Month')
    
    summary, details = get_report_data(report_type, period)
    return jsonify({
        'summary': summary,
        'details': details
    })


def generate_pdf_bytes(report_type, period, summary, details):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    
    # Header
    elements.append(Paragraph("ANTIGRAVITY HOTELS", styles['Title']))
    elements.append(Paragraph("Property Management System", styles['Normal']))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"Report Type: {report_type}", styles['Heading2']))
    elements.append(Paragraph(f"Selected Period: {period}", styles['Normal']))
    elements.append(Paragraph(f"Generated Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
    elements.append(Spacer(1, 24))
    
    # Summary
    elements.append(Paragraph("Summary", styles['Heading3']))
    summary_data = [
        ['Total Hotels', 'Total Rooms', 'Total Bookings', 'Total Revenue'],
        [str(summary['total_hotels']), str(summary['total_rooms']), str(summary['total_bookings']), f"Rp {summary['total_revenue']:,.0f}".replace(',', '.')]
    ]
    t = Table(summary_data)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F8FAFC')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor('#0F172A')),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 12),
        ('GRID', (0,0), (-1,-1), 1, colors.black)
    ]))
    elements.append(t)
    elements.append(Spacer(1, 24))
    
    # Details Table
    if report_type != 'Dashboard Summary' and details:
        elements.append(Paragraph(f"{report_type} Details", styles['Heading3']))
        
        if report_type == 'Hotels':
            headers = ['Hotel', 'Location', 'Rooms', 'Status']
            table_data = [headers]
            for row in details:
                table_data.append([row['hotel'], row['location'], str(row['rooms']), row['status']])
        elif report_type == 'Rooms':
            headers = ['Room', 'Hotel', 'Room Number', 'Price', 'Status']
            table_data = [headers]
            for row in details:
                table_data.append([row['room'], row['hotel'], row['room_number'], f"Rp {row['price']:,.0f}".replace(',', '.'), row['status']])
        elif report_type == 'Bookings':
            headers = ['Booking ID', 'Guest', 'Hotel', 'Date', 'Status']
            table_data = [headers]
            for row in details:
                table_data.append([str(row['booking_id']), row['guest'], row['hotel'], row['date'], row['status']])
                
        t_details = Table(table_data)
        t_details.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F8FAFC')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor('#0F172A')),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0,0), (-1,0), 12),
            ('GRID', (0,0), (-1,-1), 1, colors.black)
        ]))
        elements.append(t_details)
        
    elements.append(Spacer(1, 48))
    elements.append(Paragraph("Generated by Antigravity Hotels", styles['Italic']))
    
    doc.build(elements)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


@admin_bp.route('/api/reports/download_pdf', methods=['POST'])
@admin_required
def api_reports_download_pdf():
    report_type = request.form.get('type', 'Dashboard Summary')
    period = request.form.get('period', 'This Month')
    
    summary, details = get_report_data(report_type, period)
    pdf_bytes = generate_pdf_bytes(report_type, period, summary, details)
    
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
    email = data.get('email')
    subject = data.get('subject', 'Antigravity Hotels Report')
    message_body = data.get('message', '')
    
    if not email:
        return jsonify({'error': 'Recipient email is required.'}), 400
        
    summary, details = get_report_data(report_type, period)
    pdf_bytes = generate_pdf_bytes(report_type, period, summary, details)
    
    try:
        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = os.getenv('MAIL_USERNAME', 'no-reply@antigravityhotels.com')
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
            
        return jsonify({'success': True, 'message': 'Email sent successfully.'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

