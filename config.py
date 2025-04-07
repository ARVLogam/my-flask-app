import os
from flask import session

def check_role(required_role):
    """Cek apakah role user di session sesuai dengan required_role"""
    role = session.get('role')  
    return role == required_role


DB_CONFIG = {
    'host': os.getenv("DB_HOST", "maglev.proxy.rlwy.net"),
    'dbname': os.getenv("DB_NAME", "railway"),
    'user': os.getenv("DB_USER", "postgres"),
    'password': os.getenv("DB_PASSWORD", "JxlxNXWerXUEyNLkCgxgBlhSvXKMfNjo"),
    'port': os.getenv("DB_PORT", 39316)
}
