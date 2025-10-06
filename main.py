# main.py
from flask import Flask, render_template, redirect, request, session, flash, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
from functools import wraps
from itsdangerous import URLSafeTimedSerializer
from dotenv import load_dotenv
from PIL import Image
import logging, traceback, threading, time, os, psycopg2
from types import SimpleNamespace
from flask import render_template, render_template_string, request, redirect, url_for, flash, session
from flask import render_template, request, redirect, url_for, flash, session
from jinja2 import TemplateNotFound
# -- app modules
from crud import Database, create_tables
from config import MAIL_SETTINGS, DB_CONFIG as RAW_DB


# --- tambahkan di bagian import paling atas ---
from jinja2 import TemplateNotFound

# --- helper universal SELECT ALL: kembalikan list[dict] ---
def _fetch_all_sql(sql, params=None):
    params = params or []
    # coba lewat helper Database kamu (apapun nama metodenya)
    try:
        db = Database(DB_CONFIG)
        for name in ("fetch_all", "select_all", "query_all", "all"):
            if hasattr(db, name):
                rows = getattr(db, name)(sql, params) or []
                if rows and not isinstance(rows[0], dict):
                    raise RuntimeError("Rows are tuples; use psycopg2 dict cursor")
                return rows
        if hasattr(db, "execute"):
            rows = db.execute(sql, params, fetch="all") or []
            if rows and not isinstance(rows[0], dict):
                raise RuntimeError("Rows are tuples; use psycopg2 dict cursor")
            return rows
    except Exception as e:
        print("DB helper failed, fallback psycopg2:", e)

    # fallback langsung psycopg2 dict
    import psycopg2, psycopg2.extras
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql, params)
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        try: cur.close()
        except: pass
        conn.close()


# =========================
# App & Config dasar
# =========================
load_dotenv()

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev")

import os, logging
logging.basicConfig(level=logging.INFO)
logging.info(f"Jinja search path: {getattr(app.jinja_loader, 'searchpath', None)}")
tpl_dir = os.path.join(os.path.dirname(__file__), "templates")
logging.info(f"Templates dir exists? {os.path.isdir(tpl_dir)}")
try:
    logging.info(f"Templates list: {os.listdir(tpl_dir)}")
except Exception as e:
    logging.info(f"Gagal list templates: {e}")



# ==== Guard / Auth decorators ====
from functools import wraps
from flask import session, redirect, url_for, flash, request

def require_login(role=None):
    """
    Pakai @require_login() untuk halaman umum (harus login),
    atau @require_login(role="admin") untuk halaman khusus admin.
    """
    def deco(f):
        @wraps(f)
        def inner(*a, **kw):
            # belum login
            if 'user_id' not in session:
                # simpan tujuan biar bisa balik setelah login
                session['next'] = request.full_path if request.query_string else request.path
                return redirect(url_for('login'))

            # cek role kalau diminta
            if role is not None and session.get('role') != role:
                flash('Anda tidak memiliki izin mengakses halaman ini.', 'error')
                return redirect(url_for('dashboard'))
            return f(*a, **kw)
        return inner
    return deco


from flask import Response

@app.get("/no-image")
def no_image():
    svg = """
    <svg xmlns='http://www.w3.org/2000/svg' width='512' height='384' viewBox='0 0 512 384'>
      <defs>
        <linearGradient id='g' x1='0' y1='0' x2='1' y2='1'>
          <stop offset='0%' stop-color='#c08906'/>
          <stop offset='100%' stop-color='#e7b64a'/>
        </linearGradient>
      </defs>
      <rect width='100%' height='100%' fill='#f5f5f5'/>
      <rect x='24' y='24' width='464' height='336' rx='16' fill='url(#g)' opacity='.08'/>
      <g fill='#c08906' opacity='.6'>
        <circle cx='176' cy='152' r='56'/>
        <path d='M72 320h368l-96-128-96 88-56-56-120 96z'/>
      </g>
    </svg>
    """.strip()
    return Response(svg, mimetype="image/svg+xml")


# Mail
from flask_mail import Mail, Message
app.config.update(MAIL_SETTINGS)
mail = Mail(app)

logging.basicConfig(level=logging.INFO)
logging.info("App start")

# DB config normalisasi key
DB_CONFIG = {
    "host": RAW_DB.get("host"),
    "database": RAW_DB.get("dbname") or RAW_DB.get("database"),
    "user": RAW_DB.get("user"),
    "password": RAW_DB.get("password"),
    "port": RAW_DB.get("port"),
}

# =========================
# Upload Helpers (Produk + Avatar)
# =========================
ALLOWED_IMG = {"png", "jpg", "jpeg", "webp"}
app.config["MAX_CONTENT_LENGTH"] = 4 * 1024 * 1024  # 4MB

PRODUCT_FOLDER = os.path.join(app.static_folder, "img", "products")
AVATAR_FOLDER  = os.path.join(app.static_folder, "img", "avatars")
os.makedirs(PRODUCT_FOLDER, exist_ok=True)
os.makedirs(AVATAR_FOLDER,  exist_ok=True)

def _save_webp(file_storage, dst_abs: str) -> bool:
    """Simpan file ke WEBP (kecil & konsisten)."""
    try:
        im = Image.open(file_storage.stream).convert("RGB")
        im.save(dst_abs, "WEBP", quality=90)
        return True
    except Exception as e:
        print("Gagal simpan WEBP:", e)
        return False

def save_product_image(file_storage, barang_id: int):
    """
    Simpan foto produk => static/img/products/prod_<id>.webp
    Return: "INVALID" | "OK" | None
    """
    if not file_storage or not file_storage.filename:
        return None
    ext_ok = "." in file_storage.filename and file_storage.filename.rsplit(".", 1)[1].lower() in ALLOWED_IMG
    if not ext_ok:
        return "INVALID"
    dst_abs = os.path.join(PRODUCT_FOLDER, f"prod_{barang_id}.webp")
    return "OK" if _save_webp(file_storage, dst_abs) else None

def product_img_relpath(barang_id: int) -> str:
    cand = os.path.join(PRODUCT_FOLDER, f"prod_{barang_id}.webp")
    return (f"img/products/prod_{barang_id}.webp" if os.path.exists(cand)
            else "img/no-image.png")

def save_avatar(file_storage, user_id: int):
    """
    Simpan avatar => static/img/avatars/user_<id>.webp
    Return: "INVALID" | "OK" | None
    """
    if not file_storage or not file_storage.filename:
        return None
    ext_ok = "." in file_storage.filename and file_storage.filename.rsplit(".", 1)[1].lower() in ALLOWED_IMG
    if not ext_ok:
        return "INVALID"
    dst_abs = os.path.join(AVATAR_FOLDER, f"user_{user_id}.webp")
    return "OK" if _save_webp(file_storage, dst_abs) else None

def avatar_relpath(user_id: int | None) -> str:
    if not user_id:
        return "img/avatars/guest.png"
    cand = os.path.join(AVATAR_FOLDER, f"user_{user_id}.webp")
    return (f"img/avatars/user_{user_id}.webp" if os.path.exists(cand)
            else "img/avatars/guest.png")

# Inject variabel umum ke semua template (navbar aman)
@app.context_processor
def inject_user_ctx():
    uid = session.get("user_id")
    return dict(
        nama=session.get("nama", "Pengguna"),
        role=session.get("role", ""),
        avatar_url=url_for("static", filename=avatar_relpath(uid))
    )

# File kebesaran
@app.errorhandler(RequestEntityTooLarge)
def _too_big(_e):
    flash("File terlalu besar (maks 4 MB).", "error")
    return redirect(request.referrer or url_for("dashboard"))

# Jika ada template lama panggil csrf_token()
@app.context_processor
def inject_csrf():
    return dict(csrf_token=lambda: "")

# Error handler global (log ke console)
@app.errorhandler(Exception)
def handle_exception(e):
    traceback.print_exc()
    return "Internal Server Error", 500

# =========================
# Auth Utils
# =========================
def login_required(f):
    @wraps(f)
    def deco(*a, **kw):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*a, **kw)
    return deco

def check_role(required_role):
    return session.get("role") == required_role

# =========================
# Email Utils
# =========================
def send_email(to, subject, body):
    def _worker():
        try:
            with app.app_context():
                msg = Message(subject, recipients=[to])
                msg.body = body
                mail.send(msg)
        except Exception as e:
            print("[MAIL] ERROR:", e)
    threading.Thread(target=_worker, daemon=True).start()

# =========================
# Reset Password Tokens
# =========================
RESET_SALT = "reset-password"

def generate_token(email):
    s = URLSafeTimedSerializer(app.secret_key)
    return s.dumps(email, salt=RESET_SALT)

def verify_token(token, max_age=3600):
    s = URLSafeTimedSerializer(app.secret_key)
    try:
        return s.loads(token, salt=RESET_SALT, max_age=max_age)
    except Exception as e:
        print("Token error:", e)
        return None

# =========================
# ROUTES
# =========================
@app.route("/")
def home():
    return redirect(url_for("dashboard") if "user_id" in session else url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        db = Database(DB_CONFIG)
        user = db.get_user(username)
        if user and check_password_hash(user[2], password):
            session["user_id"] = user[0]
            session["role"]   = user[3]
            session["nama"]   = user[4]
            flash("Login berhasil!", "success")
            return redirect(url_for("dashboard"))
        flash("Username atau password salah", "error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out", "info")
    return redirect(url_for("login"))

@app.route('/dashboard')
@login_required
def dashboard():
    try:
        db = Database(DB_CONFIG)
        data_barang = db.read_all_barang() or []
        total_produk = len(data_barang)
        return render_template(
            "dashboard.html",
            barang=data_barang,
            total_produk=total_produk
        )
    except Exception:
        logging.exception("Dashboard load failed")
        flash("Terjadi kesalahan saat memuat dashboard.", "error")
        return render_template("dashboard.html", barang=[], total_produk=0), 200

# ---------- Forgot / Reset ----------
@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        if not email or "@" not in email:
            flash("Masukkan email yang valid.", "error")
            return redirect(url_for("forgot_password"))
        try:
            db = Database(DB_CONFIG)
            exists = False
            try:
                exists = db.check_email_exists(email)
            except Exception as e:
                print("[FORGOT] check_email_exists error:", e)

            if exists:
                token = generate_token(email)
                reset_url = url_for("reset_password", token=token, _external=True)
                try:
                    send_email(
                        to=email, subject="Reset Password",
                        body=(
                            "Halo,\n\nKlik tautan ini untuk reset password (berlaku 1 jam):\n"
                            f"{reset_url}\n\nJika tidak meminta reset, abaikan email ini."
                        )
                    )
                except Exception as e:
                    print("[FORGOT] send_email error:", e)

            flash("Jika email terdaftar, instruksi reset sudah dikirim.", "success")
            return redirect(url_for("forgot_password"))
        except Exception as e:
            print("[FORGOT] unexpected error:", e)
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
        confirm      = request.form.get("confirm_password", "")
        if not new_password or new_password != confirm:
            flash("Konfirmasi password tidak cocok.", "error")
            return redirect(request.url)

        db = Database(DB_CONFIG)
        hashed = generate_password_hash(new_password)
        if db.update_user_password_by_email(email, hashed):
            flash("Password berhasil diubah. Silakan login.", "success")
            return redirect(url_for("login"))
        flash("Gagal menyimpan password baru.", "error")
    return render_template("reset_password.html")

# ---------- Register ----------
@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    try:
        if request.method == "POST":
            username = request.form["username"]
            password = request.form["password"]
            confirm  = request.form["confirm_password"]
            nama     = request.form["nama"]
            email    = request.form["email"]
            nohp     = request.form["nohp"]

            if password != confirm:
                flash("Password dan konfirmasi password tidak sama", "error")
                return redirect(url_for("register"))

            db = Database(DB_CONFIG)
            if db.get_user(username):
                flash("Username sudah digunakan", "error")
                return redirect(url_for("register"))
            if db.check_email_exists(email):
                flash("Email sudah terdaftar", "error")
                return redirect(url_for("register"))

            role = "admin" if (db.count_users() == 0) else "user"
            user_id = db.create_user(username, password, role, nama, email, nohp)
            if user_id:
                flash("Registrasi berhasil! Silakan login.", "success")
                return redirect(url_for("login", success=True))
            flash("Registrasi gagal", "error")
    except Exception:
        logging.exception("Register error")
        flash("Terjadi kesalahan saat menyimpan data", "error")
    return render_template("register.html")

# ---------- Edit Profile (+ Avatar) ----------
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
        user = SimpleNamespace(username=u[1], nama=u[4], email=u[5], nohp=u[6])
        return render_template("editProfile.html", user=user,
                               avatar_url=url_for("static", filename=avatar_relpath(user_id)))

    # POST
    username = (request.form.get("username") or "").strip()
    password = (request.form.get("password") or "").strip() or None
    nama     = (request.form.get("nama") or "").strip()
    email    = (request.form.get("email") or "").strip()
    nohp     = (request.form.get("nohp") or "").strip()

    if not all([username, nama, email, nohp]):
        flash("Semua field kecuali password wajib diisi", "error")
        return redirect(url_for("editProfile"))

    if db.check_username_exists(username, user_id):
        flash("Username sudah digunakan pengguna lain", "error")
        return redirect(url_for("editProfile"))
    if db.check_email_exists_for_update(email, user_id):
        flash("Email sudah digunakan pengguna lain", "error")
        return redirect(url_for("editProfile"))

    ok = db.update_user(user_id, username, nama, email, nohp, role=None, password=password)
    if not ok:
        flash("Gagal memperbarui profil", "error")
        return redirect(url_for("editProfile"))

    # Avatar (opsional)
    file = request.files.get("avatar")
    if file and file.filename:
        res = save_avatar(file, user_id)
        if res == "INVALID":
            flash("Format gambar tidak didukung (png/jpg/jpeg/webp).", "error")
        elif res is None:
            flash("Gagal menyimpan foto profil.", "error")
        else:
            flash("Foto profil diperbarui.", "success")

    session["nama"] = nama
    flash("Profil berhasil diperbarui", "success")
    return redirect(url_for("editProfile"))

# ---------- CRUD Barang ----------
@app.route('/addBarang', methods=['GET', 'POST'])
def addBarang():
    if not check_role('admin'):
        flash("Akses tidak diizinkan", "error")
        return redirect('/')

    if request.method == 'POST':
        try:
            nama_barang = (request.form.get('nama_barang') or '').strip()
            harga_raw   = (request.form.get('harga') or '').strip()
            deskripsi   = (request.form.get('deskripsi') or '').strip()
            foto_file   = request.files.get('foto')  # opsional

            if not nama_barang or not harga_raw or not deskripsi:
                flash("Semua field harus diisi!", "error")
                return render_template("addBarang.html")

            # normalisasi harga: dukung format 150.000 atau 150,000.00
            try:
                harga = float(harga_raw.replace('.', '').replace(',', '.'))
            except ValueError:
                flash("Harga harus berupa angka!", "error")
                return render_template("addBarang.html")

            db = Database(DB_CONFIG)

            # (opsional) contoh validasi unik sederhana
            # if db.get_data_barang_nama_harga(nama_barang, harga):
            #     flash("Nama dan Harga Barang sudah terdaftar", "error")
            #     return render_template("addBarang.html")

            # 1) simpan record dulu untuk dapatkan ID
            barang_id = db.create_barang(nama_barang, harga, deskripsi)
            if not barang_id:
                flash("Tambah Barang gagal. Coba lagi.", "error")
                return render_template("addBarang.html")

            # 2) simpan foto (opsional) -> prod_<ID>.webp
            if foto_file and foto_file.filename:
                fname = secure_filename(foto_file.filename)
                ext = fname.rsplit('.', 1)[-1].lower() if '.' in fname else ''
                if ext not in {"png", "jpg", "jpeg", "webp"}:
                    flash("Format gambar tidak didukung (png/jpg/jpeg/webp).", "warning")
                else:
                    try:
                        img = Image.open(foto_file.stream)
                        if img.mode in ("RGBA", "P"):
                            img = img.convert("RGB")
                        dst_path = os.path.join(app.static_folder, "img", "products", f"prod_{barang_id}.webp")
                        img.save(dst_path, "WEBP", quality=90)
                    except Exception as e:
                        print("[ADD BARANG] gagal simpan foto:", e)
                        flash("Barang tersimpan, namun foto gagal diunggah.", "warning")

            flash("Barang berhasil ditambahkan!", "success")
            # balik ke dashboard (admin mengelola barang via tombol Edit di kartu)
            return redirect(url_for("dashboard"))

        except Exception as e:
            print("[ADD BARANG] error:", e)
            flash("Terjadi kesalahan saat menyimpan data.", "error")
            return render_template("addBarang.html")

    # GET
    return render_template("addBarang.html")

@app.route("/editBarang/<id_barang>", methods=["GET", "POST"])
def editBarang(id_barang):
    if not check_role("admin"):
        flash("Akses tidak diizinkan", "error")
        return redirect("/")

    if not id_barang.isdigit():
        flash("ID barang tidak valid", "error")
        return redirect(url_for("dashboard"))

    db = Database(DB_CONFIG)

    if request.method == "GET":
        barang = db.get_barang_by_id(id_barang)
        if not barang:
            flash("Data barang tidak ditemukan", "error")
            return redirect(url_for("dashboard"))
        return render_template("editBarang.html", barang=barang)

    # POST
    try:
        nama_barang = (request.form.get("nama_barang") or "").strip()
        harga_raw   = (request.form.get("harga") or "").strip()
        deskripsi   = (request.form.get("deskripsi") or "").strip()

        if not nama_barang or not harga_raw or not deskripsi:
            flash("Semua field harus diisi", "error")
            return redirect(url_for("editBarang", id_barang=id_barang))

        harga = float(harga_raw.replace(".", "").replace(",", "."))

        ok = db.update_barang(id_barang, nama_barang, harga, deskripsi)
        if not ok:
            flash("Gagal memperbarui data barang", "error")
            return redirect(url_for("editBarang", id_barang=id_barang))

        # Foto (opsional)
        file = request.files.get("foto")
        if file and file.filename:
            res = save_product_image(file, int(id_barang))
            if res == "INVALID":
                flash("Format gambar tidak didukung (png/jpg/jpeg/webp).", "error")
                return redirect(url_for("editBarang", id_barang=id_barang))
            elif res is None:
                flash("Gagal menyimpan gambar.", "error")
                return redirect(url_for("editBarang", id_barang=id_barang))

        flash("Barang berhasil diperbarui!", "success")
        return redirect(url_for("dashboard"))
    except Exception:
        logging.exception("editBarang error")
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
            return redirect(url_for("dashboard"))

        if db.delete_barang(id_barang):
            flash("Data barang berhasil dihapus!", "success")
        else:
            flash("Gagal menghapus data barang", "error")
        return redirect(url_for("dashboard"))
    except Exception:
        logging.exception("deleteBarang error")
        flash("Terjadi kesalahan sistem saat menghapus barang", "error")
        return redirect(url_for("dashboard"))

# ---------- Admin Menu: Kelola User ----------
@app.route("/menuAdmin", methods=["GET"])
def menuAdmin():
    if not check_role("admin"):
        flash("Anda tidak memiliki akses ke halaman ini", "error")
        return redirect("/")

    try:
        roleMenu = (request.args.get("roleMenu") or "kelolaUser").strip().lower()
        db = Database(DB_CONFIG)

        if roleMenu in ("kelolabarang", "barang", "produk"):
            flash("Kelola barang kini di Dashboard (tombol Edit pada kartu).", "info")
            return redirect(url_for("dashboard"))

        if roleMenu in ("kelolauser", "user"):
            users = db.read_all_users() or []
            return render_template("kelolaUser.html", users=users)

        return redirect(url_for("menuAdmin", roleMenu="kelolaUser"))

    except Exception:
        logging.exception("menuAdmin error")
        flash("Terjadi kesalahan. Coba lagi nanti.", "error")
        return redirect("/")

# ---------- CRUD User ringkas ----------
@app.route("/addUser", methods=["GET", "POST"])
def addUser():
    if not check_role("admin"):
        flash("Akses tidak diizinkan", "error")
        return redirect("/")
    if request.method == "POST":
        try:
            username = request.form["username"]
            password = request.form["password"]
            confirm  = request.form["confirm_password"]
            nama     = request.form["nama"]
            email    = request.form["email"]
            nohp     = request.form["nohp"]

            if password != confirm:
                flash("Password dan konfirmasi password tidak sama", "error")
                return redirect(url_for("addUser"))

            db = Database(DB_CONFIG)
            if db.get_user(username):
                flash("Username sudah digunakan", "error")
                return redirect(url_for("addUser"))
            if db.check_email_exists(email):
                flash("Email sudah terdaftar", "error")
                return redirect(url_for("addUser"))

            role = "admin" if db.count_users() == 0 else "user"
            user_id = db.create_user(username, password, role, nama, email, nohp)
            if user_id:
                flash("Registrasi berhasil! Silakan login.", "success")
                return redirect(url_for("login", success=True))
            flash("Registrasi gagal", "error")
        except Exception:
            logging.exception("addUser error")
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
            updated_id = db.update_user(user_id, user[1], user[4], user[5], user[6], role, None)
            if updated_id:
                flash("Role pengguna berhasil diubah", "success")
                return redirect(url_for("menuAdmin", roleMenu="kelolaUser"))
            flash("Gagal mengubah role pengguna", "error")
        except Exception:
            logging.exception("editUser role error")
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

# ---------- CART ----------
@app.route("/cart")
@login_required
def cart_view():
    db = Database(DB_CONFIG)
    items, total = db.get_cart_items(session["user_id"])
    return render_template("cart.html", items=items, total=total)

@app.route("/cart/add/<int:barang_id>", methods=["POST"])
@login_required
def cart_add(barang_id):
    qty = int((request.form.get("qty") or "1").strip() or "1")
    if qty <= 0: qty = 1
    db = Database(DB_CONFIG)
    ok = db.add_to_cart(session["user_id"], barang_id, qty)
    flash("Ditambahkan ke keranjang" if ok else "Gagal menambahkan ke keranjang",
          "success" if ok else "error")
    return redirect(request.referrer or url_for("dashboard"))

@app.route("/cart/update", methods=["POST"])
@login_required
def cart_update():
    item_id = int(request.form.get("item_id"))
    qty     = int(request.form.get("qty"))
    db = Database(DB_CONFIG)
    ok = db.update_cart_qty(item_id, qty, session["user_id"])
    flash("Keranjang diperbarui" if ok else "Gagal memperbarui keranjang",
          "success" if ok else "error")
    return redirect(url_for("cart_view"))

@app.route("/cart/remove/<int:item_id>", methods=["POST"])
@login_required
def cart_remove(item_id):
    db = Database(DB_CONFIG)
    ok = db.remove_cart_item(item_id, session["user_id"])
    flash("Item dihapus" if ok else "Gagal menghapus item",
          "success" if ok else "error")
    return redirect(url_for("cart_view"))

# ---------- CHECKOUT ----------
@app.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    db = Database(DB_CONFIG)
    if request.method == "GET":
        items, total = db.get_cart_items(session["user_id"])
        if not items:
            flash("Keranjang masih kosong", "warning")
            return redirect(url_for("dashboard"))
        return render_template("checkout.html", items=items, total=total)

    payment_method   = (request.form.get("payment_method") or "COD").upper()  # COD | TRANSFER
    shipping_address = (request.form.get("shipping_address") or "").strip()
    if not shipping_address:
        flash("Alamat pengiriman wajib diisi", "error")
        return redirect(url_for("checkout"))

    order_id = db.create_order_from_cart(session["user_id"], payment_method, shipping_address)
    if not order_id:
        flash("Gagal membuat pesanan", "error")
        return redirect(url_for("checkout"))

    # Tahap awal: COD/TRANSFER manual
    if payment_method == "COD":
        db.update_order_status(order_id, "baru", "pending")
        flash(f"Pesanan #{order_id} dibuat. Metode: COD. Admin akan memproses.", "success")
    else:
        flash(f"Pesanan #{order_id} dibuat. Silakan ikuti instruksi transfer pada daftar pesanan.", "success")

    return redirect(url_for("orders_me"))

# ---------- Pesanan Saya (user) ----------
@app.route("/orders/me")
@login_required
def orders_me():
    db = Database(DB_CONFIG)
    rows = db.list_user_orders(session["user_id"])
    return render_template("orders_me.html", orders=rows)

# ---------- Admin: Kelola Pesanan ----------
# ==== Admin: daftar pesanan ====

# =========================
# Util SQL yang fleksibel
# =========================
import psycopg2, psycopg2.extras, traceback

def _db_try_all(db, sql, params=None, one=False):
    """
    Coba berbagai method yang mungkin ada di kelas Database.
    Jika tidak ada, fallback ke psycopg2 langsung pakai DB_CONFIG.
    Return: list of rows (dict-like) atau single row (kalau one=True).
    """
    params = params or []

    # 1) Coba method umum di wrapper Database
    for name in ("select", "fetch_all", "select_all"):
        if hasattr(db, name):
            rows = getattr(db, name)(sql, params) or []
            return (rows[0] if (one and rows) else rows)

    # 2) Coba pattern execute() yang mengembalikan cursor/rows
    if hasattr(db, "execute"):
        res = db.execute(sql, params)
        try:
            rows = list(res) if res is not None else []
        except Exception:
            rows = res or []
        return (rows[0] if (one and rows) else rows)

    # 3) Fallback psycopg2 langsung
    conn = None
    try:
        conn = psycopg2.connect(
            host=DB_CONFIG.get("host"),
            port=DB_CONFIG.get("port"),
            dbname=DB_CONFIG.get("dbname") or DB_CONFIG.get("database"),
            user=DB_CONFIG.get("user"),
            password=DB_CONFIG.get("password"),
            sslmode=DB_CONFIG.get("sslmode", "require"),
        )
        with conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
            return (rows[0] if (one and rows) else rows)
    finally:
        if conn:
            conn.close()


def _get(row, key, idx):
    """Ambil kolom dari row (dict/tuple)."""
    if isinstance(row, dict):
        return row.get(key)
    try:
        return row[idx]
    except Exception:
        return None




# =========================
# ADMIN: Daftar Pesanan
# =========================
@app.route("/admin/orders")
def admin_orders():
    if not check_role("admin"):
        flash("Akses ditolak", "error")
        return redirect(url_for("dashboard"))

    status = (request.args.get("status") or "semua").lower()
    where, params = "", []
    if status != "semua":
        where = "WHERE o.status = %s"
        params = [status]

    sql = f"""
      SELECT
        o.id,
        COALESCE(u.nama, u.username) AS customer,
        o.status,
        COALESCE(o.total, 0) AS total,
        COALESCE(o.payment_method, '-') AS payment_method,
        COALESCE(o.payment_status, 'pending') AS payment_status,
        o.created_at
      FROM orders o
      LEFT JOIN users u ON u.id = o.user_id
      {where}
      ORDER BY o.id DESC
    """

    db = Database(DB_CONFIG)

    # ambil semua rows dengan kompatibel untuk berbagai wrapper Database
    def _run_all(sql, params=None):
        params = params or []
        for name in ("select", "fetch_all", "select_all"):
            if hasattr(db, name):
                return getattr(db, name)(sql, params) or []
        return []

    rows = _run_all(sql, params)

    # normalisasi row -> dict
    def _get(r, key, idx):
        if isinstance(r, dict): return r.get(key)
        try: return r[idx]
        except Exception: return None

    orders = [{
        "id":              _get(r, "id",              0),
        "customer":        _get(r, "customer",        1),
        "status":         (_get(r, "status",          2) or "baru"),
        "total":          int(_get(r, "total",        3) or 0),
        "payment_method": (_get(r, "payment_method",  4) or "-"),
        "payment_status": (_get(r, "payment_status",  5) or "pending"),
        "created_at":      _get(r, "created_at",      6),
    } for r in rows]

    # ⬇︎ render langsung file di folder templates
    return render_template("order_admin.html", orders=orders, status=status, role="admin")


# =========================
# ADMIN: Detail Pesanan
# =========================
@app.route("/admin/orders/<int:order_id>", methods=["GET", "POST"])
def admin_order_detail(order_id):
    if not check_role("admin"):
        flash("Akses ditolak", "error")
        return redirect(url_for("dashboard"))

    db = Database(DB_CONFIG)

    if request.method == "POST":
        action = (request.form.get("action") or "").lower()
        mapping = {"terima": "diterima", "proses": "diproses", "selesai": "selesai", "batal": "batal"}
        if action in mapping and hasattr(db, "update_order_status"):
            ok = db.update_order_status(order_id, mapping[action])
            flash("Status diperbarui" if ok else "Gagal memperbarui status",
                  "success" if ok else "error")
        else:
            flash("Aksi tidak dikenali", "warning")
        return redirect(url_for("admin_order_detail", order_id=order_id))

    # helper select
    def _run_one(sql, params=None):
        params = params or []
        if hasattr(db, "select_one"):
            return db.select_one(sql, params)
        rows = _run_all(sql, params)
        return rows[0] if rows else None

    def _run_all(sql, params=None):
        params = params or []
        for name in ("select", "fetch_all", "select_all"):
            if hasattr(db, name):
                return getattr(db, name)(sql, params) or []
        return []

    def _get(r, key, idx):
        if isinstance(r, dict): return r.get(key)
        try: return r[idx]
        except Exception: return None

    # header
    sql_head = """
      SELECT
        o.id,
        COALESCE(u.nama, u.username) AS customer,
        o.status,
        COALESCE(o.total,0) AS total,
        COALESCE(o.payment_method,'-') AS payment_method,
        COALESCE(o.payment_status,'-') AS payment_status,
        o.created_at
      FROM orders o
      LEFT JOIN users u ON u.id = o.user_id
      WHERE o.id = %s
    """
    h = _run_one(sql_head, [order_id])
    if not h:
        flash("Pesanan tidak ditemukan", "error")
        return redirect(url_for("admin_orders"))

    order = {
        "id":              _get(h, "id",              0),
        "customer":        _get(h, "customer",        1),
        "status":         (_get(h, "status",          2) or "-"),
        "total":          int(_get(h, "total",        3) or 0),
        "payment_method": (_get(h, "payment_method",  4) or "-"),
        "payment_status": (_get(h, "payment_status",  5) or "-"),
        "created_at":      _get(h, "created_at",      6),
    }

    # items (coba beberapa nama tabel umum)
    for sql_items in (
        "SELECT oi.id, oi.qty, oi.harga, COALESCE(b.nama,'(Produk)') AS nama FROM order_items oi LEFT JOIN barang b ON b.id=oi.barang_id WHERE oi.order_id=%s ORDER BY oi.id",
        "SELECT d.id, d.qty, d.harga, COALESCE(b.nama,'(Produk)') AS nama FROM order_details d LEFT JOIN barang b ON b.id=d.barang_id WHERE d.order_id=%s ORDER BY d.id",
    ):
        raw = _run_all(sql_items, [order_id])
        if raw:
            break
    else:
        raw = []

    items = [{
        "id":    _get(r, "id",    0),
        "qty":   int(_get(r, "qty",   1) or 0),
        "harga": int(_get(r, "harga", 2) or 0),
        "nama":  _get(r, "nama",  3),
    } for r in raw]

    # ⬇︎ render langsung file di folder templates
    return render_template("order_detail_admin.html", order=order, items=items, role="admin")




@app.context_processor
def inject_cart_count():
    cart_count = 0
    try:
        uid = session.get("user_id")
        role = session.get("role")  # pastikan role disimpan saat login
        if uid and role == "user":
            db = Database(DB_CONFIG)
            cart_count = db.get_cart_count(uid)
    except Exception as e:
        print("inject_cart_count error:", e)
    return {"cart_count": cart_count, "role": session.get("role")}

def inject_noimg():
    NOIMG = ('data:image/svg+xml;utf8,'
             '<svg xmlns="http://www.w3.org/2000/svg" width="320" height="240">'
             '<rect width="100%25" height="100%25" fill="%23f1f5f9"/>'
             '<g fill="%2394a3b8"><rect x="40" y="60" width="240" height="120" rx="12" ry="12" fill="%23e2e8f0"/>'
             '<path d="M80 150l40-40 30 30 40-50 30 40" fill="none" stroke="%2394a3b8" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/></g>'
             '</svg>')
    return {"NOIMG": NOIMG}

# =========================
# Entrypoint
# =========================
if __name__ == "__main__":
    # pastikan tabel ada
    create_tables(DB_CONFIG)

    # cek koneksi singkat
    try:
        print("Mencoba konek ke database...")
        conn = psycopg2.connect(
            host=DB_CONFIG["host"], dbname=DB_CONFIG["database"],
            user=DB_CONFIG["user"], password=DB_CONFIG["password"], port=DB_CONFIG["port"]
        )
        with conn.cursor() as cur:
            cur.execute("SELECT NOW();")
            print("Sukses konek! Waktu DB sekarang:", cur.fetchone())
        conn.close()
    except Exception as e:
        print("Gagal konek ke database:", e)

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
