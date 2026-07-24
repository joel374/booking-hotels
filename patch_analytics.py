import sys

html_content = """{% extends 'admin/base_admin.html' %}

{% block title %}Business Analytics{% endblock %}

{% block content %}
<style>
@keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}
.fade-in {
    animation: fadeIn 0.5s ease-out forwards;
}
.stat-card {
    transition: transform 0.2s, box-shadow 0.2s;
}
.stat-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 12px 30px rgba(15,23,42,0.08);
}
.trend-indicator {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    font-size: 0.75rem;
    font-weight: 600;
    padding: 0.25rem 0.5rem;
    border-radius: 999px;
    margin-top: 0.5rem;
}
.trend-up {
    background: rgba(16,185,129,0.1);
    color: var(--success);
}
.trend-down {
    background: rgba(239,68,68,0.1);
    color: var(--danger);
}
.trend-neutral {
    background: rgba(100,116,139,0.1);
    color: var(--subtext);
}
.badge-info {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    padding: 0.4rem 0.8rem;
    border-radius: 999px;
    font-size: 0.8rem;
    font-weight: 600;
    background: var(--surface);
    border: 1px solid var(--border);
    color: var(--text);
}
.chart-container {
    position: relative;
    height: 300px;
}
.chart-empty {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    background: rgba(255,255,255,0.8);
    z-index: 10;
    display: none;
}
.chart-empty svg {
    width: 3rem;
    height: 3rem;
    color: var(--subtext);
    margin-bottom: 0.5rem;
    opacity: 0.5;
}
.progress-bg {
    width: 100%;
    height: 6px;
    background: var(--border);
    border-radius: 999px;
    margin-top: 0.75rem;
    overflow: hidden;
}
.progress-fill {
    height: 100%;
    background: var(--primary);
    border-radius: 999px;
    transition: width 1s ease-out;
}
.insight-list {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
}
.insight-item {
    display: flex;
    align-items: flex-start;
    gap: 0.5rem;
    font-size: 0.9rem;
    color: var(--text);
}
.insight-icon {
    flex-shrink: 0;
    margin-top: 0.15rem;
}
</style>

<div class="welcome-banner fade-in" style="margin-bottom: 1.5rem;">
    <div class="welcome-grid">
        <div class="welcome-copy">
            <h2>Business Analytics</h2>
            <p>Monitor your hotel performance using real-time business insights.</p>
            <div style="display: flex; gap: 1rem; margin-top: 1rem; flex-wrap: wrap;">
                <div class="badge-info">
                    <svg viewBox="0 0 24 24" fill="none" style="width:1rem;height:1rem;"><path d="M12 8V12L15 15M21 12C21 16.9706 16.9706 21 12 21C7.02944 21 3 16.9706 3 12C3 7.02944 7.02944 3 12 3C16.9706 3 21 7.02944 21 12Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
                    Last Updated: <span id="lblLastUpdated">Loading...</span>
                </div>
                <div class="badge-info">
                    <svg viewBox="0 0 24 24" fill="none" style="width:1rem;height:1rem;"><path d="M8 7V3M16 7V3M7 11H17M5 21H19C20.1046 21 21 20.1046 21 19V7C21 5.89543 20.1046 5 19 5H5C3.89543 5 3 5.89543 3 7V19C3 20.1046 3.89543 21 5 21Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
                    Current Period: <span id="lblCurrentPeriod">This Month</span>
                </div>
            </div>
        </div>
        <div class="welcome-actions">
            <button id="btnOpenExportModal" class="btn btn-primary">
                <svg viewBox="0 0 24 24" fill="none" style="width:1.2rem; height:1.2rem; margin-right:0.5rem;"><path d="M12 15V3M12 15L8 11M12 15L16 11M2 17L2.621 19.485C2.72915 19.9177 2.97882 20.3018 3.33033 20.5763C3.68184 20.8508 4.11501 20.9999 4.561 21H19.439C19.885 20.9999 20.3182 20.8508 20.6697 20.5763C21.0212 20.3018 21.2708 19.9177 21.379 19.485L22 17" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
                Export Analytics
            </button>
        </div>
    </div>
</div>

<div class="table-card fade-in" style="margin-bottom: 1.5rem; display: flex; gap: 1rem; align-items: center; flex-wrap: wrap;">
    <strong style="margin-right: 0.5rem; color: var(--subtext);">Filter</strong>
    <select id="filterPeriod" class="form-control" style="width: auto; display: inline-block;">
        <option value="Today">Today</option>
        <option value="This Week">This Week</option>
        <option value="This Month" selected>This Month</option>
        <option value="This Year">This Year</option>
    </select>
    <select id="filterHotel" class="form-control" style="width: auto; display: inline-block;">
        <option value="all">All Hotels</option>
        {% for h in hotels %}
        <option value="{{ h.id }}">{{ h.name }}</option>
        {% endfor %}
    </select>
    <button id="btnRefresh" class="btn btn-secondary" style="padding: 0.6rem 1.2rem;">
        <svg viewBox="0 0 24 24" fill="none" style="width:1rem;height:1rem;margin-right:0.4rem;"><path d="M4 4V9H4.58152M19.9381 11C19.446 7.05369 16.0796 4 12 4C8.64262 4 5.76829 6.06817 4.58152 9M4.58152 9H9M20 20V15H19.4185M19.4185 15C18.2317 17.9318 15.3574 20 12 20C7.92038 20 4.55399 16.9463 4.06189 13M19.4185 15H15" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
        Refresh
    </button>
</div>

<!-- Empty State -->
<div id="emptyState" class="table-card fade-in" style="display: none; text-align: center; padding: 4rem 2rem;">
    <svg viewBox="0 0 24 24" fill="none" style="width: 4rem; height: 4rem; color: var(--subtext); margin: 0 auto 1rem;"><path d="M4 19H20M5 15L9 11L13 15L19 9" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
    <h3>No Analytics Data Available</h3>
    <p style="color: var(--subtext);">Analytics will appear once bookings are recorded for this property.</p>
</div>

<div id="analyticsContent">
    <!-- Quick Insight -->
    <div class="table-card fade-in" style="margin-bottom: 1.5rem; background: linear-gradient(135deg, rgba(79, 70, 229, 0.05) 0%, rgba(37, 99, 235, 0.05) 100%); border-left: 4px solid var(--primary);">
        <strong style="display: block; margin-bottom: 0.75rem; color: var(--primary);">Quick Insight</strong>
        <ul id="quickInsightList" class="insight-list">
            <li style="color: var(--subtext);">Loading insights...</li>
        </ul>
    </div>

    <!-- Summary Metrics -->
    <div class="cards-grid fade-in" style="margin-bottom: 1.5rem; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));">
        <div class="stat-card">
            <span class="stat-label">Total Hotels</span>
            <span class="stat-value counter" id="valTotalHotels" data-val="0">0</span>
            <span style="font-size:0.75rem; color:var(--subtext);">Registered properties</span>
        </div>
        <div class="stat-card">
            <span class="stat-label">Total Rooms</span>
            <span class="stat-value counter" id="valTotalRooms" data-val="0">0</span>
            <span style="font-size:0.75rem; color:var(--subtext);">Total inventory</span>
        </div>
        <div class="stat-card">
            <span class="stat-label">Total Revenue</span>
            <span class="stat-value" id="valTotalRevenue">Rp 0</span>
            <span style="font-size:0.75rem; color:var(--subtext);">Lifetime earnings</span>
        </div>
        <div class="stat-card">
            <span class="stat-label">Period Revenue</span>
            <span class="stat-value" id="valPeriodRevenue">Rp 0</span>
            <span id="trendPeriodRevenue" class="trend-indicator trend-neutral">No comparison</span>
        </div>
        <div class="stat-card">
            <span class="stat-label">Period Bookings</span>
            <span class="stat-value counter" id="valPeriodBookings" data-val="0">0</span>
            <span id="trendPeriodBookings" class="trend-indicator trend-neutral">No comparison</span>
        </div>
        <div class="stat-card">
            <span class="stat-label">Available Rooms</span>
            <span class="stat-value counter" id="valAvailableRooms" data-val="0">0</span>
            <span style="font-size:0.75rem; color:var(--subtext);">Currently empty</span>
        </div>
        <div class="stat-card">
            <span class="stat-label">Occupied Rooms</span>
            <span class="stat-value counter" id="valOccupiedRooms" data-val="0">0</span>
            <span style="font-size:0.75rem; color:var(--subtext);">Currently booked</span>
        </div>
        <div class="stat-card">
            <span class="stat-label">Occupancy Rate</span>
            <span class="stat-value" id="valOccupancyRate">0%</span>
            <div class="progress-bg"><div class="progress-fill" id="occProgressBar" style="width: 0%"></div></div>
        </div>
    </div>

    <!-- Charts -->
    <div class="stats-grid fade-in" style="margin-bottom: 1.5rem;">
        <div class="chart-card">
            <header>
                <span>📈</span>
                <div>
                    <h3>Revenue Trend</h3>
                    <p>Pendapatan per bulan</p>
                </div>
            </header>
            <div class="chart-container">
                <canvas id="chartRevenueTrend"></canvas>
                <div id="emptyRevenue" class="chart-empty">
                    <svg viewBox="0 0 24 24" fill="none"><path d="M4 19H20M5 15L9 11L13 15L19 9" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
                    <span style="font-size: 0.9rem;">No data available</span>
                </div>
            </div>
        </div>
        <div class="chart-card">
            <header>
                <span>📊</span>
                <div>
                    <h3>Booking Trend</h3>
                    <p>Booking per bulan</p>
                </div>
            </header>
            <div class="chart-container">
                <canvas id="chartBookingTrend"></canvas>
                <div id="emptyBooking" class="chart-empty">
                    <svg viewBox="0 0 24 24" fill="none"><path d="M4 7H20M5 7V19H19V7M8 3V7M16 3V7" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
                    <span style="font-size: 0.9rem;">No data available</span>
                </div>
            </div>
        </div>
        <div class="chart-card">
            <header>
                <span>🛏️</span>
                <div>
                    <h3>Room Status</h3>
                    <p>Available vs Occupied</p>
                </div>
            </header>
            <div class="chart-container">
                <canvas id="chartRoomStatus"></canvas>
                <div id="emptyRoomStatus" class="chart-empty">
                    <svg viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2"/></svg>
                    <span style="font-size: 0.9rem;">No data available</span>
                </div>
            </div>
        </div>
        <div class="chart-card">
            <header>
                <span>🏢</span>
                <div>
                    <h3>Top Performing Hotels</h3>
                    <p>Berdasarkan jumlah booking</p>
                </div>
            </header>
            <div class="chart-container">
                <canvas id="chartTopHotels"></canvas>
                <div id="emptyTopHotels" class="chart-empty">
                    <svg viewBox="0 0 24 24" fill="none"><rect x="3" y="3" width="18" height="18" rx="2" stroke="currentColor" stroke-width="2"/></svg>
                    <span style="font-size: 0.9rem;">No ranking available yet</span>
                </div>
            </div>
        </div>
        <div class="chart-card">
            <header>
                <span>🔑</span>
                <div>
                    <h3>Room Types Distribution</h3>
                    <p>Tipe kamar paling sering dipesan</p>
                </div>
            </header>
            <div class="chart-container">
                <canvas id="chartRoomTypes"></canvas>
                <div id="emptyRoomTypes" class="chart-empty">
                    <svg viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2"/></svg>
                    <span style="font-size: 0.9rem;">No popularity data yet</span>
                </div>
            </div>
        </div>
        <div class="chart-card">
            <header>
                <span>⏱️</span>
                <div>
                    <h3>Occupancy Rate</h3>
                    <p>Persentase tingkat hunian</p>
                </div>
            </header>
            <div class="chart-container">
                <canvas id="chartOccupancy"></canvas>
                <div id="emptyOccupancy" class="chart-empty">
                    <svg viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2"/></svg>
                    <span style="font-size: 0.9rem;">No data available</span>
                </div>
            </div>
        </div>
    </div>

    <!-- Bottom Panels -->
    <div class="fade-in" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1.5rem;">
        <div class="table-card" style="grid-column: 1 / -1; grid-row: 1;">
            <div class="table-info">
                <div>
                    <p class="table-title">Recent Bookings</p>
                    <p class="table-meta">5 booking terbaru</p>
                </div>
            </div>
            <div class="table-responsive">
                <table>
                    <thead>
                        <tr>
                            <th>Guest Name</th>
                            <th>Hotel</th>
                            <th>Check-in</th>
                            <th>Check-out</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody id="recentBookingsTable">
                    </tbody>
                </table>
            </div>
        </div>
        
        <div class="stat-card" style="background: var(--surface);">
            <div class="stat-icon">
                <span>🏆</span>
            </div>
            <span class="stat-label">Top Hotel</span>
            <span class="stat-value" id="valTopHotel">-</span>
            <span class="delta">Hotel paling banyak dipesan</span>
        </div>
        
        <div class="stat-card" style="background: var(--surface);">
            <div class="stat-icon">
                <span>🔥</span>
            </div>
            <span class="stat-label">Popular Room</span>
            <span class="stat-value" id="valPopularRoom">-</span>
            <span class="delta">Room Type yang paling sering dipesan</span>
        </div>
    </div>
</div>

<!-- Modal Export Analytics -->
<div id="modalExportAnalytics" class="modal">
    <div class="form-card">
        <button type="button" class="btn btn-outline js-close-modal" style="position:absolute; top:1rem; right:1rem; width:42px; height:42px; padding:0; line-height:0; border-radius:14px;">×</button>
        <h2>Export Analytics</h2>
        <p style="margin:0 0 1rem; color: var(--subtext);">Generate professional PDF report based on current insights.</p>
        <form id="formExportAnalytics" method="POST" action="{{ url_for('admin.api_reports_download_pdf') }}">
            <div class="input-group">
                <label>Report Type</label>
                <select name="type" class="form-control" required>
                    <option value="Business Analytics" selected>Business Analytics</option>
                    <option value="Dashboard Summary">Dashboard Summary</option>
                    <option value="Hotels">Hotels</option>
                    <option value="Rooms">Rooms</option>
                    <option value="Bookings">Bookings</option>
                </select>
            </div>
            <div class="input-group">
                <label>Period</label>
                <select name="period" id="exportPeriod" class="form-control" required>
                    <option value="Today">Today</option>
                    <option value="This Week">This Week</option>
                    <option value="This Month" selected>This Month</option>
                    <option value="This Year">This Year</option>
                </select>
            </div>
            <div class="input-group">
                <label>Format</label>
                <select class="form-control" disabled>
                    <option value="PDF" selected>PDF Document (.pdf)</option>
                </select>
            </div>
            <div style="display:flex; gap:1rem; justify-content:flex-end; margin-top:2rem;">
                <button type="button" class="btn btn-outline js-close-modal">Cancel</button>
                <button type="submit" class="btn btn-primary" onclick="document.getElementById('modalExportAnalytics').classList.remove('active')">Export Report</button>
            </div>
        </form>
    </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script>
    let charts = {};

    const formatRp = (num) => {
        return "Rp " + Math.round(num).toString().replace(/\\B(?=(\\d{3})+(?!\\d))/g, ".");
    };
    
    const animateCounter = (elementId, endValue) => {
        const el = document.getElementById(elementId);
        const duration = 1000;
        const start = 0;
        let startTimestamp = null;
        
        const step = (timestamp) => {
            if (!startTimestamp) startTimestamp = timestamp;
            const progress = Math.min((timestamp - startTimestamp) / duration, 1);
            el.textContent = Math.floor(progress * endValue);
            if (progress < 1) {
                window.requestAnimationFrame(step);
            } else {
                el.textContent = endValue;
            }
        };
        window.requestAnimationFrame(step);
    };

    const updateTime = () => {
        const now = new Date();
        const options = { year: 'numeric', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit' };
        document.getElementById('lblLastUpdated').textContent = now.toLocaleDateString('en-GB', options);
    };

    const initChart = (ctxId, type, data, options, isEmpty = false) => {
        const emptyEl = document.getElementById(ctxId.replace('chart', 'empty'));
        if (isEmpty) {
            emptyEl.style.display = 'flex';
        } else {
            emptyEl.style.display = 'none';
            const ctx = document.getElementById(ctxId).getContext('2d');
            if (charts[ctxId]) {
                charts[ctxId].destroy();
            }
            charts[ctxId] = new Chart(ctx, { type, data, options });
        }
    };

    const loadAnalytics = () => {
        updateTime();
        const period = document.getElementById('filterPeriod').value;
        const hotelId = document.getElementById('filterHotel').value;
        
        document.getElementById('lblCurrentPeriod').textContent = period;
        document.getElementById('exportPeriod').value = period; // Sync export modal
        
        document.getElementById('btnRefresh').disabled = true;
        document.getElementById('btnRefresh').innerHTML = '<svg viewBox="0 0 24 24" fill="none" style="width:1rem;height:1rem;margin-right:0.4rem;animation:spin 1s linear infinite;"><path d="M4 4V9H4.58152M19.9381 11C19.446 7.05369 16.0796 4 12 4C8.64262 4 5.76829 6.06817 4.58152 9M4.58152 9H9M20 20V15H19.4185M19.4185 15C18.2317 17.9318 15.3574 20 12 20C7.92038 20 4.55399 16.9463 4.06189 13M19.4185 15H15" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>Loading...';

        fetch(`/admin/api/analytics_data?period=${encodeURIComponent(period)}&hotel_id=${encodeURIComponent(hotelId)}`)
            .then(res => res.json())
            .then(data => {
                document.getElementById('btnRefresh').disabled = false;
                document.getElementById('btnRefresh').innerHTML = '<svg viewBox="0 0 24 24" fill="none" style="width:1rem;height:1rem;margin-right:0.4rem;"><path d="M4 4V9H4.58152M19.9381 11C19.446 7.05369 16.0796 4 12 4C8.64262 4 5.76829 6.06817 4.58152 9M4.58152 9H9M20 20V15H19.4185M19.4185 15C18.2317 17.9318 15.3574 20 12 20C7.92038 20 4.55399 16.9463 4.06189 13M19.4185 15H15" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>Refresh';

                if (data.summary.total_hotels === 0 && data.summary.total_rooms === 0) {
                    document.getElementById('analyticsContent').style.display = 'none';
                    document.getElementById('emptyState').style.display = 'block';
                    return;
                }
                document.getElementById('analyticsContent').style.display = 'block';
                document.getElementById('emptyState').style.display = 'none';

                // Populate Summary with Counters
                animateCounter('valTotalHotels', data.summary.total_hotels);
                animateCounter('valTotalRooms', data.summary.total_rooms);
                animateCounter('valAvailableRooms', data.summary.available_rooms);
                animateCounter('valOccupiedRooms', data.summary.occupied_rooms);
                animateCounter('valPeriodBookings', data.summary.period_bookings);
                
                document.getElementById('valOccupancyRate').textContent = data.summary.occupancy_rate + '%';
                document.getElementById('occProgressBar').style.width = data.summary.occupancy_rate + '%';
                
                document.getElementById('valTotalRevenue').textContent = formatRp(data.summary.total_revenue);
                document.getElementById('valPeriodRevenue').textContent = formatRp(data.summary.period_revenue);
                document.getElementById('valAvgPrice').textContent = formatRp(data.summary.avg_price);
                
                // Set trend badges
                const setTrend = (elId, trendData) => {
                    const el = document.getElementById(elId);
                    el.className = `trend-indicator trend-${trendData.status}`;
                    if (trendData.status === 'up') el.innerHTML = `↑ ${trendData.text}`;
                    else if (trendData.status === 'down') el.innerHTML = `↓ ${trendData.text}`;
                    else el.innerHTML = `- ${trendData.text}`;
                };
                setTrend('trendPeriodRevenue', data.summary.period_revenue_trend);
                setTrend('trendPeriodBookings', data.summary.period_bookings_trend);

                // Quick Insights
                const ul = document.getElementById('quickInsightList');
                ul.innerHTML = '';
                data.panels.quick_insights.forEach(insight => {
                    const li = document.createElement('li');
                    li.className = 'insight-item fade-in';
                    const iconColor = insight.status === 'up' ? 'var(--success)' : (insight.status === 'down' ? 'var(--danger)' : 'var(--primary)');
                    const iconSvg = `<svg class="insight-icon" viewBox="0 0 24 24" fill="none" style="width:1.2rem;height:1.2rem;color:${iconColor};"><path d="M5 13L9 17L19 7" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
                    li.innerHTML = `${iconSvg} <span>${insight.text}</span>`;
                    ul.appendChild(li);
                });

                document.getElementById('valTopHotel').textContent = data.panels.top_hotel;
                document.getElementById('valPopularRoom').textContent = data.panels.popular_room;

                // Populate Recent Bookings Table
                const tbody = document.getElementById('recentBookingsTable');
                tbody.innerHTML = '';
                if (data.panels.recent_bookings.length > 0) {
                    data.panels.recent_bookings.forEach(b => {
                        const tr = document.createElement('tr');
                        let badgeClass = '';
                        if (b.status === 'Booked') badgeClass = 'trend-up';
                        else if (b.status === 'Cancelled') badgeClass = 'trend-down';
                        else badgeClass = 'trend-neutral';
                        
                        tr.innerHTML = `
                            <td><strong>${b.guest_name}</strong></td>
                            <td>${b.hotel}</td>
                            <td>${b.check_in}</td>
                            <td>${b.check_out}</td>
                            <td><span class="trend-indicator ${badgeClass}" style="margin-top:0;">${b.status}</span></td>
                        `;
                        tbody.appendChild(tr);
                    });
                } else {
                    tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--subtext); padding: 2rem;">No recent bookings found.</td></tr>';
                }

                // Render Charts
                initChart('chartRevenueTrend', 'line', {
                    labels: data.charts.revenue_trend.map(d => d.label),
                    datasets: [{
                        label: 'Revenue',
                        data: data.charts.revenue_trend.map(d => d.value),
                        borderColor: '#4F46E5',
                        backgroundColor: 'rgba(79, 70, 229, 0.1)',
                        borderWidth: 2,
                        tension: 0.4,
                        fill: true
                    }]
                }, { responsive: true, maintainAspectRatio: false }, data.charts.revenue_trend.length === 0);

                initChart('chartBookingTrend', 'bar', {
                    labels: data.charts.booking_trend.map(d => d.label),
                    datasets: [{
                        label: 'Bookings',
                        data: data.charts.booking_trend.map(d => d.value),
                        backgroundColor: '#10B981',
                        borderRadius: 4
                    }]
                }, { responsive: true, maintainAspectRatio: false }, data.charts.booking_trend.length === 0);

                initChart('chartRoomStatus', 'doughnut', {
                    labels: data.charts.room_status.map(d => d.label),
                    datasets: [{
                        data: data.charts.room_status.map(d => d.value),
                        backgroundColor: ['#10B981', '#3B82F6', '#E2E8F0'],
                        borderWidth: 0
                    }]
                }, { responsive: true, maintainAspectRatio: false, cutout: '70%' }, data.charts.room_status.every(d => d.value === 0));

                initChart('chartTopHotels', 'bar', {
                    labels: data.charts.top_hotels.map(d => d.label),
                    datasets: [{
                        label: 'Bookings',
                        data: data.charts.top_hotels.map(d => d.value),
                        backgroundColor: '#4F46E5',
                        borderRadius: 4
                    }]
                }, { responsive: true, maintainAspectRatio: false, indexAxis: 'y' }, data.charts.top_hotels.length === 0);

                initChart('chartRoomTypes', 'pie', {
                    labels: data.charts.room_types.map(d => d.label),
                    datasets: [{
                        data: data.charts.room_types.map(d => d.value),
                        backgroundColor: ['#EC4899', '#8B5CF6', '#F59E0B', '#10B981', '#3B82F6'],
                        borderWidth: 0
                    }]
                }, { responsive: true, maintainAspectRatio: false }, data.charts.room_types.length === 0);

                initChart('chartOccupancy', 'doughnut', {
                    labels: ['Occupied', 'Available'],
                    datasets: [{
                        data: [data.summary.occupancy_rate, 100 - data.summary.occupancy_rate],
                        backgroundColor: ['#4F46E5', '#E2E8F0'],
                        borderWidth: 0
                    }]
                }, { 
                    responsive: true, 
                    maintainAspectRatio: false, 
                    cutout: '80%', 
                    rotation: -90, 
                    circumference: 180,
                    plugins: { tooltip: { enabled: false } }
                }, data.summary.total_rooms === 0);

            })
            .catch(err => {
                console.error("Error fetching analytics data:", err);
                document.getElementById('btnRefresh').disabled = false;
                document.getElementById('btnRefresh').innerHTML = '<svg viewBox="0 0 24 24" fill="none" style="width:1rem;height:1rem;margin-right:0.4rem;"><path d="M4 4V9H4.58152M19.9381 11C19.446 7.05369 16.0796 4 12 4C8.64262 4 5.76829 6.06817 4.58152 9M4.58152 9H9M20 20V15H19.4185M19.4185 15C18.2317 17.9318 15.3574 20 12 20C7.92038 20 4.55399 16.9463 4.06189 13M19.4185 15H15" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>Refresh';
            });
    };

    document.getElementById('btnRefresh').addEventListener('click', loadAnalytics);
    document.getElementById('filterPeriod').addEventListener('change', loadAnalytics);
    document.getElementById('filterHotel').addEventListener('change', loadAnalytics);

    document.getElementById('btnOpenExportModal').addEventListener('click', () => {
        document.getElementById('modalExportAnalytics').classList.add('active');
    });

    window.addEventListener('DOMContentLoaded', loadAnalytics);
</script>
<style>
@keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
}
</style>
{% endblock %}
"""

with open('templates/admin/analytics.html', 'w', encoding='utf-8') as f:
    f.write(html_content)

print("analytics.html patched successfully.")
