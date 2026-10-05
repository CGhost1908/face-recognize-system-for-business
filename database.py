import sqlite3
import os
from datetime import datetime

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database.db")


def get_db_connection(db_path=None):
    if db_path is None:
        db_path = DEFAULT_DB_PATH
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path=None):
    """Initialize database tables with schema for UniFace multi-angle embeddings and Cafe Management."""
    if db_path is None:
        db_path = DEFAULT_DB_PATH

    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()

        # Users table (registered customers + auto-registered guests)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                user_type TEXT DEFAULT 'customer',
                image TEXT NULL,
                total_spent REAL DEFAULT 0,
                last_login_date TEXT NOT NULL,
                encoding BLOB NOT NULL
            )
        ''')

        # Multi-vector embedding prototype table (Multi-Angle Gallery storage)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_embeddings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_name TEXT NOT NULL,
                user_type TEXT DEFAULT 'customer',
                embedding BLOB NOT NULL,
                quality_score REAL DEFAULT 1.0,
                yaw REAL DEFAULT 0.0,
                pitch REAL DEFAULT 0.0,
                created_at TEXT NOT NULL
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_embeddings_name ON user_embeddings(user_name)')

        # Entry Logs table for real-time check-ins
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS entry_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_name TEXT NOT NULL,
                user_type TEXT DEFAULT 'customer',
                entry_time TEXT NOT NULL,
                confidence REAL DEFAULT 1.0
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_entry_logs_user ON entry_logs(user_name)')

        # Products table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_name TEXT NOT NULL UNIQUE,
                category TEXT NOT NULL,
                price REAL NOT NULL,
                description TEXT DEFAULT '',
                image_url TEXT DEFAULT ''
            )
        ''')

        # Orders table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_name TEXT NOT NULL,
                name TEXT,
                total_amount REAL NOT NULL,
                foods TEXT DEFAULT '',
                order_date TEXT NOT NULL
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_name)')

        # Order Items table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                product_name TEXT NOT NULL,
                quantity INTEGER DEFAULT 1,
                unit_price REAL NOT NULL,
                FOREIGN KEY (order_id) REFERENCES orders(id)
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_order_items_product ON order_items(product_id)')

        # Admin users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admin_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_login TEXT,
                is_active BOOLEAN DEFAULT 1
            )
        ''')

        # Customer preferences table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS customer_preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_name TEXT NOT NULL,
                food TEXT NOT NULL,
                preference TEXT NOT NULL
            )
        ''')

        # Camera settings
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS camera_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cam_name TEXT NOT NULL,
                cam_value TEXT NOT NULL,
                is_active BOOLEAN DEFAULT 0,
                created_at TEXT NOT NULL
            )
        ''')

        # Customer presence table for real-time Waiter Service Terminal
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS customer_presence (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_name TEXT NOT NULL,
                user_type TEXT NOT NULL DEFAULT 'customer',
                face_image TEXT,
                status TEXT NOT NULL DEFAULT 'waiting_order',
                entry_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                order_summary TEXT,
                notes TEXT
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_presence_status ON customer_presence(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_presence_user ON customer_presence(user_name)')

        # System settings table for optional Gemini token and configurations
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS system_settings (
                setting_key TEXT PRIMARY KEY,
                setting_value TEXT
            )
        ''')

        # Robust Migration check for users table
        cursor.execute("PRAGMA table_info(users)")
        user_cols = [row[1] if isinstance(row, tuple) else row["name"] for row in cursor.fetchall()]
        if "user_type" not in user_cols:
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN user_type TEXT DEFAULT 'customer'")
            except sqlite3.OperationalError:
                pass

        # Robust Migration check for products table
        cursor.execute("PRAGMA table_info(products)")
        product_cols = [row[1] if isinstance(row, tuple) else row["name"] for row in cursor.fetchall()]
        if "description" not in product_cols:
            try:
                cursor.execute("ALTER TABLE products ADD COLUMN description TEXT DEFAULT ''")
            except sqlite3.OperationalError:
                pass
        if "image_url" not in product_cols:
            try:
                cursor.execute("ALTER TABLE products ADD COLUMN image_url TEXT DEFAULT ''")
            except sqlite3.OperationalError:
                pass

        # Robust Migration check for orders table
        cursor.execute("PRAGMA table_info(orders)")
        order_cols = [row[1] if isinstance(row, tuple) else row["name"] for row in cursor.fetchall()]
        if "user_name" not in order_cols:
            try:
                cursor.execute("ALTER TABLE orders ADD COLUMN user_name TEXT")
            except sqlite3.OperationalError:
                pass
        if "name" not in order_cols:
            try:
                cursor.execute("ALTER TABLE orders ADD COLUMN name TEXT")
            except sqlite3.OperationalError:
                pass
        if "total_amount" not in order_cols:
            try:
                cursor.execute("ALTER TABLE orders ADD COLUMN total_amount REAL DEFAULT 0")
            except sqlite3.OperationalError:
                pass
        if "foods" not in order_cols:
            try:
                cursor.execute("ALTER TABLE orders ADD COLUMN foods TEXT DEFAULT ''")
            except sqlite3.OperationalError:
                pass

        # Auto-migrate user encodings from users table to user_embeddings table if user_embeddings is empty
        cursor.execute("SELECT COUNT(*) FROM user_embeddings")
        if cursor.fetchone()[0] == 0:
            cursor.execute("SELECT name, user_type, encoding, last_login_date FROM users WHERE encoding IS NOT NULL")
            users_with_enc = cursor.fetchall()
            now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            for u in users_with_enc:
                if u["encoding"] and len(u["encoding"]) > 0:
                    cursor.execute(
                        "INSERT INTO user_embeddings (user_name, user_type, embedding, quality_score, yaw, pitch, created_at) VALUES (?, ?, ?, 1.0, 0.0, 0.0, ?)",
                        (u["name"], u["user_type"] or "customer", u["encoding"], u["last_login_date"] or now_str)
                    )

        conn.commit()

        # Insert default menu products if empty
        cursor.execute("SELECT COUNT(*) FROM products")
        if cursor.fetchone()[0] == 0:
            default_products = [
                ("Espresso", "Kahve", 45.0, "Yoğun ve zengin aromalı İtalyan kahvesi", "/static/images/espresso.jpg"),
                ("Americano", "Kahve", 55.0, "Sıcak su ile inceltilmiş double espresso", "/static/images/americano.jpg"),
                ("Caffe Latte", "Kahve", 65.0, "Espresso ve kremsi buğulanmış taze süt", "/static/images/latte.jpg"),
                ("Cappuccino", "Kahve", 65.0, "Eşit oranda espresso, sıcak süt ve yoğun süt köpüğü", "/static/images/cappuccino.jpg"),
                ("Cold Brew", "Soğuk İçecek", 75.0, "24 saat soğuk demlenmiş özel filtre kahve", "/static/images/coldbrew.jpg"),
                ("Türk Kahvesi", "Kahve", 50.0, "Geleneksel közde pişirilmiş bol köpüklü Türk kahvesi", "/static/images/turkkahvesi.jpg"),
                ("Taze Sıkma Portakal Suyu", "Soğuk İçecek", 60.0, "%100 doğal taze sıkılmış Akdeniz portakalı", "/static/images/portakalsuyu.jpg"),
                ("Tereyağlı Kruvasan", "Tatlı/Fırın", 70.0, "Çıtır çıtır taze Fransız tereyağlı kruvasan", "/static/images/kruvasan.jpg"),
                ("San Sebastian Cheesecake", "Tatlı/Fırın", 110.0, "Akışkan kıvamlı fırınlanmış özel çizkek", "/static/images/cheesecake.jpg"),
                ("Kulüp Sandviç", "Yiyecek", 95.0, "Tavuk füme, kaşar peyniri ve taze yeşillikli sandviç", "/static/images/sandvic.jpg")
            ]
            cursor.executemany(
                "INSERT INTO products (product_name, category, price, description, image_url) VALUES (?, ?, ?, ?, ?)",
                default_products
            )
            conn.commit()

        # Insert default camera settings if empty
        cursor.execute("SELECT COUNT(*) FROM camera_settings")
        if cursor.fetchone()[0] == 0:
            now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            default_cams = [
                ("Dahili Kamera (Webcam 0)", "0", 1, now_str),
                ("USB Kamera 1", "1", 0, now_str),
                ("RTSP IP Kamera (Kafe Girişi)", "rtsp://admin:admin@192.168.1.100:554/stream", 0, now_str)
            ]
            cursor.executemany(
                "INSERT INTO camera_settings (cam_name, cam_value, is_active, created_at) VALUES (?, ?, ?, ?)",
                default_cams
            )
            conn.commit()

        print("[INFO] Database schema, indexes, and multi-embedding tables initialized.")


def add_or_update_presence(user_name, user_type='customer', face_image=None):
    """
    Register or refresh a customer's presence in the venue.
    If already active (waiting_order or ordered), update last_seen_time and optionally face_image.
    If not active, create new presence session in 'waiting_order' status.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, status FROM customer_presence 
        WHERE user_name = ? AND status IN ('waiting_order', 'ordered')
        ORDER BY id DESC LIMIT 1
    """, (user_name,))
    row = cursor.fetchone()
    
    if row:
        pid = row["id"] if isinstance(row, sqlite3.Row) else row[0]
        if face_image:
            cursor.execute("""
                UPDATE customer_presence 
                SET last_seen_time = CURRENT_TIMESTAMP, face_image = ?
                WHERE id = ?
            """, (face_image, pid))
        else:
            cursor.execute("""
                UPDATE customer_presence 
                SET last_seen_time = CURRENT_TIMESTAMP 
                WHERE id = ?
            """, (pid,))
        conn.commit()
        conn.close()
        return pid
    else:
        cursor.execute("""
            INSERT INTO customer_presence (user_name, user_type, face_image, status, entry_time, last_seen_time)
            VALUES (?, ?, ?, 'waiting_order', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """, (user_name, user_type, face_image))
        pid = cursor.lastrowid
        conn.commit()
        conn.close()
        return pid


def get_active_presences():
    """Return all currently active customers in venue (waiting_order and ordered)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, user_name, user_type, face_image, status, entry_time, last_seen_time, order_summary, notes
        FROM customer_presence
        WHERE status IN ('waiting_order', 'ordered')
        ORDER BY 
            CASE status WHEN 'waiting_order' THEN 1 ELSE 2 END,
            entry_time DESC
    """)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def set_presence_status(presence_id, status, order_summary=None, notes=None):
    """Update status of a presence session ('waiting_order', 'ordered', 'exited')."""
    conn = get_db_connection()
    cursor = conn.cursor()
    updates = ["status = ?", "last_seen_time = CURRENT_TIMESTAMP"]
    params = [status]
    if order_summary is not None:
        updates.append("order_summary = ?")
        params.append(order_summary)
    if notes is not None:
        updates.append("notes = ?")
        params.append(notes)
    params.append(presence_id)
    
    cursor.execute(f"UPDATE customer_presence SET {', '.join(updates)} WHERE id = ?", params)
    conn.commit()
    conn.close()


def get_setting(key, default=None):
    """Fetch setting value from system_settings table."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT setting_value FROM system_settings WHERE setting_key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return row["setting_value"] if isinstance(row, sqlite3.Row) else row[0]
    return default


def set_setting(key, value):
    """Insert or update setting in system_settings table."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO system_settings (setting_key, setting_value) 
        VALUES (?, ?)
        ON CONFLICT(setting_key) DO UPDATE SET setting_value = excluded.setting_value
    """, (key, value))
    conn.commit()
    conn.close()


