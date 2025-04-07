import os

DB_CONFIG = {
    'host': os.getenv("DB_HOST", "maglev.proxy.rlwy.net"),
    'dbname': os.getenv("DB_NAME", "railway"),
    'user': os.getenv("DB_USER", "postgres"),
    'password': os.getenv("DB_PASSWORD", "JxlxNXWerXUEyNLkCgxgBlhSvXKMfNjo"),
    'port': os.getenv("DB_PORT", 39316)
}
