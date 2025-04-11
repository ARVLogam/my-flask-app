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
    def get_user(self, username):
        try:
            self.connect()
            query = """
                SELECT id, username, password, role, nama, email, nohp 
                FROM users WHERE username = %s
            """
            self.cursor.execute(query, (username,))
            user = self.cursor.fetchone()
            return user
        except Exception as e:
            print(f"Database error: {e}")
            return None
        finally:
            self.close()

    def get_user_by_id(self, user_id):
        try:
            self.connect()
            query = """
                SELECT id, username, password, role, nama, email, nohp 
                FROM users WHERE id = %s
            """
            self.cursor.execute(query, (user_id,))
            return self.cursor.fetchone()
        except Exception as e:
            print(f"Database error: {e}")
            return None
        finally:
            self.close()

    def create_user(self, username, password, role, nama, email, nohp):
        try:
            self.connect()
            hashed_password = generate_password_hash(password)
            query = """
                INSERT INTO users (username, password, role, nama, email, nohp) 
                VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
            """
            self.cursor.execute(query, (username, hashed_password, role, nama, email, nohp))
            user_id = self.cursor.fetchone()[0]
            self.connection.commit()
            return user_id
        except Exception as e:
            print(f"Database error: {e}")
            self.connection.rollback()
            return None
        finally:
            self.close()

def update_user(self, user_id, username, nama, email, nohp, role=None, password=None):
    try:
        self.connect()
        
        # Determine which update query to use based on password
        if password:
            hashed_password = generate_password_hash(password)
            query = """
                UPDATE users 
                SET username = %s, 
                    nama = %s, 
                    email = %s, 
                    nohp = %s, 
                    role = %s, 
                    password = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s RETURNING id
            """
            self.cursor.execute(query, (username, nama, email, nohp, role, hashed_password, user_id))
        else:
            query = """
                UPDATE users 
                SET username = %s, 
                    nama = %s, 
                    email = %s, 
                    nohp = %s, 
                    role = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s RETURNING id
            """
            self.cursor.execute(query, (username, nama, email, nohp, role, user_id))

        updated_id = self.cursor.fetchone()
        self.connection.commit()
        return updated_id[0] if updated_id else None
    except Exception as e:
        print(f"Database error: {e}")
        self.connection.rollback()
        return None
    finally:
        self.close()
    def delete_user(self, user_id):
        try:
            with self.conn.cursor() as cur:
                cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
                self.conn.commit()
                return True
        except Exception as e:
            print(f"Database error saat menghapus user: {e}")
            self.conn.rollback()
            return False

    def update_user_password(self, email, new_password):
        try:
            hashed_pw = generate_password_hash(new_password)
            self.cur.execute("UPDATE users SET password = %s WHERE email = %s", (hashed_pw, email))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Database error: {e}")
            self.conn.rollback()
            return False

    def check_email_exists(self, email):
        try:
            self.connect()
            query = "SELECT id FROM users WHERE email = %s"
            self.cursor.execute(query, (email,))
            return self.cursor.fetchone() is not None
        except Exception as e:
            print(f"Database error: {e}")
            return False
        finally:
            self.close()

    def check_email_exists_for_update(self, email, exclude_id):
        try:
            self.connect()
            query = "SELECT id FROM users WHERE email = %s AND id != %s"
            self.cursor.execute(query, (email, exclude_id))
            return self.cursor.fetchone() is not None
        except Exception as e:
            print(f"Database error: {e}")
            return False
        finally:
            self.close()

    def check_username_exists(self, username, exclude_id=None):
        try:
            self.connect()
            if exclude_id:
                query = "SELECT id FROM users WHERE username = %s AND id != %s"
                self.cursor.execute(query, (username, exclude_id))
            else:
                query = "SELECT id FROM users WHERE username = %s"
                self.cursor.execute(query, (username,))
            return self.cursor.fetchone() is not None
        except Exception as e:
            print(f"Database error: {e}")
            return False
        finally:
            self.close()

    def count_users(self):
        try:
            self.connect()
            query = "SELECT COUNT(*) FROM users"
            self.cursor.execute(query)
            result = self.cursor.fetchone()
            return result[0] if result else 0
        except Exception as e:
            print(f"Database error: {e}")
            return 0
        finally:
            self.close()

    def read_all_users(self):
        try:
            self.connect()
            query = """
                SELECT id, username, role, nama, email, nohp, created_at, updated_at
                FROM users ORDER BY id
            """
            self.cursor.execute(query)
            return self.cursor.fetchall()
        except Exception as e:
            print(f"Database error: {e}")
            return []
        finally:
            self.close()

    def create_barang(self, nama_barang, harga, deskripsi):
        try:
            self.connect()
            query = """
                INSERT INTO barang (nama_barang, harga, deskripsi)
                VALUES (%s, %s, %s) RETURNING id
            """
            self.cursor.execute(query, (nama_barang, harga, deskripsi))
            barang_id = self.cursor.fetchone()[0]
            self.connection.commit()
            return barang_id
        except Exception as e:
            print(f"Database Error: {e}")
            self.connection.rollback()
            return None
        finally:
            self.close()

    def get_barang_by_id(self, id_barang):
        try:
            self.connect()
            query = """
                SELECT id, nama_barang, harga, deskripsi
                FROM barang WHERE id = %s
            """
            self.cursor.execute(query, (id_barang,))
            return self.cursor.fetchone()
        except Exception as e:
            print(f'Database Error {e}')
            return None
        finally:
            self.close()

    def get_data_barang_nama_harga(self, nama_barang, harga):
        try:
            self.connect()
            query = """
                SELECT id, nama_barang, harga FROM barang 
                WHERE nama_barang = %s AND harga = %s
            """
            self.cursor.execute(query, (nama_barang, harga))
            return self.cursor.fetchone()
        except Exception as e:
            print(f"Database error: {e}")
            return None
        finally:
            self.close()

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
