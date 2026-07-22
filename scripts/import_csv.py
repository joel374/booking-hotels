import csv
import mysql.connector
import os
from dotenv import load_dotenv

# Load database configurations from .env
load_dotenv()

def import_csv_to_db(csv_filepath):
    # Establish connection
    try:
        conn = mysql.connector.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            user=os.getenv('DB_USER', 'root'),
            password=os.getenv('DB_PASSWORD', ''),
            database=os.getenv('DB_NAME', 'hotel_booking')
        )
        cursor = conn.cursor()
    except mysql.connector.Error as err:
        print(f"Error connecting to database: {err}")
        return

    print(f"Membuka file {csv_filepath}...")
    
    try:
        with open(csv_filepath, mode='r', encoding='utf-8') as file:
            csv_reader = csv.reader(file)
            headers = next(csv_reader, None) # Skip header
            
            success_count = 0
            
            for row in csv_reader:
                if not row or len(row) < 6:
                    continue
                
                # Mapping berdasarkan struktur CSV:
                # 0: NO
                # 1: NAMA PENGINAPAN
                # 2: BINTANG/NON BINTANG
                # 3: GOLONGAN
                # 4: JUMLAH KAMAR
                # 5: ALAMAT
                
                nama = row[1].strip()
                if not nama:
                    continue
                    
                bintang = row[2].strip()
                golongan = row[3].strip()
                alamat = row[5].strip()
                
                # Buat deskripsi dari kolom Bintang dan Golongan
                deskripsi = f"Tipe: {bintang}, Golongan: {golongan}"
                
                # Default province_id (19 = DI YOGYAKARTA)
                # Kita tidak set city_id spesifik agar lebih aman, atau set default ke NULL
                province_id = '19'
                
                # Insert ke tabel hotels
                query = """
                    INSERT INTO hotels (name, location, description, rating, province_id, city_id)
                    VALUES (%s, %s, %s, %s, %s, NULL)
                """
                values = (nama, alamat, deskripsi, 0.0, province_id)
                
                try:
                    cursor.execute(query, values)
                    success_count += 1
                except mysql.connector.Error as err:
                    print(f"Gagal memasukkan data hotel {nama}: {err}")
            
            # Commit transaksi
            conn.commit()
            print(f"Berhasil mengimpor {success_count} hotel ke dalam database!")
            
    except FileNotFoundError:
        print(f"File {csv_filepath} tidak ditemukan.")
    except Exception as e:
        print(f"Terjadi kesalahan: {e}")
    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    csv_file = '../jogja_hotels.csv' # Ubah jika path berbeda
    # Menjalankan dari root project
    if os.path.exists('jogja_hotels.csv'):
        csv_file = 'jogja_hotels.csv'
    
    import_csv_to_db(csv_file)
