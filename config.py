import os

class Config:
    SQLALCHEMY_DATABASE_URI = "postgresql://bisle_admin:C0pMvogaeVEDOrEWML5NdEBjVokXCHC8@dpg-d5ia7n94tr6s73a2loog-a.oregon-postgres.render.com/gc_db_ei5a"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = "rasta_secret_420"

    # ADD: For Superset JWT token secret (must match Superset's SECRET_KEY)
    SUPERSET_SECRET_KEY = os.environ.get('SUPERSET_SECRET_KEY', 'my-very-strong-secret-12345')  # Fallback for local; set strong one on Render
    
    # ADD: Toggle for cache flush (false on Render to skip Redis errors)
    FLUSH_CACHE_ENABLED = os.environ.get('FLUSH_CACHE_ENABLED', 'true').lower() == 'true'  # Bool for easy if-checks in app.py
# Email configuration
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', 'opiobethle@gmail.com')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')  # MUST be in env vars
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_USERNAME', 'opiobethle@gmail.com')

    PESAPAL_CONSUMER_KEY = os.environ.get('PESAPAL_CONSUMER_KEY')
    PESAPAL_CONSUMER_SECRET = os.environ.get('PESAPAL_CONSUMER_SECRET')
