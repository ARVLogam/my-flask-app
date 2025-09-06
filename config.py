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
EMAIL_ADDRESS = 'secrap7@gmail.com'
EMAIL_PASSWORD = 'itlukqqxvhkqvuwq'

MAIL_SETTINGS = {
    "MAIL_SERVER": "smtp.gmail.com",
    "MAIL_PORT": 587,
    "MAIL_USE_TLS": True,
    "MAIL_USE_SSL": False,
    "MAIL_USERNAME": "secrap7@gmail.com",
    "MAIL_PASSWORD": "itlukqqxvhkqvuwq",   # App Password Gmail
    "MAIL_DEFAULT_SENDER": "secrap7@gmail.com"
}
