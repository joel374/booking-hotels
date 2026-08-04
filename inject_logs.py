import sys

with open("routes/admin.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

def insert_after(line_idx, text):
    lines.insert(line_idx + 1, " " * (len(lines[line_idx]) - len(lines[line_idx].lstrip())) + text + "\n")

# Hotel Add
for i, line in enumerate(lines):
    if 'flash("Hotel and rooms added successfully!", "success")' in line:
        insert_after(i, "log_admin(session['user_id'], 'Hotel', 'Add Hotel', f'Added hotel: {name}')")

# Hotel Edit
for i, line in enumerate(lines):
    if 'flash("Hotel updated successfully!", "success")' in line and 'hotel_id' not in lines[i-1]: # there are two
        insert_after(i, "log_admin(session['user_id'], 'Hotel', 'Edit Hotel', f'Edited hotel ID: {id}')")

# Hotel Delete
for i, line in enumerate(lines):
    if "flash('Hotel and related data deleted successfully.', 'success')" in line:
        insert_after(i, "log_admin(session['user_id'], 'Hotel', 'Delete Hotel', f'Deleted hotel ID: {id}')")

# Room Group Add
for i, line in enumerate(lines):
    if 'flash(f"Berhasil menambahkan {quantity} kamar tipe {room_type}!", "success")' in line:
        insert_after(i, "log_admin(session['user_id'], 'Room Group', 'Add Room Group', f'Added room group {room_type} to hotel {hotel_id}')")

# Room Group Add More
for i, line in enumerate(lines):
    if 'flash(f"Berhasil menambahkan {quantity} kamar tambahan untuk tipe {room_type}!", "success")' in line:
        insert_after(i, "log_admin(session['user_id'], 'Room Group', 'Add More Room Group', f'Added {quantity} more rooms to {room_type} in hotel {hotel_id}')")

# Room Group Edit
for i, line in enumerate(lines):
    if 'flash(f"Berhasil mengubah grup kamar {old_room_type}!", "success")' in line:
        insert_after(i, "log_admin(session['user_id'], 'Room Group', 'Edit Room Group', f'Edited room group {old_room_type} in hotel {hotel_id}')")

# Room Group Delete
for i, line in enumerate(lines):
    if 'flash(f"Berhasil menghapus grup kamar {room_type}!", "success")' in line:
        insert_after(i, "log_admin(session['user_id'], 'Room Group', 'Delete Room Group', f'Deleted room group {room_type} in hotel {hotel_id}')")

# Room Group Delete Image
for i, line in enumerate(lines):
    if "flash('Gambar berhasil dihapus.', 'success')" in line:
        insert_after(i, "log_admin(session['user_id'], 'Images', 'Delete Room Image', f'Deleted room image for hotel {hotel_id}')")

# Delete Booking
for i, line in enumerate(lines):
    if "flash('Booking deleted successfully.', 'success')" in line:
        insert_after(i, "log_admin(session['user_id'], 'Bookings', 'Soft Delete Booking', f'Soft deleted booking ID: {id}')")

# Cancel Booking
for i, line in enumerate(lines):
    if 'flash("Booking cancelled successfully.", "warning")' in line:
        insert_after(i, "log_admin(session['user_id'], 'Bookings', 'Cancel Booking', f'Cancelled booking ID: {booking_id}')")

# Company Settings
for i, line in enumerate(lines):
    if 'flash("Pengaturan perusahaan berhasil disimpan.", "success")' in line:
        insert_after(i, "log_admin(session['user_id'], 'Company', 'Update Company Settings', 'Updated company settings')")

with open("routes/admin.py", "w", encoding="utf-8") as f:
    f.writelines(lines)
