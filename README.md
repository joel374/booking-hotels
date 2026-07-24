# Booking Hotels Web Application

Aplikasi pemesanan hotel komprehensif berbasis web yang memungkinkan pengguna untuk mencari, memfilter, dan memesan kamar hotel secara *real-time*. Dilengkapi dengan sistem otentikasi aman, dasbor manajemen untuk admin, laporan dinamis, serta notifikasi email otomatis.

---

## 🛠️ Tech Stack

Aplikasi ini dibangun menggunakan arsitektur *Server-Side Rendering* (SSR) yang diperkaya dengan AJAX untuk interaktivitas dinamis. Teknologi yang digunakan:

- **Bahasa Pemrograman**: Python 3.11
- **Web Framework**: Flask (lengkap dengan Blueprint routing)
- **Database**: MySQL 8.0 (diakses menggunakan `mysql-connector-python`)
- **Templating Engine**: Jinja2
- **Frontend**: Vanilla HTML5, CSS3, dan JavaScript (tanpa framework berat, fokus pada performa)
- **Authentication**: `Werkzeug.security` (hashing) dan `Authlib` (Google OAuth 2.0)
- **Session Management**: `Flask-Session` (menyimpan sesi pengguna di sisi server)
- **Email Service**: `Flask-Mail` (pengiriman SMTP otomatis)
- **PDF Generation**: `html2pdf.js` (client-side) dan `reportlab` (server-side untuk admin)
- **Deployment**: Docker & Docker Compose (`Gunicorn` HTTP server)

---

## 🗄️ Database Schema

Sistem ini memiliki 9 entitas utama yang saling berelasi:

1. **provinces & cities**: Master data lokasi untuk fitur *filtering* dinamis. (`cities.province_id` -> `provinces.province_id`)
2. **users**: Menyimpan data akun pelanggan dan admin. Mendukung autentikasi lokal (dengan *password hash*) maupun Google OAuth.
3. **hotels**: Informasi utama hotel (nama, alamat, rating, lokasi). Memiliki status *Soft Delete* (`is_deleted`).
4. **hotel_images**: Relasi *One-to-Many* ke `hotels` untuk menyimpan multi-gambar galeri hotel.
5. **rooms**: Menyimpan variasi kamar, harga, tipe kamar per hotel. (`rooms.hotel_id` -> `hotels.id`).
6. **room_images**: Relasi *One-to-Many* ke `rooms` untuk menyimpan foto spesifik per tipe kamar.
7. **bookings**: Tabel inti transaksi pemesanan. Berelasi dengan `users` dan `rooms`. Menyimpan tanggal inap, detail tamu, metode pembayaran, dan *Status* (`Pending`, `Booked`, `Cancelled`).
8. **waiting_lists**: Menyimpan data antrean pengguna (*Waitlist*) yang ingin memesan kamar yang sedang penuh pada tanggal tertentu.
9. **reviews**: Ulasan pengguna pasca-inap. Berisi *rating* 1-5 bintang dan komentar. Berelasi unik dengan `booking_id` untuk mencegah *double review*.

---

## 🌐 Rute & API Endpoints

Aplikasi ini dibagi menjadi beberapa Blueprint: `main`, `auth`, `booking`, dan `admin`.

### **Main / Public Routes**
- `GET /` : Halaman Beranda (Hero section, pencarian, dan rekomendasi awal).
- `GET /city/<id>` : Halaman daftar hotel per-kota.
- `GET /api/hotels` : Endpoint AJAX *Infinite Scroll* memuat daftar hotel berdasarkan kriteria filter & paginasi.
- `GET /api/search` : Endpoint AJAX *Global Live Search Autocomplete* untuk mencari hotel berdasar *keyword*.
- `GET /hotel/<id>` : Halaman Detail Hotel (menampilkan galeri Masonry, ulasan, daftar kamar yang tersedia).
- `GET /about` & `GET /contact` : Halaman statis profil perusahaan dan form kontak.

### **Authentication Routes (`/auth`)**
- `GET, POST /login` & `/register` : Proses autentikasi standar (Sign up & Sign in).
- `GET /login/google` & `/login/google/authorize` : Proses Single Sign-On (SSO) via Google OAuth.
- `GET, POST /profile` : Dasbor manajemen profil pengguna dan pusat notifikasi personal.
- `GET, POST /forgot-password` & `/reset-password/<token>` : Pemulihan kata sandi via token email.
- `GET /logout` : Menghapus *session* pengguna.

### **Booking & Transactions (`/booking`)**
- `GET, POST /book/<room_id>` : Form *Checkout*. (Melakukan verifikasi ketersediaan kamar, mengunci baris DB).
- `GET, POST /pay/<booking_id>` : Halaman simulasi *Payment Gateway* Midtrans Snap dengan timer 15-menit.
- `GET /invoice/<booking_id>` : Generate Digital Invoice pasca pembayaran sukses.
- `GET /my-bookings` : Halaman riwayat pemesanan pengguna.
- `POST /cancel/<booking_id>` : Membatalkan pesanan dan otomatis memicu *Waitlist Broadcast Alert*.
- `POST /waitlist/<room_id>` : Pengguna bergabung ke daftar antrean kamar penuh.
- `POST /review/<booking_id>` : Form *submit* ulasan untuk hotel pasca *check-out*.

### **Admin Dashboard (`/admin`)**
- `GET /dashboard` & `/analytics` : Statistik ringkasan pendapatan, okupansi, dan grafik *chart*.
- `GET, POST /hotels` & `/rooms` : Halaman manajemen CRUD Data Master (tambah, edit, *soft delete* hotel dan kamar) beserta upload *multi-image*.
- `GET, POST /bookings` : Manajemen transaksi dari semua pelanggan.
- `GET /reports`, `POST /api/reports/preview` : Modul pembuatan Laporan Keuangan Dinamis.
- `POST /api/reports/download_pdf` & `/api/reports/send_email` : Endpoint untuk mengekspor Laporan ke PDF dan mengirimnya via Email.

---

## 🔄 Alur Aplikasi (Application Flow)

Berikut adalah *Business Logic* murni berdasarkan eksekusi sistem dari sisi *Customer*:

### 1. Pencarian dan Filter
- Pengguna tiba di `main.index` (`/`). Mereka dapat mengetikkan kata kunci pencarian di *navbar* (menembak `/api/search` secara *real-time*) atau memilih Provinsi & Kota secara hierarkis (AJAX mengubah Kota saat Provinsi dipilih).
- Saat di-submit, pengguna diarahkan ke `/city/<id>` dan sistem akan melakukan *Infinite Scroll* ke `/api/hotels` untuk memuat daftar hotel di kota tersebut seiring *scroll* ke bawah (*Intersection Observer* + *Skeleton Loader*).

### 2. Memilih Kamar
- Pengguna membuka halaman Detail Hotel (`/hotel/<id>`). Sistem mengambil data `hotel_images` dan merendernya dalam Galeri Masonry.
- Sistem juga melakukan *query availability* yang kompleks: Semua kamar hotel tersebut di-cek terhadap tabel `bookings` untuk memastikan tidak ada rentang tanggal `check_in` & `check_out` yang *overlap* dengan pesanan berstatus `Booked`. Kamar yang lolos akan tampil dengan tombol "Booking".

### 3. Eksekusi Pemesanan (Checkout & Row Locking)
- Pengguna menekan *Booking* dan diarahkan ke `/book/<room_id>?check_in=X&check_out=Y`.
- **Validasi Kritis:** Sistem (`routes/booking.py`) memvalidasi tanggal (tidak boleh *check-out* mendahului *check-in*, atau mundur ke masa lalu). Jika *room_id* diubah secara iseng di URL, sistem mendeteksi 404.
- **Race Condition Prevention:** Saat form disubmit, sistem melakukan `SELECT ... FOR UPDATE` pada tabel kamar. Ini "mengunci" kamar sepersekian detik untuk mencegah dua orang mendaftar di kamar yang sama secara paralel (*Double Booking*).
- Jika aman, status berubah menjadi `Pending` dan pengguna menerima email "Menunggu Pembayaran".

### 4. Proses Pembayaran
- Pengguna dialihkan ke `/pay/<booking_id>`. Layar ini menampilkan UI Mockup *Snap Payment Gateway*.
- Terdapat fungsi *Timer Countdown* (15 menit). Jika kedaluwarsa, sistem otomatis (`cleanup_expired_bookings`) menandai pesanan sebagai `Cancelled`.
- Jika pembayaran berhasil disimulasikan, status berubah menjadi `Booked` dan email "Konfirmasi Pemesanan (Lunas)" terkirim. Pengguna diarahkan untuk mengunduh Invoice PDF (`/invoice/<booking_id>`).

### 5. Pasca-Inap (Review & Waiting List)
- Di dasbor `/my-bookings`, pengguna dapat membatalkan pesanan.
- **Sistem Waitlist Otomatis:** Jika pengguna A membatalkan pesanan, fungsi `cancel_booking` mencari pengguna B di tabel `waiting_lists` yang mengantre untuk tanggal yang bersinggungan di kamar tersebut. Jika ada, pengguna B akan menerima Email otomatis bahwa "Kamar Telah Tersedia Kembali".
- Setelah tanggal *check-out* berlalu, fungsi `submit_review` akan membuka gembok proteksi dan mengizinkan pengguna untuk memberi Bintang dan Ulasan pada pesanan tersebut, yang kemudian terakumulasi menjadi *rating* hotel keseluruhan.
