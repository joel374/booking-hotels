from db import get_db_connection

def validate_room_number(cursor, hotel_id, room_numbers, current_room_type=None):
    """
    Validates if any of the given room_numbers already exist for the hotel_id.
    """
    if not room_numbers:
        return []
        
    format_strings = ','.join(['%s'] * len(room_numbers))
    query = f"SELECT room_number, room_type FROM rooms WHERE hotel_id = %s AND room_number IN ({format_strings}) AND is_deleted = 0"
    
    cursor.execute(query, [hotel_id] + room_numbers)
    duplicates = cursor.fetchall()
    
    # If we are editing, we might be keeping the same numbers for the same type.
    # But usually, room number validation shouldn't clash if it's a completely new insertion.
    
    if duplicates:
        return [r['room_number'] if isinstance(r, dict) else r[0] for r in duplicates]
    return []

def generate_rooms(hotel_id, room_type, quantity, start_number, price, capacity, image_url=None):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        conn.start_transaction()
        room_numbers = [str(start_number + i) for i in range(quantity)]
        duplicates = validate_room_number(cursor, hotel_id, room_numbers)
        if duplicates:
            unique_dups = sorted(list(set(duplicates)), key=lambda x: int(x) if str(x).isdigit() else x)
            dup_str = ", ".join(unique_dups)
            end_number = start_number + quantity - 1
            raise ValueError(f"Room number range {start_number}-{end_number} overlaps with existing rooms. Conflicting room numbers: {dup_str}. Please choose another Start Number.")
            
        for r_num in room_numbers:
            cursor.execute(
                "INSERT INTO rooms (hotel_id, room_number, room_type, price, capacity) VALUES (%s, %s, %s, %s, %s)",
                (hotel_id, r_num, room_type, price, capacity)
            )
            room_id = cursor.lastrowid
            if image_url:
                cursor.execute("INSERT INTO room_images (room_id, image_url) VALUES (%s, %s)", (room_id, image_url))
        conn.commit()
        return room_numbers
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()

def edit_room_group(hotel_id, old_room_type, new_room_type, price, capacity, image_url=None):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        conn.start_transaction()
        
        # 1. Update basic room properties
        cursor.execute(
            "UPDATE rooms SET room_type = %s, price = %s, capacity = %s WHERE hotel_id = %s AND room_type = %s AND is_deleted = 0",
            (new_room_type, price, capacity, hotel_id, old_room_type)
        )
        
        # 2. Update images if provided
        if image_url:
            cursor.execute("SELECT id FROM rooms WHERE hotel_id = %s AND room_type = %s AND is_deleted = 0", (hotel_id, new_room_type))
            rooms = cursor.fetchall()
            for r in rooms:
                room_id = r['id']
                # Delete old images for this room
                cursor.execute("DELETE FROM room_images WHERE room_id = %s", (room_id,))
                # Insert new image
                cursor.execute("INSERT INTO room_images (room_id, image_url) VALUES (%s, %s)", (room_id, image_url))
                
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()

def delete_room_group(hotel_id, room_type):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        conn.start_transaction()
        cursor.execute(
            "UPDATE rooms SET is_deleted = 1 WHERE hotel_id = %s AND room_type = %s",
            (hotel_id, room_type)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()
