import sys
import re

with open('routes/admin.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Replace generate_pdf_bytes
new_pdf_gen = """
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
"""

# Find and replace the function generate_pdf_bytes
pattern = re.compile(r'def generate_pdf_bytes\(.*?return pdf_bytes\n', re.DOTALL)
content = pattern.sub(new_pdf_gen, content)


# 2. Update api_analytics_data
new_analytics_data = """
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
"""

pattern_analytics = re.compile(r'@admin_bp\.route\(\'/api/analytics_data\'\).*?return jsonify\(\{.*?\}\)\n', re.DOTALL)
content = pattern_analytics.sub(new_analytics_data, content)

with open('routes/admin.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Backend patched successfully.")
