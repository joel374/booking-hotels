import os
import sys
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add parent directory to path to import db
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import get_db_connection

def fetch_image_url(hotel):
    hotel_id = hotel['id']
    name = hotel['name'].lower()
    
    if 'villa' in name:
        keyword = 'villa,exterior'
    elif 'guest' in name or 'guesthouse' in name:
        keyword = 'guesthouse,exterior'
    elif 'homestay' in name:
        keyword = 'homestay,room'
    elif 'resort' in name:
        keyword = 'resort,exterior'
    else:
        keyword = 'hotel,exterior'
        
    url = f"https://loremflickr.com/800/600/{keyword}?random={hotel_id}"
    req = urllib.request.Request(url, method='GET')
    
    try:
        response = urllib.request.urlopen(req, timeout=15)
        final_url = response.geturl()
        return hotel_id, final_url, keyword, name, None
    except Exception as e:
        return hotel_id, None, keyword, name, str(e)

def main():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # 1. Fetch hotels without images
    cursor.execute("""
        SELECT h.id, h.name 
        FROM hotels h 
        LEFT JOIN hotel_images hi ON hi.hotel_id = h.id 
        WHERE hi.hotel_id IS NULL AND h.is_deleted = 0
    """)
    hotels = cursor.fetchall()

    if not hotels:
        print("No hotels without images found.")
        cursor.close()
        conn.close()
        return

    total = len(hotels)
    print(f"Found {total} hotels without images. Starting fast migration...")

    # 2. Fetch images concurrently
    success_count = 0
    fail_count = 0

    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(fetch_image_url, h): h for h in hotels}
        
        for i, future in enumerate(as_completed(futures), 1):
            hotel_id, final_url, keyword, name, error = future.result()
            
            if final_url:
                try:
                    cursor.execute(
                        "INSERT INTO hotel_images (hotel_id, image_url) VALUES (%s, %s)", 
                        (hotel_id, final_url)
                    )
                    conn.commit()
                    success_count += 1
                    print(f"[{i}/{total}] SUCCESS | {name} ({keyword}) -> {final_url}")
                except Exception as db_err:
                    print(f"[{i}/{total}] DB ERROR | {name}: {db_err}")
                    fail_count += 1
            else:
                fail_count += 1
                print(f"[{i}/{total}] FETCH ERROR | {name}: {error}")

    cursor.close()
    conn.close()
    print(f"\\nMigration completed. Success: {success_count}, Failed: {fail_count}")

if __name__ == '__main__':
    main()
