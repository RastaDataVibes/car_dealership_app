import os

class Config:
    SQLALCHEMY_DATABASE_URI = "postgresql://bisle_admin:C0pMvogaeVEDOrEWML5NdEBjVokXCHC8@dpg-d5ia7n94tr6s73a2loog-a.oregon-postgres.render.com/gc_db_ei5a"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = "rasta_secret_420"

    # ADD: For Superset JWT token secret (must match Superset's SECRET_KEY)
    SUPERSET_SECRET_KEY = os.environ.get('SUPERSET_SECRET_KEY', 'my-very-strong-secret-12345')  # Fallback for local; set strong one on Render
    
    # ADD: Toggle for cache flush (false on Render to skip Redis errors)
    FLUSH_CACHE_ENABLED = os.environ.get('FLUSH_CACHE_ENABLED', 'true').lower() == 'true'  # Bool for easy if-checks in app.py
