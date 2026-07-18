# 🐛 Tugas Bug Fix - Pembagian Tim

**Tim:** Joel (Core), Galih (Frontend), Rafli (Backend/Logic)

**PENTING:** Baca `AI_CONTEXT.md` dulu sebelum mulai task!

---

## 👤 Joel (Core Developer) - 5 Tugas

### Task 1.1: Perbaiki Race Condition Booking ⭐ PRIORITAS TINGGI
**File:** `routes/booking.py`  
**Masalah:** Double booking bisa terjadi kalau 2 user book kamar yang sama bersamaan  
**Kesulitan:** Sulit

**Yang harus dilakukan:**
1. Tambah database transaction
2. Pakai row locking atau unique constraint
3. Test dengan multiple request bersamaan

**AI Prompt (Copy paste ini ke ChatGPT/Claude):**
```
Fix booking race condition di routes/booking.py. Tambahkan transaction atau locking untuk mencegah double booking ketika beberapa user booking kamar yang sama secara bersamaan. Code yang ada sekarang cek availability tapi tidak lock room selama transaction.
```

---

### Task 1.2: Auto-Cleanup Booking Expired ⭐ PRIORITAS SEDANG
**File:** `routes/booking.py`, `db.py`  
**Masalah:** Fungsi `cleanup_expired_bookings()` udah ada tapi gak dipanggil otomatis  
**Kesulitan:** Sedang

**Yang harus dilakukan:**
1. Panggil `cleanup_expired_bookings()` di booking routes
2. Atau buat middleware/scheduler
3. Test dengan booking pending yang lama

**AI Prompt (Copy paste ini ke ChatGPT/Claude):**
```
Implementasi automatic cleanup untuk expired bookings. Fungsi cleanup_expired_bookings() sudah ada di db.py tapi tidak pernah dipanggil. Tambahkan di booking routes atau buat middleware yang jalanin secara berkala. Booking dengan status 'Pending' lebih dari 15 menit harus di-cancel otomatis.
```

---

### Task 1.3: Validasi Upload Gambar ⭐ PRIORITAS TINGGI
**File:** `utils.py`  
**Masalah:** Tidak ada validasi tipe file atau ukuran, bisa upload apa aja  
**Kesulitan:** Mudah

**Yang harus dilakukan:**
1. Cek ekstensi file (hanya jpg, jpeg, png, gif)
2. Batasi ukuran file (max 5MB)
3. Return error kalau validasi gagal

**AI Prompt (Copy paste ini ke ChatGPT/Claude):**
```
Tambahkan validasi file upload ke fungsi save_file() di utils.py. Validasi:
1. Tipe file: hanya perbolehkan jpg, jpeg, png, gif
2. Ukuran file: maksimal 5MB
3. Raise ValueError dengan pesan yang jelas jika validasi gagal
Ikuti style code yang sudah ada.
```

---

### Task 1.4: Hapus File Gambar Saat Delete ⭐ PRIORITAS SEDANG
**File:** `routes/admin.py`  
**Masalah:** File gambar orphan tidak terhapus dari disk  
**Kesulitan:** Mudah

**Yang harus dilakukan:**
1. Cari semua route delete hotel/room di admin.py
2. Tambah pemanggilan `cleanup_unused_images()` setelah delete
3. Test bahwa deletion menghapus file fisik juga

**AI Prompt (Copy paste ini ke ChatGPT/Claude):**
```
Tambahkan cleanup_unused_images() setelah delete hotel dan room di routes/admin.py. Ketika admin hapus hotel atau room, record database terhapus tapi file gambar fisik masih ada. Panggil fungsi cleanup dari utils.py setelah operasi delete.
```

---

### Task 1.5: Perbaiki Handling Session Expiry ⭐ PRIORITAS RENDAH
**File:** `utils.py`, `app.py`  
**Masalah:** Session expiry tidak di-handle dengan baik  
**Kesulitan:** Sedang

**Yang harus dilakukan:**
1. Tambah konfigurasi session timeout
2. Improve decorator login_required
3. Redirect ke login dengan pesan saat expiry

**AI Prompt (Copy paste ini ke ChatGPT/Claude):**
```
Improve session expiry handling. Tambahkan session timeout configuration di app.py dan perbaiki login_required decorator di utils.py untuk handle expired session dengan baik, kasih flash message sebelum redirect ke login.
```

---

## 👤 Galih (Frontend/Templates) - 5 Tugas

### Task 2.1: Tambah Loading State Dropdown Kota ⭐ PRIORITAS RENDAH
**File:** `templates/rooms.html`  
**Masalah:** Tidak ada loading indicator saat fetch cities  
**Kesulitan:** Mudah

**Yang harus dilakukan:**
1. Tambah opsi "Loading..." saat fetching cities
2. Disable dropdown selama fetch
3. Tampilkan error kalau fetch gagal

**AI Prompt (Copy paste ini ke ChatGPT/Claude):**
```
Tambahkan loading state ke dropdown kota di templates/rooms.html. Ketika user pilih provinsi, tampilkan text "Memuat kota..." di dropdown kota selama fetching. Disable dropdown selama fetch. Tampilkan pesan error jika fetch gagal.
```

---

### Task 2.2: Perbaiki Pesan Validasi Form ⭐ PRIORITAS RENDAH
**File:** `templates/booking_form.html`  
**Masalah:** Pesan validasi kurang jelas  
**Kesulitan:** Mudah

**Yang harus dilakukan:**
1. Tambah pesan validasi HTML5 yang lebih baik
2. Tambah validasi client-side untuk tanggal (check-out > check-in)
3. Style error validasi supaya lebih kelihatan

**AI Prompt (Copy paste ini ke ChatGPT/Claude):**
```
Improve validasi form di templates/booking_form.html. Tambahkan pesan validasi HTML5 yang jelas, validasi bahwa tanggal check-out lebih besar dari check-in pakai JavaScript, dan style validation error supaya lebih terlihat. Tetap pakai server-side validation yang sudah ada.
```

---

### Task 2.3: Tambah Pesan Empty State ⭐ PRIORITAS RENDAH
**File:** `templates/rooms.html`, `templates/my_bookings.html`  
**Masalah:** Hasil kosong menampilkan halaman blank  
**Kesulitan:** Mudah

**Yang harus dilakukan:**
1. Tambah pesan "Tidak ada kamar ditemukan" saat search kosong
2. Tambah "Belum ada booking" saat user belum punya booking
3. Buat tampilannya bagus dengan CSS

**AI Prompt (Copy paste ini ke ChatGPT/Claude):**
```
Tambahkan empty state messages ke templates. Di templates/rooms.html, tampilkan "Tidak ada kamar tersedia untuk kriteria pencarian Anda" ketika tidak ada hasil. Di templates/my_bookings.html, tampilkan "Anda belum memiliki booking" ketika kosong. Style pesan ini dengan CSS yang bagus.
```

---

### Task 2.4: Perbaiki Layout Mobile Responsive ⭐ PRIORITAS SEDANG
**File:** `static/css/style.css`  
**Masalah:** Beberapa halaman tidak responsive di mobile  
**Kesulitan:** Sedang

**Yang harus dilakukan:**
1. Test di mobile (Chrome DevTools)
2. Perbaiki layout card, form, table
3. Tambah/improve media queries

**AI Prompt (Copy paste ini ke ChatGPT/Claude):**
```
Perbaiki responsive mobile layout di static/css/style.css. Test aplikasi di mobile view (320px-768px lebar) dan fix semua masalah layout pada cards, forms, dan tables. Tambah atau improve media queries. Pastikan ukuran button touch-friendly.
```

---

### Task 2.5: Improve UI Admin Dashboard ⭐ PRIORITAS RENDAH
**File:** `templates/admin/dashboard.html`, `static/css/style.css`  
**Masalah:** Dashboard stats bisa lebih menarik  
**Kesulitan:** Mudah

**Yang harus dilakukan:**
1. Tambah icon ke stat cards
2. Improve skema warna
3. Buat stats lebih menarik secara visual

**AI Prompt (Copy paste ini ke ChatGPT/Claude):**
```
Improve UI admin dashboard di templates/admin/dashboard.html. Tambahkan icon (bisa pakai Unicode emoji atau HTML entities) ke stat cards untuk hotels, rooms, bookings, dan revenue. Improve color scheme dan buat stats lebih menarik secara visual. Update CSS di style.css.
```

---

## 👤 Rafli (Backend/Logic) - 5 Tugas

### Task 3.1: Tambah Email Konfirmasi Booking ⭐ BONUS
**File:** `routes/booking.py` (fungsi baru)  
**Masalah:** Tidak ada email konfirmasi yang dikirim  
**Kesulitan:** Sedang

**Yang harus dilakukan:**
1. Install flask-mail atau pakai SMTP
2. Buat template email
3. Kirim email setelah booking confirmed

**AI Prompt (Copy paste ini ke ChatGPT/Claude):**
```
Tambahkan fitur booking confirmation email ke routes/booking.py. Ketika booking dikonfirmasi (status='Booked'), kirim email ke user dengan detail booking. Pakai Python smtplib atau flask-mail. Buat simple text email template dengan booking ID, hotel, room, dates, dan total harga.
```

---

### Task 3.2: Tambah Pagination Room Search ⭐ PRIORITAS SEDANG
**File:** `routes/main.py`  
**Masalah:** Semua room ditampilkan sekaligus, bisa lambat  
**Kesulitan:** Sedang

**Yang harus dilakukan:**
1. Tambah logic pagination (LIMIT, OFFSET)
2. Tambah parameter page ke URL
3. Update template dengan tombol pagination

**AI Prompt (Copy paste ini ke ChatGPT/Claude):**
```
Tambahkan pagination ke room search di routes/main.py. Tampilkan 10 rooms per halaman. Tambah parameter page ke URL query. Update database query pakai LIMIT dan OFFSET. Update templates/rooms.html untuk menampilkan tombol pagination (Previous, 1, 2, 3..., Next).
```

---

### Task 3.3: Tambah Filter Harga Room ⭐ PRIORITAS RENDAH
**File:** `routes/main.py`, `templates/rooms.html`  
**Masalah:** Tidak ada cara untuk filter berdasarkan range harga  
**Kesulitan:** Mudah

**Yang harus dilakukan:**
1. Tambah parameter min_price, max_price
2. Update SQL query dengan filter harga
3. Tambah input filter harga ke template

**AI Prompt (Copy paste ini ke ChatGPT/Claude):**
```
Tambahkan price range filter ke room search. Di routes/main.py, tambah parameter query min_price dan max_price. Update SQL query untuk filter rooms berdasarkan range harga. Di templates/rooms.html, tambahkan dua number input untuk harga minimum dan maksimum.
```

---

### Task 3.4: Tambah Sorting History Booking ⭐ PRIORITAS RENDAH
**File:** `routes/booking.py`, `templates/my_bookings.html`  
**Masalah:** Booking selalu sorted by created_at DESC  
**Kesulitan:** Mudah

**Yang harus dilakukan:**
1. Tambah parameter sort (date, status, price)
2. Update query ORDER BY clause
3. Tambah dropdown sorting di template

**AI Prompt (Copy paste ini ke ChatGPT/Claude):**
```
Tambahkan sorting options ke booking history di routes/booking.py. Biarkan user sort berdasarkan date, status, atau price. Tambah parameter sort ke URL. Update SQL query ORDER BY clause. Di templates/my_bookings.html, tambahkan dropdown untuk pilih opsi sort.
```

---

### Task 3.5: Tambah Statistik Hotel Admin ⭐ PRIORITAS RENDAH
**File:** `routes/admin.py`, `templates/admin/dashboard.html`  
**Masalah:** Dashboard bisa lebih informatif  
**Kesulitan:** Sedang

**Yang harus dilakukan:**
1. Tambah chart/stats untuk booking per bulan
2. Tampilkan hotel paling populer
3. Hitung occupancy rate

**AI Prompt (Copy paste ini ke ChatGPT/Claude):**
```
Tambahkan lebih banyak statistik ke admin dashboard. Di routes/admin.py, tambahkan query untuk:
1. Booking per bulan (6 bulan terakhir)
2. Top 5 hotel yang paling banyak dibooking
3. Average occupancy rate
Update templates/admin/dashboard.html untuk display stats ini. Simple table aja cukup, tidak perlu library chart.
```

---

## 📋 Cara Pakai File Ini

### Untuk Setiap Orang:

1. **Baca AI_CONTEXT.md dulu** - Pahami struktur project
2. **Pilih task** dari bagian kamu
3. **Copy AI Prompt** yang disediakan
4. **Paste ke AI assistant** (Claude, ChatGPT, dll)
5. **Review code** yang di-generate AI
6. **Test di local**
7. **Commit dengan pesan yang benar**

### Format Commit Message:

```bash
# Bug fixes
git commit -m "fix: mencegah double booking race condition"
git commit -m "fix: tambah auto-cleanup untuk expired bookings"
git commit -m "fix: validasi tipe file dan ukuran upload gambar"

# Features
git commit -m "feat: tambah pagination ke room search"
git commit -m "feat: tambah filter harga ke rooms"

# UI improvements
git commit -m "ui: tambah loading state ke dropdown kota"
git commit -m "ui: improve responsive mobile layout"
git commit -m "ui: tambah empty state messages"
```

---

## 🎯 Legend Prioritas

- ⭐ **PRIORITAS TINGGI** - Masalah security/data integrity, harus di-fix
- ⭐ **PRIORITAS SEDANG** - Masalah user experience, sebaiknya di-fix
- ⭐ **PRIORITAS RENDAH** - Nice to have, bisa skip kalau waktu terbatas
- ⭐ **BONUS** - Fitur tambahan, opsional

---

## ✅ Checklist Testing

Setelah selesai task:

- [ ] Code jalan tanpa error
- [ ] Fitur berfungsi sesuai harapan
- [ ] Tidak ada breaking changes ke fitur yang sudah ada
- [ ] Test edge cases (data kosong, input invalid, dll)
- [ ] Browser console tidak ada error
- [ ] Database query execute dengan benar
- [ ] Commit message sesuai format

---

## 🆘 Butuh Bantuan?

1. **Baca AI_CONTEXT.md** - Penjelasan project lengkap
2. **Cek PROJECT_FILES.md** - Referensi file
3. **Pakai AI assistant** - Copy AI prompts yang disediakan
4. **Tanya Joel** - Core developer

---

**Ringkasan Distribusi:**
- **Joel:** 5 tugas (Bug backend yang sulit)
- **Galih:** 5 tugas (Perbaikan Frontend/UI)
- **Rafli:** 5 tugas (Fitur & logic)

**Total: 15 tugas** = Commit history yang natural untuk tim 3 orang! 🎉
