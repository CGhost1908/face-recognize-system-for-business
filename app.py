from flask import Flask, request, jsonify, send_from_directory, render_template, Response, session, redirect, url_for
from functools import wraps
import cv2
import numpy as np
import sqlite3
import os
from PIL import Image
import base64
import pickle
import requests
from datetime import datetime, timedelta
import threading
import time
import traceback
import hashlib
import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import shutil
import sys

# Import configuration
from config import (
    IS_RASPBERRY_PI, IS_WINDOWS, IS_LINUX,
    DB_PATH, DATASET_DIR, TRAINER_DIR, CASCADE_DIR,
    MODEL_PATH, LABEL_ENCODERS_PATH, SCALER_PATH, TRAINER_MODEL_PATH,
    FACE_CASCADE_PATH, FRAME_WIDTH, FRAME_HEIGHT,
    CAMERA_SLEEP_TIME, MJPEG_SLEEP_TIME, LAZY_LOAD_MODEL,
    FACE_RECOGNITION_MODEL, FACE_DETECTION_SCALE,
    FLASK_HOST, FLASK_PORT, FLASK_DEBUG, FLASK_THREADED
)

# Optional imports for face recognition (might not be available on all systems)
try:
    import face_recognition
    FACE_RECOGNITION_AVAILABLE = True
except ImportError:
    print("[WARNING] face_recognition library not available, using fallback method")
    FACE_RECOGNITION_AVAILABLE = False

# Optional import for TensorFlow (might be slow on Pi)
try:
    from tensorflow.keras.models import load_model
    TENSORFLOW_AVAILABLE = True
except ImportError:
    print("[WARNING] TensorFlow not available")
    TENSORFLOW_AVAILABLE = False
    load_model = None

camera = None
CAMERA_IDX = 0
camera_lock = threading.Lock()

known_face_encodings = []
known_face_names = []

RECOGNITION_ENABLED = True
recognition_lock = threading.Lock()

latest_raw_frame = None       
raw_frame_lock = threading.Lock()

processed_output_frame = None 
processed_frame_lock = threading.Lock()

last_recognized_name = "Yok"
last_recognized_lock = threading.Lock()

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = secrets.token_hex(32)

# Yüz tanıma modeli
face_cascade = cv2.CascadeClassifier(FACE_CASCADE_PATH)
recognizer = cv2.face.LBPHFaceRecognizer_create()
recognizer.read(TRAINER_MODEL_PATH)

# Load model lazily on Raspberry Pi, eagerly on other systems
model = None
label_encoders = None
scaler = None

def load_ml_models():
    """Load ML models - called once at startup or on demand"""
    global model, label_encoders, scaler
    if TENSORFLOW_AVAILABLE and model is None:
        try:
            print("[INFO] Loading TensorFlow model...")
            model = load_model(MODEL_PATH)
            with open(LABEL_ENCODERS_PATH, "rb") as f:
                label_encoders = pickle.load(f)
            with open(SCALER_PATH, "rb") as f:
                scaler = pickle.load(f)
            print("[INFO] ML models loaded successfully")
        except Exception as e:
            print(f"[WARNING] Could not load ML models: {e}")
            model = None
            label_encoders = None
            scaler = None
    else:
        print("[INFO] ML models already loaded or TensorFlow unavailable")

# Load models on startup unless on Raspberry Pi (lazy loading)
if not LAZY_LOAD_MODEL:
    load_ml_models()

# --- VERİTABANI İNİSİYALİZASYONU ---
def init_db():
    with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                image TEXT NOT NULL,
                total_spent REAL DEFAULT 0,
                last_login_date TEXT NOT NULL,
                encoding BLOB NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                foods TEXT NULL,
                order_date TEXT
            )
        ''')
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
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER NOT NULL,
                token TEXT NOT NULL UNIQUE,
                expires_at TEXT NOT NULL,
                used BOOLEAN DEFAULT 0,
                FOREIGN KEY (admin_id) REFERENCES admin_users(id)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_name NOT NULL UNIQUE,
                category TEXT NOT NULL,
                price INTEGER NOT NULL
            )
        ''')
        conn.commit()
    print("[INFO] Veritabanı hazır.")

def get_db():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn

# --- AUTHENTICATION HELPERS ---
def hash_password(password):
    """Hash password with salt"""
    salt = secrets.token_hex(32)
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
    return salt + pwd_hash.hex()

def verify_password(stored_hash, password):
    """Verify password against hash"""
    try:
        salt = stored_hash[:64]
        stored_pwd = stored_hash[64:]
        pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
        return pwd_hash.hex() == stored_pwd
    except:
        return False

def login_required(f):
    """Decorator to require admin login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            return redirect(url_for('admin', unauthorized=True))
        return f(*args, **kwargs)
    return decorated_function

def get_admin_user(admin_id):
    """Get admin user by ID"""
    try:
        db = get_db()
        admin = db.execute("SELECT * FROM admin_users WHERE id=?", (admin_id,)).fetchone()
        db.close()
        return dict(admin) if admin else None
    except:
        return None

def create_reset_token(admin_id):
    """Create password reset token"""
    token = secrets.token_urlsafe(32)
    expires_at = (datetime.now() + timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
    
    db = get_db()
    db.execute(
        "INSERT INTO password_reset_tokens (admin_id, token, expires_at) VALUES (?, ?, ?)",
        (admin_id, token, expires_at)
    )
    db.commit()
    db.close()
    
    return token

def verify_reset_token(token):
    """Verify password reset token"""
    db = get_db()
    row = db.execute(
        "SELECT * FROM password_reset_tokens WHERE token=? AND used=0 AND expires_at > datetime('now')",
        (token,)
    ).fetchone()
    db.close()
    
    return dict(row) if row else None

def train_model():
    print("[EĞİTİM] Veritabanı bağlanıyor...")
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False) 
        cursor = conn.cursor()
        
        for person_name in os.listdir(DATASET_DIR):
            row = cursor.execute("SELECT id FROM users WHERE name=?", (person_name,)).fetchone()

            if row is not None:
                print(f"'{person_name}' veritabanında zaten var, eklenmiyor.")
                continue

            person_dir = os.path.join(DATASET_DIR, person_name)
            if not os.path.isdir(person_dir):
                continue
            
            print(f"--- '{person_name}' için işlem başlıyor... ---")
            person_encodings = []

            profile_image_path = os.path.join(person_dir, os.listdir(person_dir)[1])
            profile_image_base64 = None
            if os.path.isfile(profile_image_path):
                with open(profile_image_path, "rb") as img_file:
                    profile_image_base64 = base64.b64encode(img_file.read()).decode('utf-8')

            for image_name in os.listdir(person_dir):
                image_path = os.path.join(person_dir, image_name)
                print(f"  > Fotoğraf okunuyor: {image_name}")
                
                image = cv2.imread(image_path)
                if image is None:
                    print(f"  [UYARI] {image_name} okunamadı, atlanıyor.")
                    continue
                
                rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

                rgb_image_contiguous = np.ascontiguousarray(rgb_image)
                rgb_image_final = rgb_image_contiguous.astype(np.uint8)
                
                if FACE_RECOGNITION_AVAILABLE:
                    face_locations = face_recognition.face_locations(rgb_image_final, model=FACE_RECOGNITION_MODEL)

                    if len(face_locations) == 1:
                        encoding = face_recognition.face_encodings(rgb_image_final, face_locations)[0]
                        person_encodings.append(encoding)
                        print(f"  > Yüz bulundu ve kodlandı.")
                    else:
                        print(f"  [UYARI] {image_name} içinde yüz bulunamadı veya birden fazla yüz var, atlanıyor.")
                else:
                    print(f"  [UYARI] face_recognition kütüphanesi yüklü değil")

            if len(person_encodings) > 0:
                avg_encoding = np.mean(person_encodings, axis=0)
                cursor.execute("INSERT INTO users (name, encoding, last_login_date, image) VALUES (?, ?, ?, ?)", (person_name, avg_encoding.tobytes(), datetime.now().strftime('%Y-%m-%d %H:%M:%S'), profile_image_base64))
                print(f"--- '{person_name}' için ortalama veritabanına eklendi. ---")

        conn.commit()
        conn.close()
        
        print("\n[EĞİTİM] Model eğitimi tamamlandı! Hafızadaki yüzler güncelleniyor...")
        load_known_faces()
        
    except Exception as e:
        print(f"[HATA] Eğitim sırasında bir hata oluştu: {e}")
        traceback.print_exc()

@app.route('/api/login', methods=['POST'])
def login():
    """API endpoint for admin login"""
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')
    remember_me = data.get('remember_me', False)

    # Validate input
    if not username or not password:
        return jsonify({
            'success': False,
            'message': 'Kullanıcı adı ve şifre gereklidir'
        }), 400

    # Check credentials
    db = get_db()
    admin = db.execute(
        "SELECT * FROM admin_users WHERE username=? AND is_active=1",
        (username,)
    ).fetchone()
    db.close()

    if not admin or not verify_password(admin['password_hash'], password):
        return jsonify({
            'success': False,
            'message': 'Kullanıcı adı veya şifre yanlış'
        }), 401

    # Update last login
    db = get_db()
    db.execute(
        "UPDATE admin_users SET last_login=? WHERE id=?",
        (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), admin['id'])
    )
    db.commit()
    db.close()

    # Create session
    session['admin_id'] = admin['id']
    session['username'] = admin['username']
    session['email'] = admin['email']
    
    if remember_me:
        session.permanent = True
        app.permanent_session_lifetime = timedelta(days=30)

    return jsonify({
        'success': True,
        'message': 'Giriş başarılı',
        'token': secrets.token_urlsafe(32),
        'admin': {
            'id': admin['id'],
            'username': admin['username'],
            'email': admin['email']
        }
    }), 200

@app.route('/api/logout', methods=['POST'])
def logout():
    """Logout API"""
    session.clear()
    return jsonify({'success': True, 'message': 'Çıkış yapıldı'}), 200

@app.route('/api/forgot-password', methods=['POST'])
def forgot_password():
    """Request password reset"""
    data = request.get_json()
    email = data.get('email', '').strip()

    if not email:
        return jsonify({
            'success': False,
            'message': 'E-posta adresi gereklidir'
        }), 400

    # Find admin by email
    db = get_db()
    admin = db.execute(
        "SELECT * FROM admin_users WHERE email=?",
        (email,)
    ).fetchone()
    db.close()

    if not admin:
        # Don't reveal if email exists (security)
        return jsonify({
            'success': True,
            'message': 'Eğer bu e-posta kayıtlıysa, şifre sıfırla bağlantısı gönderilecektir'
        }), 200

    # Create reset token
    token = create_reset_token(admin['id'])
    
    # TODO: Send email with reset link
    # reset_link = f"http://yourdomain.com/reset-password?token={token}"
    # send_reset_email(admin['email'], reset_link)

    return jsonify({
        'success': True,
        'message': 'Eğer bu e-posta kayıtlıysa, şifre sıfırla bağlantısı gönderilecektir'
    }), 200

@app.route('/api/user/profile', methods=['GET'])
@login_required
def get_profile():
    admin_id = session.get('admin_id')
    admin = get_admin_user(admin_id)
    
    if not admin:
        return jsonify({'error': 'Kullanıcı bulunamadı'}), 404

    return jsonify({
        'id': admin['id'],
        'username': admin['username'],
        'email': admin['email'],
        'created_at': admin['created_at'],
        'last_login': admin['last_login']
    }), 200


@app.route("/api/cam_changed", methods=["POST"])
def cam_changed():
    global CAMERA_IDX
    
    data = request.get_json()
    if not data or 'cam_number' not in data:
        return jsonify({"error": "Eksik veri"}), 400
    try:
        if int(data['cam_number']) in range(0, 6):
            new_cam_index = int(data['cam_number'])
    except ValueError:
        new_cam_index = data['cam_number']

    if new_cam_index == CAMERA_IDX:
         return jsonify({"message": f"Kamera zaten {new_cam_index} olarak ayarlı"})

    CAMERA_IDX = new_cam_index
    
    start_camera() 
    
    return jsonify({"message": f"Kamera {CAMERA_IDX} olarak ayarlandı"})

# --- KAMERA BAŞLATMA ---
def start_camera():
    global camera, CAMERA_IDX
    with camera_lock: 
        if camera is not None:
            camera.release()
            print(f"[INFO] Önceki kamera ({CAMERA_IDX}) kapatıldı.")
            
        print(f"[INFO] Yeni kamera {CAMERA_IDX} başlatılıyor...")
        camera = cv2.VideoCapture(CAMERA_IDX)
        camera.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
        
        if not camera.isOpened():
            print(f"[HATA] Kamera açılamadı (INDEX={CAMERA_IDX})")
            camera = None
        else:
            print(f"[INFO] Kamera {CAMERA_IDX} başarıyla başlatıldı.")

API_KEY = 'a010c2f6d9268b3039ce95c457da11d6'
@app.route('/api/weather', methods=['POST'])
def get_weather():
    data = request.get_json()
    lat = data.get('lat')
    lon = data.get('lon')

    if lat is None or lon is None:
        return jsonify({'error': 'Konum bilgisi eksik'}), 400

    url = f'https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={API_KEY}&units=metric&lang=tr'

    response = requests.get(url)
    if response.status_code != 200:
        return jsonify({'error': 'API isteği başarısız'}), 500

    return jsonify(response.json())


@app.route("/static/images/<path:filename>")
def serve_image(filename):
    return send_from_directory("static/images", filename)

# NEW CAMERA SYSTEM
def load_known_faces():
    global known_face_encodings, known_face_names
    
    known_face_encodings = []
    known_face_names = []
    
    try:
        with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name, encoding FROM users")
            rows = cursor.fetchall()

            for row in rows:
                name = row[0]
                encoding = np.frombuffer(row[1], dtype=np.float64)
                known_face_encodings.append(encoding)
                known_face_names.append(name)
                
            print(f"[INFO] {len(known_face_names)} adet bilinen yüz veritabanından yüklendi.")
    except Exception as e:
        print(f"[HATA] Veritabanından yüzler yüklenemedi: {e}")

def read_camera_loop():
    global latest_raw_frame, camera
    while True:
        frame_to_save = None 
        
        with camera_lock:
            if camera is not None and camera.isOpened():
                ret, frame = camera.read()
                if ret:
                    frame_to_save = frame.copy()
                else:
                    print("[WARNING] Kameradan frame alınamadı (read_camera_loop).")
        
        if frame_to_save is not None:
            with raw_frame_lock:
                latest_raw_frame = frame_to_save
            time.sleep(CAMERA_SLEEP_TIME)
        else:
            time.sleep(CAMERA_SLEEP_TIME * 5)

# --- VİDEO AKIŞI OLUŞTURUCULAR (GENERATORS) ---
def generate_mjpeg_processed():
    global processed_output_frame
    while True:
        with processed_frame_lock:
            if processed_output_frame is None:
                time.sleep(0.1)
                continue
            ret, buf = cv2.imencode('.jpg', processed_output_frame)
            if not ret:
                continue
            frame = buf.tobytes()
        
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        time.sleep(MJPEG_SLEEP_TIME)

def generate_mjpeg_raw():
    global latest_raw_frame
    while True:
        with raw_frame_lock:
            if latest_raw_frame is None:
                time.sleep(0.1)
                continue
            ret, buf = cv2.imencode('.jpg', latest_raw_frame)
            if not ret:
                continue
            frame = buf.tobytes()
        
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        time.sleep(MJPEG_SLEEP_TIME)


@app.route('/save-person', methods=['POST'])
def save_person():
    global camera
    data = request.get_json()
    name = data.get('name')

    if not name or not name.strip():
        return jsonify({'status': 'error', 'message': 'İsim alanı boş bırakılamaz.'})

    person_dir = os.path.join(DATASET_DIR, name.strip())
    if not os.path.exists(person_dir):
        os.makedirs(person_dir)
    else:
        return jsonify({'status': 'error', 'message': f"'{name}' zaten kayıtlı. Farklı bir isim deneyin."})
    
    print(f"[INFO] '{name}' için fotoğraf çekimi başlıyor... 5 fotoğraf çekilecek.")
    saved_photo_count = 0

    for i in range(5):
        print(f"[INFO] Fotoğraf {i+1}/5 çekiliyor...")
        
        frame_to_save = None
        with raw_frame_lock:
             if latest_raw_frame is not None:
                frame_to_save = latest_raw_frame.copy()

        if frame_to_save is None:
            print("[ERROR] Kayıt sırasında kameradan görüntü alınamadı.")
            continue
        
        file_path = os.path.join(person_dir, f"{i+1}.jpg")
        try:
            cv2.imwrite(file_path, frame_to_save)
            print(f"[INFO] Fotoğraf kaydedildi: {file_path}")
            saved_photo_count += 1
        except Exception as e:
            print(f"[ERROR] Fotoğraf kaydedilirken hata oluştu: {e}")
            
        time.sleep(1)

    if saved_photo_count == 0:
        return jsonify({'status': 'error', 'message': '5 denemede de fotoğraf kaydedilemedi.'})

    print("[INFO] Fotoğraf kaydı bitti, eğitim tetikleniyor...")
    train_model() 
    
    return jsonify({
        'status': 'success', 
        'message': f'"{name}" için {saved_photo_count}/5 fotoğraf kaydedildi ve model eğitildi!'
    })


@app.route("/api/get_users", methods=["POST"])
def get_users():
    db = get_db()
    rows = db.execute("""
        SELECT id, name, last_login_date, image, total_spent
        FROM users
    """).fetchall()
    db.close()

    users = []
    for row in rows:
        users.append({
            "id": row["id"],
            "name": row["name"],
            "image": row["image"],
            "last_login_date": row["last_login_date"],
            "total_spent": row["total_spent"]
        })

    return jsonify({"customers": users})


@app.route("/api/get_orders", methods=["POST"])
def get_all_orders():
    db = get_db()
    rows = db.execute("""
        SELECT id, name, foods, order_date
        FROM orders
        ORDER BY order_date DESC
    """).fetchall()
    db.close()

    orders = []
    for row in rows:
        orders.append({
            "id": row["id"],
            "name": row["name"],
            "foods": row["foods"],
            "order_date": row["order_date"]
        })

    return orders


@app.route("/api/get_last_customers", methods=["POST"])
def get_last_customers():
    data = request.get_json()
    count = data.get('count', 5)

    db = get_db()
    rows = db.execute("""
        SELECT id, name, last_login_date, image
        FROM users
        ORDER BY last_login_date DESC
        LIMIT ?
    """, (count,)).fetchall()
    db.close()

    customers = []
    for row in rows:
        customers.append({
            "id": row["id"],
            "name": row["name"],
            "image": row["image"],
            "total_spent": row["total_spent"],
            "last_login_date": row["last_login_date"]
        })

    return jsonify({"customers": customers})

@app.route("/api/recognize", methods=["POST"])
def recognize_once():
    global latest_raw_frame, last_recognized_name

    if not FACE_RECOGNITION_AVAILABLE:
        return jsonify({"error": "Yüz tanıma hizmeti kullanılamıyor"}), 503

    with raw_frame_lock:
        if latest_raw_frame is None:
            print("Kamera görüntüsü yok!")
            return jsonify({"error": "Kamera görüntüsü yok"}), 503
        
        frame_to_process = latest_raw_frame.copy()

    small_frame = cv2.resize(frame_to_process, (0, 0), fx=0.25, fy=0.25)
    rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

    face_locations = face_recognition.face_locations(rgb_small_frame)
    face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)

    if len(face_encodings) == 0:
        print("Yüz bulunamadı.")
        return jsonify({"error": "Yüz bulunamadı"}), 404


    face_encoding = face_encodings[0]
    matches = face_recognition.compare_faces(known_face_encodings, face_encoding)
    face_distances = face_recognition.face_distance(known_face_encodings, face_encoding)

    name = "Bilinmiyor"
    if len(face_distances) > 0:
        best_match_index = np.argmin(face_distances)
        if matches[best_match_index]:
            name = known_face_names[best_match_index]
            recognized = True

    with last_recognized_lock:
        last_recognized_name = name

    if name == "Bilinmiyor":
        print("Yüz tanınamadı.")
        return jsonify({"error": "Yüz tanınamadı"}), 404
    else:
        print(f"Tanınan kişi: {name}")
        db = get_db()
        cursor = db.cursor()
        cursor.execute("UPDATE users SET last_login_date=? WHERE name=?", (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), name))
        db.commit()
        result = db.execute("SELECT * FROM users WHERE name=?", (name,)).fetchone()
        db.close()
        
    try: 
        if result:
            id = result["id"]
            encoded_img = result["image"],
            total_spent = result["total_spent"],
            last_login_date = result["last_login_date"],
            encoding = result["encoding"]
            return jsonify({"id": id, "name": name, "image": encoded_img, "total_spent": total_spent, "last_login_date": last_login_date})
        else:
            print("Kişi bilgileri bulunamadı.")
    except:
        print("Yüz tanınamadı.")
        return jsonify({"error": "Yüz tanınamadı"}), 404
    


# --- USER islemleri ---

@app.route("/api/customer/<string:customer_name>", methods=["GET"])
def get_customer_data(customer_name):
    db = get_db()
    customer = db.execute("SELECT name, total_spent FROM users WHERE name=?", (customer_name,)).fetchone()
    db.close()

    if customer:
        return jsonify(dict(customer))
    return jsonify({"error": "Müşteri bulunamadı"}), 404

@app.route("/api/customer/<string:customer_name>/total_spent", methods=["GET"])
def get_total_spent(customer_name):
    db = get_db()
    row = db.execute("SELECT total_spent FROM users WHERE name=?", (customer_name,)).fetchone()
    db.close()

    if row is None:
        return jsonify({"error": "Müşteri bulunamadı"}), 404
    return jsonify({"total_spent": row["total_spent"]})

@app.route("/api/order_food/<string:customer_name>", methods=["POST"])
def order_food(customer_name):
    data = request.get_json()
    foods = ", ".join(data['foods'])
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute("INSERT INTO orders (name, foods, order_date) VALUES (?, ?, ?)", (customer_name, foods, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    
    cursor.execute("UPDATE users SET total_spent = total_spent + ? WHERE name = ?", (data['total'], customer_name))
    
    db.commit()
    db.close()
    
    return jsonify({"message": "Sipariş başarıyla alındı"}), 201


@app.route("/api/get_food_percentage/<string:customer_name>", methods=["GET"])
def get_food_percentage(customer_name):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("SELECT foods FROM orders WHERE name = ?", (customer_name,))
    rows = cursor.fetchall()
    conn.close()

    food_count = {}
    total_count = 0

    for row in rows:
        foods_str = row[0]
        foods = [f.strip() for f in foods_str.split(",")]
        for food in foods:
            food_count[food] = food_count.get(food, 0) + 1
            total_count += 1

    top_5 = sorted(food_count.items(), key=lambda x: x[1], reverse=True)[:5]

    food_percentages = {}
    if total_count > 0:
        for food, count in top_5:
            food_percentages[food] = round((count / total_count) * 100, 2)

    return food_percentages


@app.route("/api/suggest_food", methods=["POST"])
def suggest_food():
    data = request.get_json()
    print(data)
    
    if not TENSORFLOW_AVAILABLE or model is None:
        return jsonify({"error": "Yemek önerisi servisi kullanılamıyor"}), 503
    
    try:
        drink_encoded = label_encoders['drink_item'].transform([data['drink']])[0]
        weather_encoded = label_encoders['weather'].transform([data['weather']])[0]
        time_encoded = label_encoders['time_of_day'].transform([data['meal']])[0]
        input_data = np.array([[1, drink_encoded, weather_encoded, data['temperature'], time_encoded]])
        input_data = scaler.transform(input_data)
        prediction = model.predict(input_data)
        recommended_index = np.argmax(prediction)
        recommended_food = label_encoders['food_item'].inverse_transform([recommended_index])[0]
        return jsonify({"suggestion": recommended_food})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/preferences/<string:customer_name>", methods=["POST"])
def add_preference(customer_name):
    data = request.get_json()
    food = data.get("food")
    preference_text = data.get("preference")

    if not food or not preference_text:
        return jsonify({"error": "Yemek ve açıklama gerekli"}), 400

    # Eğer preferences tablosu yoksa oluştur
    with sqlite3.connect("database.db") as conn:
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS preferences (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            food TEXT,
                            preference_text TEXT,
                            FOREIGN KEY (id) REFERENCES users(id))''')
        cursor.execute("INSERT INTO preferences (name, food, preference_text) VALUES (?, ?, ?)", 
                       (customer_name, food, preference_text))
        conn.commit()

    return jsonify({"message": "Tercih kaydedildi"})

@app.route("/api/customer/<string:customer_name>/preferences", methods=["GET"])
def get_preferences(customer_name):
    conn = get_db()
    rows = conn.execute("SELECT food, preference_text FROM preferences WHERE name = ?", 
                        (customer_name,)).fetchall()
    conn.close()

    if not rows:
        return jsonify({"error": "Veri yok"}), 404

    preferences = [f"{row['food']}: {row['preference_text']}" for row in rows]
    return jsonify({"message": preferences})


@app.route("/api/customer/<string:customer_name>/get_orders", methods=["GET"])
def get_orders(customer_name):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT foods FROM orders WHERE name = ? ORDER BY name", (customer_name,))
    orders = [row[0] for row in cursor.fetchall()]           
    conn.close()
    return orders


@app.route('/api/customer/<string:customer_name>/last_login', methods=['GET'])
def get_last_login(customer_name):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("SELECT last_login_date FROM users WHERE name=?", (customer_name,))
    result = cursor.fetchone()

    conn.close()

    if result and result[0]:
        last_login = result[0]
    else:
        last_login = None

    return jsonify({
        'name': customer_name,
        'last_login': last_login
    })
# --- ---

@app.route('/')
def index():
    global RECOGNITION_ENABLED
    with recognition_lock:
        RECOGNITION_ENABLED = True
    return render_template('index.html')

@app.route('/admin', methods=['GET'])
def admin():
    if 'admin_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('admin.html')

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard_home.html', current_page='home')

@app.route('/dashboard/customers')
@login_required
def customers():
    return render_template('dashboard_customers.html', current_page='customers')

@app.route('/dashboard/register')
@login_required
def register():
    return render_template('dashboard_register.html', current_page='register')

@app.route('/dashboard/camera')
@login_required
def camera_page():
    return render_template('dashboard_camera.html', current_page='camera')

@app.route('/dashboard/reports')
@login_required
def reports_page():
    return render_template('dashboard_reports.html', current_page='reports')

@app.route('/dashboard/products')
@login_required
def products_page():
    return render_template('dashboard_products.html', current_page='products')

@app.route('/dashboard/settings')
@login_required
def settings_page():
    return render_template('dashboard_settings.html', current_page='settings')

@app.route('/api/get_products', methods=['GET'])
def get_products():
    try:
        db = get_db()
        rows = db.execute("""
            SELECT id, product_name, category, price
            FROM products
            ORDER BY product_name
        """).fetchall()
        db.close()

        products = []
        for row in rows:
            products.append({
                'id': row['id'],
                'name': row['product_name'],
                'category': row['category'],
                'price': row['price']
            })

        return jsonify({'products': products}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/add_product', methods=['POST'])
@login_required
def add_product():
    try:
        data = request.get_json()
        product_name = data.get('product_name', '').strip()
        category = data.get('category', '').strip() or None
        price = data.get('price')

        if not product_name:
            return jsonify({'error': 'Ürün adı gereklidir'}), 400

        if price is None:
            return jsonify({'error': 'Fiyat gereklidir'}), 400

        try:
            price = float(price)
            if price < 0:
                return jsonify({'error': 'Fiyat negatif olamaz'}), 400
        except (ValueError, TypeError):
            return jsonify({'error': 'Geçersiz fiyat'}), 400

        db = get_db()
        cursor = db.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO products (product_name, category, price)
                VALUES (?, ?, ?)
            """, (product_name, category, price))
            db.commit()
            product_id = cursor.lastrowid
            db.close()

            return jsonify({
                'status': 'success',
                'message': f'"{product_name}" başarıyla eklendi',
                'product': {
                    'id': product_id,
                    'name': product_name,
                    'category': category,
                    'price': price
                }
            }), 201
        except sqlite3.IntegrityError:
            db.close()
            return jsonify({'error': f'"{product_name}" zaten kayıtlı'}), 400

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/product/<int:product_id>', methods=['PUT'])
@login_required
def edit_product(product_id):
    try:
        data = request.get_json()
        product_name = data.get('product_name', '').strip()
        category = data.get('category', '').strip() or None
        price = data.get('price')

        if not product_name:
            return jsonify({'error': 'Ürün adı gereklidir'}), 400

        if price is None:
            return jsonify({'error': 'Fiyat gereklidir'}), 400

        try:
            price = float(price)
            if price < 0:
                return jsonify({'error': 'Fiyat negatif olamaz'}), 400
        except (ValueError, TypeError):
            return jsonify({'error': 'Geçersiz fiyat'}), 400

        db = get_db()
        
        product = db.execute(
            "SELECT product_name FROM products WHERE id=?",
            (product_id,)
        ).fetchone()
        
        if not product:
            db.close()
            return jsonify({'error': 'Ürün bulunamadı'}), 404
        
        try:
            db.execute("""
                UPDATE products 
                SET product_name=?, category=?, price=?
                WHERE id=?
            """, (product_name, category, price, product_id))
            db.commit()
            db.close()

            return jsonify({
                'status': 'success',
                'message': f'"{product_name}" başarıyla güncellendi',
                'product': {
                    'id': product_id,
                    'name': product_name,
                    'category': category,
                    'price': price
                }
            }), 200
        except sqlite3.IntegrityError:
            db.close()
            return jsonify({'error': f'"{product_name}" zaten kayıtlı'}), 400

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/user/<int:user_id>', methods=['DELETE'])
@login_required
def delete_user(user_id):
    try:
        db = get_db()

        user = db.execute(
            "SELECT name FROM users WHERE id=?",
            (user_id,)
        ).fetchone()
        
        if not user:
            db.close()
            return jsonify({'error': 'Müşteri bulunamadı'}), 404
        
        user_name = user["name"]
        
        db.execute("DELETE FROM orders WHERE name=?", (user_name,))
        
        try:
            db.execute("DELETE FROM preferences WHERE name=?", (user_name,))
        except:
            pass
        
        db.execute("DELETE FROM users WHERE id=?", (user_id,))
        db.commit()
        db.close()

        # delete dataset folder
        person_dir = os.path.join(DATASET_DIR, user_name)
        if os.path.exists(person_dir):
            shutil.rmtree(person_dir)
        
        return jsonify({
            'status': 'success',
            'message': f'"{user_name}" başarıyla silindi'
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/product/<int:product_id>', methods=['DELETE'])
@login_required
def delete_product(product_id):
    try:
        db = get_db()

        product = db.execute(
            "SELECT product_name FROM products WHERE id=?",
            (product_id,)
        ).fetchone()
        
        if not product:
            db.close()
            return jsonify({'error': 'Ürün bulunamadı'}), 404
        
        db.execute("DELETE FROM products WHERE id=?", (product_id,))
        db.commit()
        db.close()
        
        return jsonify({
            'status': 'success',
            'message': f'"{product["product_name"]}" başarıyla silindi'
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500    

@app.route('/video_feed')
def video_feed():
    return Response(generate_mjpeg_raw(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == "__main__":
    print(f"\n{'='*60}")
    print(f"[STARTUP] Yüz Tanıma Sistemi Başlatılıyor")
    print(f"[STARTUP] Platform: {'Raspberry Pi' if IS_RASPBERRY_PI else 'Windows' if IS_WINDOWS else 'Linux'}")
    print(f"{'='*60}\n")
    
    init_db()
    train_model()
    load_known_faces()
    
    # Load ML models now if lazy loading is enabled and not already loaded
    if LAZY_LOAD_MODEL:
        load_ml_models()

    start_camera()

    t_camera = threading.Thread(target=read_camera_loop, daemon=True)
    t_camera.start()

    print(f"\n[STARTUP] Sunucu başlatılıyor: {FLASK_HOST}:{FLASK_PORT}")
    print(f"[STARTUP] Web arayüzüne şuradan erişin: http://localhost:{FLASK_PORT}")
    
    app.run(host=FLASK_HOST, port=FLASK_PORT, threaded=FLASK_THREADED, debug=FLASK_DEBUG)
