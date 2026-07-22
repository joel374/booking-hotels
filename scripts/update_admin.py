import os

ADMIN_PY_PATH = os.path.join('routes', 'admin.py')

with open(ADMIN_PY_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

imports_to_add = """
import io
import datetime
import smtplib
from email.message import EmailMessage
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from flask import Response
"""

routes_to_add = """

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
        query = \"\"\"
            SELECT h.name as hotel, CONCAT(IFNULL(c.city_name, ''), ', ', IFNULL(p.province, '')) as location,
                   (SELECT COUNT(*) FROM rooms r WHERE r.hotel_id = h.id) as rooms,
                   'Active' as status
            FROM hotels h
            LEFT JOIN cities c ON h.city_id = c.city_id
            LEFT JOIN provinces p ON h.province_id = p.province_id
        \"\"\"
        cursor.execute(query)
        details = cursor.fetchall()
    elif report_type == 'Rooms':
        query = \"\"\"
            SELECT r.room_type as room, h.name as hotel, r.room_number, r.price, 'Available' as status
            FROM rooms r
            JOIN hotels h ON r.hotel_id = h.id
        \"\"\"
        cursor.execute(query)
        details = cursor.fetchall()
        for d in details:
            d['price'] = float(d['price'])
    elif report_type == 'Bookings':
        query = \"\"\"
            SELECT b.id as booking_id, b.guest_name as guest, h.name as hotel, 
                   b.created_at as date, b.status
            FROM bookings b
            JOIN rooms r ON b.room_id = r.id
            JOIN hotels h ON r.hotel_id = h.id
        \"\"\"
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

"""

# Insert imports at the top right after the first imports
lines = content.split('\n')
import_idx = 0
for i, line in enumerate(lines):
    if line.startswith('from') or line.startswith('import'):
        import_idx = i
# Insert after the last import
import_idx += 1

lines.insert(import_idx, imports_to_add)

new_content = '\n'.join(lines) + routes_to_add

with open(ADMIN_PY_PATH, 'w', encoding='utf-8') as f:
    f.write(new_content)
    
print("admin.py updated successfully.")
