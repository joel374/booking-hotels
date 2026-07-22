from flask import Blueprint, render_template, request, flash, redirect, url_for, session
from datetime import datetime, timedelta
import mysql.connector
from db import get_db_connection, cleanup_expired_bookings

booking_bp = Blueprint('booking', __name__)

@booking_bp.route('/book/<int:room_id>', methods=['GET', 'POST'])
def book_room(room_id):
    if 'user_id' not in session:
        flash("Please login to book a room.", "warning")
        return redirect(url_for('auth.login'))

    check_in = request.args.get('check_in')
    check_out = request.args.get('check_out')

    if not check_in or not check_out:
        return redirect(url_for('main.index'))
        
    try:
        ci_date = datetime.strptime(check_in, '%Y-%m-%d').date()
        co_date = datetime.strptime(check_out, '%Y-%m-%d').date()
        today = datetime.now().date()
        
        if ci_date < today:
            flash("Tanggal check-in tidak boleh di masa lalu.", "danger")
            return redirect(url_for('main.index'))
            
        if co_date <= ci_date:
            flash("Tanggal check-out harus setelah check-in.", "danger")
            return redirect(url_for('main.index'))
    except ValueError:
        flash("Format tanggal tidak valid.", "danger")
        return redirect(url_for('main.index'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT * FROM rooms r JOIN hotels h ON r.hotel_id = h.id WHERE r.id = %s", (room_id,))
    room = cursor.fetchone()

    if request.method == 'POST':
        guest_name = request.form.get('guest_name', '').strip()
        contact_number = request.form.get('contact_number', '').strip()
        payment_method = request.form.get('payment_method', '').strip()
        
        if not guest_name or not contact_number or not payment_method:
            flash("Semua data pemesanan wajib diisi.", "danger")
            return render_template('booking_form.html', room=room, check_in=check_in, check_out=check_out)
            
        if len(guest_name) < 3:
            flash("Nama lengkap tamu minimal 3 karakter.", "danger")
            return render_template('booking_form.html', room=room, check_in=check_in, check_out=check_out)
            
        import re
        if not re.match(r'^[\d\+\-\(\)\s]{9,15}$', contact_number):
            flash("Nomor kontak tidak valid. Harap masukkan 9-15 digit angka.", "danger")
            return render_template('booking_form.html', room=room, check_in=check_in, check_out=check_out)

        cleanup_expired_bookings(cursor)
        
        # LOCK THE ROOM ROW to prevent race conditions (Double Booking)
        cursor.execute("SELECT id FROM rooms WHERE id = %s FOR UPDATE", (room_id,))
        cursor.fetchone() # Clear the unread result from the buffer
        
        query = """
            SELECT COUNT(*) as count FROM bookings 
            WHERE room_id = %s AND status IN ('Booked', 'Pending')
            AND (check_in < %s AND check_out > %s)
        """
        cursor.execute(query, (room_id, check_out, check_in))
        result = cursor.fetchone()
        
        if result['count'] > 0:
            flash("Sorry, this room just got booked or locked by someone else.", "danger")
            return redirect(url_for('main.index'))

        insert_query = """
            INSERT INTO bookings (user_id, room_id, guest_name, contact_number, check_in, check_out, payment_method, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'Pending')
        """
        cursor.execute(insert_query, (session['user_id'], room_id, guest_name, contact_number, check_in, check_out, payment_method))
        conn.commit()
        booking_id = cursor.lastrowid
        
        # Kirim Email Pending
        cursor.execute("""
            SELECT b.*, r.room_number, r.room_type, r.price, h.name as hotel_name, u.email as user_email
            FROM bookings b 
            JOIN rooms r ON b.room_id = r.id 
            JOIN hotels h ON r.hotel_id = h.id 
            JOIN users u ON b.user_id = u.id
            WHERE b.id = %s
        """, (booking_id,))
        booking_data = cursor.fetchone()
        
        if booking_data and booking_data.get('user_email'):
            from services.email_service import send_email
            from flask import render_template
            
            html_content = render_template('emails/booking_pending.html', booking=booking_data)
            subject = f"Menunggu Pembayaran - {booking_data['hotel_name']}"
            send_email(booking_data['user_email'], subject, html_content)
            
        cursor.close()
        conn.close()
        
        return redirect(url_for('booking.pay', booking_id=booking_id))

    cursor.close()
    conn.close()
    return render_template('booking_form.html', room=room, check_in=check_in, check_out=check_out)

@booking_bp.route('/pay/<int:booking_id>', methods=['GET', 'POST'])
def pay(booking_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cleanup_expired_bookings(cursor)
    
    cursor.execute("SELECT * FROM bookings WHERE id = %s AND user_id = %s", (booking_id, session['user_id']))
    booking_record = cursor.fetchone()

    if not booking_record:
        flash("Booking not found or you don't have permission.", "danger")
        return redirect(url_for('main.index'))

    if booking_record['status'] == 'Cancelled':
        flash("Your booking session has expired.", "warning")
        return redirect(url_for('main.index'))

    if booking_record['status'] == 'Booked':
        return render_template('invoice.html', booking=booking_record)

    expiry_time = booking_record['created_at'] + timedelta(minutes=15)
    now = datetime.now()
    if now > expiry_time:
        cursor.execute("UPDATE bookings SET status = 'Cancelled' WHERE id = %s", (booking_id,))
        conn.commit()
        flash("Your booking session has expired.", "warning")
        return redirect(url_for('main.index'))

    time_left_seconds = (expiry_time - now).total_seconds()

    if request.method == 'POST':
        cursor.execute("UPDATE bookings SET status = 'Booked' WHERE id = %s", (booking_id,))
        conn.commit()
        
        # Ambil data lengkap untuk email konfirmasi
        cursor.execute("""
            SELECT b.*, r.room_number, r.room_type, r.price, h.name as hotel_name, u.email as user_email
            FROM bookings b 
            JOIN rooms r ON b.room_id = r.id 
            JOIN hotels h ON r.hotel_id = h.id 
            JOIN users u ON b.user_id = u.id
            WHERE b.id = %s
        """, (booking_id,))
        booking_data = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if booking_data and booking_data.get('user_email'):
            from services.email_service import send_email
            from flask import render_template
            
            html_content = render_template('emails/booking_confirmation.html', booking=booking_data)
            subject = f"Konfirmasi Pemesanan - {booking_data['hotel_name']} (INV-{booking_data['id']})"
            send_email(booking_data['user_email'], subject, html_content)
            
        flash("Payment successful! Room booked.", "success")
        return redirect(url_for('booking.invoice', booking_id=booking_id))

    cursor.execute("SELECT * FROM rooms r JOIN hotels h ON r.hotel_id = h.id WHERE r.id = %s", (booking_record['room_id'],))
    room = cursor.fetchone()
    cursor.close()
    conn.close()
    
    return render_template('pay.html', booking=booking_record, room=room, time_left_seconds=int(time_left_seconds))

@booking_bp.route('/invoice/<int:booking_id>')
def invoice(booking_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT b.*, r.room_number, r.room_type, r.price, h.name as hotel_name 
        FROM bookings b 
        JOIN rooms r ON b.room_id = r.id 
        JOIN hotels h ON r.hotel_id = h.id 
        WHERE b.id = %s AND b.user_id = %s
    """, (booking_id, session['user_id']))
    booking_record = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if not booking_record or booking_record['status'] != 'Booked':
        return redirect(url_for('main.index'))
        
    return render_template('invoice.html', booking=booking_record)

@booking_bp.route('/my-bookings')
def my_bookings():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cleanup_expired_bookings(cursor)
    
    query = """
        SELECT b.*, r.room_number, r.room_type, r.price, h.name as hotel_name,
               (SELECT COUNT(*) FROM reviews WHERE booking_id = b.id) as has_reviewed
        FROM bookings b 
        JOIN rooms r ON b.room_id = r.id 
        JOIN hotels h ON r.hotel_id = h.id 
        WHERE b.user_id = %s 
        ORDER BY b.created_at DESC
    """
    cursor.execute(query, (session['user_id'],))
    bookings = cursor.fetchall()
    
    wl_query = """
        SELECT w.*, r.room_number, r.room_type, h.name as hotel_name 
        FROM waiting_lists w 
        JOIN rooms r ON w.room_id = r.id 
        JOIN hotels h ON r.hotel_id = h.id 
        WHERE w.user_id = %s 
        ORDER BY w.created_at DESC
    """
    cursor.execute(wl_query, (session['user_id'],))
    waiting_lists = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    now_date = datetime.now().date()
    for b in bookings:
        b['can_review'] = (b['status'] == 'Booked' and now_date >= b['check_out'])
        b['can_cancel'] = (now_date < b['check_in'])
        
    return render_template('my_bookings.html', bookings=bookings, waiting_lists=waiting_lists)

@booking_bp.route('/cancel/<int:booking_id>', methods=['POST'])
def cancel_booking(booking_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT check_in FROM bookings WHERE id = %s AND user_id = %s", (booking_id, session['user_id']))
    booking = cursor.fetchone()
    
    if not booking:
        cursor.close()
        conn.close()
        flash("Pesanan tidak ditemukan.", "danger")
        return redirect(url_for('booking.my_bookings'))
        
    if datetime.now().date() >= booking['check_in']:
        cursor.close()
        conn.close()
        flash("Pesanan tidak dapat dibatalkan karena sudah melewati batas waktu (24 jam sebelum check-in).", "danger")
        return redirect(url_for('booking.my_bookings'))

    cursor.execute("UPDATE bookings SET status = 'Cancelled' WHERE id = %s AND user_id = %s", (booking_id, session['user_id']))
    conn.commit()
    
    # Kirim Email Cancelled
    cursor.execute("""
        SELECT b.*, r.room_type, h.name as hotel_name, u.email as user_email
        FROM bookings b 
        JOIN rooms r ON b.room_id = r.id 
        JOIN hotels h ON r.hotel_id = h.id 
        JOIN users u ON b.user_id = u.id
        WHERE b.id = %s
    """, (booking_id,))
    booking_data = cursor.fetchone()
    
    if booking_data and booking_data.get('user_email'):
        from services.email_service import send_email
        from flask import render_template
        
        html_content = render_template('emails/booking_cancelled.html', booking=booking_data)
        subject = f"Pesanan Dibatalkan - {booking_data['hotel_name']}"
        send_email(booking_data['user_email'], subject, html_content)

    cursor.close()
    conn.close()
    flash("Booking cancelled successfully.", "success")
    return redirect(url_for('booking.my_bookings'))

@booking_bp.route('/waitlist/<int:room_id>', methods=['POST'])
def join_waitlist(room_id):
    if 'user_id' not in session:
        flash("Please login to join the waiting list.", "warning")
        return redirect(url_for('auth.login'))

    check_in = request.form['check_in']
    check_out = request.form['check_out']

    try:
        ci_date = datetime.strptime(check_in, '%Y-%m-%d').date()
        co_date = datetime.strptime(check_out, '%Y-%m-%d').date()
        today = datetime.now().date()
        
        if ci_date < today:
            flash("Tanggal check-in tidak boleh di masa lalu.", "danger")
            return redirect(url_for('main.index'))
            
        if co_date <= ci_date:
            flash("Tanggal check-out harus setelah check-in.", "danger")
            return redirect(url_for('main.index'))
    except ValueError:
        flash("Format tanggal tidak valid.", "danger")
        return redirect(url_for('main.index'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO waiting_lists (user_id, room_id, check_in, check_out) VALUES (%s, %s, %s, %s)",
                   (session['user_id'], room_id, check_in, check_out))
    conn.commit()
    cursor.close()
    conn.close()
    
    flash("Successfully joined the waiting list! We will notify you if it becomes available (Mock).", "success")
    return redirect(url_for('booking.my_bookings'))

@booking_bp.route('/review/<int:booking_id>', methods=['POST'])
def submit_review(booking_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
        
    rating = request.form.get('rating', type=int)
    comment = request.form.get('comment')
    
    if not rating or rating < 1 or rating > 5:
        flash("Invalid rating submitted.", "danger")
        return redirect(url_for('booking.my_bookings'))
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT r.hotel_id, b.check_out FROM bookings b JOIN rooms r ON b.room_id = r.id WHERE b.id = %s AND b.user_id = %s AND b.status = 'Booked'", (booking_id, session['user_id']))
    booking = cursor.fetchone()
    
    if not booking:
        cursor.close()
        conn.close()
        flash("Booking not found or cannot be reviewed.", "danger")
        return redirect(url_for('booking.my_bookings'))
        
    if datetime.now().date() < booking['check_out']:
        cursor.close()
        conn.close()
        flash("Ulasan hanya dapat diberikan setelah Anda selesai menginap (melewati tanggal check-out).", "warning")
        return redirect(url_for('booking.my_bookings'))
        
    try:
        cursor.execute("""
            INSERT INTO reviews (hotel_id, user_id, booking_id, rating, comment)
            VALUES (%s, %s, %s, %s, %s)
        """, (booking['hotel_id'], session['user_id'], booking_id, rating, comment))
        conn.commit()
        flash("Thank you for your review!", "success")
    except mysql.connector.IntegrityError:
        flash("You have already reviewed this booking.", "warning")
    except Exception as e:
        flash("An error occurred while submitting your review.", "danger")
        
    cursor.close()
    conn.close()
    
    return redirect(url_for('booking.my_bookings'))
