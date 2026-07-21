import csv
import os
import sys
import argparse

# Tambahkan folder project ke PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import get_db_connection

CSV_PATH = os.path.join(os.path.dirname(__file__), '..', 'jogja_hotels.csv')

def normalize_row(row):
    # CSV columns based on provided file
    # 0: NO, 1: NAMA PENGINAPAN, 2: BINTANG/NON BINTANG, 3: GOLONGAN,
    # 4: JUMLAH KAMAR, 5: ALAMAT, 6: Latitude, 7: Longitude
    name = row[1].strip()
    star = row[2].strip() if len(row) > 2 else ''
    golongan = row[3].strip() if len(row) > 3 else ''
    jumlah_kamar = row[4].strip() if len(row) > 4 else ''
    alamat = row[5].strip() if len(row) > 5 else ''
    lat = row[6].strip() if len(row) > 6 else ''
    lng = row[7].strip() if len(row) > 7 else ''

    description = f"star:{star} | type:{golongan} | rooms:{jumlah_kamar} | lat:{lat} lon:{lng}"

    return {
        'name': name,
        'location': alamat,
        'description': description,
        'province_id': None,
        'city_id': None
    }


def import_csv(dry_run=True):
    path = os.path.abspath(CSV_PATH)
    if not os.path.exists(path):
        print('CSV file not found at', path)
        return

    conn = get_db_connection()
    cursor = conn.cursor()

    inserted = 0
    skipped = 0

    with open(path, newline='', encoding='utf-8') as fh:
        reader = csv.reader(fh)
        header = next(reader, None)
        for row in reader:
            if not row or len(row) < 2:
                continue
            data = normalize_row(row)

            # avoid duplicate by name + location
            cursor.execute("SELECT id FROM hotels WHERE name = %s AND location = %s", (data['name'], data['location']))
            if cursor.fetchone():
                skipped += 1
                continue

            if dry_run:
                print('Would insert:', data['name'], '-', data['location'])
                inserted += 1
                continue

            cursor.execute(
                "INSERT INTO hotels (name, location, description, province_id, city_id) VALUES (%s, %s, %s, %s, %s)",
                (data['name'], data['location'], data['description'], data['province_id'], data['city_id'])
            )
            inserted += 1

    if not dry_run:
        conn.commit()
    cursor.close()
    conn.close()

    print(f"Processed rows. Inserted: {inserted}, Skipped (dupes): {skipped}")


def main():
    parser = argparse.ArgumentParser(description='Import jogja_hotels.csv into hotels table')
    parser.add_argument('--commit', action='store_true', help='Actually insert into DB (default is dry-run)')
    args = parser.parse_args()

    print('CSV path:', os.path.abspath(CSV_PATH))
    import_csv(dry_run=not args.commit)


if __name__ == '__main__':
    main()
