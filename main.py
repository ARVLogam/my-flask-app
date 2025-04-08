from flask import Flask, render_template, redirect, request, session, flash, url_for
from werkzeug.security import check_password_hash
import psycopg2
import os
import traceback
import logging
from crud import Database, create_tables
from itsdangerous import URLSafeTimedSerializer

logging.basicConfig(level=logging.DEBUG)

print("Dashboard route - Current working directory:", os.getcwd())
print("Static folder path:", os.path.join(os.getcwd(), 'static', 'img'))
print("Logo file exists:", os.path.exists(os.path.join(os.getcwd(), 'static', 'img', 'logo.PNG')))
# Di bagian awal main.py
try:
    # Kode inisialisasi
    logging.debug("Aplikasi dimulai")
except Exception as e:
    logging.error(f"Error saat inisialisasi: {e}")
    traceback.print_exc()

app = Flask(__name__, static_folder='static')
app.secret_key = os.urandom(24)  # Secret key for session management

# Pindahkan error handler setelah inisialisasi app
@app.errorhandler(500)
def handle_500(error):
    print("Internal Server Error:")
    traceback.print_exc()
    return "Internal Server Error", 500

def check_role(required_role):
    """Memeriksa role pengguna dalam session"""
    return session.get('role') == required_role

# Sisa kode tetap sama...

# Database configuration - replace with your actual credentials
DB_CONFIG = {
    'host': os.environ.get('PGHOST', 'postgres-q03m.railway.internal'),
    'database': os.environ.get('PGDATABASE', 'railway'),
    'user': os.environ.get('PGUSER', 'postgres'),
    'password': os.environ.get('PGPASSWORD', 'JxlxNXWerXUEyNLkCgxgBlhSvXKMfNjo')
}
#basic crud start
@app.route("/")
def home():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        db = Database(DB_CONFIG)
        user = db.get_user(username)
        
        if user and check_password_hash(user[2], password):
            # Simpan lebih banyak data user di session
            session['user_id'] = user[0]
            # session['username'] = user[1]
            session['role'] = user[3]
            session['nama'] = user[4]
            # session['email'] = user[5]
            # session['nohp'] = user[6]
            
            flash('Login berhasil!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Username atau password salah', 'error')
    
    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    else:
        db = Database(DB_CONFIG)
        
        # Ambil data barang
        data_barang = db.read_all_barang()
        
        # Statistik Total Produk
        total_produk = len(data_barang)
        
        # Ambil aktivitas terakhir
        produk_terakhir = data_barang[-1] if data_barang else None
        
        # Misalkan Anda punya method untuk get user
        users = db.read_all_users()
        total_pengguna = len(users)
        user_terakhir = users[-1] if users else None

        # Tambahkan logging ini
        import os
        print("Dashboard route - Current working directory:", os.getcwd())
        print("Static folder path:", os.path.join(os.getcwd(), 'static', 'img'))
        print("Logo file exists:", os.path.exists(os.path.join(os.getcwd(), 'static', 'img', 'logo.PNG')))

    return render_template(
        "dashboard.html", 
        role=session['role'],
        nama=session['nama'],
        barang=data_barang,
        total_produk=total_produk,
        total_pengguna=total_pengguna,
        produk_terakhir=produk_terakhir,
        user_terakhir=user_terakhir
    )

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    email = verify_token(token)  # Fungsi untuk decode token
    if not email:
        flash("Token tidak valid atau kedaluwarsa", "danger")
        return redirect(url_for('login'))

    if request.method == 'POST':
        new_password = request.form['password']
        confirm = request.form['confirm_password']
        if new_password != confirm:
            flash("Konfirmasi password tidak cocok", "warning")
            return redirect(request.url)
        db = Database(DB_CONFIG)
        db.update_user_password(email, new_password)

        flash("Password berhasil diubah", "success")
        return redirect(url_for('login'))

    return render_template('reset_password.html')
def verify_token(token, max_age=3600):  # 1 jam
    s = URLSafeTimedSerializer(app.secret_key)
    try:
        email = s.loads(token, max_age=max_age)
        return email
    except Exception as e:
        print(f"Token error: {e}")
        return None

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        # Di sini kamu bisa tambah logika cek email, kirim link reset, dll
        flash("Instruksi reset password telah dikirim ke email jika terdaftar.", "info")
        return redirect(url_for('login'))
    return render_template("forgot_password.html")


@app.route("/register", methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    
    try:
        if request.method == 'POST':
            username = request.form['username']
            password = request.form['password']
            confirm_password = request.form['confirm_password']
            nama = request.form['nama']
            email = request.form['email']
            nohp = request.form['nohp']
            
            # Validasi password
            if password != confirm_password:
                flash('Password dan konfirmasi password tidak sama', 'error')
                return redirect(url_for('register'))
            
            db = Database(DB_CONFIG)
            
            # Cek apakah username atau email sudah terdaftar
            if db.get_user(username):
                flash('Username sudah digunakan', 'error')
                return redirect(url_for('register'))
            
            if db.check_email_exists(email):
                flash('Email sudah terdaftar', 'error')
                return redirect(url_for('register'))
            
            # Hitung jumlah user yang sudah terdaftar
            total_users = db.count_users()
            
            # Jika ini adalah user pertama, jadikan admin
            role = 'admin' if total_users == 0 else 'user'
            
            # Buat user baru
            user_id = db.create_user(username, password, role, nama, email, nohp)
            print('INI USER ID', user_id)
            
            if user_id:
                flash('Registrasi berhasil! Silakan login.', 'success')
                return redirect(url_for('login', success=True))
            else:
                flash('Registrasi gagal', 'error')
    
    except Exception as e:
        print(f"Error in register: {str(e)}")
        flash("Terjadi kesalahan saat menyimpan data", "error")
        return render_template("register.html")
    
    return render_template("register.html")

@app.route("/editProfile", methods=["GET", "POST"])
def editProfile():
    if "user_id" not in session:
        flash("Silakan login terlebih dahulu", "error")
        return redirect(url_for("menuAdmin", roleMenu="kelolaUser"))

    
    user_id = session["user_id"]
    db = Database(DB_CONFIG)
    
    if request.method == "GET":
        user = db.get_user_by_id(user_id)
        
        if user:
            user_data = {
                "username": user[1],  # username
                "nama": user[4],      # nama
                "email": user[5],     # email
                "nohp": user[6]       # nohp
            }
            return render_template("editProfile.html", user=user_data)
        else:
            flash("Data pengguna tidak ditemukan", "error")
            return redirect(url_for("dashboard"))
    
    elif request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        nama = request.form["nama"]
        email = request.form["email"]
        nohp = request.form["nohp"]
        
        # Validasi input (bisa ditambahkan sesuai kebutuhan)
        
        # Cek apakah username sudah digunakan oleh user lain
        if db.check_username_exists(username, user_id):
            flash("Username sudah digunakan oleh pengguna lain", "error")
            return redirect(url_for("editProfile"))
        
        # Cek apakah email sudah digunakan oleh user lain
        if db.check_email_exists_for_update(email, user_id):
            flash("Email sudah digunakan oleh pengguna lain", "error")
            return redirect(url_for("editProfile"))
        
        # Update data user
        if password.strip():
            result = db.update_user(user_id, username, nama, email, nohp, password)
        else:
            result = db.update_user(user_id, username, nama, email, nohp)
        
        if result:
            # Update nama di session jika diperlukan
            session["nama"] = nama
            flash("Profil berhasil diperbarui", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Gagal memperbarui profil", "error")
            return redirect(url_for("editProfile"))

@app.route("/logout")
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('login'))
#basic crud end

# crud barang start
@app.route('/addBarang', methods=['GET', 'POST'])
def addBarang():
    if not check_role('admin'):
        flash("Akses tidak diizinkan", "error")
        return redirect('/')
    
    if request.method == 'POST':
        try:
            nama_barang = request.form['nama_barang']
            harga = request.form['harga']
            deskripsi = request.form['deskripsi']
            
            try:
                harga = float(harga)
            except ValueError:
                flash("Harga harus berupa angka!", "error")
                return render_template("addBarang.html")
            
            db = Database(DB_CONFIG)
            
            if db.get_data_barang_nama_harga(nama_barang, harga):
                flash("Nama dan Harga Barang sudah terdaftar", "error")
                return render_template("addBarang.html")
            
            barang_id = db.create_barang(nama_barang, harga, deskripsi)
            
            if barang_id:
                flash("Tambah Barang Berhasil", "success")
                # Redirect to menuAdmin with the kelolaBarang parameter
                return redirect(url_for("menuAdmin", roleMenu="kelolaBarang"))
            else:
                flash("Tambah Barang Gagal, silakan ulangi", "error")
                return render_template("addBarang.html")
                
        except Exception as e:
            print(f"Error in addBarang: {str(e)}")
            flash("Terjadi kesalahan saat menyimpan data", "error")
            return render_template("addBarang.html")
    
    return render_template("addBarang.html")

@app.route('/editBarang/<id_barang>', methods=['GET','POST'])
def editBarang(id_barang):
    if not check_role('admin'):
        flash("Akses tidak diizinkan", "error")
        return redirect('/')
    
    try:
        db = Database(DB_CONFIG)
        
        # Validasi ID barang
        if not id_barang.isdigit():
            flash("ID barang tidak valid", "error")
            return redirect(url_for("dashboard"))

        if request.method == "GET":
            barang = db.get_barang_by_id(id_barang)
            
            if not barang:
                flash("Data barang tidak ditemukan", "error")
                return redirect(url_for("dashboard"))
            
            # Kirim data barang langsung tanpa konversi ke dictionary
            return render_template("editBarang.html", barang=barang)
            
        elif request.method == "POST":
            # Validasi input
            nama_barang = request.form.get("nama_barang", "").strip()
            harga = request.form.get("harga", "")
            deskripsi = request.form.get("deskripsi", "").strip()
            
            if not nama_barang or not harga or not deskripsi:
                flash("Semua field harus diisi", "error")
                return redirect(url_for("editBarang", id_barang=id_barang))
                
            try:
                harga = float(harga)
            except ValueError:
                flash("Harga harus berupa angka", "error")
                return redirect(url_for("editBarang", id_barang=id_barang))
                
            # Update data
            result = db.update_barang(id_barang, nama_barang, harga, deskripsi)
            
            if result:
                flash("Data barang berhasil diperbarui!", "success")
                # Redirect ke dashboard setelah update berhasil
                return redirect(url_for("menuAdmin", roleMenu="kelolaBarang"))
            else:
                flash("Gagal memperbarui data barang", "error")
                # Kembali ke form edit jika gagal
                return redirect(url_for("editBarang", id_barang=id_barang))
            
    except Exception as e:
        print(f"Error in editBarang: {str(e)}")
        flash("Terjadi kesalahan sistem", "error")
        return redirect(url_for("dashboard"))
        
@app.route('/deleteBarang/<id_barang>', methods=['POST'])
def deleteBarang(id_barang):
    if not check_role('admin'):
        flash("Akses tidak diizinkan", "error")
        return redirect('/')
    
    try:              
        db = Database(DB_CONFIG)
        
        # Cek apakah barang ada sebelum dihapus
        barang = db.get_barang_by_id(id_barang)
        if not barang:
            flash("Barang tidak ditemukan", "error")
            return redirect(url_for("menuAdmin", roleMenu="kelolaBarang"))
        
        delete_barang = db.delete_barang(id_barang)

        if delete_barang:
            flash("Data barang berhasil dihapus!", "success")
        else:
            flash("Gagal menghapus data barang", "error")
            
        return redirect(url_for("menuAdmin", roleMenu="kelolaBarang"))

    except Exception as e:
        print(f"Error saat menghapus barang: {str(e)}")
        flash("Terjadi kesalahan sistem saat menghapus barang", "error")
        return redirect(url_for("menuAdmin", roleMenu="kelolaBarang"))
#crud barang end

# crud user start
@app.route('/addUser', methods=['GET', 'POST'])
def addUser():
    if not check_role('admin'):
        flash("Akses tidak diizinkan", "error")
        return redirect('/')
    if request.method == 'POST':
        try:
            if request.method == 'POST':
                username = request.form['username']
                password = request.form['password']
                confirm_password = request.form['confirm_password']
                nama = request.form['nama']
                email = request.form['email']
                nohp = request.form['nohp']
                
                # Validasi password
                if password != confirm_password:
                    flash('Password dan konfirmasi password tidak sama', 'error')
                    return redirect(url_for('addUser'))
                
                db = Database(DB_CONFIG)
                
                # Cek apakah username atau email sudah terdaftar
                if db.get_user(username):
                    flash('Username sudah digunakan', 'error')
                    return redirect(url_for('addUser'))
                
                if db.check_email_exists(email):
                    flash('Email sudah terdaftar', 'error')
                    return redirect(url_for('addUser'))
                
                # Hitung jumlah user yang sudah terdaftar
                total_users = db.count_users()
                
                # Jika ini adalah user pertama, jadikan admin
                role = 'admin' if total_users == 0 else 'user'
                
                # Buat user baru
                user_id = db.create_user(username, password, role, nama, email, nohp)
                print('INI USER ID', user_id)
                
                if user_id:
                    flash('Registrasi berhasil! Silakan login.', 'success')
                    return redirect(url_for('login', success=True))
                else:
                    flash('Registrasi gagal', 'error')
        except Exception as e:
            print(f"Error in add User: {str(e)}")
            flash("Terjadi kesalahan saat menyimpan data", "error")
            return render_template("addUser.html")
    
    return render_template("addUser.html")




@app.route('/menuAdmin', methods=['GET', 'POST'])
def menuAdmin():
    if not check_role('admin'):
        flash("Anda tidak memiliki akses ke halaman ini", "error")
        return redirect('/')
    
    try:
        role = session.get('role')
        nama = session.get('nama')
        roleMenu = request.args.get('roleMenu')
        
        if not roleMenu:
            # Default ke dashboard jika tidak ada roleMenu
            return render_template('admin_dashboard.html', role=role, nama=nama)
        
        db = Database(DB_CONFIG)
        
        match roleMenu:
            case 'kelolaBarang':
                # Ambil data barang untuk ditampilkan
                data_barang = db.read_all_barang()
                return render_template('kelolaBarang.html', role=role, nama=nama, barang=data_barang)
            
            case 'kelolaUser':
                # Ambil data user untuk ditampilkan
                data_users = db.read_all_users()
                return render_template('kelolaUser.html',role=role, nama=nama, users=data_users)                        
            
            case _:
                # Jika roleMenu tidak dikenali
                flash(f"Menu '{roleMenu}' tidak tersedia", "error")
                return redirect(url_for('menuAdmin'))
                
    except Exception as e:
        # print(f"Error di menuAdmin: {e}")
        print("Terjadi error di menuAdmin:", e)
        flash(f"Terjadi kesalahan: {str(e)}", "error")
        return redirect('/')
    


db = Database(DB_CONFIG)  # <-- ini penting!
create_tables(DB_CONFIG)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

try:
    print("Mencoba konek ke database...")
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("SELECT NOW();")
    result = cursor.fetchone()
    print("Sukses konek! Waktu DB sekarang:", result)
    cursor.close()
    conn.close()
except Exception as e:
    print("Gagal konek ke database:", e)

# kelola user
# {{ url_for('editUser', id=user[0]) }} titip
#{{ url_for('hapusUser') }}

#edit barang
# {{ url_for('edit_barang', barang_id=item[0]) }}
