from extensions import db
from app import app
from models import Inventory

with app.app_context():
    try:
        items = Inventory.query.limit(5).all()
        for i in items:
            print(i.id, i.make, i.model, i.status)
        print("✅ Database connection successful!")
    except Exception as e:
        print("❌ Error connecting to database:", e)
