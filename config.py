import os

class Config:
    SQLALCHEMY_DATABASE_URI = "postgresql+psycopg2://zaga_admin:Y1hfxNhumANyST9BcyjxO0RC4m2KXOA2@dpg-d3n1av49c44c73cgjts0-a.oregon-postgres.render.com:5432/used_car_dealership_db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = "rasta_secret_420"

    # ADD: For Superset JWT token secret (must match Superset's SECRET_KEY)
    SUPERSET_SECRET_KEY = os.environ.get('SUPERSET_SECRET_KEY', 'my-very-strong-secret-12345')  # Fallback for local; set strong one on Render
    
    # ADD: Toggle for cache flush (false on Render to skip Redis errors)
    FLUSH_CACHE_ENABLED = os.environ.get('FLUSH_CACHE_ENABLED', 'true').lower() == 'true'  # Bool for easy if-checks in app.py
