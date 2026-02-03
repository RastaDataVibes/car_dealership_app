import os
import redis
import jwt
import time
import requests
from flask import render_template_string
from werkzeug.utils import secure_filename
from flask import Flask, render_template, jsonify, request, redirect, url_for, flash, current_app
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, FloatField, SubmitField, SelectField, PasswordField
from wtforms.validators import DataRequired, Email, EqualTo
from wtforms.validators import Optional
from flask_wtf.file import FileField, FileAllowed
from config import Config
from extensions import db
# Tweak: Added 'date' import for fixed CURRENT_DATE
from datetime import datetime, timezone, date, timedelta
from dashboard_view import dashboard_bp
# Tweak: Uncommented/ensured import for models
from models import Inventory, Expense, Payment, User
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer
from wtforms import PasswordField
from functools import wraps
from groq import Groq


def subscription_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('login'))

        # Check trial
        if current_user.is_trial:
            trial_end = current_user.trial_start + timedelta(days=30)
            if datetime.utcnow() > trial_end:
                flash('Your 30-day free trial has ended. Please subscribe.', 'warning')
                return redirect(url_for('subscribe'))

        # Check paid subscription
        if current_user.subscription_end and datetime.utcnow() > current_user.subscription_end:
            flash('Your subscription has expired. Please renew.', 'warning')
            return redirect(url_for('subscribe'))

        return f(*args, **kwargs)
    return decorated_function



def clean_float(value):
    """Convert string like '2,500,000' or '2500000.50' to float safely"""
    if value is None or value == '':
        return 0.0
    # Remove commas, then convert
    cleaned = str(value).replace(',', '')
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return 0.0

# ------------------------
# Initialize Flask app
# ------------------------
app = Flask(__name__)
app.config.from_object(Config)
'''db = SQLAlchemy(app)'''
db.init_app(app)

with app.app_context():
    from sqlalchemy import inspect
    inspector = inspect(db.engine)
    if not inspector.has_table('users'):           # or 'inventory' — your choice
        db.create_all()
        print("✅ Database tables created successfully (first run)")
    else:
        print("✅ Tables already exist, skipping creation")

app.register_blueprint(dashboard_bp)

UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

mail = Mail(app)
s = URLSafeTimedSerializer(app.config['SECRET_KEY'])

# PESAPAL SETTINGS
PESAPAL_BASE_URL = 'https://pay.pesapal.com/v3/'  
PESAPAL_TOKEN_URL = 'https://pay.pesapal.com/v3/api/Auth/RequestToken'  
PESAPAL_ORDER_URL = 'https://pay.pesapal.com/v3/api/Transactions/SubmitOrderRequest' 
PESAPAL_CALLBACK_URL = 'https://car-dealership-app-wxs8.onrender.com/pesapal_callback'  

REAL_NOTIFICATION_ID = "8e0dc841-be13-4158-a7a4-dad520d11491"

def get_pesapal_token():
    payload = {
        "consumer_key": app.config['PESAPAL_CONSUMER_KEY'],
        "consumer_secret": app.config['PESAPAL_CONSUMER_SECRET']
    }
    headers = {'Content-Type': 'application/json'}
    response = requests.post(PESAPAL_TOKEN_URL, json=payload, headers=headers)
    print("Token request status:", response.status_code)
    print("Token response:", response.text)

    if response.status_code == 200:
        try:
            return response.json()['token']
        except KeyError:
            print("Token key missing in response")
            return None
    else:
        print("Pesapal login failed")
        return None
        

def initiate_pesapal_payment(amount, plan, user):
    print("Inside initiate_pesapal_payment for user ID:", user.id)
    
    token = get_pesapal_token()
    if not token:
        print("!!! CRITICAL: No token received from Pesapal - check consumer key/secret in Render env vars")
        return None
    
    print("Token received successfully")
    
    merchant_ref = f"user_{user.id}_{int(time.time())}"
    print("Generated merchant_ref:", merchant_ref)
    
    order_data = {
        "id": merchant_ref,
        "currency": "UGX",
        "amount": float(amount),  # force number
        "description": f"GreenChain {plan} subscription",
        "callback_url": PESAPAL_CALLBACK_URL,
        "notification_id": REAL_NOTIFICATION_ID,
        "billing_address": {
            "email_address": user.email or "test@example.com",  # fallback if missing
            "phone_number": user.phone or "256700000000",
            "first_name": user.dealership_name or "Test User"
        }
    }
    print("Order data being sent to Pesapal:", order_data)
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {token}'
    }
    
    print("Sending POST to:", PESAPAL_ORDER_URL)
    response = requests.post(PESAPAL_ORDER_URL, json=order_data, headers=headers)
    
    print("Pesapal response status:", response.status_code)
    print("Pesapal full response text:", response.text)
    
    if response.status_code == 200:
        try:
            data = response.json()
            print("Parsed response JSON:", data)
            redirect_url = data.get('redirect_url') or data.get('url') or data.get('order_tracking_id')
            if redirect_url:
                print("Redirect URL found:", redirect_url)
                return redirect_url
            else:
                print("No redirect_url in response JSON")
        except Exception as e:
            print("JSON parse error:", str(e))
    else:
        print("Non-200 status from Pesapal - likely the cause of 'Payment error'")
        try:
            print("Error details:", response.json())
        except:
            print("Could not parse error JSON")
    
    return None
# NEW: Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # Route name for login page
login_manager.login_message = "Please log in to access GreenChain"
login_manager.login_message_category = "info"

# NEW: Tell Flask-Login how to load a user from session


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Forms
# ------------------------


class InventoryForm(FlaskForm):
    make = StringField("Make", validators=[Optional()])
    model = StringField("Model", validators=[Optional()])
    year = IntegerField("Year", validators=[Optional()])
    registration_number = StringField(
        "Registration Number (e.g. UBK 123X)", validators=[Optional()])
    sourced_from = StringField(
        "Sourced From (e.g. John K, Copart)", validators=[Optional()])
    purchase_price = FloatField("Purchase Price", validators=[Optional()])
    mileage = IntegerField("Mileage (km)", validators=[Optional()])
    notes = StringField("Notes (optional)", validators=[Optional()],
                        render_kw={"placeholder": "e.g. Dent on door, clean title, spare key missing"})
    photo = FileField("Vehicle Photo", validators=[
                      Optional(), FileAllowed(['jpg', 'jpeg', 'png'], 'Images only!')])
    submit = SubmitField("Add Vehicle")


class ExpenseForm(FlaskForm):
    vehicle_id = SelectField('Vehicle', coerce=int, validators=[Optional()])
    expense_category = StringField('Expense Category', validators=[Optional()])
    expense_amount = FloatField('Expense Amount', validators=[Optional()])
    submit = SubmitField('Add Expense')

class RecordSaleForm(FlaskForm):
    vehicle_id = SelectField(
        'Vehicle', coerce=int, validators=[Optional()])
    sold_to = StringField('Sold To (Name & Phone)',
                          validators=[Optional()])
    fixed_selling_price = FloatField(
        'Fixed Selling Price', validators=[Optional()])
    add_installment = FloatField(
        'Add Installment', validators=[Optional()])
    notes = StringField('Notes (optional)', validators=[Optional()])
    submit = SubmitField('Record Sale')

class LoginForm(FlaskForm):
    identifier = StringField(
        'Email or Phone Number',
        validators=[DataRequired()],
        render_kw={"placeholder": "Phone or email"}
    )
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')


class SignupForm(FlaskForm):
    dealership_name = StringField(
        'Dealership Name', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    phone = StringField('Phone (optional)')
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', validators=[
                                     DataRequired(), EqualTo('password')])
    submit = SubmitField('Sign Up')


class ForgotPasswordForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Send Reset Link')


class ResetPasswordForm(FlaskForm):
    password = PasswordField('New Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', validators=[
                                     DataRequired(), EqualTo('password')])
    submit = SubmitField('Reset Password')
# ------------------------
# Routes
# ------------------------


@app.route('/')
@subscription_required
def home():
    return render_template('dashboard.html')

# ---------- AJAX endpoints ----------


@app.route('/get_vehicles')
@subscription_required
def get_vehicles():
    vehicles = Inventory.query.filter_by(dealership_id=current_user.id).all()
    data = [
        {'id': v.id, 'name': f"{v.make or 'N/A'} {v.model or 'N/A'} ({v.year or 'Unknown'}-{v.registration_number or 'No Reg'}({v.status})"} for v in vehicles]
    return jsonify(data)


@app.route('/get_vehicle/<int:vehicle_id>')
@subscription_required
def get_vehicle(vehicle_id):
    vehicle = Inventory.query.filter_by(
        id=vehicle_id, dealership_id=current_user.id).first_or_404()
    if not vehicle:
        return jsonify({})
    return jsonify({
        'make': vehicle.make,
        'model': vehicle.model,
        'year': vehicle.year,
        'registration_number': vehicle.registration_number,
        'sourced_from': vehicle.sourced_from,
        'purchase_price': vehicle.purchase_price,
        'status': vehicle.status or 'Available',
        'sold_to': vehicle.sold_to or '',
        'fixed_selling_price': vehicle.fixed_selling_price or '',
        'mileage': vehicle.mileage
    })



@app.route('/add_vehicle_ajax', methods=['POST'])
@subscription_required
def add_vehicle_ajax():
    make = request.form.get('make') or None
    model = request.form.get('model') or None
    year = request.form.get('year', type=int) or None
    purchase_price = clean_float(request.form.get('purchase_price'))
    registration_number = request.form.get('registration_number') or None
    sourced_from = request.form.get('sourced_from') or None
    mileage = clean_float(request.form.get('mileage'))
    notes = request.form.get('notes') or None

    photo_file = request.files.get('photo')
    filename = None
    if photo_file:
        filename = secure_filename(photo_file.filename)
        photo_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

    vehicle = Inventory(
        make=make,
        model=model,
        year=year,
        purchase_price=purchase_price,
        registration_number=registration_number,
        sourced_from=sourced_from,
        mileage=mileage,
        notes=notes,
        photo_filename=filename,
        date_added=datetime.now(timezone.utc),
        dealership_id=current_user.id
        
    )
    db.session.add(vehicle)
    db.session.commit()

    return jsonify({'message': f'Vehicle added successfully!', 'vehicle_id': vehicle.id})



@app.route('/add_expense_ajax', methods=['POST'])
@subscription_required
def add_expense_ajax():
    vehicle_id = request.form.get('vehicle_id', type=int)
    vehicle = Inventory.query.filter_by(
        id=vehicle_id, dealership_id=current_user.id).first_or_404()
    category = request.form.get('expense_category') or None
    amount = clean_float(request.form.get('expense_amount'))

    expense = Expense(vehicle_id=vehicle_id,
                      expense_category=category, expense_amount=amount)
    db.session.add(expense)
    db.session.commit()

    total = db.session.query(db.func.sum(Expense.expense_amount)).filter(
        Expense.vehicle_id == vehicle_id).scalar() or 0
    vehicle = Inventory.query.get(vehicle_id)
    vehicle.expenses_amount = total
    db.session.commit()

    return jsonify({'message': 'Expense added and total updated!'})


@app.route('/edit_vehicle_ajax', methods=['POST'])
@subscription_required
def edit_vehicle_ajax():
    vehicle_id = request.form.get('vehicle_id', type=int)
    vehicle = Inventory.query.filter_by(id=vehicle_id, dealership_id=current_user.id).first()
    if not vehicle:
        return jsonify({'message': 'Vehicle not found!'}), 404

    vehicle.make = request.form.get('make') or vehicle.make
    vehicle.model = request.form.get('model') or vehicle.model
    vehicle.year = request.form.get('year', type=int) or vehicle.year
    vehicle.purchase_price = clean_float(request.form.get(
        'purchase_price')) or vehicle.purchase_price
    vehicle.registration_number = request.form.get(
        'registration_number') or vehicle.registration_number
    vehicle.sourced_from = request.form.get(
        'sourced_from') or vehicle.sourced_from
    vehicle.mileage = clean_float(
        request.form.get('mileage')) or vehicle.mileage
    vehicle.notes = request.form.get('notes') or vehicle.notes

    photo_file = request.files.get('photo')
    if photo_file:
        filename = secure_filename(photo_file.filename)
        photo_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        vehicle.photo_filename = filename

    db.session.commit()

    return jsonify({'message': f'Vehicle updated successfully!'})

@app.route('/record_sale_ajax', methods=['POST'])
@subscription_required
def record_sale_ajax():
    vehicle_id = request.form.get('vehicle_id', type=int)
    reg_number = request.form.get('registration_number', '').strip().upper()

    # Resolve vehicle: prefer ID, fallback to registration number
    if vehicle_id:
        vehicle = Inventory.query.filter_by(
            id=vehicle_id, dealership_id=current_user.id).first()
    elif reg_number:
        vehicle = Inventory.query.filter(
            db.func.upper(Inventory.registration_number) == reg_number,
            Inventory.dealership_id == current_user.id
        ).first()
    else:
        return jsonify({'success': False, 'message': 'Please select or enter a vehicle'}), 400

    if not vehicle:
        return jsonify({'success': False, 'message': 'Vehicle not found!'}), 404

    # Rest of your logic (same as before)
    sold_to = request.form.get('sold_to', '').strip()
    fixed_selling_price = clean_float(request.form.get('fixed_selling_price'))
    add_installment = clean_float(request.form.get('add_installment'))
    notes = request.form.get('notes', '').strip()

    was_first_sale = vehicle.status == 'Available'

    if was_first_sale:
        vehicle.status = 'Sold'
        if sold_to:
            vehicle.sold_to = sold_to
        if fixed_selling_price is not None and fixed_selling_price > 0:
            vehicle.fixed_selling_price = fixed_selling_price
        vehicle.sale_date = date.today()

        total_cost = (vehicle.purchase_price or 0) + \
            (vehicle.expenses_amount or 0)
        if fixed_selling_price is not None and fixed_selling_price > 0:
            vehicle.booked_profit = fixed_selling_price - total_cost

    # Record installment
    next_number = Payment.query.filter_by(vehicle_id=vehicle.id).count() + 1
    payment = Payment(
        vehicle_id=vehicle.id,
        amount=add_installment,
        category=f"Installment #{next_number}",
        notes=notes or None
    )
    db.session.add(payment)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Installment #{next_number} recorded for {vehicle.registration_number or "vehicle"}!',
        'vehicle_id': vehicle.id,
        'registration_number': vehicle.registration_number,
        'installment_number': next_number
    })


@app.route('/delete_vehicle/<int:car_id>', methods=['DELETE'])
@subscription_required
def delete_vehicle(car_id):
    try:
        vehicle = Inventory.query.filter_by(id=car_id, dealership_id=current_user.id).first_or_404()
        if not vehicle:
            return jsonify({'error': 'Car not found'}), 404

        # Delete related expenses first (if any)
        Expense.query.filter_by(vehicle_id=car_id).delete()
        Payment.query.filter_by(vehicle_id=car_id).delete()

        db.session.delete(vehicle)  # Delete car
        db.session.commit()
        print(f"✅ Deleted car ID {car_id}")
        return jsonify({'message': 'Deleted'}), 200
    except Exception as e:
        db.session.rollback()  # Rollback on error
        print(f"❌ Delete error for ID {car_id}: {e}")
        return jsonify({'error': str(e)}), 500


@app.route("/api/superset/guest-token/<string:dashboard_id>")
@login_required
def superset_guest_token(dashboard_id):
    current_app.logger.info(
    f"dealer_id={current_user.id} type={type(current_user.id)}"
)
    now = datetime.now(timezone.utc).timestamp()

    payload = {
        "user": {
            "username": f"user_{current_user.id}",
            "first_name": current_user.dealership_name or "Guest",
            "last_name": "User",
            "email": f"guest_{current_user.id}@example.com",
            "active": True,
            "roles": ["Gamma"],
            "sub": f"user_{current_user.id}"
        },
        "resources": [
            {"type": "dashboard", "id": dashboard_id}
        ],
        "rls_rules": [  # Changed from "rls" to "rls_rules"
            {"clause": f"dealership_id = '{current_user.id}'"}  # Quoted value for safety (assuming string ID)
        ],
        "iat": now,
        "exp": now + 3600,     # valid for 1 hour
        "aud": "superset",    # MUST match Superset config
        "type": "guest"
    }

    token = jwt.encode(
        payload,
        os.environ["GUEST_TOKEN_JWT_SECRET"],
        algorithm="HS256"
    )

    return jsonify({"token": token})


@app.route('/api/inventory', methods=['GET'])
@subscription_required
def get_inventory():
    vehicles = Inventory.query.filter_by(dealership_id=current_user.id).all()
    # Shows if data fetched
    print(f"DEBUG: Raw query found {len(vehicles)} vehicles")

    formatted_data = []
    max_profit = 0
    max_price = 0
    profits = []
    prices = []

    current_date = date(2025, 10, 27)

    for v in vehicles:
        try:
            # Per-row check
            print(f"DEBUG: Processing ID {v.id} (make: {v.make or 'NULL'})")

            # Safe days_in_inventory
            days_in_inventory = "Fresh"
            if v.date_added:
                delta = (current_date - v.date_added.date()).days
                if delta > 30:
                    days_in_inventory = "⚠️ Over 30 Days"

            # Safe dates (handles NULL or bad format)
            date_added = ""
            if v.date_added:
                try:
                    date_added = v.date_added.strftime("%d-%m-%Y %H:%M:%S")
                except:
                    date_added = str(v.date_added)[:19] if v.date_added else ""
            sale_date = ""
            if v.sale_date:
                try:
                    sale_date = v.sale_date.strftime("%d-%m-%Y %H:%M:%S")
                except:
                    sale_date = str(v.sale_date)[:19] if v.sale_date else ""

            # Safe numerics (handles NULL)
            def format_numeric(val):
                if val is None:
                    return ""
                try:
                    sign = '+' if val >= 0 else ''
                    return f"{sign}${abs(val):,.2f}"
                except:
                    return f"${val or 0:.2f}"

            purchase_price = format_numeric(v.purchase_price)
            expenses_amount = format_numeric(v.expenses_amount)
            total_paid = db.session.query(db.func.sum(Payment.amount)).filter_by(
                vehicle_id=v.id).scalar() or 0
            balance_due = (v.fixed_selling_price or 0) - total_paid

            cost = (v.purchase_price or 0) + (v.expenses_amount or 0)
            realized_profit = total_paid - cost
            # Safe max
            if v.booked_profit is not None:
                profits.append(float(v.booked_profit)
                               if v.booked_profit else 0)
            if v.fixed_selling_price is not None:
                prices.append(float(v.fixed_selling_price)
                              if v.fixed_selling_price else 0)

            formatted_data.append({
                "id": v.id,
                "date_added": date_added,
                "make": v.make or '',
                "model": v.model or '',
                "year": v.year or '',
                "registration_number": v.registration_number or '',
                "mileage": v.mileage or '',
                "sourced_from": v.sourced_from or '',
                "sold_to": v.sold_to or '',
                "notes": v.notes or '',
                "status": v.status or '',
                "purchase_price": format_numeric(v.purchase_price),
                "expenses_amount": format_numeric(v.expenses_amount),
                "fixed_selling_price": format_numeric(v.fixed_selling_price),
                "total_paid": format_numeric(total_paid),
                "balance_due": format_numeric(balance_due),
                "booked_profit": format_numeric(v.booked_profit),
                "realized_profit": format_numeric(realized_profit),
                "sale_date": sale_date,
                "photo_filename": v.photo_filename or '',
                "days_in_inventory": days_in_inventory
            })
            print(f"DEBUG: Added row for ID {v.id}")

        except Exception as e:
            print(f"DEBUG: Skipped ID {v.id} error: {e}")
            continue

    max_profit = max(profits) if profits else 1
    max_price = max(prices) if prices else 1
    print(f"DEBUG: Returning {len(formatted_data)} rows")

    return jsonify({
        "formatted_data": formatted_data,
        "max_profit": max_profit,
        "max_price": max_price
    })

@app.route('/flush_superset_cache', methods=['POST'])
def flush_superset_cache():
    # RECOMMENDATION: Add env var toggle—set FLUSH_CACHE_ENABLED=false on Render to disable (avoids Redis connection errors in prod).
    if os.environ.get('FLUSH_CACHE_ENABLED', 'true').lower() == 'false':
        # PROD SKIP: No-op; log reminder for manual flush (e.g., edit/save dashboard in Superset UI).
        print("Cache flush SKIPPED (prod mode). Manually refresh dashboard in Superset UI for fresh data.")
        return jsonify({'message': 'Cache flush disabled in prod—refresh your Superset dashboard manually!'}), 200
    
    try:
        # Direct connect to your Superset Redis (Docker exposes it on localhost:6379)
        # NOTE: This will not work on Render deployment as Redis is internal/not exposed on localhost.
        #       For production flush, consider using Superset's admin API if available, or manual cache refresh in Superset UI.
        #       Leaving as-is for local dev compatibility; disable or update host/port for Render if Redis is exposed.
        # RECOMMENDATION: If you expose Redis externally (advanced, via Render add-on), swap 'localhost' for your Redis URL here.
        r = redis.Redis(host='localhost', port=6379,
                        db=0, decode_responses=True)
        # NUCLEAR CLEAR: Deletes EVERY cache key in ALL databases
        r.flushall()
        print("Superset Redis cache FULLY FLUSHED via flushall() — ALL STALE DATA GONE!")
        return jsonify({'message': 'Cache flushed'}), 200
    except Exception as e:
        error_msg = str(e)
        # RECOMMENDATION: Enhanced handling—soft-fail on connection errors (common in prod) with a helpful message; hard-fail only on other issues.
        if 'localhost' in error_msg.lower() or 'Connection' in error_msg:
            print(f"Redis connection failed (expected in prod): {error_msg}. Use manual UI flush.")
            return jsonify({'error': 'Redis unavailable (prod mode)—refresh dashboard manually!'}), 200  # Soft 200 to keep JS calls non-breaking
        print("Redis flush error:", error_msg)
        return jsonify({'error': error_msg}), 500
'''
@app.route("/superset_token/<dashboard_id>")
def superset_token(dashboard_id):
    resources = [{"type": "dashboard", "id": dashboard_id}]
    try:
        token = generate_guest_token(resources)
        return jsonify({"token": token})
    except ValueError as e:
        print(f"Token error: {e}")
        return jsonify({"error": str(e)}), 500
'''

# ------------------------
# New Inventory Table Route (Standalone, uses Jinja for full specs match)
# ------------------------
# Tweak: Added route for /inventory (optional standalone page); formats data like API, renders template with all rows. Achieves: Exact Superset if accessed directly, but dashboard uses API for integration.


@app.route('/inventory')
@subscription_required
def inventory():
    # No limit; all data like LIMIT 100000 (but query.all() for model)
    vehicles = Inventory.query.filter_by(dealership_id=current_user.id).all()

    rows = []
    max_profit = 0
    max_price = 0
    profits = []
    prices = []

    # Tweak: Same fixed date and formatting as API
    current_date = date(2025, 10, 27)

    for v in vehicles:
        days_in_inventory = "Fresh"
        if v.date_added:
            delta = (current_date - v.date_added.date()).days
            if delta > 30:
                days_in_inventory = "⚠️ Over 30 Days"

        sale_date = v.sale_date.strftime(
            "%d-%m-%Y %H:%M:%S") if v.date_added else ""
        sale_date = v.sale_date.strftime(
            "%d-%m-%Y %H:%M:%S") if v.sale_date else ""

        def format_numeric(val):
            if val is None:
                return ""
            sign = '+' if val >= 0 else ''
            return f"{sign}${abs(val):,.2f}"

        purchase_price = format_numeric(v.purchase_price)
        expenses_amount = format_numeric(v.expenses_amount)
        total_paid = db.session.query(db.func.sum(Payment.amount)).filter_by(
            vehicle_id=v.id).scalar() or 0
        balance_due = (v.fixed_selling_price or 0) - total_paid

        cost = (v.purchase_price or 0) + (v.expenses_amount or 0)
        realized_profit = total_paid - cost

        if v.booked_profit is not None:
            profits.append(float(v.booked_profit) if v.booked_profit else 0)
        if v.fixed_selling_price is not None:
            prices.append(float(v.fixed_selling_price)
                          if v.fixed_selling_price else 0)

        row = {
            "id": v.id,
            "date_added": date_added,
            "make": v.make or '',
            "model": v.model or '',
            "year": v.year or '',
            "registration_number": v.registration_number or '',
            "mileage": v.mileage or '',
            "sourced_from": v.sourced_from or '',
            "sold_to": v.sold_to or '',
            "notes": v.notes or '',
            "status": v.status or '',
            "purchase_price": format_numeric(v.purchase_price),
            "expenses_amount": format_numeric(v.expenses_amount),
            "fixed_selling_price": format_numeric(v.fixed_selling_price),
            "total_paid": format_numeric(total_paid),
            "balance_due": format_numeric(balance_due),
            "booked_profit": format_numeric(v.booked_profit),
            "realized_profit": format_numeric(realized_profit),
            "sale_date": sale_date,
            "photo_filename": v.photo_filename or '',
            "days_in_inventory": days_in_inventory
        }
        rows.append(row)

    max_profit = max(profits) if profits else 1
    max_price = max(prices) if prices else 1
    count = len(rows)

    return render_template('inventory.html',
                           rows=rows,
                           count=count,
                           max_profit=max_profit,
                           max_price=max_price)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = LoginForm()
    if form.validate_on_submit():
        identifier = form.identifier.data.strip()
        user = User.query.filter_by(email=identifier.lower()).first()
        if user is None:
            normalized_phone = User.normalize_phone(identifier)
            if normalized_phone:
                user = User.query.filter_by(phone=normalized_phone).first()
        if user is None or not user.check_password(form.password.data):
            flash('Invalid email/phone or password', 'danger')
            return redirect(url_for('login'))
        login_user(user)
        flash('Logged in successfully!', 'success')
        return redirect(url_for('home'))
    return render_template('login.html', form=form)


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = SignupForm()
    if form.validate_on_submit():
        if User.query.filter_by(email=form.email.data).first():
            flash('Email already registered', 'danger')
            return redirect(url_for('signup'))
        if User.query.filter_by(dealership_name=form.dealership_name.data).first():
            flash('Dealership name already taken', 'danger')
            return redirect(url_for('signup'))
        user = User(
            dealership_name=form.dealership_name.data,
            email=form.email.data,
            phone=form.phone.data
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        login_user(user)  # NEW: Log in right away
        flash('Welcome! Choose your plan to start your 30-day free trial.', 'success')
        return redirect(url_for('subscribe'))  # NEW: Go to subscribe page
    return render_template('signup.html', form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully', 'info')
    return redirect(url_for('login'))


@app.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    name = request.form.get('name')
    photo_file = request.files.get('photo')

    if name:
        current_user.profile_name = name

    if photo_file and photo_file.filename:
        filename = secure_filename(photo_file.filename)
        photo_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        current_user.profile_photo_filename = filename

    db.session.commit()
    flash('Profile updated successfully!', 'success')
    return jsonify({'success': True})


@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            token = s.dumps({'user_id': user.id}, salt='password-reset')
            link = url_for('reset_password', token=token, _external=True)
            msg = Message('GreenChain Password Reset', recipients=[user.email])
            msg.body = f'Click this link to reset your password: {link}\nThis link expires in 1 hour.'
            mail.send(msg)
            flash('Check your email for the password reset link', 'info')
        else:
            flash('If the email exists, a reset link has been sent',
                  'info')  # Security
        return redirect(url_for('login'))
    return render_template('forgot_password.html', form=form)


@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        data = s.loads(token, salt='password-reset', max_age=3600)  # 1 hour
    except:
        flash('Invalid or expired link', 'danger')
        return redirect(url_for('forgot_password'))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        user = User.query.get(data['user_id'])
        user.set_password(form.password.data)
        db.session.commit()
        flash('Password reset successful! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('reset_password.html', form=form)


@app.route('/subscribe')
@login_required
def subscribe():
    return render_template('subscribe.html')

# NEW: Initiate Pesapal payment

# NEW: Start free trial


@app.route('/start_trial', methods=['POST'])
@login_required
def start_trial():
    current_user.is_trial = True
    current_user.trial_start = datetime.utcnow()
    current_user.subscription_plan = 'trial'
    db.session.commit()
    return '', 204  # Success, no content


@app.route('/initiate_payment', methods=['POST'])
@login_required
def initiate_payment():
    print("=== initiate_payment route called by user ID:", current_user.id)
    data = request.json
    print("Received JSON data:", data)
    
    amount = data.get('amount')
    plan = data.get('plan')
    
    if not amount or not plan:
        print("Missing amount or plan in JSON")
        return jsonify({'error': 'Missing amount or plan'}), 400
    
    print(f"Starting payment for {plan} - amount: {amount}")
    
    redirect_url = initiate_pesapal_payment(amount, plan, current_user)
    
    if redirect_url:
        print("Success - redirecting to:", redirect_url)
        return jsonify({'redirect_url': redirect_url})
    else:
        print("No redirect_url returned - payment initiation failed")
        return jsonify({'error': 'Payment failed - see server logs'}), 400

@app.route('/pesapal_callback')
def pesapal_callback():
    print("Pesapal callback received! All params:", request.args)
    
    # Get the merchant reference Pesapal sent back
    received_ref = request.args.get('merchantReference')
    
    if received_ref and received_ref.startswith('user_'):
        try:
            # Extract user ID from the reference
            parts = received_ref.split('_')
            user_id = int(parts[1])  # the number after "user_"
            user = User.query.get(user_id)
            if user:
                print(f"Activating subscription for user ID {user_id}")
                user.subscription_plan = 'monthly'
                user.is_trial = False
                user.subscription_end = datetime.utcnow() + timedelta(days=30)
                db.session.commit()
                flash('Payment successful! Subscription activated.', 'success')
            else:
                flash('User not found for this payment', 'warning')
        except Exception as e:
            print("Error processing callback:", str(e))
            flash('Payment received, but reference missing.', 'warning')
    else:
        flash('Payment received, but reference missing.', 'warning')
    
    return redirect(url_for('home'))
    
# ==================== BEST AI — USES v.expenses AND v.payments DIRECTLY! ====================
@app.route('/api/ai_chat', methods=['POST'])
@subscription_required
def ai_chat():
    data = request.get_json()
    user_message = data.get('message', '').strip()
    
    if not user_message:
        return jsonify({"reply": "Ask me about cars, expenses, payments, or advice! 🚗💸"})
    
    vehicles = Inventory.query.filter_by(dealership_id=current_user.id).all()
    
    total_cars = len(vehicles)
    sold_cars = len([v for v in vehicles if v.status == 'Sold'])
    available_cars = total_cars - sold_cars
    
    total_sales = sum(clean_float(v.fixed_selling_price or 0) for v in vehicles if v.status == 'Sold')
    total_profit = sum(clean_float(v.booked_profit or 0) for v in vehicles if v.status == 'Sold')
    
    car_details = []
    for v in vehicles:
        status = "Sold" if v.status == 'Sold' else "Available"
        
        # EVERY EXPENSE — category, amount, date
        expenses_list = []
        total_expenses = 0
        for exp in sorted(v.expenses, key=lambda e: e.date_created or datetime.min):
            amount = clean_float(exp.expense_amount or 0)
            total_expenses += amount
            date_str = exp.date_created.strftime('%d %B %Y') if exp.date_created else 'Unknown date'
            category = exp.expense_category or 'Unknown'
            expenses_list.append(f"   → {category}: UGX {amount:,.0f} on {date_str}")
        expenses_text = "\n".join(expenses_list) if expenses_list else "   → No expenses"
        
        # EVERY PAYMENT — amount, date, note
        payments_list = []
        total_paid = 0
        for pay in sorted(v.payments, key=lambda p: p.payment_date or datetime.min):
            amount = clean_float(pay.amount or 0)
            total_paid += amount
            date_str = pay.payment_date.strftime('%d %B %Y') if pay.payment_date else 'Unknown date'
            note = pay.notes or pay.category or 'No note'
            payments_list.append(f"   → UGX {amount:,.0f} on {date_str} ({note})")
        payments_text = "\n".join(payments_list) if payments_list else "   → No payments"
        
        balance_due = clean_float(v.fixed_selling_price or 0) - total_paid
        
        days_in_stock = (date.today() - v.date_added.date()).days if v.date_added else "Unknown"
        
        car_details.append(f"""
• Car ID: {v.id} | {v.make or 'Unknown'} {v.model or ''} {v.year or ''} (Reg: {v.registration_number or 'None'})
  Status: {status} | Sold to: {v.sold_to or 'None'}
  Buy price: UGX {clean_float(v.purchase_price):,.0f} | Sell price: UGX {clean_float(v.fixed_selling_price):,.0f}
  Booked profit: UGX {clean_float(v.booked_profit):,.0f}
  Total paid: UGX {total_paid:,.0f} | Balance due: UGX {balance_due:,.0f}
  Days in stock: {days_in_stock} | Mileage: {v.mileage or 'N/A'} km
  Notes: {v.notes or 'None'}

  Expenses (Total: UGX {total_expenses:,.0f}):
{expenses_text}

  Payments:
{payments_text}
""")
    
    all_cars_text = "\n".join(car_details)
    
    system_prompt = f"""
You are GreenChain AI — expert adviser for this Ugandan car dealership.

REAL DATA TODAY (December 18, 2025):
- Total cars: {total_cars} | Available: {available_cars} | Sold: {sold_cars}
- Total sales: UGX {total_sales:,.0f} | Total profit: UGX {total_profit:,.0f}

EVERY CAR WITH FULL EXPENSES & PAYMENTS:
{all_cars_text}

YOUR JOB:
- List exact expenses and payments with dates and categories when asked
- Example: "Brakes: UGX 3,000,000 on 10 December 2025"
- Show totals and balance clearly
- Give smart advice: "High expenses on this car", "Customer paying well"
- Be friendly and clear. Use full dates.
"""

    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    
    try:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            return jsonify({"reply": "ERROR: GROQ_API_KEY is missing in Render Environment! Add it and redeploy."})
        print(f"Using Groq key: {api_key[:5]}...")  # Logs first 5 chars to check
        client = Groq(api_key=api_key)
        chat_response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.6,
            max_tokens=1500
        )
        reply = chat_response.choices[0].message.content.strip()
        return jsonify({"reply": reply})
    except ImportError as e:
        return jsonify({"reply": "IMPORT ERROR: groq library not installed — check requirements.txt and redeploy with clear cache!"})
    except Exception as e:
        error_msg = str(e)
        return jsonify({"reply": f"CRASH: {error_msg} — check Render logs for details!"})
# ==========================================================================
# ------------------------
# Run app
# ------------------------
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
