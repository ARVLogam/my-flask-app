# main.py
from flask import Flask, render_template, redirect, request, session, flash, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps
from itsdangerous import URLSafeTimedSerializer
from dotenv import load_dotenv
import os
import traceback
import logging
import psycopg2

from flask_mail import Mail, Message

# app modules
from crud import Database, create_tables
from config import MAIL_SETTINGS, DB_CONFIG as RAW_DB  # dari config.py

# ---------------------------
# Init dasar
# ---------------------------
load_dotenv()

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev")

# Log ringan (optional)
logging.basicConfig(level=logging.INFO)
logging.info("App start")

# ---------------------------
# Konfigurasi Mail dari config.py
# ---------------------------
app.config.update(MAIL_SETTINGS)
# Jangan aktifkan MAIL_SUPPRESS_SEND di produksi
mail = Mail(app)

# Helper kirim email
def send_email(to, subject, body):
    sender = app.config.get("MAIL_DEFAULT_SENDER") or app.config.get("MAIL_USERNAME")
    msg = Message(subject, sender=sender, recipients=[to])
    msg.body = body
    mail.send(msg)

# ---------------------------
# DB config (normalisasi key)
# psycopg2 biasa pakai 'dbname', sementara code lama pernah pakai 'database'
# Kita bikin dict standar 'database' untuk class Database()
# ---------------------------
DB_CONFIG = {
    "host": RAW_DB.get("host"),
    "database": RAW_DB.get("dbname") or RAW_DB.get("database"),
    "user": RAW_DB.get("user"),
    "password": RAW_DB.get("password"),
    "port": RAW_DB.get("port"),
}

# ---------------------------
# Utilities
# ---------------------------
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

def check_role(required_role):
    return session.get("role") == required_role

# Jika ada template yang masih memanggil {{ csrf_token() }} tapi kita tidak pakai Flask-WTF,
# ini mencegah error Jinja.
@app.context_processor
def inject_csrf():
    return dict(csrf_token=lambda: "")

# Error handler ringkas (biar stacktrace muncul di log)
@app.errorhandler(Exception)
def handle_exception(e):
    traceback.print_exc()
    return "Internal Server Error", 500

# ---------------------------
# Token reset password
# ---------------------------
RESET_SALT = "reset-password"

def generate_token(email):
    s = URLSafeTimedSerializer(app.secret_key)
    return s.dumps(email, salt=RESET_SALT)

def verify_token(token, max_age=3600):
    s = URLSafeTimedSerializer(app.secret_key)
    try:
        return s.loads(token, salt=RESET_SALT, max_age=max_age)
    except Exception as e:
        print(f"Token error: {e}")
        return None

# ---------------------------
# ROUTES
# ---------------------------
@app.route("/")
def home():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        db = Database(DB_CONFIG)
        user = db.get_user(username)

        if user and check_password_hash(user[2], password):
            session["user_id"] = user[0]
            session["role"] = user[3]
            session["nama"] = user[4]
            flash("Login berhasil!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Username atau password salah", "error")

    return render_template("login.html")

@app.route("/dashboard")
@login_required
def dashboard():
    db = Database(DB_CONFIG)
    data_barang = db.read_all_barang()
    users = db.read_all_users()

    total_produk = len(data_barang)
    produk_terakhir = data_barang[-1] if data_barang else None
    total_pengguna = len(users)
    user_terakhir = users[-1] if users else None

    return render_template(
        "dashboard.html",
        role=session["role"],
        nama=session["nama"],
        barang=data_barang,
        total_produk=total_produk,
        total_pengguna=total_pengguna,
        produk_terakhir=produk_terakhir,
        user_terakhir=user_terakhir,
    )

@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        try:
            db = Database(DB_CONFIG)
            if db.check_email_exists(email):
                token = generate_token(email)
                reset_url = url_for("reset_password", token=token, _external=True)
                try:
                    send_email(
                        to=email,
                        subject="Reset Password",
                        body=(
                            "Halo,\n\n"
                            "Klik tautan berikut untuk mengatur ulang password (berlaku 1 jam):\n"
                            f"{reset_url}\n\n"
                            "Jika tidak meminta reset, abaikan email ini."
                        ),
                    )
                except Exception as e:
                    print("Gagal mengirim email:", e)

            # Pesan generik (keamanan): sama saja walau email tidak terdaftar
            flash("Jika email terdaftar, instruksi reset sudah dikirim.", "success")
            return redirect(url_for("forgot_password"))
        except Exception as e:
            print("Error di forgot_password:", e)
            flash("Terjadi kesalahan. Coba lagi nanti.", "error")
            return redirect(url_for("forgot_password"))

    return render_template("forget_password.html")

@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    email = verify_token(token)
    if not email:
        flash("Token tidak valid atau kedaluwarsa.", "error")
        return redirect(url_for("forgot_password"))

    if request.method == "POST":
        new_password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        if not new_password or new_password != confirm:
            flash("Konfirmasi password tidak cocok.", "error")
            return redirect(request.url)

        db = Database(DB_CONFIG)
        hashed = generate_password_hash(new_password)
        ok = db.update_user_password_by_email(email, hashed)
        if ok:
            flash("Password berhasil diubah. Silakan login.", "success")
            return redirect(url_for("login"))
        else:
            flash("Gagal menyimpan password baru.", "error")
            return redirect(request.url)

    return render_template("reset_password.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    try:
        if request.method == "POST":
            username = request.form["username"]
            password = request.form["password"]
            confirm_password = request.form["confirm_password"]
            nama = request.form["nama"]
            email = request.form["email"]
            nohp = request.form["nohp"]

            if password != confirm_password:
                flash("Password dan konfirmasi password tidak sama", "error")
                return redirect(url_for("register"))

            db = Database(DB_CONFIG)

            if db.get_user(username):
                flash("Username sudah digunakan", "error")
                return redirect(url_for("register"))

            if db.check_email_exists(email):
                flash("Email sudah terdaftar", "error")
                return redirect(url_for("register"))

            total_users = db.count_users()
            role = "admin" if total_users == 0 else "user"

            user_id = db.create_user(username, password, role, nama, email, nohp)
            if user_id:
                flash("Registrasi berhasil! Silakan login.", "success")
                return redirect(url_for("login", success=True))
            else:
                flash("Registrasi gagal", "error")

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
                "username": user[1],
                "nama": user[4],
                "email": user[5],
                "nohp": user[6],
            }
            return render_template("editProfile.html", user=user_data)
        else:
            flash("Data pengguna tidak ditemukan", "error")
            return redirect(url_for("dashboard"))

    # POST
    username = request.form["username"]
    password = request.form.get("password", "")
    nama = request.form["nama"]
    email = request.form["email"]
    nohp = request.form["nohp"]

    if db.check_username_exists(username, user_id):
        flash("Username sudah digunakan oleh pengguna lain", "error")
        return redirect(url_for("editProfile"))

    if db.check_email_exists_for_update(email, user_id):
        flash("Email sudah digunakan oleh pengguna lain", "error")
        return redirect(url_for("editProfile"))

    if password.strip():
        result = db.update_user(
            user_id, username, nama, email, nohp, role=None, password=password
        )
    else:
        result = db.update_user(user_id, username, nama, email, nohp, role=None)

    if result:
        session["nama"] = nama
        flash("Profil berhasil diperbarui", "success")
        return redirect(url_for("dashboard"))
    else:
        flash("Gagal memperbarui profil", "error")
        return redirect(url_for("editProfile"))

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out", "info")
    return redirect(url_for("login"))

# ---------------------------
# CRUD Barang
# ---------------------------
@app.route("/addBarang", methods=["GET", "POST"])
def addBarang():
    if not check_role("admin"):
        flash("Akses tidak diizinkan", "error")
        return redirect("/")

    if request.method == "POST":
        try:
            nama_barang = request.form["nama_barang"]
            harga = request.form["harga"]
            deskripsi = request.form["deskripsi"]

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
                return redirect(url_for("menuAdmin", roleMenu="kelolaBarang"))
            else:
                flash("Tambah Barang Gagal, silakan ulangi", "error")
                return render_template("addBarang.html")

        except Exception as e:
            print(f"Error in addBarang: {str(e)}")
            flash("Terjadi kesalahan saat menyimpan data", "error")
            return render_template("addBarang.html")

    return render_template("addBarang.html")

@app.route("/editBarang/<id_barang>", methods=["GET", "POST"])
def editBarang(id_barang):
    if not check_role("admin"):
        flash("Akses tidak diizinkan", "error")
        return redirect("/")

    try:
        db = Database(DB_CONFIG)

        if not id_barang.isdigit():
            flash("ID barang tidak valid", "error")
            return redirect(url_for("dashboard"))

        if request.method == "GET":
            barang = db.get_barang_by_id(id_barang)
            if not barang:
                flash("Data barang tidak ditemukan", "error")
                return redirect(url_for("dashboard"))
            return render_template("editBarang.html", barang=barang)

        # POST
        nama_barang = request.form.get("nama_barang", "").strip()
        harga = request.form.get("harga", "")
        deskripsi = request.form.get("deskripsi", "").strip()

        if not nama_barang or not harga or not deskripsi:
            flash("Semua field harus diisi", "error")
            return redirect(url_for("editBarang", id_barang=id_barang))

        try:
            harga = float(harga.replace(",", "."))
        except ValueError:
            flash("Harga harus berupa angka", "error")
            return redirect(url_for("editBarang", id_barang=id_barang))

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

@app.route("/deleteBarang/<id_barang>", methods=["POST"])
def deleteBarang(id_barang):
    if not check_role("admin"):
        flash("Akses tidak diizinkan", "error")
        return redirect("/")

    try:
        db = Database(DB_CONFIG)
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

# ---------------------------
# CRUD User (ringkas)
# ---------------------------
@app.route("/addUser", methods=["GET", "POST"])
def addUser():
    if not check_role("admin"):
        flash("Akses tidak diizinkan", "error")
        return redirect("/")

    if request.method == "POST":
        try:
            username = request.form["username"]
            password = request.form["password"]
            confirm_password = request.form["confirm_password"]
            nama = request.form["nama"]
            email = request.form["email"]
            nohp = request.form["nohp"]

            if password != confirm_password:
                flash("Password dan konfirmasi password tidak sama", "error")
                return redirect(url_for("addUser"))

            db = Database(DB_CONFIG)

            if db.get_user(username):
                flash("Username sudah digunakan", "error")
                return redirect(url_for("addUser"))

            if db.check_email_exists(email):
                flash("Email sudah terdaftar", "error")
                return redirect(url_for("addUser"))

            total_users = db.count_users()
            role = "admin" if total_users == 0 else "user"

            user_id = db.create_user(username, password, role, nama, email, nohp)
            if user_id:
                flash("Registrasi berhasil! Silakan login.", "success")
                return redirect(url_for("login", success=True))
            else:
                flash("Registrasi gagal", "error")
        except Exception as e:
            print(f"Error in addUser: {str(e)}")
            flash("Terjadi kesalahan saat menyimpan data", "error")
            return render_template("addUser.html")

    return render_template("addUser.html")

@app.route("/editUser/<int:user_id>", methods=["GET", "POST"])
def editUser(user_id):
    if not check_role("admin"):
        flash("Akses ditolak", "error")
        return redirect("/")

    db = Database(DB_CONFIG)
    user = db.get_user_by_id(user_id)
    if not user:
        flash("User tidak ditemukan", "error")
        return redirect(url_for("menuAdmin", roleMenu="kelolaUser"))

    if request.method == "POST":
        role = request.form.get("role", "").strip()
        if role not in ["admin", "user"]:
            flash("Role tidak valid", "error")
            return redirect(url_for("editUser", user_id=user_id))

        try:
            updated_id = db.update_user(
                user_id, user[1], user[4], user[5], user[6], role, None
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

    return render_template("editUser.html", user=user)

@app.route("/deleteUser", methods=["POST"])
def deleteUser():
    if not check_role("admin"):
        flash("Akses ditolak", "error")
        return redirect("/")

    user_id = request.form.get("user_id")
    if not user_id:
        flash("ID pengguna tidak valid", "error")
        return redirect(url_for("menuAdmin", roleMenu="kelolaUser"))

    db = Database(DB_CONFIG)
    if db.delete_user(user_id):
        flash("Pengguna berhasil dihapus", "success")
    else:
        flash("Gagal menghapus pengguna", "error")

    return redirect(url_for("menuAdmin", roleMenu="kelolaUser"))

@app.route("/menuAdmin", methods=["GET", "POST"])
def menuAdmin():
    if not check_role("admin"):
        flash("Anda tidak memiliki akses ke halaman ini", "error")
        return redirect("/")

    try:
        role = session.get("role")
        nama = session.get("nama")
        roleMenu = request.args.get("roleMenu")

        db = Database(DB_CONFIG)

        if roleMenu == "kelolaBarang":
            data_barang = db.read_all_barang()
            return render_template("kelolaBarang.html", role=role, nama=nama, barang=data_barang)
        elif roleMenu == "kelolaUser":
            data_users = db.read_all_users()
            return render_template("kelolaUser.html", role=role, nama=nama, users=data_users)
        else:
            return render_template("admin_dashboard.html", role=role, nama=nama)

    except Exception as e:
        print("Terjadi error di menuAdmin:", e)
        flash(f"Terjadi kesalahan: {str(e)}", "error")
        return redirect("/")

# ---------------------------
# Entrypoint
# ---------------------------
if __name__ == "__main__":
    # Buat tabel kalau belum ada
    create_tables(DB_CONFIG)

    # (opsional) Cek koneksi DB cepat
    try:
        print("Mencoba konek ke database...")
        conn = psycopg2.connect(
            host=DB_CONFIG["host"],
            dbname=DB_CONFIG["database"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            port=DB_CONFIG["port"],
        )
        with conn.cursor() as cur:
            cur.execute("SELECT NOW();")
            print("Sukses konek! Waktu DB sekarang:", cur.fetchone())
        conn.close()
    except Exception as e:
        print("Gagal konek ke database:", e)

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
