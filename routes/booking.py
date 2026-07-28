from flask import Blueprint, render_template, request, flash, redirect, url_for, session
from datetime import datetime, timedelta
import math
import mysql.connector
from db import get_db_connection, cleanup_expired_bookings
from utils import login_required, add_notification

booking_bp = Blueprint('booking', __name__)

@booking_bp.route('/book/<int:hotel_id>', methods=['GET', 'POST'])
@login_required
def book_room(hotel_id):
    room_type = request.args.get('room_type')
    check_in = request.args.get('check_in')
    check_out = request.args.get('check_out')

    if not check_in or not check_out or not room_type:
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

    # Instead of picking a specific room_id, we fetch one available room of the requested type
    cursor.execute("""
        SELECT r.*, h.name as hotel_name 
        FROM rooms r 
        JOIN hotels h ON r.hotel_id = h.id 
        WHERE r.hotel_id = %s AND r.room_type = %s AND r.is_deleted = 0 AND h.is_deleted = 0
        AND r.id NOT IN (
            SELECT b.room_id FROM bookings b
            WHERE b.status IN ('Booked', 'Checked In')
            AND (b.check_in < %s AND b.check_out > %s)
        )
        ORDER BY r.room_number ASC LIMIT 1
    """, (hotel_id, room_type, check_out, check_in))
    
    room = cursor.fetchone()

    if not room:
        cursor.close()
        conn.close()
        flash("Mohon maaf, tipe kamar ini sudah penuh untuk tanggal yang dipilih.", "danger")
        return redirect(url_for('main.hotel_rooms', hotel_id=hotel_id))

    room_id = room['id']
    nights = (co_date - ci_date).days
    grand_total = room['price'] * nights

    if request.method == 'POST':
        guest_name = request.form.get('guest_name', '').strip()
        contact_number = request.form.get('contact_number', '').strip()
        payment_method = request.form.get('payment_method', '').strip()

        if not guest_name or not contact_number or not payment_method:
            flash("Semua data pemesanan wajib diisi.", "danger")
            return render_template('booking_form.html', room=room, check_in=check_in, check_out=check_out, nights=nights, grand_total=grand_total)

        if len(guest_name) < 3:
            flash("Nama lengkap tamu minimal 3 karakter.", "danger")
            return render_template('booking_form.html', room=room, check_in=check_in, check_out=check_out, nights=nights, grand_total=grand_total)

        import re
        if not re.match(r'^[\d\+\-\(\)\s]{9,15}$', contact_number):
            flash("Nomor kontak tidak valid. Harap masukkan 9-15 digit angka.", "danger")
            return render_template('booking_form.html', room=room, check_in=check_in, check_out=check_out, nights=nights, grand_total=grand_total)

        cleanup_expired_bookings(cursor)

        # LOCK THE ROOM ROW to prevent race conditions (Double Booking)
        # However, to be totally safe we should query again WITH FOR UPDATE
        cursor.execute("""
            SELECT id FROM rooms 
            WHERE hotel_id = %s AND room_type = %s AND is_deleted = 0 
            AND id NOT IN (
                SELECT room_id FROM bookings
                WHERE status IN ('Booked', 'Checked In')
                AND (check_in < %s AND check_out > %s)
            )
            ORDER BY room_number ASC LIMIT 1 FOR UPDATE
        """, (hotel_id, room_type, check_out, check_in))
        locked_room = cursor.fetchone()
        
        if not locked_room:
            conn.rollback()
            cursor.close()
            conn.close()
            flash("Maaf, kamar baru saja di-booking oleh orang lain. Silakan coba lagi.", "danger")
            return redirect(url_for('main.hotel_rooms', hotel_id=hotel_id))

        final_room_id = locked_room['id']

        insert_query = """
            INSERT INTO bookings (user_id, room_id, guest_name, contact_number, check_in, check_out, payment_method, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'Booked')
        """
        cursor.execute(insert_query, (session['user_id'], final_room_id, guest_name, contact_number, check_in, check_out, payment_method))
        conn.commit()
        booking_id = cursor.lastrowid

        add_notification(
            title="Booking Baru Dibuat",
            description=f"Guest {guest_name} membuat reservasi baru.",
            icon_type="booking"
        )

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
            html_content = render_template('emails/booking_confirmation.html', booking=booking_data)
            subject = f"Konfirmasi Pemesanan - {booking_data['hotel_name']} (INV-{booking_data['id']})"
            send_email(booking_data['user_email'], subject, html_content)

        cursor.close()
        conn.close()

        flash("Pemesanan berhasil! Kamar telah dibooking.", "success")
        return redirect(url_for('booking.invoice', booking_id=booking_id))

    cursor.close()
    conn.close()
    return render_template('booking_form.html', room=room, check_in=check_in, check_out=check_out, nights=nights, grand_total=grand_total)



@booking_bp.route('/invoice/<int:booking_id>')
@login_required
def invoice(booking_id):
        
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
        
    nights = (booking_record['check_out'] - booking_record['check_in']).days
    grand_total = booking_record['price'] * nights
        
    return render_template('invoice.html', booking=booking_record, nights=nights, grand_total=grand_total)

@booking_bp.route('/my-bookings')
@login_required
def my_bookings():

    status = request.args.get('status', 'Semua')
    page = request.args.get('page', 1, type=int)
    wl_page = request.args.get('wl_page', 1, type=int)
    
    per_page = 6
    offset = (page - 1) * per_page
    wl_offset = (wl_page - 1) * per_page

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
    """
    count_query = "SELECT COUNT(*) as count FROM bookings b WHERE b.user_id = %s"
    params = [session['user_id']]
    
    if status != 'Semua':
        query += " AND b.status = %s"
        count_query += " AND b.status = %s"
        params.append(status)
        
    query += " ORDER BY b.created_at DESC LIMIT %s OFFSET %s"
    
    cursor.execute(count_query, tuple(params))
    total_bookings = cursor.fetchone()['count']
    total_pages = math.ceil(total_bookings / per_page)
    
    params.extend([per_page, offset])
    cursor.execute(query, tuple(params))
    bookings = cursor.fetchall()
    
    wl_query = """
        SELECT w.*, r.room_number, r.room_type, h.name as hotel_name 
        FROM waiting_lists w 
        JOIN rooms r ON w.room_id = r.id 
        JOIN hotels h ON r.hotel_id = h.id 
        WHERE w.user_id = %s 
        ORDER BY w.created_at DESC
        LIMIT %s OFFSET %s
    """
    cursor.execute("SELECT COUNT(*) as count FROM waiting_lists WHERE user_id = %s", (session['user_id'],))
    total_wl = cursor.fetchone()['count']
    wl_total_pages = math.ceil(total_wl / per_page)
    
    cursor.execute(wl_query, (session['user_id'], per_page, wl_offset))
    waiting_lists = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    now_date = datetime.now().date()
    for b in bookings:
        b['can_review'] = (b['status'] == 'Checked Out') and (b['has_reviewed'] == 0)
        b['can_cancel'] = (b['status'] == 'Booked') and (now_date < b['check_in'])
        
    return render_template('my_bookings.html', bookings=bookings, waiting_lists=waiting_lists, 
                           status=status, page=page, total_pages=total_pages, 
                           wl_page=wl_page, wl_total_pages=wl_total_pages)

@booking_bp.route('/cancel/<int:booking_id>', methods=['POST'])
@login_required
def cancel_booking(booking_id):

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT check_in, status FROM bookings WHERE id = %s AND user_id = %s", (booking_id, session['user_id']))
    booking = cursor.fetchone()
    
    if not booking:
        cursor.close()
        conn.close()
        flash("Pesanan tidak ditemukan.", "danger")
        return redirect(url_for('booking.my_bookings'))
        
    if booking['status'] != 'Booked':
        cursor.close()
        conn.close()
        flash("Pesanan ini tidak dapat dibatalkan (mungkin sudah dibatalkan atau sudah check-in).", "danger")
        return redirect(url_for('booking.my_bookings'))
        
    if datetime.now().date() >= booking['check_in']:
        cursor.close()
        conn.close()
        flash("Pesanan tidak dapat dibatalkan karena sudah melewati batas waktu (24 jam sebelum check-in).", "danger")
        return redirect(url_for('booking.my_bookings'))

    cancel_reason = request.form.get('cancel_reason', 'Dibatalkan oleh Pengguna')
    
    cursor.execute("UPDATE bookings SET status = 'Cancelled', cancel_reason = %s WHERE id = %s AND user_id = %s", (cancel_reason, booking_id, session['user_id']))
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

        
        html_content = render_template('emails/booking_cancelled.html', booking=booking_data)
        subject = f"Pesanan Dibatalkan - {booking_data['hotel_name']}"
        send_email(booking_data['user_email'], subject, html_content)
        
        # Cek Waiting List (berdasarkan tipe kamar yang sama di hotel yang sama)
        cursor.execute("""
            SELECT w.id, w.check_in, w.check_out, u.email as user_email, u.username, h.name as hotel_name, rw.room_type, h.id as hotel_id
            FROM waiting_lists w
            JOIN users u ON w.user_id = u.id
            JOIN rooms rw ON w.room_id = rw.id
            JOIN hotels h ON rw.hotel_id = h.id
            JOIN rooms rc ON rc.hotel_id = h.id AND rc.room_type = rw.room_type
            WHERE rc.id = %s
            AND w.check_in < %s AND w.check_out > %s
        """, (booking_data['room_id'], booking_data['check_out'], booking_data['check_in']))
        waitlist_users = cursor.fetchall()
        
        for wu in waitlist_users:
            # Pastikan kamar yang dibatalkan ini benar-benar kosong untuk keseluruhan tanggal pengantre
            cursor.execute("""
                SELECT id FROM bookings
                WHERE room_id = %s
                AND status != 'Cancelled'
                AND (check_in < %s AND check_out > %s)
            """, (booking_data['room_id'], wu['check_out'], wu['check_in']))
            conflicts = cursor.fetchone()
            
            if not conflicts and wu.get('user_email'):
                html_waitlist = render_template('emails/waitlist_available.html', waitlist=wu)
                subject_waitlist = f"Kabar Gembira! Kamar Tersedia - {wu['hotel_name']}"
                send_email(wu['user_email'], subject_waitlist, html_waitlist)

    cursor.close()
    conn.close()
    flash("Booking cancelled successfully.", "success")
    return redirect(url_for('booking.my_bookings'))

@booking_bp.route('/waitlist/<int:hotel_id>', methods=['POST'])
@login_required
def join_waitlist(hotel_id):
    room_type = request.args.get('room_type') or request.form.get('room_type')

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
    cursor = conn.cursor(dictionary=True)
    
    # Try to find a specific room type first, or just any room in the hotel
    if room_type:
        cursor.execute("SELECT id FROM rooms WHERE hotel_id = %s AND room_type = %s LIMIT 1", (hotel_id, room_type))
    else:
        cursor.execute("SELECT id FROM rooms WHERE hotel_id = %s LIMIT 1", (hotel_id,))
        
    room = cursor.fetchone()
    if not room:
        cursor.close()
        conn.close()
        flash("Tidak ada kamar yang bisa diantre di hotel ini.", "danger")
        return redirect(url_for('main.index'))
        
    room_id = room['id']
    
    # Cek apakah user sudah masuk waiting list untuk ruangan dan tanggal yang sama
    cursor.execute("""
        SELECT id FROM waiting_lists 
        WHERE user_id = %s AND room_id = %s AND check_in = %s AND check_out = %s
    """, (session['user_id'], room_id, check_in, check_out))
    existing = cursor.fetchone()
    
    if existing:
        cursor.close()
        conn.close()
        flash("Anda sudah berada dalam daftar antrean untuk tipe kamar dan tanggal ini.", "warning")
        return redirect(url_for('booking.my_bookings'))
    
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
    
    cursor.execute("SELECT r.hotel_id, b.check_out FROM bookings b JOIN rooms r ON b.room_id = r.id WHERE b.id = %s AND b.user_id = %s AND b.status = 'Checked Out'", (booking_id, session['user_id']))
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
        
        # Update hotel average rating
        cursor.execute("SELECT AVG(rating) as avg_rating FROM reviews WHERE hotel_id = %s", (booking['hotel_id'],))
        result = cursor.fetchone()
        avg_rating = result['avg_rating'] if result and result['avg_rating'] else 0.0
        cursor.execute("UPDATE hotels SET rating = %s WHERE id = %s", (avg_rating, booking['hotel_id']))
        
        conn.commit()
        flash("Thank you for your review!", "success")
    except mysql.connector.IntegrityError:
        flash("You have already reviewed this booking.", "warning")
    except Exception as e:
        flash("An error occurred while submitting your review.", "danger")
        
    cursor.close()
    conn.close()
    
    return redirect(url_for('booking.my_bookings'))
