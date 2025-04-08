import os
from flask import session

def check_role(required_role):
    """Cek apakah role user di session sesuai dengan required_role"""
    role = session.get('role')  
    return role == required_role


DB_CONFIG = {
    'host': "maglev.proxy.rlwy.net",
    'dbname': "railway",
    'user': "postgres",
    'password': "JxlxNXWerXUEyNLkCgxgBlhSvXKMfNjo",
    'port': 39316
}
EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
