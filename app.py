from flask import Flask, render_template, request, redirect, url_for, jsonify, send_from_directory
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import pytz
import os
import requests
import logging
import mimetypes
import time
from enrollment_processors import (
    process_daily_enrollments, process_leadsource_data,
    process_initial_payments, process_admin_monthly_revenue,
    process_enrollments_per_opener, process_monthly_revenue_enrollments
)

mimetypes.add_type('video/mp4', '.mp4')
mimetypes.add_type('video/webm', '.webm')
mimetypes.add_type('video/ogg', '.ogg')

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)

# Update database configuration to use environment variables
db_url = os.environ.get('DATABASE_URL')
if db_url and db_url.startswith('postgres://'):
    db_url = db_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

WEBHOOK_URL = 'https://public-webhook-receiver-juy917.replit.app/get_webhooks'
MAX_RETRIES = 3
RETRY_DELAY = 1
WEBHOOK_TIMEOUT = 30

class MonthlyGoal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    goal = db.Column(db.Integer, nullable=False, default=120)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    @classmethod
    def get_current_goal(cls):
        current_goal = cls.query.order_by(cls.updated_at.desc()).first()
        return current_goal.goal if current_goal else 120

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        logger.debug(f"Password hash set: {self.password_hash}")

    def check_password(self, password):
        result = check_password_hash(self.password_hash, password)
        logger.debug(f"Password check result: {result}")
        return result

    @classmethod
    def get_admin(cls):
        admin = cls.query.filter_by(username='admin').first()
        logger.debug(f"Admin user retrieved: {admin}")
        return admin

class SalesData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    value = db.Column(db.Float, nullable=False)
    demos = db.Column(db.Integer, nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

last_processed_officer = None
last_sale_timestamp = {}
webhook_last_success = None
webhook_cache = None
webhook_cache_duration = timedelta(seconds=5)

def fetch_webhook_data():
    global webhook_last_success, webhook_cache
    
    current_time = datetime.now()
    
    # Return cached data if still valid
    if webhook_cache and webhook_last_success:
        if current_time - webhook_last_success < webhook_cache_duration:
            logger.debug("Returning cached webhook data")
            return webhook_cache

    session = requests.Session()
    session.mount('https://', requests.adapters.HTTPAdapter(max_retries=MAX_RETRIES))

    for attempt in range(MAX_RETRIES):
        try:
            logger.info(f"Fetching webhook data (attempt {attempt + 1}/{MAX_RETRIES})")
            response = session.get(WEBHOOK_URL, timeout=WEBHOOK_TIMEOUT)
            response.raise_for_status()
            
            webhook_cache = response.json()
            webhook_last_success = current_time
            
            logger.info(f"Successfully fetched webhook data. Status code: {response.status_code}")
            return webhook_cache

        except requests.exceptions.Timeout as e:
            logger.error(f"Timeout error on attempt {attempt + 1}: {str(e)}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error on attempt {attempt + 1}: {str(e)}")
        except ValueError as e:
            logger.error(f"JSON decode error on attempt {attempt + 1}: {str(e)}")
        
        if attempt < MAX_RETRIES - 1:
            time.sleep(RETRY_DELAY * (attempt + 1))  # Exponential backoff

    if webhook_cache:
        logger.warning("Using cached data after all retries failed")
        return webhook_cache
        
    logger.error("All webhook fetch attempts failed")
    return None

# Error handler for API endpoints
@app.errorhandler(500)
def internal_server_error(error):
    logger.error(f"Internal Server Error: {str(error)}")
    return jsonify({"error": "Internal Server Error"}), 500

@app.errorhandler(404)
def not_found_error(error):
    logger.error(f"Not Found Error: {str(error)}")
    return jsonify({"error": "Not Found"}), 404

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form['password']
        logger.debug(f"Login attempt with password: {password}")
        user = User.get_admin()
        if user and user.check_password(password):
            login_user(user)
            logger.debug("Login successful")
            return redirect(url_for('admin_panel'))
        else:
            logger.debug("Login failed: Invalid password")
            return render_template('login.html', error='Invalid password')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/admin')
@login_required
def admin_panel():
    if not current_user.username == 'admin':
        return redirect(url_for('index'))
    current_goal = MonthlyGoal.get_current_goal()
    return render_template('admin_panel.html', current_goal=current_goal)

@app.route('/api/set-monthly-goal', methods=['POST'])
@login_required
def set_monthly_goal():
    if not current_user.username == 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    try:
        data = request.get_json()
        new_goal = int(data.get('goal'))
        if new_goal <= 0:
            return jsonify({'success': False, 'message': 'Goal must be greater than 0'}), 400

        new_goal_entry = MonthlyGoal(goal=new_goal)
        db.session.add(new_goal_entry)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Monthly goal updated to {new_goal} enrollments'
        })
    except (TypeError, ValueError) as e:
        return jsonify({
            'success': False,
            'message': 'Invalid goal value provided'
        }), 400
    except Exception as e:
        logger.error(f"Error updating monthly goal: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Error updating monthly goal'
        }), 500

@app.route('/api/leadsource-data')
def leadsource_data():
    webhook_data = fetch_webhook_data()
    if webhook_data:
        leadsource_sales = process_leadsource_data(webhook_data)
        return jsonify(leadsource_sales)
    else:
        app.logger.error("Failed to fetch webhook data")
        return jsonify({"error": "Failed to fetch data"}), 500

@app.route('/api/dashboard-data')
def dashboard_data():
    global last_processed_officer, last_sale_timestamp
    webhook_data = fetch_webhook_data()
    if webhook_data:
        sales_data = process_admin_monthly_revenue(webhook_data)

        for data in sales_data:
            db_entry = SalesData(
                name=data['name'],
                value=data['value'],
                demos=data['demos']
            )
            db.session.merge(db_entry)
        db.session.commit()

        new_enrollments = sorted(sales_data, key=lambda x: x['demos'], reverse=True)[:3]
        monthly_revenue = sorted(sales_data, key=lambda x: x['value'], reverse=True)
        upcoming_demos = sum(rep['demos'] for rep in sales_data)
        current_goal = MonthlyGoal.get_current_goal()

        new_sales_officer = None
        if sales_data:
            for entry in sales_data:
                officer_name = entry['name']
                last_sale_demos = last_sale_timestamp.get(officer_name, 0)

                if entry['demos'] > 0 and entry['demos'] != last_sale_demos:
                    new_sales_officer = officer_name
                    last_processed_officer = officer_name
                    last_sale_timestamp[officer_name] = entry['demos']
                    app.logger.info(f"New sale detected for: {new_sales_officer}")
                    break

        response_data = {
            "new_enrollments": new_enrollments,
            "monthly_revenue": monthly_revenue,
            "upcoming_demos": upcoming_demos,
            "monthly_goal": current_goal,
            "new_sales_officer": new_sales_officer
        }
        return jsonify(response_data)
    else:
        app.logger.error("Failed to fetch webhook data")
        return jsonify({"error": "Failed to fetch data"}), 500

@app.route('/api/admin-monthly-revenue')
def admin_monthly_revenue():
    webhook_data = fetch_webhook_data()
    if webhook_data:
        monthly_revenue = process_admin_monthly_revenue(webhook_data)
        return jsonify(monthly_revenue)
    else:
        app.logger.error("Failed to fetch webhook data")
        return jsonify({"error": "Failed to fetch data"}), 500

@app.route('/api/daily-enrollments')
def daily_enrollments():
    webhook_data = fetch_webhook_data()
    if webhook_data:
        daily_data = process_daily_enrollments(webhook_data)
        return jsonify(daily_data)
    else:
        app.logger.error("Failed to fetch webhook data")
        return jsonify({"error": "Failed to fetch data"}), 500

@app.route('/api/enrollments-per-opener')
def enrollments_per_opener():
    webhook_data = fetch_webhook_data()
    if webhook_data:
        opener_data = process_enrollments_per_opener(webhook_data)
        return jsonify(opener_data)
    else:
        app.logger.error("Failed to fetch webhook data")
        return jsonify({"error": "Failed to fetch data"}), 500

@app.route('/static/videos/<path:filename>')
def serve_video(filename):
    video_path = os.path.join('static/videos', filename)
    if os.path.exists(video_path):
        return send_from_directory('static/videos', filename, mimetype=mimetypes.guess_type(filename)[0])
    else:
        app.logger.error(f"Video file not found: {video_path}")
        return "Video not found", 404

@app.route('/api/initial-payments')
def initial_payments():
    webhook_data = fetch_webhook_data()
    if webhook_data:
        payments_data = process_initial_payments(webhook_data)
        # Convert sets to lists for JSON serialization
        for officer in payments_data.values():
            officer['cases'] = list(officer['cases'])
        return jsonify(payments_data)
    else:
        app.logger.error("Failed to fetch webhook data")
        return jsonify({"error": "Failed to fetch data"}), 500

@app.route('/api/monthly-revenue-data')
def monthly_revenue_data():
    webhook_data = fetch_webhook_data()
    if webhook_data:
        monthly_revenue = process_monthly_revenue_enrollments(webhook_data)
        return jsonify(monthly_revenue)
    else:
        app.logger.error("Failed to fetch webhook data")
        return jsonify({"error": "Failed to fetch data"}), 500

if __name__ == '__main__':
    with app.app_context():
        try:
            db.create_all()
            admin = User.get_admin()
            if not admin:
                admin = User(username='admin')
                admin.set_password('admin_password')
                db.session.add(admin)
                db.session.commit()
                logger.info("Admin user created successfully")
        except Exception as e:
            logger.error(f"Database initialization error: {str(e)}")
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)