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
import threading
import time
from flask_mail import Mail, Message

from werkzeug.utils import secure_filename
from PIL import Image  # optional, untuk normalisasi ke PNG (lebih aman)
import io

# app modules
from crud import Database, create_tables
from config import MAIL_SETTINGS, DB_CONFIG as RAW_DB  # dari config.py

# ---------------------------
# Init dasar
# ---------------------------
load_dotenv()

# ====== Upload Foto Produk (Admin) ======
from werkzeug.utils import secure_filename
from pathlib import Path
import re

# Folder upload
UPLOAD_FOLDER = Path("static/img/products")
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

# Ekstensi yang diijinkan
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

_slug_re = re.compile(r"[^a-z0-9]+")
def slugify(text: str) -> str:
    return _slug_re.sub("-", text.lower()).strip("-")

def save_product_image(file_storage, nama_barang: str) -> str | None:
    """
    Simpan foto produk ke static/img/products dengan nama file berbasis slug.
    Return: relative path (contoh: 'img/products/kabel-tembaga.png') atau None.
    """
    if not file_storage or file_storage.filename == "":
        return None
    if not allowed_file(file_storage.filename):
        return None

    ext = file_storage.filename.rsplit(".", 1)[1].lower()
    slug = slugify(nama_barang)
    filename = secure_filename(f"{slug}.{ext}")
    dest = UPLOAD_FOLDER / filename
    file_storage.save(dest)

    # kembalikan path RELATIF dari /static
    return f"img/products/{filename}"



app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev")

# --- Konfigurasi upload ---
ALLOWED_IMAGE_EXT = {"png", "jpg", "jpeg", "webp"}
UPLOAD_FOLDER = os.path.join(app.static_folder, "img", "products")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def _allowed_image(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXT

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# --- Avatar upload (letakkan SETELAH app = Flask(...)) ---
import os
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
from PIL import Image

# Maksimal ukuran upload 4MB (opsional)
app.config['MAX_CONTENT_LENGTH'] = 4 * 1024 * 1024

# Folder penyimpanan avatar
AVATAR_FOLDER = os.path.join(app.static_folder, "img", "avatars")
os.makedirs(AVATAR_FOLDER, exist_ok=True)

# Ekstensi gambar yang diizinkan
ALLOWED_IMAGE_EXT = {"png", "jpg", "jpeg", "webp"}

def _allowed_img(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXT

def _save_avatar(file_storage, user_id: int):
    """
    Simpan avatar ke static/img/avatars/user_<id>.webp.
    Return:
      - 'INVALID' jika ekstensi tidak diizinkan
      - 'ERROR'   jika gagal proses/simpan
      - relative path 'img/avatars/user_<id>.webp' jika sukses
      - None      jika tidak ada file
    """
    if not file_storage or not getattr(file_storage, "filename", ""):
        return None

    filename = secure_filename(file_storage.filename)
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_IMAGE_EXT:
        return "INVALID"

    try:
        # Normalisasi ke WEBP agar konsisten & ukuran kecil
        img = Image.open(file_storage.stream).convert("RGB")
        dst_abs = os.path.join(AVATAR_FOLDER, f"user_{user_id}.webp")
        img.save(dst_abs, "WEBP", quality=90)
        return f"img/avatars/user_{user_id}.webp"
    except Exception:
        import traceback; traceback.print_exc()
        return "ERROR"

def _avatar_relpath(user_id: int) -> str:
    """Kembalikan relative path avatar user jika ada, kalau tidak pakai guest."""
    candidate = os.path.join(AVATAR_FOLDER, f"user_{user_id}.webp")
    if os.path.exists(candidate):
        return f"img/avatars/user_{user_id}.webp"
    return "img/avatars/guest.png"

# Handler jika file melebihi MAX_CONTENT_LENGTH
@app.errorhandler(RequestEntityTooLarge)
def _file_too_big(_):
    flash("File terlalu besar (maks 4 MB).", "error")
    return redirect(request.referrer or url_for("editProfile"))



app.config.update(MAIL_SETTINGS)

# Untuk debugging cepat (boleh dibiarkan)
print("MAIL_SERVER:", app.config.get("MAIL_SERVER"))
print("MAIL_PORT:", app.config.get("MAIL_PORT"))
print("MAIL_USE_TLS:", app.config.get("MAIL_USE_TLS"))
print("MAIL_TIMEOUT:", app.config.get("MAIL_TIMEOUT"))
print("MAIL_USERNAME set?:", bool(app.config.get("MAIL_USERNAME")))
print("MAIL_DEFAULT_SENDER set?:", bool(app.config.get("MAIL_DEFAULT_SENDER")))

mail = Mail(app)
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
    """Kirim email di thread terpisah + timeout supaya request tidak hang."""
    start_ts = time.time()
    print(f"[MAIL] Prepare send -> to={to}, subject={subject}")

    def _worker():
        try:
            with app.app_context():
                msg = Message(subject, recipients=[to])
                msg.body = body
                mail.send(msg)
                print(f"[MAIL] Sent OK in {time.time() - start_ts:.2f}s")
        except Exception as e:
            # Jangan bikin request hang—cukup log errornya
            print(f"[MAIL] ERROR: {e}")

    t = threading.Thread(target=_worker, daemon=True)
    t.start()  # langsung jalan di background

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
        cache_bust=int(time.time())
    )

@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()

        # (opsional) validasi format sederhana biar gak kirim ke string kosong/aneh
        if not email or "@" not in email:
            flash("Masukkan email yang valid.", "error")
            return redirect(url_for("forgot_password"))

        try:
            db = Database(DB_CONFIG)

            # Jangan bocorkan apakah email ada/tidak
            user_exists = False
            try:
                user_exists = db.check_email_exists(email)
            except Exception as e:
                # kalau terjadi error saat cek, log saja—tetap kasih pesan generik
                print("[FORGOT] check_email_exists error:", e)

            if user_exists:
                # Buat token & link reset
                token = generate_token(email)  # pastikan pakai SALT di helper
                reset_url = url_for("reset_password", token=token, _external=True)

                # Kirim email di background (tidak blok UI)
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
                    print("[FORGOT] reset email dispatched to:", email)
                except Exception as e:
                    # Jangan bikin request gagal hanya karena kirim email error
                    print("[FORGOT] send_email error:", e)

            # Pesan generik selalu sama (keamanan)
            flash("Jika email terdaftar, instruksi reset sudah dikirim.", "success")
            return redirect(url_for("forgot_password"))

        except Exception as e:
            print("[FORGOT] unexpected error:", e)
            flash("Terjadi kesalahan. Coba lagi nanti.", "error")
            return redirect(url_for("forgot_password"))

        finally:
            # Tutup koneksi DB kalau class Database kamu punya .close()
            try:
                if "db" in locals() and hasattr(db, "close"):
                    db.close()
            except Exception as e:
                print("[FORGOT] db.close error:", e)

    # GET → tampilkan form
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
        return redirect(url_for("login"))

    user_id = session["user_id"]
    db = Database(DB_CONFIG)

    if request.method == "GET":
        u = db.get_user_by_id(user_id)
        if not u:
            flash("Data pengguna tidak ditemukan", "error")
            return redirect(url_for("dashboard"))

        user = {
            "username": u[1],  # sesuaikan indeks dengan struktur tabelmu
            "nama":     u[4],
            "email":    u[5],
            "nohp":     u[6],
        }
        avatar_url = url_for("static", filename=_avatar_relpath(user_id))
        return render_template("editProfile.html", user=user, avatar_url=avatar_url)

    # POST
    try:
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()  # opsional
        nama     = request.form.get("nama", "").strip()
        email    = request.form.get("email", "").strip()
        nohp     = request.form.get("nohp", "").strip()

        # Validasi sederhana
        if not username or not nama or not email or not nohp:
            flash("Semua field (kecuali password) wajib diisi", "error")
            return redirect(url_for("editProfile"))

        # Cek duplikasi username/email milik user lain
        if db.check_username_exists(username, user_id):
            flash("Username sudah digunakan oleh pengguna lain", "error")
            return redirect(url_for("editProfile"))
        if db.check_email_exists_for_update(email, user_id):
            flash("Email sudah digunakan oleh pengguna lain", "error")
            return redirect(url_for("editProfile"))

        # Simpan avatar (opsional). Tidak perlu simpan ke DB.
        avatar_file = request.files.get("avatar")
        if avatar_file and avatar_file.filename:
            saved = _save_avatar(avatar_file, user_id)
            if saved == "INVALID":
                flash("Format gambar tidak diizinkan. Gunakan png/jpg/jpeg/webp.", "error")
                return redirect(url_for("editProfile"))
            if saved is None:
                flash("Gagal menyimpan gambar. Coba file lain.", "error")
                return redirect(url_for("editProfile"))

        # Update user. Password hanya diubah jika diisi.
        if password:
            ok = db.update_user(user_id, username, nama, email, nohp, role=None, password=password)
        else:
            ok = db.update_user(user_id, username, nama, email, nohp, role=None)

        if not ok:
            flash("Gagal memperbarui profil", "error")
            return redirect(url_for("editProfile"))

        # Perbaharui session nama untuk navbar
        session["nama"] = nama

        flash("Profil berhasil diperbarui", "success")
        return redirect(url_for("dashboard"))

    except Exception as e:
        # Supaya kelihatan error aslinya di log/container
        import traceback; traceback.print_exc()
        flash("Terjadi kesalahan saat menyimpan profil", "error")
        return redirect(url_for("editProfile"))




@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out", "info")
    return redirect(url_for("login"))

# ---------------------------
# CRUD Barang
# ---------------------------
@app.route('/addBarang', methods=['GET', 'POST'])
def addBarang():
    if not check_role('admin'):
        flash("Akses tidak diizinkan", "error")
        return redirect('/')

    if request.method == 'POST':
        try:
            nama_barang = request.form.get('nama_barang', '').strip()
            harga = request.form.get('harga', '').strip()
            deskripsi = request.form.get('deskripsi', '').strip()
            foto_file = request.files.get('foto')  # <--- ambil file

            if not nama_barang or not harga or not deskripsi:
                flash("Semua field harus diisi!", "error")
                return render_template("addBarang.html")

            try:
                harga = float(harga.replace(',', '.'))
            except ValueError:
                flash("Harga harus berupa angka!", "error")
                return render_template("addBarang.html")

            db = Database(DB_CONFIG)
            if db.get_data_barang_nama_harga(nama_barang, harga):
                flash("Nama dan Harga Barang sudah terdaftar", "error")
                return render_template("addBarang.html")

            # simpan dulu barang di DB
            barang_id = db.create_barang(nama_barang, harga, deskripsi)
            if not barang_id:
                flash("Tambah Barang Gagal, silakan ulangi", "error")
                return render_template("addBarang.html")

            # simpan foto (opsional)
            relpath = save_product_image(foto_file, nama_barang)
            if relpath:
                # kalau tabel kamu belum ada kolom foto, lewati bagian ini.
                # jika SUDAH ada kolom foto, panggil method update foto kamu:
                try:
                    db.update_barang_foto(barang_id, relpath)  # <-- buat method ini di crud.py jika ada kolom foto
                except Exception:
                    pass  # aman, tetap lanjut walau tanpa kolom foto

            flash("Tambah Barang Berhasil", "success")
            return redirect(url_for("menuAdmin", roleMenu="kelolaBarang"))

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
            # path gambar (konvensi: products/<id>.png)
            image_url = url_for("static", filename=f"img/products/{id_barang}.png")
            return render_template("editBarang.html", barang=barang, image_url=image_url)

        # --- POST ---
        nama_barang = request.form.get("nama_barang", "").strip()
        harga_raw    = request.form.get("harga", "").strip()
        deskripsi    = request.form.get("deskripsi", "").strip()

        if not nama_barang or not harga_raw or not deskripsi:
            flash("Semua field harus diisi", "error")
            return redirect(url_for("editBarang", id_barang=id_barang))

        # Normalisasi harga (dukung koma Indonesia)
        try:
            harga = float(harga_raw.replace(".", "").replace(",", "."))
        except ValueError:
            flash("Harga harus berupa angka yang valid", "error")
            return redirect(url_for("editBarang", id_barang=id_barang))

        # Simpan data barang ke DB dulu
        ok = db.update_barang(id_barang, nama_barang, harga, deskripsi)
        if not ok:
            flash("Gagal memperbarui data barang", "error")
            return redirect(url_for("editBarang", id_barang=id_barang))

        # Tangani upload foto (opsional)
        file = request.files.get("foto")
        if file and file.filename:
            if not _allowed_image(file.filename):
                flash("Format gambar tidak didukung. Gunakan png/jpg/jpeg/webp", "error")
                return redirect(url_for("editBarang", id_barang=id_barang))

            try:
                # Amankan nama lalu pakai konvensi ID.png agar stabil
                dst_path = os.path.join(UPLOAD_FOLDER, f"{id_barang}.png")

                # Baca & normalisasi ke PNG agar konsisten
                img = Image.open(file.stream)
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                img.save(dst_path, format="PNG", optimize=True)

            except Exception as e:
                print("ERROR save image:", e)
                flash("Data tersimpan, tapi gagal menyimpan foto.", "warning")
                return redirect(url_for("menuAdmin", roleMenu="kelolaBarang"))

        flash("Barang berhasil diperbarui!", "success")
        return redirect(url_for("menuAdmin", roleMenu="kelolaBarang"))

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

@app.route("/menuAdmin", methods=["GET"])
def menuAdmin():
    # Hanya admin
    if not check_role("admin"):
        flash("Anda tidak memiliki akses ke halaman ini", "error")
        return redirect("/")

    try:
        role = session.get("role")
        nama = session.get("nama")
        # default ke kelolaUser
        roleMenu = (request.args.get("roleMenu") or "kelolaUser").strip().lower()

        db = Database(DB_CONFIG)

        # LEGACY: jika masih ada link lama menuju kelola barang → arahkan ke dashboard
        if roleMenu in ("kelolabarang", "barang", "produk"):
            flash("Kelola barang kini dipindahkan ke Dashboard. Gunakan tombol Edit pada kartu produk.", "info")
            return redirect(url_for("dashboard"))

        # Satu-satunya halaman admin yang aktif: Kelola User
        if roleMenu in ("kelolauser", "user"):
            data_users = db.read_all_users()
            return render_template("kelolaUser.html", role=role, nama=nama, users=data_users)

        # Jika parameter tidak dikenal, fallback ke kelolaUser
        return redirect(url_for("menuAdmin", roleMenu="kelolaUser"))

    except Exception as e:
        print("Terjadi error di menuAdmin:", e)
        flash("Terjadi kesalahan. Coba lagi nanti.", "error")
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
