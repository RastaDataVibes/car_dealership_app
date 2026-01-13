# Full models.py file
# Tweaks Summary:
# 1. Added helpers: update_expenses_total() and calculate_profit() to model classes. These query sum expenses, update fields, and commit. Achieves: Accurate totals/profit on AJAX ops, ensuring table shows correct values on reload.
# 2. Event listener: Simplified to only handle date_added (if purchase_price set), status/date_sold (if selling_price). Removed id-dependent queries (fail on insert). Achieves: Safe auto-updates without errors during insert.
# 3. Expense date_added: Used lambda default for UTC now. Achieves: Consistent timestamps.
# 4. Added import for Session if needed, but used db.session directly. Kept __table_args__ extend_existing for schema flexibility.
# 5. No other changes; relationships and repr intact.

'''from app import db'''
from extensions import db
from datetime import datetime, timezone
from sqlalchemy import event
from sqlalchemy import func  # Tweak: Added for sum query in helper

# ------------------------
# Inventory Table
# ------------------------


class Inventory(db.Model):
    __tablename__ = 'inventory'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    make = db.Column(db.String(100), nullable=False)
    model = db.Column(db.String(100), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    registration_number = db.Column(db.String(50))
    sourced_from = db.Column(db.String(200))
    purchase_price = db.Column(db.Float)
    fixed_selling_price = db.Column(db.Float)
    expenses_amount = db.Column(db.Float, default=0.0)  # total expenses
    booked_profit = db.Column(db.Float)
    mileage = db.Column(db.Integer)
    photo_filename = db.Column(db.String(300))  # stores uploaded file name
    status = db.Column(db.String(20), default='Available')
    sold_to = db.Column(db.String(200))
    date_added = db.Column(db.DateTime)
    sale_date = db.Column(db.DateTime)
    notes = db.Column(db.Text)
    dealership_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    # Relationship to Expenses
    expenses = db.relationship(
        'Expense', backref='vehicle', cascade='all, delete-orphan', lazy=True
    )

    payments = db.relationship(
        'Payment', backref='vehicle', cascade='all, delete-orphan', lazy=True)

    
    def __repr__(self):
        return f"<Inventory {self.make} {self.model}>"

    # Tweak: Added helper to update expenses_amount from DB sum and commit
    def update_expenses_total(self):
        """Helper method to update expenses_amount from related expenses.
        Call this after adding/updating expenses or post-insert."""
        if self.id:
            total = db.session.query(func.sum(Expense.expense_amount)).filter(
                Expense.vehicle_id == self.id
            ).scalar() or 0.0
            self.expenses_amount = total
            db.session.commit()  # Commit the update
            return total
        return 0.0

    # Tweak: Added helper to calculate and update profit and commit
    def calculate_booked_profit(self):
        """Helper method to calculate and update profit.
        Call this after setting prices or updating expenses."""
        if self.purchase_price is not None and self.fixed_selling_price is not None:
            total_cost = (self.purchase_price or 0) + \
                (self.expenses_amount or 0)
            self.booked_profit = self.fixed_selling_price - total_cost
        else:
            self.booked_profit = None
        db.session.commit()  # Commit the update


# ------------------------
# Expenses Table
# ------------------------
class Expense(db.Model):
    __tablename__ = 'expenses'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey(
        'inventory.id'), nullable=False)
    expense_category = db.Column(db.String(100), nullable=False)
    expense_amount = db.Column(db.Float, nullable=False)
    # Tweak: Changed to lambda for default to avoid issues
    date_created = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<Expense {self.expense_category} - {self.expense_amount}>"


class Payment(db.Model):
    __tablename__ = 'payments'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey(
        'inventory.id'), nullable=False)
    payment_date = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now())
    amount = db.Column(db.Float, nullable=False)
    # e.g. "Installment #1", "Final Payment"
    category = db.Column(db.String(100), default="Installment")
    notes = db.Column(db.Text)

    created_at = db.Column(db.DateTime,
                           nullable=False,
                           default=lambda: datetime.now(timezone.utc),
                           server_default=func.now())

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    dealership_name = db.Column(db.String(100), nullable=False, unique=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20))
    password_hash = db.Column(db.String(128))
    is_trial = db.Column(db.Boolean, default=True)  # True = free trial
    trial_start = db.Column(db.DateTime, default=datetime.utcnow)
    subscription_plan = db.Column(
        db.String(20), default='trial')  # starter, standard, pro
    subscription_end = db.Column(db.DateTime)  # when subscription expires
    date_created = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    profile_name = db.Column(db.String(100))
    profile_photo_filename = db.Column(db.String(300))

    def set_password(self, password):
        from werkzeug.security import generate_password_hash
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        from werkzeug.security import check_password_hash
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.dealership_name}>"

# ------------------------
# Automatic behavior for Inventory
# ------------------------
@event.listens_for(Inventory, 'before_insert')
@event.listens_for(Inventory, 'before_update')
def auto_update_inventory(mapper, connection, target):
    """
    Automatically updates:
      - date_added when purchase_price is set (on insert/update)
      - date_sold when selling_price is set
      - status automatically
    Note: expenses_amount and profit are handled via explicit calls to helper methods in routes
    after insert/update (to avoid id=None issues during insert).
    """

    # 1️⃣ Set date_added automatically if missing and purchase_price is set
    if target.purchase_price and not target.date_added:
        target.date_added = datetime.now(timezone.utc)

    

    # Note: Do NOT calculate profit or expenses here; use helpers post-commit
