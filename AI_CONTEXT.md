# 🤖 AI Context - Hotel Booking Application

**Project:** Hotel Booking Web Application  
**Tech Stack:** Flask (Python), MySQL, Jinja2, Vanilla CSS/JS  
**Architecture:** Server-Side Rendering (SSR) with AJAX for dynamic features

---

## 🎯 Project Overview

Aplikasi booking hotel dengan fitur:

- Customer: Browse hotels, search by location, book rooms
- Admin: Manage hotels/rooms, view bookings, upload images
- Auth: Local login/register + Google OAuth ready

---

## 🏗️ Architecture & Flow

### **Frontend-Backend Communication**

```
User Browser
    ↓
Flask Routes (Server-Side Rendering)
    ↓
Jinja2 Templates (Generate HTML)
    ↓
MySQL Database
    ↓
Return Complete HTML Page
```

### **AJAX for Dynamic Features**

```
User Action (Select Province)
    ↓
JavaScript Fetch API
    ↓
Flask API Route (/get_cities/<id>)
    ↓
JSON Response
    ↓
JavaScript Updates DOM (Populate Cities)
```

**NOT a SPA! Traditional multi-page application with server-side rendering.**

---

## 📂 Project Structure

```
booking-hotels/
├── app.py                      # Main Flask application entry
├── db.py                       # Database connection & helpers
├── utils.py                    # File upload, auth decorators
├── extensions.py               # Flask extensions (Session, OAuth)
│
├── routes/
│   ├── auth.py                # Login, register, logout
│   ├── main.py                # Homepage, rooms search, about, contact
│   ├── booking.py             # Booking flow, payment, invoice
│   └── admin.py               # Admin dashboard, hotel/room CRUD
│
├── templates/                  # Jinja2 HTML templates
│   ├── base.html              # Base layout
│   ├── index.html             # Homepage
│   ├── rooms.html             # Room search & listing
│   ├── booking_form.html      # Booking form
│   ├── my_bookings.html       # User booking history
│   ├── login.html, register.html
│   └── admin/                 # Admin templates
│       ├── dashboard.html
│       ├── hotels.html
│       ├── rooms.html
│       └── bookings.html
│
├── static/
│   ├── css/style.css          # All styling (no framework)
│   └── uploads/               # Uploaded images
│       ├── hotels/
│       └── rooms/
│
├── schema.sql                  # Database schema (9 tables)
├── seed_data.sql              # Master data (provinces, cities)
└── init_db.py                 # Database initialization
```

---

## 🗄️ Database Schema

### **Key Tables:**

**1. users**

- `id`, `username`, `password_hash`, `email`, `role` (customer/admin)
- `google_id`, `auth_provider` (local/google)

**2. provinces** (Master data)

- `province_id`, `province` (34 provinces)

**3. cities** (Master data)

- `city_id`, `province_id`, `city_name` (489 cities)

**4. hotels**

- `id`, `name`, `location`, `description`, `province_id`, `city_id`
- NO `image_url` (migrated to separate table)

**5. hotel_images** (One-to-Many)

- `id`, `hotel_id`, `image_url`
- **CASCADE DELETE**: Deleting hotel deletes images

**6. rooms**

- `id`, `hotel_id`, `room_number`, `room_type`, `price`

**7. room_images** (One-to-Many)

- `id`, `room_id`, `image_url`
- **CASCADE DELETE**: Deleting room deletes images

**8. bookings**

- `id`, `user_id`, `room_id`, `guest_name`, `contact_number`
- `check_in`, `check_out`, `payment_method`
- `status` (Pending/Booked/Cancelled), `created_at`

**9. waiting_lists**

- `id`, `user_id`, `room_id`, `check_in`, `check_out`

**10. reviews**

- `id`, `hotel_id`, `user_id`, `booking_id`, `rating`, `comment`, `created_at`
- **CASCADE DELETE**: Deleting hotel, user, or booking deletes the review

---

## 🔄 Critical Flows

### **1. Room Search & Availability**

**Route:** `GET /rooms?province_id=X&city_id=Y&check_in=...&check_out=...`

**Logic:**

```python
# routes/main.py::rooms()

# 1. Get filter params
province_id = request.args.get('province_id')
city_id = request.args.get('city_id')
check_in = request.args.get('check_in')
check_out = request.args.get('check_out')

# 2. Build query with availability check
query = """
    SELECT DISTINCT h.*, r.id as room_id, r.room_type, r.price
    FROM hotels h
    JOIN rooms r ON h.id = r.hotel_id
    WHERE h.province_id = %s AND h.city_id = %s
    AND r.id NOT IN (
        SELECT room_id FROM bookings
        WHERE status != 'Cancelled'
        AND NOT (check_out <= %s OR check_in >= %s)
    )
"""

# 3. Fetch hotel images (separate query)
# 4. Render templates/rooms.html with data
```

**⚠️ Known Issues:**

- Availability logic might have edge cases (overlapping dates)

---

### **2. Hotel Listing & Infinite Scroll (AJAX)**

**Route:** `GET /api/hotels?city_id=X&page=Y`

**Logic:**

```python
# routes/main.py::api_hotels()
# 1. Base query for hotels in a city
# 2. Add limits and offset based on `page` (per_page = 14)
# 3. Retrieve min_price and cover image for each hotel
# 4. Return JSON response
```

**Frontend Interaction (`city_hotels.html`):**

- Uses `IntersectionObserver` to detect when the user scrolls near the bottom of the page.
- Injects a Skeleton Loader animation while fetching data.
- Fetches the next page of hotels via `/api/hotels` and appends them to the DOM without refreshing the page.

---

### **2. Dynamic Location Filter (AJAX)**

**User Flow:**

```
1. User selects province dropdown
2. JavaScript triggers onChange event
3. Fetch cities for selected province
4. Populate city dropdown dynamically
```

**Frontend (templates/rooms.html):**

```javascript
document.getElementById("province_id").addEventListener("change", function () {
  const provinceId = this.value;

  // Fetch cities via AJAX
  fetch(`/get_cities/${provinceId}`)
    .then((response) => response.json())
    .then((cities) => {
      const citySelect = document.getElementById("city_id");
      citySelect.innerHTML = '<option value="">All Cities</option>';

      cities.forEach((city) => {
        citySelect.innerHTML += `<option value="${city.city_id}">${city.city_name}</option>`;
      });
    });
});
```

**Backend (routes/main.py):**

```python
@main_bp.route('/get_cities/<province_id>')
def get_cities(province_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT city_id, city_name FROM cities WHERE province_id = %s ORDER BY city_name",
        (province_id,)
    )
    cities = cursor.fetchall()

    cursor.close()
    conn.close()

    return jsonify(cities)  # Return JSON
```

---

### **3. Image Upload & Storage**

**Upload Flow:**

```
Admin uploads hotel image
    ↓
POST /admin/add_hotel (FormData with files)
    ↓
utils.py::save_file(file, folder)
    - Generate unique filename (secure_filename + timestamp)
    - Save to static/uploads/{folder}/
    - Return filename
    ↓
Insert into hotel_images table
    INSERT INTO hotel_images (hotel_id, image_url) VALUES (?, ?)
    ↓
Physical file stored, DB record created
```

**Delete Flow:**

```
Admin deletes hotel
    ↓
DELETE FROM hotels WHERE id = ?
    ↓
CASCADE DELETE: hotel_images records auto-deleted
    ↓
utils.py::cleanup_unused_images('hotels')
    - Find orphaned files (file exists but no DB record)
    - Delete physical files
```

**⚠️ Known Issues:**

- `cleanup_unused_images()` might NOT be called automatically
- Potential orphaned files if delete fails midway
- No file size validation (could upload huge images)

---

### **4. Booking Flow**

**Complete Flow:**

```
1. User clicks "Book Room" on /rooms page
   → GET /booking/<room_id>

2. Display booking form (routes/booking.py::booking_form)
   → Check room availability for date range
   → Render templates/booking_form.html

3. User submits form
   → POST /booking/<room_id>
   → Validate dates
   → Check availability again
   → Insert into bookings table (status='Pending')
   → Redirect to /pay/<booking_id>

4. Payment confirmation page
   → GET /pay/<booking_id>
   → Display payment details
   → User confirms payment

5. Confirm payment
   → POST /pay/<booking_id>
   → Update booking status = 'Booked'
   → Redirect to /invoice/<booking_id>

6. Invoice/Receipt
   → GET /invoice/<booking_id>
   → Display invoice with booking details
```

**⚠️ Known Issues:**

- Pending bookings expire after 15 minutes (db.py::cleanup_expired_bookings)
- BUT cleanup function might NOT run automatically
- Race condition: Multiple users booking same room at same time

---

### **5. Admin Dashboard Stats**

**Route:** `GET /admin/dashboard`

**Logic:**

```python
# routes/admin.py::dashboard()

# 1. Count total hotels
cursor.execute("SELECT COUNT(*) as count FROM hotels")
total_hotels = cursor.fetchone()['count']

# 2. Count total rooms
cursor.execute("SELECT COUNT(*) as count FROM rooms")
total_rooms = cursor.fetchone()['count']

# 3. Count total bookings
cursor.execute("SELECT COUNT(*) as count FROM bookings WHERE status = 'Booked'")
total_bookings = cursor.fetchone()['count']

# 4. Calculate total revenue
cursor.execute("""
    SELECT SUM(r.price * DATEDIFF(b.check_out, b.check_in)) as revenue
    FROM bookings b
    JOIN rooms r ON b.room_id = r.id
    WHERE b.status = 'Booked'
""")
total_revenue = cursor.fetchone()['revenue'] or 0

# 5. Get recent bookings (last 10)
cursor.execute("""
    SELECT b.*, u.username, r.room_type, h.name as hotel_name
    FROM bookings b
    JOIN users u ON b.user_id = u.id
    JOIN rooms r ON b.room_id = r.id
    JOIN hotels h ON r.hotel_id = h.id
    ORDER BY b.created_at DESC
    LIMIT 10
""")
recent_bookings = cursor.fetchall()

# 6. Render dashboard
return render_template('admin/dashboard.html',
    total_hotels=total_hotels,
    total_rooms=total_rooms,
    total_bookings=total_bookings,
    total_revenue=total_revenue,
    recent_bookings=recent_bookings
)
```

---

## 🐛 Known Issues & Potential Bugs

### **Issue 1: Booking Availability Race Condition**

**Status:** ✅ RESOLVED
- **Fix Applied:** Added `SELECT ... FOR UPDATE` row-level locking on the `rooms` table in `routes/booking.py` before inserting new bookings to prevent double bookings.

---

### **Issue 2: Expired Bookings Not Auto-Cleaned**

**Status:** ✅ RESOLVED
- **Fix Applied:** `cleanup_expired_bookings(cursor)` is now explicitly called on critical routes (`/rooms`, `/book`, `/my-bookings`) to ensure stale pending bookings are cancelled lazily before checking availability.

---

### **Issue 3: Orphaned Image Files**

**Status:** ✅ RESOLVED
- **Fix Applied:** Physical image files are now safely deleted via `delete_image_file()` iteratively before running `DELETE CASCADE` operations in `routes/admin.py` for both hotels and rooms.

---

### **Issue 4: No File Upload Validation**

**Status:** ✅ RESOLVED
- **Fix Applied:** `MAX_FILE_SIZE` restricted to 5MB in both Flask app config (`app.py`) and manual check (`utils.py`). Extensions restricted to valid image formats (`.jpg`, `.png`, `.webp`).

---

### **Issue 5: Session Expiry Not Handled**

**Problem:**

- Flask session might expire
- User not redirected to login properly
- No refresh token mechanism

**Location:** `utils.py::login_required()`

**Fix Needed:** Add session timeout handling

---

## 🔧 Common Tasks for Bug Fixes

### **Task 1: Fix Booking Availability Check**

**File:** `routes/booking.py`

**Current Logic:**

```python
# Check if room already booked
cursor.execute("""
    SELECT * FROM bookings
    WHERE room_id = %s
    AND status != 'Cancelled'
    AND NOT (check_out <= %s OR check_in >= %s)
""", (room_id, check_in, check_out))

if cursor.fetchone():
    flash('Room not available for selected dates')
    return redirect('/rooms')
```

**Suggested Fix:** Add database-level constraint or use transactions

---

### **Task 2: Auto-Cleanup Expired Bookings**

**File:** `routes/booking.py` (or create middleware)

**Add this before booking queries:**

```python
def booking_form(room_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # CALL CLEANUP HERE
    cleanup_expired_bookings(cursor)
    conn.commit()

    # Rest of code...
```

---

### **Task 3: Add Image Upload Validation**

**File:** `utils.py`

**Current:**

```python
def save_file(file, folder):
    filename = secure_filename(file.filename)
    # No validation!
    filepath = os.path.join('static', 'uploads', folder, filename)
    file.save(filepath)
    return filename
```

**Fix:**

```python
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

def save_file(file, folder):
    # Validate file type
    if not allowed_file(file.filename):
        raise ValueError('Invalid file type')

    # Validate file size
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    if file_size > MAX_FILE_SIZE:
        raise ValueError('File too large')
    file.seek(0)

    # Save file
    filename = secure_filename(file.filename)
    filepath = os.path.join('static', 'uploads', folder, filename)
    file.save(filepath)
    return filename
```

---

### **Task 4: Call Image Cleanup After Delete**

**File:** `routes/admin.py`

**After deleting hotel:**

```python
@admin_bp.route('/admin/delete_hotel/<int:hotel_id>', methods=['POST'])
def delete_hotel(hotel_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM hotels WHERE id = %s", (hotel_id,))
    conn.commit()

    # ADD THIS
    cleanup_unused_images('hotels')
    cleanup_unused_images('rooms')  # In case rooms deleted too (CASCADE)

    cursor.close()
    conn.close()

    flash('Hotel deleted successfully')
    return redirect('/admin/hotels')
```

---

## 🎯 Guidelines for AI Assistant

### **DO:**

- ✅ Maintain Flask + Jinja2 structure (no React, Vue, etc.)
- ✅ Use existing `db.py::get_db_connection()` for DB access
- ✅ Follow existing route patterns (Blueprints)
- ✅ Use `flash()` for user messages
- ✅ Keep CSS in `static/css/style.css` (no inline styles)
- ✅ Use `login_required` and `admin_required` decorators
- ✅ Follow existing template structure (extend base.html)
- ✅ **ALWAYS update this AI_CONTEXT.md file** after completing a task or preparing a commit, so the context is always fresh.
- ✅ **ALWAYS update `schema.sql`** whenever there is a change to the database structure (adding tables, altering columns) so the team stays synced.

### **DON'T:**

- ❌ Don't introduce frontend frameworks (React, Vue, Angular)
- ❌ Don't change database schema without migration plan
- ❌ Don't remove existing functionality
- ❌ Don't use inline styles or JS (keep in separate files)
- ❌ Don't bypass authentication decorators
- ❌ Don't hardcode credentials or secrets

### **When Fixing Bugs:**

1. Identify root cause
2. Propose minimal fix (follow existing patterns)
3. Consider side effects (CASCADE deletes, etc.)
4. Test edge cases (date overlaps, empty data, etc.)
5. Update comments in code

### **When Adding Features:**

1. Check if functionality already exists
2. Follow existing code style and structure
3. Add to appropriate Blueprint (routes/\*.py)
4. Create/update templates in templates/
5. Update CSS in static/css/style.css if needed
6. Consider security (SQL injection, XSS, file upload)

---

## 🚦 Testing Checklist

Before marking task complete:

**Frontend:**

- [ ] Page loads without errors (check browser console)
- [ ] Forms submit correctly
- [ ] Flash messages display properly
- [ ] AJAX calls work (check Network tab)
- [ ] Responsive on mobile (basic check)

**Backend:**

- [ ] Database queries execute (no SQL errors)
- [ ] Data saved correctly to database
- [ ] Redirects work after POST requests
- [ ] Error handling (try invalid inputs)
- [ ] Session/auth checks work

**Security:**

- [ ] SQL queries use parameterized statements (no string concat)
- [ ] File uploads validated (type, size)
- [ ] Auth decorators applied to protected routes
- [ ] No sensitive data in URLs or logs

---

## 📞 Help Resources

- **Setup issues:** See `SETUP_GUIDE.md` - **File reference:** See `PROJECT_FILES.md`
- **Code explanation:** See `penjelasan_kode.md`
- **Database schema:** See `schema.sql`
- **Migration notes:** See `MIGRATION_NOTES.md`

---

## ✅ Quick Reference

### **Run Application:**

```bash
source venv/Scripts/activate  # Git Bash
python app.py
```

### **Database Operations:**

```bash
python init_db.py           # Initialize DB
python verify_setup.py      # Verify setup
mysql -u root -p hotel_booking  # Access DB
```

### **Common Queries:**

```sql
-- Check bookings
SELECT * FROM bookings WHERE status = 'Pending';

-- Check hotel images
SELECT h.name, COUNT(hi.id) as image_count
FROM hotels h
LEFT JOIN hotel_images hi ON h.id = hi.hotel_id
GROUP BY h.id;

-- Check room availability
SELECT r.*, COUNT(b.id) as active_bookings
FROM rooms r
LEFT JOIN bookings b ON r.id = b.room_id AND b.status != 'Cancelled'
GROUP BY r.id;
```

---

## 👥 Team Modules & Ownership (Pembagian Tim)

Proyek ini dirancang agar dapat dikerjakan secara paralel oleh 3 orang tanpa menimbulkan _merge conflict_ pada Git. Berikut adalah pembagian modul dan kepemilikannya:

### **Modul 1: Akun & Keamanan (Modul Auth)**

- **Fokus:** Autentikasi, Profil Pengguna, dan Keamanan.
- **Wilayah Kode (Ownership):**
  - `routes/auth.py`
  - `templates/auth/` (atau file-file login/register)
- **Tabel Database:** `users`
- **Next Enhancements:** Halaman Profil Pengguna (`/profile`), Fitur Lupa Password, Verifikasi Email pendaftaran.

### **Modul 2: Katalog & Admin (Modul Inventory)**

- **Fokus:** Dasbor Admin, Manajemen Hotel/Kamar, dan _File System_ (Upload/Hapus Gambar).
- **Wilayah Kode (Ownership):**
  - `routes/admin.py`
  - `utils.py` (Fungsi unggah & hapus gambar fisik, Decorators)
  - `templates/admin/`
- **Tabel Database:** `hotels`, `rooms`, `hotel_images`, `room_images`, `provinces`, `cities`.
- **Next Enhancements:** Grafik/Statistik di Dasbor, _Soft Delete_ untuk hotel, Fitur Pencarian/Pagination di tabel admin, Kompresi gambar dengan library Pillow.

### **Modul 3: Pencarian & Transaksi (Modul Booking)**

- **Fokus:** Tampilan pelanggan, Filter Ketersediaan, dan Proses Pemesanan (Checkout).
- **Wilayah Kode (Ownership):**
  - `routes/main.py`
  - `routes/booking.py`
  - `templates/index.html`, `templates/rooms.html`, `templates/booking_form.html`, `templates/city_hotels.html`, `templates/pay.html`, `templates/invoice.html` dll.
- **Tabel Database:** `bookings`, `waiting_lists`, `reviews`.
- **Next Enhancements:** Integrasi API Eksternal OTA (Jika diperlukan).

* **Recent Updates:**
  - Pembersihan _inline-style_ di seluruh HTML Modul 3 dan standarisasi CSS.
  - Implementasi _Horizontal Scroll_ ala Netflix di Beranda (`index.html`).
  - Implementasi _Infinite Scroll_ (AJAX API & IntersectionObserver) dengan _Skeleton Loader_ dan Filter Kriteria (`city_hotels.html`).
  - Redesign detail hotel dengan *Masonry Gallery* UI dan Sistem Ulasan Pengguna (`rooms.html`).
  - Integrasi UI Mock Midtrans Snap untuk Gateway Pembayaran (`pay.html`).
  - Implementasi ekspor Invoice ke PDF dengan `html2pdf.js` (`invoice.html`).

---

**Last Updated:** July 22, 2026  
**Version:** 1.4  
**Status:** Active Development (Distributed to 3 Team Members)
