# 🔐 Panduan Setup Password Reset

Sistem reset password memungkinkan user untuk mengubah password mereka melalui email verification link.

## ✅ Persyaratan

- [x] Flask-Mail (sudah ada di requirements.txt)
- [x] Database schema dengan kolom `password_reset_token` dan `password_reset_expires`
- [x] SMTP Server (Gmail, Mailgun, SendGrid, dll)

## 🔧 Konfigurasi Email

Edit file `.env` dan isi konfigurasi SMTP:

```env
# Email / SMTP Configuration
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USERNAME=your_email@gmail.com
MAIL_PASSWORD=your_app_password    # Bukan password akun, tapi App Password untuk Gmail
MAIL_USE_TLS=True
MAIL_DEFAULT_SENDER=noreply@bookinghotels.com
```

### Untuk Gmail (Recommended)

1. Buka [Google Account Security](https://myaccount.google.com/security)
2. Aktifkan **2-Step Verification**
3. Buat **App Password** untuk Mail (16 karakter)
4. Copy app password ke `MAIL_PASSWORD` di `.env`

### Untuk Email Lain

- **Outlook**: `smtp-mail.outlook.com:587`
- **Mailgun**: `smtp.mailgun.org:587`
- **SendGrid**: `smtp.sendgrid.net:587`

## 🗄️ Database Schema Update

Jika schema lama, jalankan:

```sql
ALTER TABLE users ADD COLUMN password_reset_token VARCHAR(255) DEFAULT NULL;
ALTER TABLE users ADD COLUMN password_reset_expires DATETIME DEFAULT NULL;
```

Atau gunakan `init_db.py` yang sudah updated.

## 📋 Alur Penggunaan

1. User click "Lupa password?" di halaman login
2. Masukkan email terdaftar
3. Email dikirim dengan link reset (berlaku 1 jam)
4. User buka link → form reset password
5. Masukkan password baru 2x
6. Tekan "Reset Password"
7. Login dengan password baru

## 🛡️ Keamanan

- ✅ Token random 32-byte (cryptographically secure)
- ✅ Token expired setelah 1 jam
- ✅ Token dihapus setelah password berhasil direset
- ✅ Google OAuth users tidak bisa reset via email (gunakan Google recovery)
- ✅ Password di-hash dengan werkzeug (bcrypt-style)

## 📧 Testing Tanpa Email Real

Untuk development, gunakan **Console Mail Backend**:

Edit `app.py`:

```python
if os.getenv('FLASK_ENV') == 'development':
    app.config['MAIL_BACKEND'] = 'logging'
    import logging
    logging.basicConfig()
    logging.getLogger('flask_mail').setLevel(logging.DEBUG)
```

Email akan di-print ke console, bukan dikirim.

## ❌ Troubleshooting

### Email tidak terkirim

- Periksa konfigurasi MAIL_SERVER, MAIL_PORT, MAIL_USERNAME, MAIL_PASSWORD
- Cek apakah akun email sudah aktif 2FA (untuk Gmail)
- Lihat logs aplikasi untuk error messages

### Link reset tidak berfungsi

- Pastikan `SECRET_KEY` di `.env` sudah set (untuk generate token)
- Verifikasi database sudah ada kolom `password_reset_token` dan `password_reset_expires`
- Cek URL base di `_external=True` sudah benar (harus sesuai domain produksi)

### Token expired terlalu cepat

- Edit waktu expire di `routes/auth.py` line `expires_at = datetime.utcnow() + timedelta(hours=1)`
- Default adalah 1 jam, bisa diubah ke `days=1` atau `minutes=30` sesuai kebutuhan

---

**Status**: ✅ Production Ready
**Last Updated**: 22 July 2026
