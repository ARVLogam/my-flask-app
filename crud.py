import psycopg2
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import pytz 

class Database:
    def __init__(self, config):
        self.config = config
        self.conn = psycopg2.connect(**config)
        self.cur = self.conn.cursor()
        self.connection = None
        self.cursor = None

    def connect(self):
        self.connection = psycopg2.connect(**self.config)
        self.cursor = self.connection.cursor()

    def close(self):
        if self.cur:
            self.cur.close()
        if self.conn:
            self.conn.close()
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()

    # ... (semua method sebelumnya tetap sama)

    def read_all_barang(self):
        try:
            self.connect()
            query = """
                SELECT id, nama_barang, harga, deskripsi, 
                       to_char(created_at, 'DD-MM-YYYY HH24:MI') as created, 
                       to_char(updated_at, 'DD-MM-YYYY HH24:MI') as updated
                FROM barang ORDER BY id
            """
            self.cursor.execute(query)
            return self.cursor.fetchall()
        except Exception as e:
            print(f"Database error: {e}")
            return []
        finally:
            self.close()

    def update_barang(self, barang_id, nama_barang, harga, deskripsi):
        try:
            self.connect()
            query = """
                UPDATE barang 
                SET nama_barang = %s, 
                    harga = %s, 
                    deskripsi = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s RETURNING id
            """
            self.cursor.execute(query, (nama_barang, harga, deskripsi, barang_id))
            updated_id = self.cursor.fetchone()
            self.connection.commit()
            return updated_id[0] if updated_id else None
        except Exception as e:
            print(f"Database Error saat update barang: {e}")
            self.connection.rollback()
            return None
        finally:
            self.close()
    
    def delete_barang(self, barang_id):
        try:
            self.connect()
            query = "DELETE FROM barang WHERE id = %s RETURNING id"
            self.cursor.execute(query, (barang_id,))
            deleted_id = self.cursor.fetchone()
            self.connection.commit()
            return deleted_id[0] if deleted_id else None
        except Exception as e:
            print(f"Database Error saat menghapus barang: {e}")
            self.connection.rollback()
            return None
        finally:
            self.close()

# Fungsi create_tables di luar class
def create_tables(db_config):
    try:
        conn = psycopg2.connect(**db_config)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role VARCHAR(10) NOT NULL,
                nama TEXT NOT NULL,
                email TEXT NOT NULL,
                nohp TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS barang (
                id SERIAL PRIMARY KEY,
                nama_barang TEXT NOT NULL,
                harga NUMERIC NOT NULL,
                deskripsi TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
    except Exception as e:
        print(f"Error creating tables: {e}")
    finally:
        conn.close()
