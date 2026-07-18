# 📋 Setup Guide - Hotel Booking Application

Panduan lengkap untuk setup project Hotel Booking ini dari awal.

## 📦 Prerequisites

Sebelum mulai, pastikan sudah terinstall:

1. **Python 3.8 atau lebih tinggi**
   - Download: https://www.python.org/downloads/
   - Verifikasi: `python --version` atau `python3 --version`

2. **MySQL Server**
   - Download: https://dev.mysql.com/downloads/mysql/
   - Atau gunakan XAMPP/Laragon (lebih mudah untuk Windows)
   - Pastikan MySQL service sudah running

3. **Git** (untuk clone repository)
   - Download: https://git-scm.com/downloads

---

## 🚀 Langkah-langkah Setup

### Step 1: Clone atau Download Project

```bash
# Clone via Git
git clone <repository-url>
cd booking-hotels

# Atau download ZIP dan extract, lalu masuk ke folder project
cd booking-hotels
```

---

### Step 2: Setup Virtual Environment

Virtual environment berfungsi untuk isolasi dependencies Python.

**Windows:**
```bash
python -m venv venv
.\venv\Scripts\activate
```

**Mac/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

Jika berhasil, akan muncul `(venv)` di awal command prompt.

---

### Step 3: Install Dependencies

Install semua package yang diperlukan:

```bash
pip install -r requirements.txt
```

Dependencies yang akan terinstall:
- Flask (web framework)
- mysql-connector-python (database connector)
- Flask-Session (session management)
- python-dotenv (environment variables)
- Werkzeug (security utilities)

---

### Step 4: Setup Database Configuration

1. **Copy file `.env.example` menjadi `.env`:**

   **Windows:**
   ```bash
   copy .env.example .env
   ```

   **Mac/Linux:**
   ```bash
   cp .env.example .env
   ```

2. **Edit file `.env` dengan text editor:**

   ```env
   # Flask Configuration
   FLASK_APP=app.py
   FLASK_ENV=development
   FLASK_DEBUG=1
   SECRET_KEY=ganti_dengan_random_string_yang_panjang
   
   # Database Configuration
   DB_HOST=localhost
   DB_USER=root
   DB_PASSWORD=password_mysql_kamu
   DB_NAME=hotel_booking
   
   # Google OAuth (Optional - kosongkan jika tidak pakai)
   GOOGLE_CLIENT_ID=
   GOOGLE_CLIENT_SECRET=
   ```

   **PENTING:**
   - Ganti `DB_PASSWORD` dengan password MySQL kamu
   - Ganti `SECRET_KEY` dengan string random yang panjang
   - Jika pakai XAMPP/Laragon default, biasanya password kosong

---

### Step 5: Pastikan MySQL Server Running

**XAMPP:**
- Buka XAMPP Control Panel
- Start Apache dan MySQL

**Laragon:**
- Start All

**MySQL Native:**
- Windows: Service MySQL harus running
- Mac/Linux: `sudo service mysql start`

Verifikasi MySQL bisa diakses:
```bash
mysql -u root -p
# Masukkan password MySQL kamu
```

---

### Step 6: Initialize Database

Jalankan script untuk membuat database, tables, dan insert data provinces & cities:

```bash
python init_db.py
```

Script ini akan:
1. Create database `hotel_booking`
2. Create semua tables yang diperlukan:
   - `users` (user accounts)
   - `provinces` (34 provinsi)
   - `cities` (489 kota/kabupaten)
   - `hotels` (data hotel)
   - `hotel_images` (multiple images per hotel)
   - `rooms` (data kamar)
   - `room_images` (multiple images per room)
   - `bookings` (transaksi booking)
   - `waiting_lists` (daftar tunggu)
3. Insert data 34 provinces dan 489 cities Indonesia

**Output yang diharapkan:**
```
Initializing database...
✓ Schema created successfully
✓ Seed data inserted successfully

Database initialization completed!
```

---

### Step 7: Create Uploads Directory

Buat folder untuk menyimpan gambar upload:

**Windows:**
```bash
mkdir static\uploads
mkdir static\uploads\hotels
mkdir static\uploads\rooms
```

**Mac/Linux:**
```bash
mkdir -p static/uploads/hotels
mkdir -p static/uploads/rooms
```

---

### Step 8: Run Application

Jalankan aplikasi Flask:

```bash
python app.py
```

**Output yang diharapkan:**
```
 * Serving Flask app 'app'
 * Debug mode: on
WARNING: This is a development server. Do not use it in a production deployment.
 * Running on http://127.0.0.1:5000
Press CTRL+C to quit
```

Buka browser dan akses: **http://localhost:5000**

---

## 👤 Create Admin Account

Untuk akses admin dashboard, ada 2 cara:

### Cara 1: Register User Biasa, Lalu Ubah Role

1. Register account baru via web: http://localhost:5000/register
2. Login ke MySQL:
   ```bash
   mysql -u root -p
   ```
3. Ubah role user menjadi admin:
   ```sql
   USE hotel_booking;
   UPDATE users SET role = 'admin' WHERE username = 'username_kamu';
   ```

### Cara 2: Insert Admin Langsung via SQL

```sql
USE hotel_booking;

INSERT INTO users (username, password_hash, email, role) 
VALUES (
  'admin', 
  'scrypt:32768:8:1$fCEQvj5TBnqpMRqK$1c85f8e3c8f8e0f2e3c8f8e0f2e3c8f8e0f2e3c8f8e0f2e3c8f8e0f2e3c8f8e0f2e3c8f8e0f2e3c8f8e0f2e3c8',
  'admin@example.com',
  'admin'
);
```

Login dengan:
- Username: `admin`
- Password: `admin123`

**PENTING:** Segera ganti password setelah login pertama kali!

---

## 🔧 Troubleshooting

### Error: "Access denied for user 'root'@'localhost'"
- Pastikan password MySQL di `.env` sudah benar
- Cek MySQL service sudah running

### Error: "No module named 'flask'"
- Pastikan virtual environment sudah diaktifkan `(venv)` muncul di prompt
- Jalankan lagi: `pip install -r requirements.txt`

### Error: "Can't connect to MySQL server"
- Pastikan MySQL service running
- Cek `DB_HOST` di `.env` (biasanya `localhost` atau `127.0.0.1`)

### Error: "seed_data.sql not found"
- Jalankan: `python generate_seed_data.py` dulu untuk generate file seed data
- Lalu jalankan lagi: `python init_db.py`

### Port 5000 sudah dipakai
- Edit `app.py`, ubah port:
  ```python
  app.run(debug=True, port=5001)
  ```

---

## 📁 File Structure (Important Files)

```
booking-hotels/
├── .env                    # Environment variables (JANGAN DICOMMIT!)
├── .env.example            # Template untuk .env
├── requirements.txt        # Python dependencies
├── schema.sql              # Database schema
├── seed_data.sql           # Master data (provinces & cities)
├── init_db.py              # Script initialize database
├── app.py                  # Main Flask application
├── db.py                   # Database connection
├── utils.py                # Helper functions
├── routes/                 # Application routes
│   ├── auth.py            # Authentication
│   ├── main.py            # Public pages
│   ├── admin.py           # Admin dashboard
│   └── booking.py         # Booking logic
├── templates/              # HTML templates
└── static/                 # CSS, JS, Images
    └── uploads/           # Uploaded images
```

---

## ✅ Checklist Setup

Pastikan semua sudah done:

- [ ] Python 3.8+ terinstall
- [ ] MySQL Server terinstall dan running
- [ ] Virtual environment sudah dibuat dan diaktifkan
- [ ] Dependencies terinstall (`pip install -r requirements.txt`)
- [ ] File `.env` sudah dibuat dan dikonfigurasi
- [ ] Database sudah diinisialisasi (`python init_db.py`)
- [ ] Folder `static/uploads` sudah dibuat
- [ ] Aplikasi bisa dijalankan (`python app.py`)
- [ ] Browser bisa akses http://localhost:5000
- [ ] Admin account sudah dibuat

---

## 🎯 Next Steps

Setelah setup berhasil:

1. Login sebagai admin
2. Tambah data hotel via Admin Dashboard
3. Tambah kamar untuk setiap hotel
4. Upload gambar hotel dan kamar
5. Test booking sebagai customer

---

## 📞 Need Help?

Jika ada masalah, cek:
1. Error message di terminal
2. Browser console (F12)
3. MySQL error logs

Good luck! 🚀
