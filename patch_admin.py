import re

# Patch routes/admin.py
with open("routes/admin.py", "r", encoding="utf-8") as f:
    content = f.read()

# Add import
content = content.replace("from utils import admin_required, delete_image_file, save_file, add_notification",
                          "from utils import admin_required, delete_image_file, save_file, add_notification, log_admin")

# Add Hotel
content = re.sub(r'(flash\(_\(\'Hotel berhasil ditambahkan\'\), \'success\'\))',
                 r"\1\n                log_admin(session['user_id'], 'Hotel', 'Add Hotel', f'Added hotel: {name}')", content)

# Edit Hotel
content = re.sub(r'(flash\(_\(\'Hotel berhasil diperbarui\'\), \'success\'\))',
                 r"\1\n            log_admin(session['user_id'], 'Hotel', 'Edit Hotel', f'Edited hotel ID: {id}')", content)

# Delete Hotel
content = re.sub(r'(flash\(_\(\'Hotel berhasil dihapus\'\), \'success\'\))',
                 r"\1\n        log_admin(session['user_id'], 'Hotel', 'Delete Hotel', f'Deleted hotel ID: {id}')", content)

# Add Room Group (Admin Dashboard) -> Wait, let's see routes for room groups.
# In /hotel/edit/<int:hotel_id>/room_group/add
content = re.sub(r'(flash\(_\(\'Group Kamar berhasil ditambahkan\'\), \'success\'\))',
                 r"\1\n        log_admin(session['user_id'], 'Room Group', 'Add Room Group', f'Added room group {room_type} to hotel {hotel_id}')", content)

# Edit Room Group
content = re.sub(r'(flash\(_\(\'Group Kamar berhasil diperbarui\'\), \'success\'\))',
                 r"\1\n        log_admin(session['user_id'], 'Room Group', 'Edit Room Group', f'Edited room group {new_room_type} in hotel {hotel_id}')", content)

# Delete Room Group
content = re.sub(r'(flash\(_\(\'Group kamar berhasil dihapus\'\), \'success\'\))',
                 r"\1\n        log_admin(session['user_id'], 'Room Group', 'Delete Room Group', f'Deleted room group {room_type} in hotel {hotel_id}')", content)

# Upload Hotel Image (handled in Add/Edit Hotel usually, wait)
# Delete Hotel Image
# Wait, /hotel/edit/<int:id> handles main image upload. We can ignore detailed image tracking if it's part of Edit Hotel. But user asked specifically: "Upload Hotel Image, Delete Hotel Image, Upload Room Image, Delete Room Image"
# Let's check delete_image route
content = re.sub(r'flash\(_\(\'Gambar kamar berhasil dihapus\'\), \'success\'\)',
                 r"flash(_('Gambar kamar berhasil dihapus'), 'success')\n        log_admin(session.get('user_id'), 'Images', 'Delete Room Image', f'Deleted room image for hotel {hotel_id}')", content)

# Company Settings
content = re.sub(r'(flash\(_\(\'Pengaturan perusahaan berhasil disimpan!\'\), \'success\'\))',
                 r"\1\n        log_admin(session['user_id'], 'Company', 'Update Company Settings', 'Updated company settings')", content)

# Delete Booking (Soft Delete)
content = re.sub(r'(flash\(_\(\'Pesanan berhasil dihapus\'\), \'success\'\))',
                 r"\1\n        log_admin(session['user_id'], 'Bookings', 'Soft Delete Booking', f'Soft deleted booking ID: {id}')", content)

# Cancel Booking (if admin does it from Dashboard)
# Is there a cancel booking route in admin.py? Let's check.
# Let's write back what we have first
with open("routes/admin.py", "w", encoding="utf-8") as f:
    f.write(content)
