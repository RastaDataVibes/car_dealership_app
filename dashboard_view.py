from flask import Blueprint, render_template

dashboard_bp = Blueprint('dashboard_bp', __name__)


@dashboard_bp.route('/dashboard')
def dashboard():
    # The dashboard ID from Superset Embedded SDK
    dashboard_id = "e9413e09-3526-47c6-9867-e9230f411f3b"
    return render_template('dashboard.html', dashboard_id=dashboard_id)
