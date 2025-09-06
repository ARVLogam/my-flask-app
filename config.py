import os
from flask import session

def check_role(required_role):
    """Cek apakah role user di session sesuai dengan required_role"""
    role = session.get('role')
    return role == required_role


DB_CONFIG = {
    'host': os.getenv("PGHOST", "maglev.proxy.rlwy.net"),
    'dbname': os.getenv("PGDATABASE", "railway"),
    'user': os.getenv("PGUSER", "postgres"),
    'password': os.getenv("PGPASSWORD", "JxlxNXWerXUEyNLkCgxgBlhSvXKMfNjo"),
    'port': os.getenv("PGPORT", 39316)
}

MAIL_SETTINGS = {
    "MAIL_SERVER": "smtp.gmail.com",
    "MAIL_PORT": 587,
    "MAIL_USE_TLS": True,
    "MAIL_USE_SSL": False,
    "MAIL_USERNAME": os.getenv("EMAIL_ADDRESS", "secrap7@gmail.com"),
    "MAIL_PASSWORD": os.getenv("EMAIL_PASSWORD", "itlukqqxvhkqvuwq"),  # App Password Gmail
    "MAIL_DEFAULT_SENDER": os.getenv("EMAIL_ADDRESS", "secrap7@gmail.com"),
}
