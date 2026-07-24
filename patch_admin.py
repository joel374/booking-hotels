import sys

code_to_add = """
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
    
    if period == 'Today':
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == 'This Week':
        start_date = now - datetime.timedelta(days=now.weekday())
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == 'This Month':
        start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif period == 'This Year':
        start_date = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    
    hotel_filter = ""
    params = []
    
    if hotel_id and hotel_id != 'all':
        hotel_filter = " AND h.id = %s "
        params.append(hotel_id)
        
    date_filter = ""
    date_params = []
    if start_date:
        date_filter = " AND b.created_at >= %s AND b.created_at <= %s "
        date_params = [start_date, end_date]
        
    cursor.execute("SELECT COUNT(*) as total FROM hotels h WHERE h.is_deleted = 0" + hotel_filter, params)
    total_hotels = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as total FROM rooms r JOIN hotels h ON r.hotel_id = h.id WHERE r.is_deleted = 0 AND h.is_deleted = 0" + hotel_filter, params)
    total_rooms = cursor.fetchone()['total']
    
    b_join = " FROM bookings b JOIN rooms r ON b.room_id = r.id JOIN hotels h ON r.hotel_id = h.id WHERE r.is_deleted = 0 AND h.is_deleted = 0 "
    
    cursor.execute("SELECT IFNULL(SUM(r.price), 0) as revenue " + b_join + " AND b.status = 'Booked' " + hotel_filter, params)
    total_revenue_lifetime = float(cursor.fetchone()['revenue'])
    
    cursor.execute("SELECT IFNULL(SUM(r.price), 0) as revenue " + b_join + " AND b.status = 'Booked' " + hotel_filter + date_filter, params + date_params)
    period_revenue = float(cursor.fetchone()['revenue'])
    
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    cursor.execute("SELECT COUNT(*) as total " + b_join + " AND b.created_at >= %s " + hotel_filter, [today_start] + params)
    todays_bookings = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as total " + b_join + hotel_filter + date_filter, params + date_params)
    period_bookings = cursor.fetchone()['total']
    
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
    
    cursor.execute("SELECT b.guest_name, h.name as hotel, DATE_FORMAT(b.created_at, '%Y-%m-%d') as date, b.status " + b_join + hotel_filter + " ORDER BY b.created_at DESC LIMIT 5", params)
    recent_bookings = cursor.fetchall()
    
    top_hotel_name = top_performing_hotels[0]['label'] if top_performing_hotels else "None"
    top_room_name = room_types[0]['label'] if room_types else "None"
    
    cursor.execute("SELECT IFNULL(SUM(r.price), 0) as revenue " + b_join + " AND b.status = 'Booked' AND b.created_at >= DATE_SUB(NOW(), INTERVAL 1 MONTH) " + hotel_filter, params)
    last_month_rev = float(cursor.fetchone()['revenue'])
    
    if period_revenue > last_month_rev:
        insight = f"Revenue is looking good! You generated Rp {period_revenue:,.0f} this period."
    elif occupancy_rate > 80:
        insight = "High occupancy rate detected! Great utilization."
    elif period_bookings > 0:
        insight = f"Booking activity is stable with {period_bookings} bookings this period."
    else:
        insight = "No recent activity to generate insights."
    
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
            'total_revenue': total_revenue_lifetime,
            'period_revenue': period_revenue,
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
            'quick_insight': insight
        }
    })
"""

with open('routes/admin.py', 'a', encoding='utf-8') as f:
    f.write(code_to_add)

print("Admin routes appended successfully.")
