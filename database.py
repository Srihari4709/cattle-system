import sqlite3
import os
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

DATABASE_PATH = os.path.join(os.path.dirname(__file__), 'cattle.db')

def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS customer_orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL,
        product_name TEXT NOT NULL,
        quantity REAL NOT NULL,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (customer_id) REFERENCES users(id)
    )
    ''')

    cursor.execute("PRAGMA table_info(customer_orders)")
    order_columns = [column[1] for column in cursor.fetchall()]
    if 'unit_price' not in order_columns:
        cursor.execute("ALTER TABLE customer_orders ADD COLUMN unit_price REAL NOT NULL DEFAULT 0")
    if 'payment_status' not in order_columns:
        cursor.execute("ALTER TABLE customer_orders ADD COLUMN payment_status TEXT NOT NULL DEFAULT 'Unpaid'")
    if 'payment_method' not in order_columns:
        cursor.execute("ALTER TABLE customer_orders ADD COLUMN payment_method TEXT NOT NULL DEFAULT 'Cash on delivery'")
    if 'payment_reference' not in order_columns:
        cursor.execute("ALTER TABLE customer_orders ADD COLUMN payment_reference TEXT")
    
    # Create cattle table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS cattle (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        age REAL NOT NULL,
        breed TEXT NOT NULL,
        purchase_date TEXT,
        purchase_price REAL,
        current_market_value REAL,
        image_url TEXT,
        status TEXT DEFAULT 'Active',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Migration: check if image_url column exists in cattle table
    cursor.execute("PRAGMA table_info(cattle)")
    cols = [c[1] for c in cursor.fetchall()]
    if 'image_url' not in cols:
        try:
            cursor.execute("ALTER TABLE cattle ADD COLUMN image_url TEXT")
        except Exception:
            pass
    
    # Create health_records table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS health_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cattle_id TEXT NOT NULL,
        record_date TEXT NOT NULL,
        record_type TEXT NOT NULL, -- 'vaccination', 'medical_treatment', 'checkup'
        details TEXT NOT NULL,
        cost REAL DEFAULT 0,
        FOREIGN KEY (cattle_id) REFERENCES cattle(id) ON DELETE CASCADE
    )
    ''')
    
    # Create production_records table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS production_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cattle_id TEXT NOT NULL,
        record_date TEXT NOT NULL,
        milk_production REAL NOT NULL, -- in Liters
        feed_consumption REAL NOT NULL, -- in kg
        FOREIGN KEY (cattle_id) REFERENCES cattle(id) ON DELETE CASCADE
    )
    ''')
    
    # Create breeding_records table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS breeding_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cattle_id TEXT NOT NULL,
        record_date TEXT NOT NULL,
        event_type TEXT NOT NULL, -- 'calving', 'insemination', 'heat'
        details TEXT,
        calving_interval_days INTEGER DEFAULT NULL,
        FOREIGN KEY (cattle_id) REFERENCES cattle(id) ON DELETE CASCADE
    )
    ''')
    
    # Create financial_records table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS financial_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cattle_id TEXT NOT NULL,
        record_date TEXT NOT NULL,
        maintenance_cost REAL NOT NULL, -- labor, feed (non-production), shelter etc.
        estimated_market_value REAL NOT NULL,
        FOREIGN KEY (cattle_id) REFERENCES cattle(id) ON DELETE CASCADE
    )
    ''')

    # Create waste_records table (Dung & Organic Waste tracking)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS waste_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cattle_id TEXT NOT NULL,
        record_date TEXT NOT NULL,
        dung_weight_kg REAL NOT NULL,
        urine_liters REAL DEFAULT 0,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (cattle_id) REFERENCES cattle(id) ON DELETE CASCADE
    )
    ''')

    # Create cattle_gps_logs table (Cost-efficient QR Geolocation Tracking)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS cattle_gps_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cattle_id TEXT NOT NULL,
        latitude REAL NOT NULL,
        longitude REAL NOT NULL,
        location_name TEXT DEFAULT 'Pasture Checkpoint',
        accuracy_meters REAL DEFAULT 5.0,
        scanned_by TEXT DEFAULT 'Farm Staff',
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (cattle_id) REFERENCES cattle(id) ON DELETE CASCADE
    )
    ''')
    
    conn.commit()
    conn.close()
    print("Database tables initialized successfully.")

def seed_data():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Clear existing data to make seeding idempotent
    cursor.execute("DELETE FROM users")
    cursor.execute("DELETE FROM health_records")
    cursor.execute("DELETE FROM production_records")
    cursor.execute("DELETE FROM breeding_records")
    cursor.execute("DELETE FROM financial_records")
    cursor.execute("DELETE FROM waste_records")
    cursor.execute("DELETE FROM cattle_gps_logs")
    cursor.execute("DELETE FROM cattle")
    
    # 1. Seed users
    roles = ['Cattle Owner', 'Veterinarian', 'Dairy Farm Manager', 'Cooperative Inspector', 'Market Agent']
    for idx, role in enumerate(roles):
        username = role.lower().replace(' ', '')
        password_hash = generate_password_hash("password123")
        cursor.execute("INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                       (username, password_hash, role))
    
    # Base date for generating historical logs (30 days ago)
    base_date = datetime.now() - timedelta(days=30)
    
    # High-quality representative Kangeyam cattle images
    default_images = [
        "https://images.unsplash.com/photo-1546445317-29f4545e9d53?auto=format&fit=crop&w=600&q=80",
        "https://images.unsplash.com/photo-1570042225831-d98fa7577f1e?auto=format&fit=crop&w=600&q=80",
        "https://images.unsplash.com/photo-1527153857715-3908f2ae5e81?auto=format&fit=crop&w=600&q=80",
        "https://images.unsplash.com/photo-1500595046743-cd271d694d30?auto=format&fit=crop&w=600&q=80",
        "https://images.unsplash.com/photo-1596733430284-f7437764b1a9?auto=format&fit=crop&w=600&q=80",
        "https://images.unsplash.com/photo-1568644396922-5c3bfae12521?auto=format&fit=crop&w=600&q=80",
        "https://images.unsplash.com/photo-1589923188900-85dae523342b?auto=format&fit=crop&w=600&q=80"
    ]
    
    # 2. Seed Cattle with specific profiles representing the test cases
    cattle_profiles = [
        # Case A: High milk production but extremely high maintenance and medical cost
        {
            "id": "KANG-001",
            "name": "Lakshmi (High Production, High Cost)",
            "age": 5.2,
            "breed": "Kangeyam",
            "purchase_date": (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d"),
            "purchase_price": 45000.0,
            "current_market_value": 48000.0,
            "image_url": default_images[0],
            "status": "Active"
        },
        # Case B: Vaccination overdue
        {
            "id": "KANG-002",
            "name": "Gauri (Vaccine Overdue)",
            "age": 4.5,
            "breed": "Kangeyam",
            "purchase_date": (datetime.now() - timedelta(days=200)).strftime("%Y-%m-%d"),
            "purchase_price": 42000.0,
            "current_market_value": 41000.0,
            "image_url": default_images[1],
            "status": "Active"
        },
        # Case C: Declining milk production
        {
            "id": "KANG-003",
            "name": "Sita (Declining Production)",
            "age": 6.0,
            "breed": "Kangeyam",
            "purchase_date": (datetime.now() - timedelta(days=400)).strftime("%Y-%m-%d"),
            "purchase_price": 40000.0,
            "current_market_value": 35000.0,
            "image_url": default_images[2],
            "status": "Active"
        },
        # Case D: Missing health records
        {
            "id": "KANG-004",
            "name": "Rathi (Missing Health Records)",
            "age": 3.8,
            "breed": "Kangeyam",
            "purchase_date": (datetime.now() - timedelta(days=100)).strftime("%Y-%m-%d"),
            "purchase_price": 38000.0,
            "current_market_value": 39000.0,
            "image_url": default_images[3],
            "status": "Active"
        },
        # Case E: Young animal with limited history
        {
            "id": "KANG-005",
            "name": "Karpagam (Young Heifer)",
            "age": 1.5,
            "breed": "Kangeyam",
            "purchase_date": (datetime.now() - timedelta(days=50)).strftime("%Y-%m-%d"),
            "purchase_price": 25000.0,
            "current_market_value": 28000.0,
            "image_url": default_images[4],
            "status": "Active"
        },
        # Case F: Sudden productivity decrease
        {
            "id": "KANG-006",
            "name": "Sona (Sudden Drop)",
            "age": 4.0,
            "breed": "Kangeyam",
            "purchase_date": (datetime.now() - timedelta(days=150)).strftime("%Y-%m-%d"),
            "purchase_price": 43000.0,
            "current_market_value": 42000.0,
            "image_url": default_images[5],
            "status": "Active"
        },
        # Case G: Changing market value
        {
            "id": "KANG-007",
            "name": "Meena (Fluctuating Market)",
            "age": 5.5,
            "breed": "Kangeyam",
            "purchase_date": (datetime.now() - timedelta(days=300)).strftime("%Y-%m-%d"),
            "purchase_price": 46000.0,
            "current_market_value": 30000.0,
            "image_url": default_images[6],
            "status": "Active"
        }
    ]
    
    for cattle in cattle_profiles:
        cursor.execute("""
            INSERT INTO cattle (id, name, age, breed, purchase_date, purchase_price, current_market_value, image_url, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (cattle["id"], cattle["name"], cattle["age"], cattle["breed"], cattle["purchase_date"], cattle["purchase_price"], cattle["current_market_value"], cattle["image_url"], cattle["status"]))
        
    # --- Generate detailed records for each case for 30 days ---
    for day in range(30):
        log_date = (base_date + timedelta(days=day)).strftime("%Y-%m-%d")
        
        # 1. KANG-001: Lakshmi
        cursor.execute("""
            INSERT INTO production_records (cattle_id, record_date, milk_production, feed_consumption)
            VALUES (?, ?, ?, ?)
        """, ("KANG-001", log_date, 15.2, 12.5))
        cursor.execute("""
            INSERT INTO financial_records (cattle_id, record_date, maintenance_cost, estimated_market_value)
            VALUES (?, ?, ?, ?)
        """, ("KANG-001", log_date, 150.0, 48000.0))
        cursor.execute("""
            INSERT INTO waste_records (cattle_id, record_date, dung_weight_kg, urine_liters, notes)
            VALUES (?, ?, ?, ?, ?)
        """, ("KANG-001", log_date, 15.5, 9.0, "High intake, high organic yield"))
        
        # 2. KANG-002: Gauri
        cursor.execute("""
            INSERT INTO production_records (cattle_id, record_date, milk_production, feed_consumption)
            VALUES (?, ?, ?, ?)
        """, ("KANG-002", log_date, 8.5, 6.0))
        cursor.execute("""
            INSERT INTO financial_records (cattle_id, record_date, maintenance_cost, estimated_market_value)
            VALUES (?, ?, ?, ?)
        """, ("KANG-002", log_date, 4.0, 41000.0))
        cursor.execute("""
            INSERT INTO waste_records (cattle_id, record_date, dung_weight_kg, urine_liters, notes)
            VALUES (?, ?, ?, ?, ?)
        """, ("KANG-002", log_date, 11.2, 7.0, "Normal organic waste"))
        
        # 3. KANG-003: Sita
        milk_yield_c = max(3.0, 14.0 - (day * 0.38))
        cursor.execute("""
            INSERT INTO production_records (cattle_id, record_date, milk_production, feed_consumption)
            VALUES (?, ?, ?, ?)
        """, ("KANG-003", log_date, milk_yield_c, 7.0))
        cursor.execute("""
            INSERT INTO financial_records (cattle_id, record_date, maintenance_cost, estimated_market_value)
            VALUES (?, ?, ?, ?)
        """, ("KANG-003", log_date, 4.5, 35000.0))
        cursor.execute("""
            INSERT INTO waste_records (cattle_id, record_date, dung_weight_kg, urine_liters, notes)
            VALUES (?, ?, ?, ?, ?)
        """, ("KANG-003", log_date, 10.0, 6.5, "Routine dung collection"))
        
        # 4. KANG-004: Rathi
        cursor.execute("""
            INSERT INTO production_records (cattle_id, record_date, milk_production, feed_consumption)
            VALUES (?, ?, ?, ?)
        """, ("KANG-004", log_date, 9.0, 7.0))
        cursor.execute("""
            INSERT INTO financial_records (cattle_id, record_date, maintenance_cost, estimated_market_value)
            VALUES (?, ?, ?, ?)
        """, ("KANG-004", log_date, 4.0, 39000.0))
        cursor.execute("""
            INSERT INTO waste_records (cattle_id, record_date, dung_weight_kg, urine_liters, notes)
            VALUES (?, ?, ?, ?, ?)
        """, ("KANG-004", log_date, 11.5, 7.2, "Clean barn dung log"))
        
        # 5. KANG-005: Karpagam (Young Heifer)
        cursor.execute("""
            INSERT INTO production_records (cattle_id, record_date, milk_production, feed_consumption)
            VALUES (?, ?, ?, ?)
        """, ("KANG-005", log_date, 0.0, 4.0))
        cursor.execute("""
            INSERT INTO financial_records (cattle_id, record_date, maintenance_cost, estimated_market_value)
            VALUES (?, ?, ?, ?)
        """, ("KANG-005", log_date, 2.0, 28000.0))
        cursor.execute("""
            INSERT INTO waste_records (cattle_id, record_date, dung_weight_kg, urine_liters, notes)
            VALUES (?, ?, ?, ?, ?)
        """, ("KANG-005", log_date, 6.5, 4.0, "Heifer daily dung"))
        
        # 6. KANG-006: Sona (Sudden Drop)
        milk_yield_f = 2.0 if day >= 27 else 11.2
        cursor.execute("""
            INSERT INTO production_records (cattle_id, record_date, milk_production, feed_consumption)
            VALUES (?, ?, ?, ?)
        """, ("KANG-006", log_date, milk_yield_f, 8.0))
        cursor.execute("""
            INSERT INTO financial_records (cattle_id, record_date, maintenance_cost, estimated_market_value)
            VALUES (?, ?, ?, ?)
        """, ("KANG-006", log_date, 4.5, 42000.0))
        cursor.execute("""
            INSERT INTO waste_records (cattle_id, record_date, dung_weight_kg, urine_liters, notes)
            VALUES (?, ?, ?, ?, ?)
        """, ("KANG-006", log_date, 12.0, 7.5, "Regular dung"))
        
        # 7. KANG-007: Meena
        cursor.execute("""
            INSERT INTO production_records (cattle_id, record_date, milk_production, feed_consumption)
            VALUES (?, ?, ?, ?)
        """, ("KANG-007", log_date, 10.0, 7.5))
        market_val = 46000.0 - (day * 550)
        cursor.execute("""
            INSERT INTO financial_records (cattle_id, record_date, maintenance_cost, estimated_market_value)
            VALUES (?, ?, ?, ?)
        """, ("KANG-007", log_date, 5.0, market_val))
        cursor.execute("""
            INSERT INTO waste_records (cattle_id, record_date, dung_weight_kg, urine_liters, notes)
            VALUES (?, ?, ?, ?, ?)
        """, ("KANG-007", log_date, 13.0, 8.0, "Standard dung collection"))
        
    # --- Add specific health records & treatments ---
    cursor.execute("""
        INSERT INTO health_records (cattle_id, record_date, record_type, details, cost)
        VALUES 
        ('KANG-001', ?, 'medical_treatment', 'Mastitis antibiotic therapy', 1800.0),
        ('KANG-001', ?, 'medical_treatment', 'Vet consultation and supplements', 750.0),
        ('KANG-001', ?, 'vaccination', 'Foot and Mouth Vaccine', 15.0)
    """, (
        (datetime.now() - timedelta(days=4)).strftime("%Y-%m-%d"),
        (datetime.now() - timedelta(days=20)).strftime("%Y-%m-%d"),
        (datetime.now() - timedelta(days=80)).strftime("%Y-%m-%d")
    ))
    
    cursor.execute("""
        INSERT INTO health_records (cattle_id, record_date, record_type, details, cost)
        VALUES 
        ('KANG-002', ?, 'vaccination', 'Anthrax Vaccine', 10.0),
        ('KANG-002', ?, 'vaccination', 'Brucellosis Vaccine', 12.0)
    """, (
        (datetime.now() - timedelta(days=400)).strftime("%Y-%m-%d"),
        (datetime.now() - timedelta(days=410)).strftime("%Y-%m-%d")
    ))
    
    cursor.execute("""
        INSERT INTO health_records (cattle_id, record_date, record_type, details, cost)
        VALUES 
        ('KANG-003', ?, 'medical_treatment', 'Deworming & Indigestion tonic', 40.0),
        ('KANG-003', ?, 'vaccination', 'Black Quarter Vaccine', 15.0)
    """, (
        (datetime.now() - timedelta(days=12)).strftime("%Y-%m-%d"),
        (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")
    ))
    
    cursor.execute("""
        INSERT INTO health_records (cattle_id, record_date, record_type, details, cost)
        VALUES 
        ('KANG-005', ?, 'vaccination', 'Brucellosis Vaccine (Calfhood)', 12.0),
        ('KANG-005', ?, 'checkup', 'Routine growth check', 0.0)
    """, (
        (datetime.now() - timedelta(days=45)).strftime("%Y-%m-%d"),
        (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
    ))
    
    cursor.execute("""
        INSERT INTO health_records (cattle_id, record_date, record_type, details, cost)
        VALUES 
        ('KANG-006', ?, 'medical_treatment', 'High fever treatment', 85.0),
        ('KANG-006', ?, 'vaccination', 'Foot and Mouth Vaccine', 15.0)
    """, (
        (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d"),
        (datetime.now() - timedelta(days=70)).strftime("%Y-%m-%d")
    ))
    
    cursor.execute("""
        INSERT INTO health_records (cattle_id, record_date, record_type, details, cost)
        VALUES 
        ('KANG-007', ?, 'vaccination', 'Foot and Mouth Vaccine', 15.0),
        ('KANG-007', ?, 'vaccination', 'Hemorrhagic Septicemia Vaccine', 15.0)
    """, (
        (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"),
        (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    ))
    
    # --- Add Breeding Records ---
    cursor.execute("""
        INSERT INTO breeding_records (cattle_id, record_date, event_type, details, calving_interval_days)
        VALUES ('KANG-001', ?, 'calving', 'Healthy male calf born', 380)
    """, ((datetime.now() - timedelta(days=100)).strftime("%Y-%m-%d"),))
    
    cursor.execute("""
        INSERT INTO breeding_records (cattle_id, record_date, event_type, details)
        VALUES ('KANG-005', ?, 'heat', 'First heat detected, ready for breeding')
    """, ((datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d"),))
    
    cursor.execute("""
        INSERT INTO breeding_records (cattle_id, record_date, event_type, details, calving_interval_days)
        VALUES ('KANG-007', ?, 'calving', 'Healthy female calf born', 365)
    """, ((datetime.now() - timedelta(days=120)).strftime("%Y-%m-%d"),))
    
    # --- Add Sample GPS Checkpoint Logs (Kangeyam coordinates: 11.0063° N, 77.5639° E) ---
    sample_gps_locations = [
        {"id": "KANG-001", "lat": 11.0075, "lon": 77.5642, "loc": "Main Dairy Shed Stall A1", "scanner": "Murugan (Supervisor)"},
        {"id": "KANG-002", "lat": 11.0092, "lon": 77.5680, "loc": "North Pasture Grazing Block 3", "scanner": "Ramasamy (Herder)"},
        {"id": "KANG-003", "lat": 11.0048, "lon": 77.5615, "loc": "East Water Pond Checkpoint", "scanner": "Velu (Farmhand)"},
        {"id": "KANG-004", "lat": 11.0081, "lon": 77.5655, "loc": "Central Kangeyam Shed B2", "scanner": "Murugan (Supervisor)"},
        {"id": "KANG-005", "lat": 11.0110, "lon": 77.5702, "loc": "Heifer Rearing Meadow #1", "scanner": "Ramasamy (Herder)"},
        {"id": "KANG-006", "lat": 11.0060, "lon": 77.5630, "loc": "Veterinary Quarantine Shed", "scanner": "Dr. Selvam (Vet)"},
        {"id": "KANG-007", "lat": 11.0088, "lon": 77.5671, "loc": "Open Korambu Grassland Zone", "scanner": "Velu (Farmhand)"}
    ]
    
    for g in sample_gps_locations:
        cursor.execute("""
            INSERT INTO cattle_gps_logs (cattle_id, latitude, longitude, location_name, accuracy_meters, scanned_by, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (g["id"], g["lat"], g["lon"], g["loc"], 3.5, g["scanner"], "QR Code Tag Scanned in field"))
        
    conn.commit()
    conn.close()
    print("Database seeded successfully with all 10 features, test cases, GPS logs, and waste records.")

if __name__ == '__main__':
    init_db()
    seed_data()
