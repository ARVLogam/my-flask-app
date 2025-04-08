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
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

MAIL_SETTINGS = {
    "MAIL_SERVER": "smtp.gmail.com",
    "MAIL_PORT": 587,
    "MAIL_USE_TLS": True,
    "MAIL_USERNAME": EMAIL_ADDRESS,
    "MAIL_PASSWORD": EMAIL_PASSWORD
}
