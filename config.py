# config.py

from flask import session
import redis
import os

def check_role(required_role):
    """Cek apakah role user di session sesuai dengan required_role"""
    role = session.get('role')  
    return role == required_role

# Tambahkan ini:
SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "postgresql://postgres:JxlxNXWerXUEyNLkCgxgBlhSvXKMfNjo@maglev.proxy.rlwy.net:39316/railway")
SQLALCHEMY_TRACK_MODIFICATIONS = False
