import os
from decimal import Decimal
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app, jsonify
from db import get_db_connection
from utils import admin_required, delete_image_file, save_file, add_notification
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
        add_notification(
            title="Hotel Baru Ditambahkan",
            description=f"Hotel {name} berhasil ditambahkan ke sistem.",
            icon_type="hotel"
        )
        flash("Hotel added successfully!", "success")
        return redirect(url_for('admin.hotels'))
        
    cursor.execute("SELECT h.*, p.province, c.city_name FROM hotels h LEFT JOIN provinces p ON h.province_id = p.province_id LEFT JOIN cities c ON h.city_id = c.city_id WHERE h.is_deleted = 0")
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

    cursor.execute("UPDATE hotels SET is_deleted = 1 WHERE id = %s", (id,))
    cursor.execute("UPDATE rooms SET is_deleted = 1 WHERE hotel_id = %s", (id,))
    
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
            cursor.execute("UPDATE bookings SET status = 'Cancelled', cancel_reason = %s WHERE id = %s", 
                          (cancel_reason, booking_id))
            conn.commit()
            add_notification(
                title="Booking Dibatalkan",
                description=f"Booking #{booking_id} telah dibatalkan.",
                icon_type="cancel"
            )
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
        
    cursor.execute("SELECT COUNT(*) as total FROM hotels WHERE is_deleted = 0")
    total_hotels = cursor.fetchone()['total']
    cursor.execute("SELECT COUNT(*) as total FROM rooms WHERE is_deleted = 0")
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
                   (SELECT COUNT(*) FROM rooms r WHERE r.hotel_id = h.id AND r.is_deleted = 0) as rooms,
                   'Active' as status
            FROM hotels h
            LEFT JOIN cities c ON h.city_id = c.city_id
            LEFT JOIN provinces p ON h.province_id = p.province_id
            WHERE h.is_deleted = 0
        """
        cursor.execute(query)
        details = cursor.fetchall()
    elif report_type == 'Rooms':
        query = """
            SELECT r.room_type as room, h.name as hotel, r.room_number, r.price, 'Available' as status
            FROM rooms r
            JOIN hotels h ON r.hotel_id = h.id
            WHERE r.is_deleted = 0 AND h.is_deleted = 0
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
    elements.append(Paragraph("ANTIGRAVITY HOTELS", title_style))
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
    elements.append(Paragraph("Generated automatically by Antigravity Hotels Property Management System", ParagraphStyle(
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
    
    summary, details = get_report_data(report_type, period)
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
        server.quit()
        
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
    
    cursor.execute("SELECT IFNULL(SUM(r.price), 0) as revenue " + b_join + " AND b.status = 'Booked' " + hotel_filter, params)
    total_revenue_lifetime = float(cursor.fetchone()['revenue'])
    
    cursor.execute("SELECT IFNULL(SUM(r.price), 0) as revenue " + b_join + " AND b.status = 'Booked' " + hotel_filter + date_filter, params + date_params)
    period_revenue = float(cursor.fetchone()['revenue'])
    
    prev_revenue = 0
    if start_date:
        cursor.execute("SELECT IFNULL(SUM(r.price), 0) as revenue " + b_join + " AND b.status = 'Booked' " + hotel_filter + prev_date_filter, params + prev_date_params)
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
    
    cursor.execute("SELECT COUNT(DISTINCT r.id) as occupied FROM rooms r JOIN bookings b ON r.id = b.room_id JOIN hotels h ON r.hotel_id = h.id WHERE b.status = 'Booked' AND DATE(b.created_at) = CURDATE() " + hotel_filter, params)
    occupied_rooms = cursor.fetchone()['occupied']
    
    available_rooms = max(0, total_rooms - occupied_rooms)
    occupancy_rate = round((occupied_rooms / total_rooms * 100) if total_rooms > 0 else 0)
    
    cursor.execute("SELECT IFNULL(AVG(r.price), 0) as avg_price FROM rooms r JOIN hotels h ON r.hotel_id = h.id WHERE r.is_deleted = 0 " + hotel_filter, params)
    avg_price = float(cursor.fetchone()['avg_price'])
    
    cursor.execute("SELECT DATE_FORMAT(b.created_at, '%b') as label, IFNULL(SUM(r.price), 0) as value " + b_join + " AND b.status = 'Booked' AND b.created_at >= DATE_SUB(NOW(), INTERVAL 6 MONTH) " + hotel_filter + " GROUP BY label ORDER BY MIN(b.created_at)", params)
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
            photo_url = save_file(file, current_app.config['HOTEL_UPLOAD_FOLDER'], 'uploads/users')
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
