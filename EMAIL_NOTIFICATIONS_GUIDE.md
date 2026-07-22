# Email Notifications System - Antigravity Hotels

## Overview

Sistem email notifications telah diintegrasikan ke dalam authentication flow. User akan menerima email otomatis untuk beberapa event penting:

1. **Welcome Email** - Ketika user berhasil register
2. **Login Notification** - Setiap kali user login
3. **Password Reset** - Link untuk reset password (sudah ada sebelumnya)

---

## 1. Welcome Email Notification

### Trigger

- User berhasil melakukan **registration** (register form)
- User membuat akun baru melalui **Google OAuth**

### Isi Email

- Greeting dengan nama username user
- Konfirmasi bahwa akun berhasil dibuat
- Detail akun (username & email)
- List fitur yang bisa digunakan
- CTA button "Mulai Jelajahi Hotel"
- Contact support information

### Contoh Flow

```
User → Fill Register Form → Submit
  ↓
Server: Validate & Insert to Database
  ↓
Server: Send Welcome Email
  ↓
User: Menerima email di inbox
  ↓
Redirect: Login page
```

---

## 2. Login Notification Email

### Trigger

- User berhasil **login** dengan username/email/phone
- User login melalui **Google OAuth** (termasuk login yang sudah exist)

### Isi Email

- Greeting dengan nama username
- Notifikasi login terdeteksi
- Detail login:
  - **Waktu login** (dengan timezone WIB)
  - **Perangkat** (Browser)
  - **IP Address** dari user
- Security warning jika login tidak dikenali
- CTA button "Manage Account"

### Contoh Flow

```
User → Login Form → Submit Credentials
  ↓
Server: Validate Password
  ↓
Server: Create Session
  ↓
Server: Get IP Address & Send Notification
  ↓
User: Menerima email notifikasi login
  ↓
Redirect: Dashboard / Home Page
```

---

## 3. Setup & Configuration

### Prerequisites

1. Flask-Mail sudah terinstall
2. SMTP credentials sudah dikonfigurasi di `.env`

### Environment Variables (.env)

```env
# Email Configuration
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=xxxx xxxx xxxx xxxx
MAIL_USE_TLS=True
MAIL_DEFAULT_SENDER=noreply@antigravityhotels.com
```

### Configure untuk Gmail

1. Buka [Google Account Security](https://myaccount.google.com/security)
2. Aktifkan **2-Step Verification** jika belum
3. Ke **App passwords** → Select **Mail** & **Windows Computer**
4. Generate password 16 karakter
5. Copy ke `MAIL_PASSWORD` di `.env`

### Configure untuk Email Provider Lain

#### **Outlook/Hotmail**

```env
MAIL_SERVER=smtp.office365.com
MAIL_PORT=587
MAIL_USERNAME=your-email@outlook.com
MAIL_PASSWORD=your-password
MAIL_USE_TLS=True
```

#### **SendGrid (Recommended for Production)**

```env
MAIL_SERVER=smtp.sendgrid.net
MAIL_PORT=587
MAIL_USERNAME=apikey
MAIL_PASSWORD=SG.xxxxxxxxxxxxx
MAIL_USE_TLS=True
```

---

## 4. Implementation Details

### Helper Functions

#### `send_welcome_email(email, username)`

```python
from routes.auth import send_welcome_email

# Usage
send_welcome_email('user@example.com', 'john_doe')
```

- **Parameters:**
  - `email` (str): Email recipient
  - `username` (str): Username dari user
- **Returns:** `True` jika berhasil, `False` jika error
- **Auto-generated:** Setelah user register atau create account via Google

#### `send_login_notification(email, username, ip_address)`

```python
from routes.auth import send_login_notification

# Usage
send_login_notification('user@example.com', 'john_doe', '192.168.1.1')
```

- **Parameters:**
  - `email` (str): Email recipient
  - `username` (str): Username dari user
  - `ip_address` (str): IP address login user
- **Returns:** `True` jika berhasil, `False` jika error
- **Auto-generated:** Setiap kali user login (local atau Google)

### Modified Routes

#### `/register` (POST)

**Perubahan:**

- Kirim welcome email setelah user berhasil register
- Flash message: "Registration successful. Please check your email for welcome message. You can now login."

#### `/login` (POST)

**Perubahan:**

- Extract IP address dari `request.remote_addr` atau `X-Forwarded-For` header
- Kirim login notification email setelah authentication berhasil
- Flash message tetap: "Berhasil masuk."

#### `/login/google/authorize`

**Perubahan:**

- Untuk existing users: Kirim login notification
- Untuk new users: Kirim welcome email
- Flash message updated untuk new users

---

## 5. Error Handling

Jika email gagal dikirim:

- **Silently logged** ke console (tidak crash app)
- User tetap bisa login/register normalement
- Error message muncul di console untuk debugging

### Debug Output

```python
# Jika error, console akan show:
Error sending welcome email to user@example.com: [error details]
Error sending login notification to user@example.com: [error details]
```

---

## 6. Testing

### Test Welcome Email

1. Register akun baru dengan email yang accessible
2. Check inbox untuk "Selamat Datang! Akun Anda Berhasil Dibuat" email
3. Verify: username, welcome message, CTA button works

### Test Login Notification

1. Login dengan akun yang sudah ada
2. Check inbox untuk login notification email
3. Verify: login time, IP address, security warning shown

### Test Google OAuth

1. Register via Google → check welcome email
2. Login via Google (existing) → check login notification

### Troubleshooting

#### Email tidak terkirim

**Check:**

- `.env` file ada & terisi dengan benar
- MAIL_USERNAME & MAIL_PASSWORD benar
- 2-Step Verification aktif (untuk Gmail)
- App Password generated (untuk Gmail)
- SMTP server/port accessible dari network

#### Error di Console

```
Error sending welcome email to user@example.com:
[SMTPAuthenticationError: (535, b'5.7.8 Username and Password not accepted')]
```

**Solution:** Check MAIL_USERNAME & MAIL_PASSWORD di `.env`

```
Error sending login notification to user@example.com:
[SMTPRecipientsRefused: {email@example.com: (550, b'user unknown')}]
```

**Solution:** Email recipient tidak valid atau tidak diterima SMTP server

---

## 7. Future Enhancements

Fitur yang bisa ditambahkan:

- [ ] Configurable notification preferences (user bisa disable notifications)
- [ ] Email templates di database (bukan hardcoded di Python)
- [ ] Send email in background (Celery/Queue)
- [ ] Email unsubscribe link
- [ ] Multiple language support
- [ ] Account activity log di database
- [ ] Suspicious login detection & auto-alert
- [ ] Email verification on registration

---

## 8. Security Notes

✅ **Best Practices Implemented:**

- Email tidak terekspos di public (hanya di email headers)
- IP address dicatat untuk security audit
- Login notification membantu user detect unauthorized access
- HTTPS recommended untuk production
- Flask-Mail handles SMTP encryption (TLS)

⚠️ **Recommendations:**

- Jangan simpan plain email password di `.env` (production: gunakan secrets manager)
- Gunakan dedicated SMTP service (SendGrid, Mailgun) untuk production
- Monitor bounced emails
- Rate limit email sending (prevent spam)
- Implement DKIM/SPF untuk better deliverability

---

## 9. Usage Summary

### Untuk Developer

```python
# Import helper functions
from routes.auth import send_welcome_email, send_login_notification

# Send welcome email
send_welcome_email('user@example.com', 'username')

# Send login notification
send_login_notification('user@example.com', 'username', '192.168.1.1')
```

### Untuk User

1. Register → menerima welcome email
2. Login → menerima login notification email
3. Forgot password → menerima password reset link
4. Check email untuk alerts & confirmations

---

**Last Updated:** 2026-07-22  
**Status:** ✅ Production Ready
