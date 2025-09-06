from flask import Flask, render_template, redirect, request, session, flash, url_for
from werkzeug.security import check_password_hash
import psycopg2
import os
import traceback
import logging
from crud import Database, create_tables
from itsdangerous import URLSafeTimedSerializer
from dotenv import load_dotenv
import os
from functools import wraps
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_reset_email(recipient_email, token):
    sender_email = 'secrap7@gmail.com'  # Ganti dengan emailmu
    sender_password = 'pmbnqjbiosnuzszt'  # Ganti dengan App Password (bukan password biasa)
    reset_link = f"https://my-flask-app-production-9042.up.railway.app/forgot-password/{token}"  # Ganti ke domain aslimu saat deploy

    subject = "Reset Password"
    body = f'''
    Hai,\n
    Klik link berikut untuk mereset password kamu:\n
    {reset_link}\n
    Jika kamu tidak meminta reset password, abaikan email ini.
    '''

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        print('Email berhasil dikirim.')
    except Exception as e:
        print('Gagal mengirim email:', e)


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function



load_dotenv()

EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")



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
import os
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev")


from flask_mail import Mail, Message
from config import MAIL_SETTINGS

app.config.update(MAIL_SETTINGS)
mail = Mail(app)


# Konfigurasi email
#app.config['MAIL_SERVER'] = 'smtp.gmail.com'
#app.config['MAIL_PORT'] = 587
#app.config['MAIL_USE_TLS'] = True
#app.config['MAIL_USERNAME'] = 'secrap7@gmail.com'
#app.config['MAIL_PASSWORD'] = 'itlukqqxvhkqvuwq'  # gunakan App Password di sini   

mail = Mail(app)


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

@app.route('/dashboard')
@login_required
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
        db.close()
        flash("Password berhasil diubah", "success")
        return redirect(url_for('login'))

    return render_template('reset_password.html')
def verify_token(token, max_age=3600):
    s = URLSafeTimedSerializer(app.secret_key)
    try:
        email = s.loads(token, max_age=max_age)
        return email
    except Exception as e:
        print(f"Token error: {e}")
        return None

def generate_token(email):
    s = URLSafeTimedSerializer(app.secret_key)
    return s.dumps(email)
    
def send_email(to, subject, body):
    msg = Message(subject, sender=app.config['MAIL_USERNAME'], recipients=[to])
    msg.body = body
    mail.send(msg)


@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        db = Database(DB_CONFIG)

        # Cek apakah email terdaftar
        if db.check_email_exists(email):
            token = generate_token(email)
            reset_url = url_for('reset_password', token=token, _external=True)

            try:
                msg = Message("Reset Password", sender=app.config['MAIL_USERNAME'], recipients=[email])
                msg.body = f"Klik link berikut untuk mereset password kamu: {reset_url}\n\nLink ini berlaku 1 jam."
                mail.send(msg)
                flash("Email reset password telah dikirim.", "info")
            except Exception as e:
                print("Gagal mengirim email:", e)
                flash("Gagal mengirim email reset password", "error")
        else:
            flash("Email tidak ditemukan", "warning")
            
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
                # Konversi harga ke float
                harga = float(harga.replace(',', '.'))
            except ValueError:
                flash("Harga harus berupa angka", "error")
                return redirect(url_for("editBarang", id_barang=id_barang))
                
            # Update data
            result = db.update_barang(id_barang, nama_barang, harga, deskripsi)
            
            if result:
                flash("Data barang berhasil diperbarui!", "success")
                return redirect(url_for("menuAdmin", roleMenu="kelolaBarang"))
            else:
                flash("Gagal memperbarui data barang", "error")
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


@app.route('/editUser/<int:user_id>', methods=['GET', 'POST'])
def editUser(user_id):
    if not check_role('admin'):
        flash("Akses ditolak", "error")
        return redirect('/')

    db = Database(DB_CONFIG)
    user = db.get_user_by_id(user_id)
    if not user:
        flash("User tidak ditemukan", "error")
        return redirect(url_for("menuAdmin", roleMenu="kelolaUser"))

    if request.method == 'POST':
        # Ambil role dari form
        role = request.form.get('role', '').strip()

        # Validasi role
        if role not in ['admin', 'user']:
            flash("Role tidak valid", "error")
            return redirect(url_for("editUser", user_id=user_id))

        try:
            # Update user dengan role baru
            updated_id = db.update_user(
                user_id, 
                user[1],   # username (tetap sama)
                user[4],   # nama (tetap sama)
                user[5],   # email (tetap sama)
                user[6],   # nohp (tetap sama)
                role,      # role baru
                None       # password (tidak diubah)
            )

            if updated_id:
                flash("Role pengguna berhasil diubah", "success")
                return redirect(url_for("menuAdmin", roleMenu="kelolaUser"))
            else:
                flash("Gagal mengubah role pengguna", "error")
                return redirect(url_for("editUser", user_id=user_id))

        except Exception as e:
            print(f"Error updating user role: {e}")
            flash("Terjadi kesalahan saat mengubah role", "error")
            return redirect(url_for("editUser", user_id=user_id))

    # Render halaman edit untuk GET request
    return render_template('editUser.html', user=user)

@app.route('/deleteUser', methods=['POST'])
def deleteUser():
    if not check_role('admin'):
        flash("Akses ditolak", "error")
        return redirect('/')

    user_id = request.form.get('user_id')
    if not user_id:
        flash("ID pengguna tidak valid", "error")
        return redirect(url_for("menuAdmin", roleMenu="kelolaUser"))

    db = Database(DB_CONFIG)
    if db.delete_user(user_id):
        flash("Pengguna berhasil dihapus", "success")
    else:
        flash("Gagal menghapus pengguna", "error")

    return redirect(url_for("menuAdmin", roleMenu="kelolaUser"))




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

if __name__ == '__main__':
     create_tables(DB_CONFIG)
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
