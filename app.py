import os
import io
import json
import sqlite3
import requests
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import qrcode

from database import get_db_connection, init_db, seed_data
from decision_engine import run_decision_engine

app = Flask(__name__)
app.secret_key = 'smart_kangeyam_cattle_secret_key'

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Ensure database exists
if not os.path.exists(os.path.join(os.path.dirname(__file__), 'cattle.db')):
    init_db()
    seed_data()
else:
    init_db()

def is_logged_in():
    return 'user_id' in session

def is_customer():
    return session.get('role') == 'Customer'

PRODUCTS = [
    {"name": "Fresh Colostrum", "unit": "liter", "price": 120, "icon": "fa-bottle-droplet", "color": "amber"},
    {"name": "Fresh Kangeyam Milk", "unit": "liter", "price": 80, "icon": "fa-glass-water", "color": "cyan"},
    {"name": "Traditional Milk Products", "unit": "pack", "price": 180, "icon": "fa-cheese", "color": "rose"},
    {"name": "Organic Fertilizer", "unit": "25 kg bag", "price": 350, "icon": "fa-seedling", "color": "emerald"},
    {"name": "Farm Biogas", "unit": "cubic meter", "price": 45, "icon": "fa-fire-flame-simple", "color": "orange"},
]
UPI_ID = os.environ.get('KANGEYAM_UPI_ID', 'your-upi-id@bank')

def available_products():
    return PRODUCTS + session.get('custom_products', [])

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# -------------------------------------------------------------
# REAL-TIME MARKET TICKER & FLASH NEWS (Feature 10)
# -------------------------------------------------------------
def get_milk_market_data():
    """Generates yesterday, today, and tomorrow's live milk market pricing and forecasts."""
    now = datetime.now()
    # Dynamic slight variation based on day of month to simulate live mandi prices
    base_price = 41.20 + (now.day % 3) * 0.30
    yesterday_price = round(base_price - 0.70, 2)
    today_price = round(base_price, 2)
    tomorrow_price = round(base_price + 0.60, 2)
    diff = round(today_price - yesterday_price, 2)
    percent_change = round((diff / yesterday_price) * 100, 2)

    return {
        "yesterday": yesterday_price,
        "yesterday_price": yesterday_price,
        "today": today_price,
        "today_price": today_price,
        "tomorrow": tomorrow_price,
        "tomorrow_price": tomorrow_price,
        "diff": diff,
        "percent_change": percent_change,
        "trend": "Bullish ▲" if diff >= 0 else "Bearish ▼",
        "a2_premium": 75.00,
        "fat_content_avg": "4.5% Butterfat",
        "mandi_status": "Kangeyam Cooperative Mandi: Active / High Demand",
        "last_updated": now.strftime("%I:%M %p, %d %b %Y")
    }

# -------------------------------------------------------------
# ENVIRONMENT-AWARE WEATHER RISK & THI SCORE (Feature 4)
# -------------------------------------------------------------
_weather_cache = {"data": None, "timestamp": 0}

def get_realtime_weather_risk():
    """Fetches real-time weather data for Kangeyam region and calculates cattle THI Risk."""
    global _weather_cache
    now_ts = datetime.now().timestamp()
    
    # Cache for 10 minutes to maintain speed
    if _weather_cache["data"] and (now_ts - _weather_cache["timestamp"] < 600):
        return _weather_cache["data"]

    temp = 32.0
    humidity = 62.0
    apparent_temp = 35.0
    wind_speed = 12.5
    precipitation = 0.0
    condition = "Partly Cloudy"
    source = "Kangeyam Regional Met Station"

    try:
        # Open-Meteo API for Kangeyam (11.0063° N, 77.5639° E)
        url = "https://api.open-meteo.com/v1/forecast?latitude=11.0063&longitude=77.5639&current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,wind_speed_10m&timezone=Asia%2FKolkata"
        res = requests.get(url, timeout=3.0)
        if res.status_code == 200:
            data = res.json().get("current", {})
            temp = float(data.get("temperature_2m", temp))
            humidity = float(data.get("relative_humidity_2m", humidity))
            apparent_temp = float(data.get("apparent_temperature", apparent_temp))
            wind_speed = float(data.get("wind_speed_10m", wind_speed))
            precipitation = float(data.get("precipitation", 0.0))
            condition = "Real-time Live Weather (Google/Open-Meteo)"
            source = "Google Weather Live Feed (Kangeyam Station)"
    except Exception:
        # Fallback to realistic dynamic values
        source = "Simulated Live Telemetry (Kangeyam Microclimate)"

    # Standard Livestock THI (Temperature-Humidity Index) Formula:
    # THI = (1.8 * T + 32) - (0.55 - 0.0055 * RH) * (1.8 * T - 26)
    thi = (1.8 * temp + 32) - (0.55 - 0.0055 * humidity) * (1.8 * temp - 26)
    thi = round(thi, 1)

    # Risk Categories:
    # THI < 72: Safe / Comfort
    # 72-78: Mild Heat Stress
    # 79-88: Moderate / High Stress
    # >= 89: Severe Emergency
    if thi < 72:
        risk_level = "Low Risk (Comfort Zone)"
        risk_color = "emerald"
        risk_score = max(10, int((thi / 72.0) * 40))
        advisory = "Comfortable grazing conditions. Regular drinking water frequency is sufficient."
    elif thi <= 78:
        risk_level = "Mild Heat Stress (Moderate Risk)"
        risk_color = "amber"
        risk_score = 45 + int(((thi - 72) / 6.0) * 25)
        advisory = "Provide shade access during midday hours (12 PM - 3 PM) and ensure cool drinking water."
    elif thi <= 88:
        risk_level = "High Heat Stress (Severe Warning)"
        risk_color = "rose"
        risk_score = 70 + int(((thi - 79) / 9.0) * 20)
        advisory = "Activate shed fans/sprinklers. Shift grazing to early morning & dusk. Add electrolytes in drinking water."
    else:
        risk_level = "Critical Heat Stress (Emergency)"
        risk_color = "red"
        risk_score = min(99, 90 + int(thi - 88))
        advisory = "High risk of thermal shock & severe milk yield crash. Immediate shed misting & veterinary observation required."

    weather_data = {
        "temperature": temp,
        "humidity": humidity,
        "apparent_temperature": apparent_temp,
        "wind_speed": wind_speed,
        "precipitation": precipitation,
        "condition": condition,
        "source": source,
        "thi": thi,
        "risk_level": risk_level,
        "risk_color": risk_color,
        "risk_score": risk_score,
        "advisory": advisory,
        "location": "Kangeyam, Tiruppur District, Tamil Nadu"
    }

    _weather_cache["data"] = weather_data
    _weather_cache["timestamp"] = now_ts
    return weather_data

# -------------------------------------------------------------
# DEDICATED ALERTS ENGINE (Feature 7)
# -------------------------------------------------------------
def get_categorized_alerts():
    """Extracts and groups all herd alerts by specific criteria."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, breed, age, current_market_value, status, image_url FROM cattle")
    cattles = cursor.fetchall()

    alerts_by_category = {
        "vaccination_overdue": [],
        "declining_milk": [],
        "sudden_drop": [],
        "high_cost_high_production": [],
        "missing_health": []
    }
    
    all_alerts_flat = []

    for c in cattles:
        analysis = run_decision_engine(c['id'])
        if not analysis:
            continue

        # 1. Vaccination Overdue Check
        if "Vaccination Overdue Alert" in analysis['global_alerts'] or any("vaccination overdue" in p.lower() for p in analysis['health_penalties']):
            alert_obj = {
                "cattle_id": c['id'],
                "name": c['name'],
                "image_url": c['image_url'],
                "category": "Vaccination Overdue",
                "severity": "High",
                "severity_badge": "bg-rose-100 text-rose-800 border-rose-200",
                "message": "Vaccination schedule is overdue (> 365 days or missing). Risk of contagious bovine infection.",
                "action": "Administer Booster Dose",
                "action_url": url_for('cattle_detail', id=c['id'])
            }
            alerts_by_category["vaccination_overdue"].append(alert_obj)
            all_alerts_flat.append(alert_obj)

        # 2. Declining Milk Production Check
        if "Declining Milk Yield Alert" in analysis['global_alerts'] or any("declining" in p.lower() for p in analysis['productivity_penalties']):
            alert_obj = {
                "cattle_id": c['id'],
                "name": c['name'],
                "image_url": c['image_url'],
                "category": "Declining Milk Yield",
                "severity": "Medium",
                "severity_badge": "bg-amber-100 text-amber-800 border-amber-200",
                "message": "Consistent downward trend in milk yield over the past 2-3 weeks. Review nutrition & lactation stage.",
                "action": "Check Feed & Mineral Intake",
                "action_url": url_for('cattle_detail', id=c['id'])
            }
            alerts_by_category["declining_milk"].append(alert_obj)
            all_alerts_flat.append(alert_obj)

        # 3. Sudden Production Decrease Check
        if "Sudden Milk Drop Alert" in analysis['global_alerts'] or any("sudden drop" in p.lower() for p in analysis['productivity_penalties']):
            alert_obj = {
                "cattle_id": c['id'],
                "name": c['name'],
                "image_url": c['image_url'],
                "category": "Sudden Production Crash",
                "severity": "Urgent",
                "severity_badge": "bg-red-100 text-red-900 border-red-300 animate-pulse",
                "message": "Milk yield plummeted by >50% in the last 48 hours. Potential acute mastitis, injury, or severe infection.",
                "action": "Immediate Vet Consultation",
                "action_url": url_for('cattle_detail', id=c['id'])
            }
            alerts_by_category["sudden_drop"].append(alert_obj)
            all_alerts_flat.append(alert_obj)

        # 4. High Milk Production but High Maintenance Cost
        if (analysis['productivity_score'] >= 75 or any("high production" in c['name'].lower() for _ in [1])) and analysis['economic_score'] <= 40:
            alert_obj = {
                "cattle_id": c['id'],
                "name": c['name'],
                "image_url": c['image_url'],
                "category": "High Yield / High Maintenance Overhead",
                "severity": "High",
                "severity_badge": "bg-purple-100 text-purple-800 border-purple-200",
                "message": "Excellent lactation output, but exorbitant medical and housing overheads erode farm net profitability.",
                "action": "Review Cost Structure",
                "action_url": url_for('cattle_detail', id=c['id'])
            }
            alerts_by_category["high_cost_high_production"].append(alert_obj)
            all_alerts_flat.append(alert_obj)

        # 5. Missing Health Records
        if "Missing Health History Alert" in analysis['global_alerts'] or any("missing vaccination history" in p.lower() for p in analysis['health_penalties']):
            alert_obj = {
                "cattle_id": c['id'],
                "name": c['name'],
                "image_url": c['image_url'],
                "category": "Missing Health History",
                "severity": "Low",
                "severity_badge": "bg-slate-100 text-slate-700 border-slate-200",
                "message": "Animal lacks documented medical or vaccination records, lowering diagnostic confidence.",
                "action": "Log Health Baseline",
                "action_url": url_for('cattle_detail', id=c['id'])
            }
            alerts_by_category["missing_health"].append(alert_obj)
            all_alerts_flat.append(alert_obj)

    conn.close()
    return alerts_by_category, all_alerts_flat

# -------------------------------------------------------------
# MARKET TIMING ADVISOR ENGINE (Feature 5)
# -------------------------------------------------------------
def get_market_timing_advice():
    """Evaluates each animal for optimal sale, hold, or breeding windows based on seasonal trends and margins."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM cattle")
    cattles = cursor.fetchall()
    
    advice_list = []
    
    for c in cattles:
        analysis = run_decision_engine(c['id'])
        if not analysis:
            continue
            
        age = c['age']
        current_val = c['current_market_value']
        econ_score = analysis['economic_score']
        prod_score = analysis['productivity_score']
        breed_score = analysis['breeding_score']
        
        # 30-day projected milk revenue & expenses
        cursor.execute("""
            SELECT AVG(milk_production) as avg_m, AVG(feed_consumption) as avg_f
            FROM production_records WHERE cattle_id = ?
        """, (c['id'],))
        prod_stat = cursor.fetchone()
        avg_milk = prod_stat['avg_m'] if prod_stat and prod_stat['avg_m'] is not None else 0.0
        avg_feed = prod_stat['avg_f'] if prod_stat and prod_stat['avg_f'] is not None else 4.0
        
        cursor.execute("SELECT AVG(maintenance_cost) as avg_maint FROM financial_records WHERE cattle_id = ?", (c['id'],))
        maint_stat = cursor.fetchone()
        avg_maint = maint_stat['avg_maint'] if maint_stat and maint_stat['avg_maint'] is not None else 5.0
        
        daily_rev = avg_milk * 41.20
        daily_exp = (avg_feed * 30.0) + avg_maint
        daily_net = daily_rev - daily_exp
        
        # Holding projections
        net_30d = daily_net * 30
        net_90d = daily_net * 90
        
        # Strategy categorization
        if econ_score <= 35 and age >= 3.0:
            action = "Sell Now (Peak Valuation Before Depreciation)"
            badge = "bg-red-100 text-red-800 border-red-200"
            icon = "fa-handshake-slash"
            reason = f"Negative or marginal net margin (-₹{abs(daily_net):.1f}/day). Selling now realizes peak asset value (₹{int(current_val):,}) before maintenance costs accumulate further."
            future_30d_val = current_val - 1500
            recommendation_type = "sell"
        elif breed_score >= 80 and (1.2 <= age <= 6.0):
            action = "Prime Breeding Window (Retain for Offspring Value)"
            badge = "bg-blue-100 text-blue-800 border-blue-200"
            icon = "fa-seedling"
            reason = f"High genetic & reproductive score ({breed_score}/100). Breeding in this cycle will boost cattle valuation by 25-35% upon confirmed conception."
            future_30d_val = current_val + 4000
            recommendation_type = "breed"
        elif prod_score >= 70 and daily_net > 0:
            action = "Hold & Maximize Milk Cashflow"
            badge = "bg-emerald-100 text-emerald-800 border-emerald-200"
            icon = "fa-arrow-trend-up"
            reason = f"Consistent milk yields generate strong recurring profit (+₹{daily_net:.1f}/day). Projected 90-day milk profit: ₹{int(net_90d):,}."
            future_30d_val = current_val + 500
            recommendation_type = "hold"
        else:
            action = "Prepare for Pongal / Mandi Festival Surge"
            badge = "bg-amber-100 text-amber-800 border-amber-200"
            icon = "fa-bullhorn"
            reason = "Kangeyam native breed auctions experience 15-20% price premiums during upcoming festive seasons. Hold and condition the animal."
            future_30d_val = current_val * 1.12
            recommendation_type = "festival"
            
        advice_list.append({
            "cattle_id": c['id'],
            "name": c['name'],
            "image_url": c['image_url'],
            "age": age,
            "breed": c['breed'],
            "current_val": current_val,
            "current_market_value": current_val,
            "peak_festival_value": round(future_30d_val),
            "future_30d_val": round(future_30d_val),
            "daily_net": round(daily_net, 1),
            "net_30d": round(net_30d),
            "net_90d": round(net_90d),
            "projected_net_30d": round(net_30d),
            "projected_net_90d": round(net_90d),
            "action": action,
            "advice": action.split('(')[0].strip(),
            "optimal_window": "30-45 Days" if recommendation_type != 'sell' else "Immediate (0-7 Days)",
            "action_badge": "HOLD_PEAK" if recommendation_type == 'hold' else ("BREED_FIRST" if recommendation_type == 'breed' else ("MONITOR_FEED" if recommendation_type == 'festival' else "CONSIDER_SALE")),
            "badge": badge,
            "icon": icon,
            "reason": reason,
            "recommendation_type": recommendation_type,
            "overall_score": analysis['overall_score']
        })
        
    conn.close()
    return advice_list

# -------------------------------------------------------------
# WASTE CONVERSION CALCULATOR (Features 8 & 9)
# -------------------------------------------------------------
def calculate_waste_conversion(dung_kg, urine_liters=0):
    """
    Computes real-time conversion values from organic cattle waste:
    - Biogas: 1 kg dung ~= 0.045 m3 biogas ~= 0.22 kWh / 0.25 kg LPG equivalent
    - Compost / Vermicompost: 1 kg dung ~= 0.35 kg premium organic compost (@ Rs 8/kg)
    - Liquid Bio-Fertilizer (Panchagavya / Jeevamrutham): (Dung + Urine) * 2.5 Liters (@ Rs 25/L)
    - LPG Cylinder equivalent & monetary fuel savings
    - CO2e emission reduction
    """
    dung = float(dung_kg or 0)
    urine = float(urine_liters or 0)

    biogas_m3 = round(dung * 0.045, 2)
    lpg_equivalent_kg = round(biogas_m3 * 0.43, 2)
    lpg_savings_inr = round(lpg_equivalent_kg * 95.0, 2) # Rs. 95/kg LPG domestic rate

    compost_kg = round(dung * 0.35, 2)
    compost_value_inr = round(compost_kg * 8.0, 2) # Rs. 8/kg compost

    liquid_fertilizer_liters = round((dung * 0.5 + urine) * 2.5, 2) if (dung > 0 or urine > 0) else round(dung * 2.5, 2)
    liquid_fertilizer_value_inr = round(liquid_fertilizer_liters * 25.0, 2) # Rs. 25/L

    total_daily_revenue_saved = round(lpg_savings_inr + compost_value_inr + liquid_fertilizer_value_inr, 2)
    monthly_projection = round(total_daily_revenue_saved * 30, 2)
    yearly_projection = round(total_daily_revenue_saved * 365, 2)

    dung_value_inr = compost_value_inr
    urine_value_inr = round(urine * 2.5 * 25.0, 2)

    carbon_offset_kg_co2e = round(dung * 0.18, 2) # 0.18 kg CO2e avoided per kg dung processed

    return {
        "dung_kg": dung,
        "urine_liters": urine,
        "urine_l": urine,
        "biogas_m3": biogas_m3,
        "lpg_equivalent_kg": lpg_equivalent_kg,
        "lpg_equiv_kg": lpg_equivalent_kg,
        "lpg_savings_inr": lpg_savings_inr,
        "lpg_savings_rupees": lpg_savings_inr,
        "compost_kg": compost_kg,
        "compost_value_inr": compost_value_inr,
        "compost_value_rupees": compost_value_inr,
        "liquid_fertilizer_liters": liquid_fertilizer_liters,
        "liquid_fertilizer_value_inr": liquid_fertilizer_value_inr,
        "liquid_fert_value_rupees": liquid_fertilizer_value_inr,
        "dung_value_inr": dung_value_inr,
        "urine_value_inr": urine_value_inr,
        "organic_waste_value_inr": total_daily_revenue_saved,
        "total_daily_value": total_daily_revenue_saved,
        "monthly_projection": monthly_projection,
        "yearly_projection": yearly_projection,
        "carbon_offset_kg_co2e": carbon_offset_kg_co2e
    }

# -------------------------------------------------------------
# GLOBAL CONTEXT PROCESSOR (Injects Flash Ticker, Alerts, Weather into all templates)
# -------------------------------------------------------------
@app.context_processor
def inject_global_data():
    ticker = get_milk_market_data()
    _, all_alerts = get_categorized_alerts()
    weather = get_realtime_weather_risk()
    return {
        "ticker": ticker,
        "global_ticker": ticker,
        "global_alert_count": len(all_alerts),
        "weather": weather,
        "global_weather": weather
    }

# -------------------------------------------------------------
# CORE ROUTES
# -------------------------------------------------------------
@app.route('/')
def index():
    if is_logged_in():
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if is_logged_in():
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        username = request.form['username'].strip().lower()
        password = request.form['password']
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        conn.close()
        
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            flash(f"Welcome back, {user['role']}!", "success")
            if user['role'] == 'Customer':
                return redirect(url_for('customer_shop'))
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid username or password. Try again.", "danger")
            
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip().lower()
        password = request.form['password']
        role = request.form.get('role')
        
        if not username or not password or role != 'Customer':
            flash("All fields are required.", "danger")
            return redirect(url_for('register'))
            
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        existing = cursor.fetchone()
        
        if existing:
            conn.close()
            flash("Username already exists.", "danger")
            return redirect(url_for('register'))
            
        password_hash = generate_password_hash(password)
        cursor.execute("INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                       (username, password_hash, role))
        conn.commit()
        conn.close()
        
        flash("Registration successful. Please log in.", "success")
        return redirect(url_for('login'))
        
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("Successfully logged out.", "success")
    return redirect(url_for('login'))

# -------------------------------------------------------------
# DASHBOARD ROUTE
# -------------------------------------------------------------
@app.route('/shop', methods=['GET', 'POST'])
def customer_shop():
    if not is_logged_in() or not is_customer():
        return redirect(url_for('dashboard' if is_logged_in() else 'login'))

    if request.method == 'POST':
        product_name = request.form.get('product_name', '').strip()
        quantity = float(request.form.get('quantity') or 0)
        notes = request.form.get('notes', '').strip()
        valid_names = {product['name'] for product in available_products()}
        if product_name not in valid_names or quantity <= 0:
            flash("Select a product and enter a quantity greater than zero.", "danger")
            return redirect(url_for('customer_shop'))

        cart = session.get('cart', [])
        cart.append({"product_name": product_name, "quantity": quantity, "notes": notes})
        session['cart'] = cart
        flash("Product added to your cart.", "success")
        return redirect(url_for('customer_shop'))

    return render_template('shop.html', products=available_products())

@app.route('/products', methods=['GET', 'POST'])
def customer_products():
    if not is_logged_in() or not is_customer():
        return redirect(url_for('dashboard' if is_logged_in() else 'login'))
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        unit = request.form.get('unit', '').strip()
        price = float(request.form.get('price') or 0)
        if not name or not unit or price <= 0:
            flash("Enter a product name, unit, and price greater than zero.", "danger")
            return redirect(url_for('customer_products'))
        if any(product['name'].lower() == name.lower() for product in available_products()):
            flash("A product with that name already exists.", "danger")
            return redirect(url_for('customer_products'))
        custom_products = session.get('custom_products', [])
        custom_products.append({"name": name, "unit": unit, "price": price, "icon": "fa-box", "color": "slate"})
        session['custom_products'] = custom_products
        flash(f"{name} was added to the Farm Shop.", "success")
        return redirect(url_for('customer_products'))
    return render_template('products.html', products=available_products())

@app.route('/cart', methods=['GET', 'POST'])
def customer_cart():
    if not is_logged_in() or not is_customer():
        return redirect(url_for('dashboard' if is_logged_in() else 'login'))

    cart = session.get('cart', [])
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'remove':
            index = int(request.form.get('index', -1))
            if 0 <= index < len(cart):
                cart.pop(index)
        elif action == 'checkout' and cart:
            payment_method = request.form.get('payment_method', 'Cash on delivery')
            payment_reference = request.form.get('payment_reference', '').strip()
            if payment_method == 'UPI' and not payment_reference:
                flash("Enter the UPI transaction reference after completing payment.", "danger")
                return redirect(url_for('customer_cart'))
            payment_status = 'Payment Submitted' if payment_method == 'UPI' else 'Unpaid'
            conn = get_db_connection()
            conn.executemany("""
                INSERT INTO customer_orders (customer_id, product_name, quantity, notes, unit_price, payment_method, payment_reference, payment_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, [(session['user_id'], item['product_name'], item['quantity'], item['notes'],
                    next((product['price'] for product in available_products() if product['name'] == item['product_name']), 0),
                    payment_method, payment_reference, payment_status)
                   for item in cart])
            conn.commit()
            conn.close()
            session['cart'] = []
            flash("Your order was received. We will contact you to confirm delivery.", "success")
            return redirect(url_for('customer_account'))
        session['cart'] = cart
        return redirect(url_for('customer_cart'))

    product_map = {product['name']: product for product in available_products()}
    items = [{**item, **product_map[item['product_name']]} for item in cart]
    total = sum(item['price'] * item['quantity'] for item in items)
    return render_template('cart.html', items=items, total=total, upi_id=UPI_ID)

@app.route('/account')
def customer_account():
    if not is_logged_in() or not is_customer():
        return redirect(url_for('dashboard' if is_logged_in() else 'login'))
    conn = get_db_connection()
    orders = conn.execute("""
        SELECT product_name, quantity, notes, unit_price, payment_method, payment_reference, payment_status, created_at FROM customer_orders
        WHERE customer_id = ? ORDER BY created_at DESC
    """, (session['user_id'],)).fetchall()
    user = conn.execute("SELECT username, role, created_at FROM users WHERE id = ?", (session['user_id'],)).fetchone()
    conn.close()
    return render_template('customer_account.html', user=user, orders=orders)

@app.route('/customer-orders', methods=['GET', 'POST'])
def customer_orders():
    if not is_logged_in() or session.get('role') != 'Cattle Owner':
        return redirect(url_for('dashboard' if is_logged_in() else 'login'))
    conn = get_db_connection()
    if request.method == 'POST':
        order_id = request.form.get('order_id')
        payment_status = request.form.get('payment_status')
        if payment_status in ('Paid', 'Unpaid', 'Payment Submitted'):
            conn.execute("UPDATE customer_orders SET payment_status = ? WHERE id = ?", (payment_status, order_id))
            conn.commit()
        return redirect(url_for('customer_orders'))
    orders = conn.execute("""
        SELECT o.id, o.product_name, o.quantity, o.unit_price, o.notes, o.payment_method, o.payment_reference, o.payment_status,
               o.created_at, u.username AS customer_name
        FROM customer_orders o JOIN users u ON u.id = o.customer_id
        ORDER BY o.created_at DESC
    """).fetchall()
    conn.close()
    return render_template('customer_orders.html', orders=orders)

@app.route('/maintenance-cost')
def maintenance_cost():
    if not is_logged_in():
        return redirect(url_for('login'))
    if is_customer():
        return redirect(url_for('customer_shop'))

    conn = get_db_connection()
    cattle = conn.execute("""
        SELECT c.id, c.name, c.current_market_value,
               COALESCE((SELECT maintenance_cost FROM financial_records f
                         WHERE f.cattle_id = c.id ORDER BY f.record_date DESC LIMIT 1), 0) AS latest_maintenance
        FROM cattle c ORDER BY c.name
    """).fetchall()
    conn.close()
    return render_template('maintenance_cost.html', cattle=cattle, now_date=datetime.now().strftime("%Y-%m-%d"))

@app.route('/dashboard')
def dashboard():
    if not is_logged_in():
        return redirect(url_for('login'))
    if is_customer():
        return redirect(url_for('customer_shop'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, breed, age, current_market_value, image_url, status FROM cattle")
    cattles = cursor.fetchall()
    
    analyzed_cattle = []
    total_score_sum = 0
    categories = {
        "Continue Dairy Production": 0,
        "Breeding Candidate": 0,
        "Monitor Closely": 0,
        "Consider Sale": 0
    }
    
    for c in cattles:
        analysis = run_decision_engine(c['id'])
        if analysis:
            analysis['image_url'] = c['image_url']
            latest_production = cursor.execute("""
                SELECT milk_production, feed_consumption, record_date
                FROM production_records
                WHERE cattle_id = ? ORDER BY record_date DESC LIMIT 1
            """, (c['id'],)).fetchone()
            analysis['latest_milk'] = latest_production['milk_production'] if latest_production else 0.0
            analysis['latest_feed'] = latest_production['feed_consumption'] if latest_production else 0.0
            analyzed_cattle.append(analysis)
            total_score_sum += analysis['overall_score']
            categories[analysis['recommendation']] += 1
            
    avg_score = round(total_score_sum / len(analyzed_cattle), 1) if analyzed_cattle else 0
    
    # Calculate revenue vs expense over the whole farm
    cursor.execute("""
        SELECT SUM(milk_production) as total_milk, SUM(feed_consumption) as total_feed 
        FROM production_records
    """)
    totals = cursor.fetchone()
    total_milk_produced = totals['total_milk'] if totals['total_milk'] is not None else 0.0
    total_feed_consumed = totals['total_feed'] if totals['total_feed'] is not None else 0.0
    
    cursor.execute("SELECT SUM(maintenance_cost) as total_maint FROM financial_records")
    maint_val = cursor.fetchone()
    total_maint_cost = maint_val['total_maint'] if maint_val['total_maint'] is not None else 0.0
    
    cursor.execute("SELECT SUM(cost) as total_med FROM health_records")
    med_val = cursor.fetchone()
    total_med_cost = med_val['total_med'] if med_val['total_med'] is not None else 0.0

    # Waste aggregate
    cursor.execute("SELECT SUM(dung_weight_kg) as total_dung, SUM(urine_liters) as total_urine FROM waste_records")
    waste_res = cursor.fetchone()
    total_dung = waste_res['total_dung'] if waste_res and waste_res['total_dung'] is not None else 0.0
    
    # Financial aggregate
    total_revenue = total_milk_produced * 41.20
    total_feed_cost = total_feed_consumed * 30.0
    total_expense = total_feed_cost + total_maint_cost + total_med_cost
    net_profit = total_revenue - total_expense
    
    conn.close()
    
    # Get Categorized Alerts & Weather Risk
    alerts_by_cat, all_alerts = get_categorized_alerts()
    weather_risk = get_realtime_weather_risk()
    waste_calc = calculate_waste_conversion(total_dung)
    
    return render_template(
        'dashboard.html',
        cattles=analyzed_cattle,
        avg_score=avg_score,
        categories=categories,
        total_revenue=round(total_revenue, 2),
        total_expense=round(total_expense, 2),
        net_profit=round(net_profit, 2),
        total_milk_produced=round(total_milk_produced, 1),
        total_dung=round(total_dung, 1),
        waste_calc=waste_calc,
        alerts=all_alerts[:8],
        alerts_by_cat=alerts_by_cat,
        weather=weather_risk
    )

# -------------------------------------------------------------
# CATTLE DIRECTORY & REGISTRATION (Features 1 & 2)
# -------------------------------------------------------------
@app.route('/cattle', methods=['GET', 'POST'])
def cattle_list():
    if not is_logged_in():
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if request.method == 'POST':
        cattle_id = request.form['cattle_id'].strip().upper()
        name = request.form['name'].strip()
        age = float(request.form['age'])
        breed = request.form['breed'].strip()
        purchase_date = request.form['purchase_date']
        purchase_price = float(request.form['purchase_price'] or 0)
        market_value = float(request.form['market_value'] or purchase_price)
        milk_production = float(request.form.get('milk_production') or 0)
        feed_consumption = float(request.form.get('feed_consumption') or 0)
        image_url = request.form.get('image_url', '').strip()
        
        # Handle file upload if provided
        if 'image_file' in request.files:
            file = request.files['image_file']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(f"{cattle_id}_{file.filename}")
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                image_url = url_for('static', filename=f'uploads/{filename}')
                
        if not image_url:
            image_url = "https://images.unsplash.com/photo-1546445317-29f4545e9d53?auto=format&fit=crop&w=600&q=80"
        
        if not cattle_id or not name:
            flash("Cattle ID and Name are required.", "warning")
            return redirect(url_for('cattle_list'))
            
        cursor.execute("SELECT id FROM cattle WHERE id = ?", (cattle_id,))
        if cursor.fetchone():
            flash(f"Cattle with ID {cattle_id} already exists.", "danger")
            conn.close()
            return redirect(url_for('cattle_list'))
            
        cursor.execute("""
            INSERT INTO cattle (id, name, age, breed, purchase_date, purchase_price, current_market_value, image_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (cattle_id, name, age, breed, purchase_date, purchase_price, market_value, image_url))
        
        now_str = datetime.now().strftime("%Y-%m-%d")
        cursor.execute("""
            INSERT INTO production_records (cattle_id, record_date, milk_production, feed_consumption)
            VALUES (?, ?, ?, ?)
        """, (cattle_id, now_str, milk_production, feed_consumption))
        
        cursor.execute("""
            INSERT INTO financial_records (cattle_id, record_date, maintenance_cost, estimated_market_value)
            VALUES (?, ?, ?, ?)
        """, (cattle_id, now_str, 5.0, market_value))

        cursor.execute("""
            INSERT INTO waste_records (cattle_id, record_date, dung_weight_kg, urine_liters, notes)
            VALUES (?, ?, ?, ?, ?)
        """, (cattle_id, now_str, 10.0, 6.0, "Initial registration dung record"))

        # Initial GPS check-in
        cursor.execute("""
            INSERT INTO cattle_gps_logs (cattle_id, latitude, longitude, location_name, scanned_by, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (cattle_id, 11.0063, 77.5639, "Kangeyam Farm Headquarters", "System Registration", "Initial tagging"))
        
        conn.commit()
        flash(f"Cattle {name} ({cattle_id}) registered successfully with scannable QR identity.", "success")
        conn.close()
        return redirect(url_for('cattle_list'))
        
    cursor.execute("SELECT * FROM cattle")
    cattles = cursor.fetchall()
    
    analyzed_cattle = []
    for c in cattles:
        analysis = run_decision_engine(c['id'])
        if analysis:
            analysis['image_url'] = c['image_url']
            analyzed_cattle.append(analysis)
            
    conn.close()
    return render_template('cattle_list.html', cattles=analyzed_cattle)

# -------------------------------------------------------------
# CATTLE DETAIL PROFILE (Feature 1, 2, 6, 8)
# -------------------------------------------------------------
@app.route('/cattle/<id>')
def cattle_detail(id):
    if not is_logged_in():
        return redirect(url_for('login'))
        
    analysis = run_decision_engine(id)
    if not analysis:
        flash("Cattle not found.", "danger")
        return redirect(url_for('dashboard'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT image_url FROM cattle WHERE id = ?", (id,))
    c_row = cursor.fetchone()
    analysis['image_url'] = c_row['image_url'] if c_row else None
    
    # 30 days logs
    cursor.execute("""
        SELECT record_date, milk_production, feed_consumption FROM production_records
        WHERE cattle_id = ? ORDER BY record_date ASC LIMIT 30
    """, (id,))
    prod_history = cursor.fetchall()
    
    cursor.execute("""
        SELECT record_date, maintenance_cost, estimated_market_value FROM financial_records
        WHERE cattle_id = ? ORDER BY record_date ASC LIMIT 30
    """, (id,))
    fin_history = cursor.fetchall()
    
    cursor.execute("""
        SELECT id, record_date, record_type, details, cost FROM health_records
        WHERE cattle_id = ? ORDER BY record_date DESC
    """, (id,))
    health_records = cursor.fetchall()
    
    cursor.execute("""
        SELECT id, record_date, event_type, details, calving_interval_days FROM breeding_records
        WHERE cattle_id = ? ORDER BY record_date DESC
    """, (id,))
    breeding_records = cursor.fetchall()

    cursor.execute("""
        SELECT id, record_date, dung_weight_kg, urine_liters, notes FROM waste_records
        WHERE cattle_id = ? ORDER BY record_date DESC LIMIT 30
    """, (id,))
    waste_records = cursor.fetchall()

    cursor.execute("""
        SELECT id, latitude, longitude, location_name, accuracy_meters, scanned_by, notes, created_at
        FROM cattle_gps_logs WHERE cattle_id = ? ORDER BY created_at DESC LIMIT 15
    """, (id,))
    gps_logs = cursor.fetchall()
    
    chart_dates = [p['record_date'] for p in prod_history]
    chart_milk = [p['milk_production'] for p in prod_history]
    chart_feed = [p['feed_consumption'] for p in prod_history]
    chart_revenues = [p['milk_production'] * 41.20 for p in prod_history]
    
    chart_expenses = []
    for idx, p in enumerate(prod_history):
        p_date = p['record_date']
        maint_cost = 5.0
        for f in fin_history:
            if f['record_date'] == p_date:
                maint_cost = f['maintenance_cost']
                break
        feed_cost = p['feed_consumption'] * 30.0
        chart_expenses.append(feed_cost + maint_cost)
        
    conn.close()
    
    datetime_str = datetime.now().strftime("%d %B %Y, %I:%M %p")
    
    return render_template(
        'cattle_detail.html',
        analysis=analysis,
        health_records=health_records,
        breeding_records=breeding_records,
        waste_records=waste_records,
        gps_logs=gps_logs,
        chart_dates=chart_dates,
        chart_milk=chart_milk,
        chart_feed=chart_feed,
        chart_revenues=chart_revenues,
        chart_expenses=chart_expenses,
        datetime_str=datetime_str
    )

# -------------------------------------------------------------
# QR CODE GENERATION & MOBILE QUICK-VIEW (Feature 2 & 6)
# -------------------------------------------------------------
@app.route('/cattle/<id>/qr')
def cattle_qr_code(id):
    """Generate a QR image containing the cattle details as plain text."""
    conn = get_db_connection()
    cattle = conn.execute("""
        SELECT id, name, breed, age, status, current_market_value
        FROM cattle WHERE id = ?
    """, (id,)).fetchone()
    latest_prod = conn.execute("""
        SELECT milk_production, record_date FROM production_records
        WHERE cattle_id = ? ORDER BY record_date DESC LIMIT 1
    """, (id,)).fetchone()
    conn.close()

    if not cattle:
        return jsonify({"error": "Cattle profile not found."}), 404

    qr_data = "\n".join([
        "SMART KANGEYAM CATTLE",
        f"ID: {cattle['id']}",
        f"Name: {cattle['name']}",
        f"Breed: {cattle['breed']}",
        f"Age: {cattle['age']} years",
        f"Status: {cattle['status']}",
        f"Milk: {latest_prod['milk_production']} L/day ({latest_prod['record_date']})" if latest_prod else "Milk: No record",
        f"Market value: Rs. {cattle['current_market_value']:,.0f}" if cattle['current_market_value'] is not None else "Market value: Not available",
    ])

    qr = qrcode.QRCode(version=None, box_size=10, border=3)
    qr.add_data(qr_data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#064e3b", back_color="#ffffff")
    
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return send_file(buf, mimetype='image/png')

@app.route('/cattle/<id>/quick-view')
def cattle_quick_view(id):
    """Fast-loading, mobile-friendly landing page displayed immediately when physical QR tag is scanned."""
    analysis = run_decision_engine(id)
    if not analysis:
        flash("Cattle profile not found.", "danger")
        return redirect(url_for('dashboard'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT image_url, name, breed, age, current_market_value FROM cattle WHERE id = ?", (id,))
    c_row = cursor.fetchone()
    if c_row:
        analysis['image_url'] = c_row['image_url']
        analysis['market_value'] = c_row['current_market_value']
    
    # Latest production
    cursor.execute("SELECT milk_production, feed_consumption, record_date FROM production_records WHERE cattle_id = ? ORDER BY record_date DESC LIMIT 1", (id,))
    latest_prod = cursor.fetchone()
    
    # Latest GPS log
    cursor.execute("SELECT location_name, created_at, latitude, longitude FROM cattle_gps_logs WHERE cattle_id = ? ORDER BY created_at DESC LIMIT 1", (id,))
    latest_gps = cursor.fetchone()
    
    conn.close()
    
    latest_milk = latest_prod['milk_production'] if latest_prod else 0.0
    
    return render_template(
        'cattle_quick_view.html',
        cattle=analysis,
        analysis=analysis,
        latest_milk=latest_milk,
        latest_prod=latest_prod,
        latest_gps=latest_gps
    )

# -------------------------------------------------------------
# GPS TRACKING & QR GEOSTAMP LOGGING (Feature 6)
# -------------------------------------------------------------
@app.route('/gps-tracking')
def gps_tracking_fleet():
    if not is_logged_in():
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT c.id as cattle_id, c.id, c.name, c.breed, c.age, c.image_url, 
               COALESCE(g.latitude, 11.0063) as last_latitude,
               COALESCE(g.longitude, 77.5639) as last_longitude,
               COALESCE(g.location_name, 'Kangeyam Pasture') as last_location,
               g.scanned_by, g.created_at as last_scan_time
        FROM cattle c
        LEFT JOIN (
            SELECT cattle_id, latitude, longitude, location_name, scanned_by, created_at
            FROM cattle_gps_logs
            WHERE id IN (SELECT MAX(id) FROM cattle_gps_logs GROUP BY cattle_id)
        ) g ON c.id = g.cattle_id
    """)
    fleet_markers = cursor.fetchall()
    
    # All recent 50 logs
    cursor.execute("""
        SELECT g.*, c.name as name, g.cattle_id 
        FROM cattle_gps_logs g
        JOIN cattle c ON g.cattle_id = c.id
        ORDER BY g.created_at DESC LIMIT 50
    """)
    all_logs = cursor.fetchall()
    
    conn.close()
    return render_template(
        'gps_tracking.html',
        fleet=fleet_markers,
        cattle_locations=fleet_markers,
        logs=all_logs,
        recent_logs=all_logs
    )

@app.route('/cattle/<id>/log-gps', methods=['POST'])
def log_cattle_gps(id):
    """Logs a new GPS Checkpoint coordinate when scanned in the field."""
    req_json = request.get_json(silent=True) or {}
    lat = float(request.form.get('latitude', req_json.get('latitude', 11.0063)))
    lon = float(request.form.get('longitude', req_json.get('longitude', 77.5639)))
    location_name = str(request.form.get('location_name', req_json.get('location_name', 'Field Checkpoint'))).strip()
    scanned_by = str(request.form.get('scanned_by', req_json.get('scanned_by', session.get('username', 'Mobile Herder App')))).strip()
    notes = str(request.form.get('notes', req_json.get('notes', 'Scanned via QR Tag'))).strip()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO cattle_gps_logs (cattle_id, latitude, longitude, location_name, scanned_by, notes)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (id, lat, lon, location_name, scanned_by, notes))
    conn.commit()
    conn.close()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json or request.path.endswith('/log-gps'):
        return jsonify({"success": True, "status": "success", "message": f"GPS coordinate ({lat}, {lon}) logged for {id}"})
        
    flash(f"GPS location '{location_name}' successfully geostamped for Cattle {id}.", "success")
    return redirect(request.referrer or url_for('cattle_detail', id=id))

# -------------------------------------------------------------
# DEDICATED ALERTS CENTER (Feature 7)
# -------------------------------------------------------------
@app.route('/alerts')
def alerts_center():
    if not is_logged_in():
        return redirect(url_for('login'))
        
    alerts_by_cat, all_alerts = get_categorized_alerts()
    return render_template(
        'alerts.html',
        alerts_by_cat=alerts_by_cat,
        alerts_by_category=alerts_by_cat,
        all_alerts=all_alerts,
        total_count=len(all_alerts)
    )

# -------------------------------------------------------------
# MARKET TIMING ADVISOR VIEW (Feature 5)
# -------------------------------------------------------------
@app.route('/market-timing')
def market_timing():
    if not is_logged_in():
        return redirect(url_for('login'))
        
    advice_list = get_market_timing_advice()
    
    summary = {
        "hold": len([a for a in advice_list if a['recommendation_type'] == 'hold']),
        "breed": len([a for a in advice_list if a['recommendation_type'] == 'breed']),
        "sell": len([a for a in advice_list if a['recommendation_type'] == 'sell']),
        "festival": len([a for a in advice_list if a['recommendation_type'] == 'festival'])
    }
    
    return render_template(
        'market_timing.html',
        advice=advice_list,
        advice_list=advice_list,
        summary=summary
    )

# -------------------------------------------------------------
# ENVIRONMENT-AWARE RISK SCORE API (Feature 4)
# -------------------------------------------------------------
@app.route('/api/weather-risk')
def api_weather_risk():
    return jsonify(get_realtime_weather_risk())

# -------------------------------------------------------------
# WASTE MANAGEMENT & CONVERSION CALCULATOR (Features 8 & 9)
# -------------------------------------------------------------
@app.route('/waste-management', methods=['GET', 'POST'])
def waste_management():
    if not is_logged_in():
        return redirect(url_for('login'))
    if is_customer():
        return redirect(url_for('customer_shop'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if request.method == 'POST':
        cattle_id = request.form['cattle_id']
        record_date = request.form.get('record_date') or datetime.now().strftime("%Y-%m-%d")
        dung_kg = float(request.form.get('dung_weight_kg', 0))
        urine_l = float(request.form.get('urine_liters', 0))
        notes = request.form.get('notes', '').strip()
        
        cursor.execute("""
            INSERT INTO waste_records (cattle_id, record_date, dung_weight_kg, urine_liters, notes)
            VALUES (?, ?, ?, ?, ?)
        """, (cattle_id, record_date, dung_kg, urine_l, notes))
        conn.commit()
        flash("Organic waste entry logged successfully.", "success")
        return redirect(url_for('waste_management'))
        
    # Query waste logs
    cursor.execute("""
        SELECT w.*, c.name as cattle_name, c.name as name
        FROM waste_records w 
        JOIN cattle c ON w.cattle_id = c.id 
        ORDER BY w.record_date DESC, w.id DESC LIMIT 50
    """)
    waste_logs = cursor.fetchall()
    
    # Aggregates
    cursor.execute("SELECT SUM(dung_weight_kg) as total_dung, SUM(urine_liters) as total_urine, AVG(dung_weight_kg) as avg_dung FROM waste_records")
    aggs = cursor.fetchone()
    total_dung = aggs['total_dung'] or 0.0
    total_urine = aggs['total_urine'] or 0.0
    
    cursor.execute("SELECT id, id as cattle_id, name FROM cattle")
    cattles = cursor.fetchall()
    
    conn.close()
    
    calc = calculate_waste_conversion(total_dung, total_urine)
    
    return render_template(
        'waste_management.html',
        waste_logs=waste_logs,
        records=waste_logs,
        total_dung=round(total_dung, 1),
        total_urine=round(total_urine, 1),
        cattles=cattles,
        calc=calc,
        waste_calc=calc
    )

@app.route('/waste-calculator')
def waste_calculator():
    dung_kg = float(request.args.get('dung_kg', 0))
    urine_l = float(request.args.get('urine_l', 0))
    if dung_kg > 0 or urine_l > 0 or request.is_json or request.headers.get('Accept') == 'application/json' or request.args.get('format') == 'json':
        return jsonify(calculate_waste_conversion(dung_kg, urine_l))
    return redirect(url_for('waste_management'))

# -------------------------------------------------------------
# VOICE-BASED FARMER ASSISTANT API (Feature 3)
# -------------------------------------------------------------
@app.route('/api/voice-assistant', methods=['POST'])
def voice_assistant_api():
    """NLP Intent processor for voice requests with speech-synthesis responses."""
    data = request.get_json(silent=True) or {}
    query = data.get('query', '').strip().lower()
    
    if not query:
        return jsonify({
            "success": True,
            "reply": "I'm listening! You can ask about any cattle, milk prices, weather risk, or biogas calculations.",
            "speech": "I am listening. Please ask your question.",
            "speech_text": "I am listening. Please ask your question."
        })

    if is_customer():
        product_matches = [product for product in available_products() if any(word in query for word in product['name'].lower().split())]
        if 'shop' in query or 'product' in query or 'buy' in query or product_matches:
            if product_matches:
                product = product_matches[0]
                speech_text = f"{product['name']} costs rupees {product['price']} per {product['unit']} in the farm shop."
                reply_text = f"**{product['name']}** is ₹{product['price']} per {product['unit']}. You can add it to your cart from the Farm Shop."
            else:
                speech_text = "The farm shop sells colostrum, fresh milk, traditional milk products, organic fertilizer, and biogas."
                reply_text = "The Farm Shop sells **colostrum, fresh milk, traditional milk products, organic fertilizer, and biogas**. Ask for a product price or open the shop to order."
            return jsonify({"success": True, "reply": reply_text, "speech": speech_text, "speech_text": speech_text, "link": url_for('customer_shop')})
        return jsonify({"success": True, "reply": "I can help with farm shop products, prices, cart orders, and delivery requests.", "speech": "I can help with farm shop products, prices, cart orders, and delivery requests.", "speech_text": "I can help with farm shop products, prices, cart orders, and delivery requests."})

    conn = get_db_connection()
    cursor = conn.cursor()

    # Intent 1: Specific cattle query
    cursor.execute("SELECT id, name FROM cattle")
    all_cows = cursor.fetchall()
    
    matched_cow = None
    for cow in all_cows:
        cow_name_parts = cow['name'].lower().split()
        if cow['id'].lower() in query or any(part in query for part in cow_name_parts if len(part) > 2):
            matched_cow = cow
            break
            
    if matched_cow:
        analysis = run_decision_engine(matched_cow['id'])
        if analysis:
            reply_text = (
                f"📊 **{matched_cow['name']} ({matched_cow['id']}) Status**:\n"
                f"- Health Score: {analysis['health_score']}/100\n"
                f"- Productivity: {analysis['productivity_score']}/100\n"
                f"- Recommendation: **{analysis['recommendation']}**\n"
                f"- Active Alerts: {', '.join(analysis['global_alerts']) if analysis['global_alerts'] else 'None'}"
            )
            speech_text = f"{matched_cow['name']} has a health score of {analysis['health_score']}, productivity of {analysis['productivity_score']}, and the system recommends {analysis['recommendation']}."
            conn.close()
            return jsonify({
                "success": True,
                "reply": reply_text,
                "speech": speech_text,
                "speech_text": speech_text,
                "link": url_for('cattle_detail', id=matched_cow['id'])
            })

    # Intent 2: Milk Price Query
    if "milk" in query and ("price" in query or "rate" in query or "market" in query or "today" in query or "tomorrow" in query):
        m = get_milk_market_data()
        reply_text = (
            f"🥛 **Live Kangeyam Milk Market Flash**:\n"
            f"- Today's Price: **₹{m['today']} / Liter** ({m['trend']})\n"
            f"- Yesterday: ₹{m['yesterday']} / L\n"
            f"- Tomorrow Forecast: **₹{m['tomorrow']} / L**\n"
            f"- Pure A2 Kangeyam Premium: **₹{m['a2_premium']} / L**"
        )
        speech_text = f"Today's milk price is rupees {m['today']} per liter, up from {m['yesterday']} yesterday. Tomorrow's forecast is {m['tomorrow']} rupees per liter."
        conn.close()
        return jsonify({
            "success": True,
            "reply": reply_text,
            "speech": speech_text,
            "speech_text": speech_text
        })

    # Intent 3: Weather & Risk Query
    if "weather" in query or "heat" in query or "risk" in query or "temperature" in query:
        w = get_realtime_weather_risk()
        reply_text = (
            f"⛅ **Live Weather & Cattle Risk Status**:\n"
            f"- Temperature: **{w['temperature']}°C** (Humidity: {w['humidity']}%)\n"
            f"- Livestock THI Index: **{w['thi']}**\n"
            f"- Risk Assessment: **{w['risk_level']}**\n"
            f"- Recommendation: {w['advisory']}"
        )
        speech_text = f"Current temperature is {w['temperature']} degrees Celsius with a THI index of {w['thi']}. Risk level is {w['risk_level']}. {w['advisory']}"
        conn.close()
        return jsonify({
            "success": True,
            "reply": reply_text,
            "speech": speech_text,
            "speech_text": speech_text
        })

    # Intent 4: Alerts Query
    if "alert" in query or "warning" in query or "urgent" in query or "vaccine" in query:
        _, all_alerts = get_categorized_alerts()
        count = len(all_alerts)
        if count == 0:
            reply_text = "✅ **All Clear!** There are currently zero urgent health or maintenance alerts for your herd."
            speech_text = "All clear! There are currently no urgent alerts for your herd."
        else:
            first_three = all_alerts[:3]
            details = "\n".join([f"- **{a['name']}**: {a['category']} - {a['message']}" for a in first_three])
            reply_text = f"⚠️ You have **{count} active alerts** across the herd:\n{details}"
            speech_text = f"You have {count} active alerts across the herd. For example, {first_three[0]['name']} has a {first_three[0]['category']} alert."
        conn.close()
        return jsonify({
            "success": True,
            "reply": reply_text,
            "speech": speech_text,
            "speech_text": speech_text,
            "link": url_for('alerts_center')
        })

    # Intent 5: Waste or Biogas query
    if "dung" in query or "waste" in query or "biogas" in query or "compost" in query:
        cursor.execute("SELECT SUM(dung_weight_kg) as total_dung FROM waste_records")
        res = cursor.fetchone()
        dung_total = res['total_dung'] or 100.0
        calc = calculate_waste_conversion(dung_total)
        reply_text = (
            f"🌱 **Herd Waste & Biogas Valuation**:\n"
            f"- Total Recorded Dung: **{calc['dung_kg']} kg**\n"
            f"- Biogas Generated: **{calc['biogas_m3']} m³** (~{calc['lpg_equivalent_kg']} kg LPG saved)\n"
            f"- LPG Value Saved: **₹{calc['lpg_savings_inr']}**\n"
            f"- Organic Compost Value: **₹{calc['compost_value_inr']}**\n"
            f"- Monthly Economic Return: **₹{calc['monthly_projection']}**"
        )
        speech_text = f"Recorded dung can produce {calc['biogas_m3']} cubic meters of biogas, saving rupees {calc['lpg_savings_inr']} in LPG cooking gas."
        conn.close()
        return jsonify({
            "success": True,
            "reply": reply_text,
            "speech": speech_text,
            "speech_text": speech_text,
            "link": url_for('waste_management')
        })

    # Intent 6: General Overview
    cursor.execute("SELECT COUNT(*) as cnt FROM cattle")
    c_cnt = cursor.fetchone()['cnt']
    conn.close()
    
    reply_text = (
        f"🐄 **Smart Kangeyam Farm Assistant**:\n"
        f"- Total Cattle Monitored: **{c_cnt}**\n"
        f"You can ask me: *'What is the milk price?'*, *'How is Lakshmi doing?'*, *'What is today's weather risk?'*, or *'Show me overdue vaccines'*."
    )
    speech_text = f"You have {c_cnt} cattle registered. You can ask me about milk price, weather risk, or any individual cow."
    return jsonify({
        "success": True,
        "reply": reply_text,
        "speech": speech_text,
        "speech_text": speech_text
    })

# -------------------------------------------------------------
# REST OF LOGGING & UTILITY ROUTES
# -------------------------------------------------------------
@app.route('/cattle/<id>/add_log', methods=['POST'])
def add_log(id):
    if not is_logged_in():
        return redirect(url_for('login'))
        
    log_type = request.form.get('log_type')
    log_date = request.form.get('log_date') or datetime.now().strftime("%Y-%m-%d")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        if log_type == 'production':
            milk = float(request.form.get('milk_production', 0))
            feed = float(request.form.get('feed_consumption', 0))
            cursor.execute("""
                INSERT INTO production_records (cattle_id, record_date, milk_production, feed_consumption)
                VALUES (?, ?, ?, ?)
            """, (id, log_date, milk, feed))
            
            cursor.execute("""
                SELECT estimated_market_value FROM financial_records 
                WHERE cattle_id = ? ORDER BY record_date DESC LIMIT 1
            """, (id,))
            last_fin = cursor.fetchone()
            market_val = last_fin['estimated_market_value'] if last_fin else 40000.0
            
            cursor.execute("""
                INSERT INTO financial_records (cattle_id, record_date, maintenance_cost, estimated_market_value)
                VALUES (?, ?, ?, ?)
            """, (id, log_date, 5.0, market_val))
            
            flash("Production log added successfully.", "success")
            
        elif log_type == 'health':
            rec_type = request.form.get('health_type')
            details = request.form.get('details')
            cost = float(request.form.get('cost', 0))
            cursor.execute("""
                INSERT INTO health_records (cattle_id, record_date, record_type, details, cost)
                VALUES (?, ?, ?, ?, ?)
            """, (id, log_date, rec_type, details, cost))
            flash("Health record logged successfully.", "success")
            
        elif log_type == 'breeding':
            ev_type = request.form.get('event_type')
            details = request.form.get('details')
            interval = request.form.get('calving_interval')
            interval_val = int(interval) if interval else None
            cursor.execute("""
                INSERT INTO breeding_records (cattle_id, record_date, event_type, details, calving_interval_days)
                VALUES (?, ?, ?, ?, ?)
            """, (id, log_date, ev_type, details, interval_val))
            flash("Breeding event logged successfully.", "success")
            
        elif log_type == 'financial':
            cost_components = ('feed_cost', 'labor_cost', 'housing_cost', 'medicine_cost', 'other_cost')
            maint = sum(float(request.form.get(component) or 0) for component in cost_components)
            market_val = float(request.form.get('market_value', 0))
            cursor.execute("""
                INSERT INTO financial_records (cattle_id, record_date, maintenance_cost, estimated_market_value)
                VALUES (?, ?, ?, ?)
            """, (id, log_date, maint, market_val))
            
            cursor.execute("UPDATE cattle SET current_market_value = ? WHERE id = ?", (market_val, id))
            flash("Financial record logged successfully.", "success")
            
        elif log_type == 'waste':
            dung = float(request.form.get('dung_weight_kg', 0))
            urine = float(request.form.get('urine_liters', 0))
            notes = request.form.get('notes', '')
            cursor.execute("""
                INSERT INTO waste_records (cattle_id, record_date, dung_weight_kg, urine_liters, notes)
                VALUES (?, ?, ?, ?, ?)
            """, (id, log_date, dung, urine, notes))
            flash("Waste record logged successfully.", "success")

        conn.commit()
    except Exception as e:
        conn.rollback()
        flash(f"Error logging record: {str(e)}", "danger")
    finally:
        conn.close()
        
    return redirect(url_for('cattle_detail', id=id))

@app.route('/cattle/<id>/log-booster')
def log_vaccination_booster(id):
    """Open the cattle profile directly at the vaccination booster form."""
    if not is_logged_in():
        return redirect(url_for('login'))
    return redirect(url_for('cattle_detail', id=id, tab='health'))

@app.route('/cattle/<id>/delete', methods=['POST'])
def delete_cattle(id):
    if not is_logged_in():
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM cattle WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    flash("Cattle profile deleted successfully.", "success")
    return redirect(url_for('cattle_list'))

@app.route('/cattle/<id>/edit', methods=['GET', 'POST'])
def edit_cattle(id):
    if not is_logged_in():
        return redirect(url_for('login'))

    conn = get_db_connection()
    cattle = conn.execute("SELECT * FROM cattle WHERE id = ?", (id,)).fetchone()
    if not cattle:
        conn.close()
        flash("Cattle profile not found.", "danger")
        return redirect(url_for('cattle_list'))

    if request.method == 'POST':
        name = request.form['name'].strip()
        age = float(request.form['age'])
        breed = request.form['breed'].strip()
        purchase_date = request.form.get('purchase_date', '')
        purchase_price = float(request.form.get('purchase_price') or 0)
        market_value = float(request.form.get('market_value') or 0)
        status = request.form.get('status', 'Active').strip()
        image_url = request.form.get('image_url', '').strip() or cattle['image_url']

        conn.execute("""
            UPDATE cattle
            SET name = ?, age = ?, breed = ?, purchase_date = ?, purchase_price = ?,
                current_market_value = ?, image_url = ?, status = ?
            WHERE id = ?
        """, (name, age, breed, purchase_date, purchase_price, market_value, image_url, status, id))
        conn.commit()
        conn.close()
        flash(f"Cattle profile {id} updated successfully.", "success")
        return redirect(url_for('cattle_detail', id=id))

    conn.close()
    return render_template('cattle_edit.html', cattle=cattle)

@app.route('/reset_database', methods=['POST'])
def reset_database():
    if not is_logged_in():
        return redirect(url_for('login'))
        
    try:
        seed_data()
        flash("Database has been reset to default test cases with sample GPS logs and waste records.", "success")
    except Exception as e:
        flash(f"Error resetting database: {str(e)}", "danger")
        
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(debug=True)

