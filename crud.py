import psycopg2
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from flask import flash

class Database:
    def __init__(self, config):
        self.config = config
        self.connection = None
        self.cursor = None

    def connect(self):
        """Connect to the PostgreSQL database"""
        self.connection = psycopg2.connect(**self.config)
        self.cursor = self.connection.cursor()

    def close(self):
        """Close database connection"""
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()

    def get_user(self, username):
        """Get user by username"""
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

    def get_data_barang_nama_harga(self,nama_barang,harga):
        """Get nama barang & harga"""
        try:
            self.connect()
            query = """
                SELECT id, nama_barang,harga FROM barang WHERE nama_barang = %s AND harga = %s
            """
            self.cursor.execute(query,(nama_barang,harga))
            barang = self.cursor.fetchone()
            return barang
        except Exception as e:
            print(f"Database error: {e}")
            return None
        finally:
            self.close()

    def create_user(self, username, password, role, nama, email, nohp):
        """Create a new user with complete data"""
        try:
            self.connect()
            hashed_password = generate_password_hash(password)
            query = """
                INSERT INTO users 
                (username, password, role, nama, email, nohp) 
                VALUES (%s, %s, %s, %s, %s, %s) 
                RETURNING id
            """
            self.cursor.execute(query, 
                (username, hashed_password, role, nama, email, nohp))
            user_id = self.cursor.fetchone()[0]
            self.connection.commit()
            return user_id
        except Exception as e:
            print(f"Database error: {e}")
            self.connection.rollback()
            return None
        finally:
            self.close()

    def create_barang(self, nama_barang, harga, deskripsi):
        """Create barang in table barang"""
        try:
            self.connect()
            query = """
                INSERT INTO barang (nama_barang, harga, deskripsi)
                VALUES (%s, %s, %s) RETURNING id
            """
            self.cursor.execute(query, (nama_barang, harga, deskripsi))
            barang_id = self.cursor.fetchone()[0]  # Mengambil id yang baru dimasukkan
            self.connection.commit()
            return barang_id
        except Exception as e:
            print(f"Database Error: {e}")
            self.connection.rollback()
            return None
        finally:
            self.close()


    def check_email_exists(self, email):
        """Check if email already exists in database"""
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

    def count_users(self):
        """Menghitung jumlah pengguna dalam tabel users"""
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

    # Tambahkan method ini ke class Database

    def update_user(self, user_id, username, nama, email, nohp, password=None):
        """Update data user dengan ID tertentu"""
        try:
            self.connect()
            if password:
                # Update dengan password baru
                hashed_password = generate_password_hash(password)
                query = """
                    UPDATE users 
                    SET username = %s, password = %s, nama = %s, email = %s, nohp = %s, 
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    RETURNING id
                """
                self.cursor.execute(query, (username, hashed_password, nama, email, nohp, user_id))
            else:
                # Update tanpa mengubah password
                query = """
                    UPDATE users 
                    SET username = %s, nama = %s, email = %s, nohp = %s, 
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    RETURNING id
                """
                self.cursor.execute(query, (username, nama, email, nohp, user_id))
            
            updated_id = self.cursor.fetchone()
            self.connection.commit()
            return updated_id[0] if updated_id else None
        except Exception as e:
            print(f"Database error: {e}")
            self.connection.rollback()
            return None
        finally:
            self.close()

    def update_barang(self, barang_id, nama_barang, harga, deskripsi):
        """Update data barang berdasarkan ID"""
        try:
            self.connect()
            query = """UPDATE barang 
                    SET nama_barang = %s, 
                        harga = %s, 
                        deskripsi = %s
                    WHERE id = %s
                    RETURNING id
            """
            self.cursor.execute(query, (nama_barang, harga, deskripsi, barang_id))
            
            updated_id = self.cursor.fetchone()
            self.connection.commit()
            return updated_id[0] if updated_id else None
        except Exception as e:
            print(f"Database Error saat update barang: {e}")
            flash("Terjadi kesalahan saat memperbarui barang", "error")
            self.connection.rollback()
            return None
        finally:
            self.close()

    def check_username_exists(self, username, exclude_id=None):
        """Check if username already exists, optionally excluding a specific user"""
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

    def check_email_exists_for_update(self, email, exclude_id):
        """Check if email already exists, excluding a specific user"""
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

    def get_user_by_id(self, user_id):
        """Get user by ID"""
        try:
            self.connect()
            query = """
                SELECT id, username, password, role, nama, email, nohp 
                FROM users WHERE id = %s
            """
            self.cursor.execute(query, (user_id,))
            user = self.cursor.fetchone()
            return user
        except Exception as e:
            print(f"Database error: {e}")
            return None
        finally:
            self.close()
    
    def get_barang_by_id(self,id_barang):
        """GET barang by ID"""
        try:
            self.connect()
            query = """
                SELECT id, nama_barang,harga,deskripsi
                FROM barang WHERE id = %s
            """
            self.cursor.execute(query,(id_barang,))
            barang = self.cursor.fetchone()
            return barang
        except Exception as e:
            print(f'Database Error {e}')
            return None
        finally:self.close()

    def read_all_users(self):
        """Mengambil semua data user dari database"""
        try:
            self.connect()
            query = """
                SELECT id, username, role, nama, email, nohp, created_at, updated_at
                FROM users
                ORDER BY id
            """
            self.cursor.execute(query)
            users = self.cursor.fetchall()
            return users
        except Exception as e:
            print(f"Database error: {e}")
            return []
        finally:
            self.close()


    def read_all_barang(self):
        """Mengambil semua data barang dari database"""
        try:
            self.connect()
            query = """
                SELECT id, nama_barang, harga, deskripsi, created_at, updated_at
                FROM barang
                ORDER BY id
            """
            self.cursor.execute(query)
            barang = self.cursor.fetchall()
            return barang
        except Exception as e:
            print(f"Database error: {e}")
            return []
        finally:
            self.close()

    def delete_barang(self, barang_id):
        """Menghapus barang berdasarkan ID"""
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
            def create_tables(db_config):
    def create_tables(db_config):
    """
    Membuat tabel-tabel yang dibutuhkan untuk aplikasi
    dan menambahkan kolom created_at dan updated_at
    """
    import psycopg2
    
    connection = None
    try:
        # Koneksi ke database
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()
        
        # Membuat tabel users jika belum ada
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            role VARCHAR(20) NOT NULL,
            nama VARCHAR(100) NOT NULL,
            email VARCHAR(100) UNIQUE NOT NULL,
            nohp VARCHAR(20),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Membuat tabel barang jika belum ada
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS barang (
            id SERIAL PRIMARY KEY,
            nama_barang VARCHAR(100) NOT NULL,
            harga DECIMAL(10,2) NOT NULL,
            deskripsi TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Commit perubahan
        connection.commit()
        print("Tabel berhasil dibuat/diperbarui")
    
    except Exception as e:
        print(f"Error membuat tabel: {e}")
        if connection:
            connection.rollback()
    
    finally:
        # Tutup koneksi
        if connection:
            connection.close()

# Tambahkan method ini sebagai method dari class Database
def create_tables_method(self):
    """
    Method wrapper untuk create_tables yang dapat dipanggil dari instance Database
    """
    create_tables(self.config)
