import os
# Optimize thread pools for Raspberry Pi 5 ARM64 and low-power CPU architectures
os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "2")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "2")

import io
import time
import base64
import threading
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, Response, redirect, url_for, session, send_from_directory
import requests
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from PIL import Image
import numpy as np

from database import (
    init_db,
    get_db_connection,
    get_active_presences,
    set_presence_status,
    add_or_update_presence,
    get_setting,
    set_setting
)
from uniface_engine import UniFaceEngine
from camera_stream import CameraStream
from recognition_service import RecognitionService
from recommendation_service import RecommendationService
from mediamtx_service import MediaMTXService

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "uniface_cafe_secret_key_2026")
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

UPLOAD_PRODUCTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "images", "products")
os.makedirs(UPLOAD_PRODUCTS_DIR, exist_ok=True)
ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}

# Initialize database
init_db()

def get_active_camera_source_from_db():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT cam_value FROM camera_settings WHERE is_active = 1 ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        if row and row['cam_value']:
            val = str(row['cam_value']).strip()
            if val.isdigit():
                return int(val)
            return val
    except Exception as e:
        print(f"[WARN] Error reading active camera from DB: {e}")
    return 0


def persist_active_camera_to_db(cam_source, cam_name=None):
    try:
        src_str = str(cam_source).strip()
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE camera_settings SET is_active = 0")
        cursor.execute("SELECT id FROM camera_settings WHERE cam_value = ?", (src_str,))
        existing = cursor.fetchone()
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if existing:
            cursor.execute("UPDATE camera_settings SET is_active = 1 WHERE id = ?", (existing['id'],))
        else:
            name = cam_name or (f"Kamera {src_str}" if src_str.isdigit() else "RTSP Kamera")
            cursor.execute("INSERT INTO camera_settings (cam_name, cam_value, is_active, created_at) VALUES (?, ?, 1, ?)", (name, src_str, now_str))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[WARN] Error persisting active camera to DB: {e}")


# Initialize core services
uniface_engine = UniFaceEngine()
initial_camera_source = get_active_camera_source_from_db()
camera = CameraStream(camera_source=initial_camera_source, width=1920, height=1080)
camera.start()

recognition_service = RecognitionService(uniface_engine=uniface_engine)
recommendation_service = RecommendationService()

# MediaMTX WebRTC & RTSP Streaming Server
mediamtx_service = MediaMTXService(fps=25)
try:
    mediamtx_service.start()
except Exception as e:
    print(f"[WARN] MediaMTXService could not start: {e}")

import atexit
atexit.register(mediamtx_service.stop)
atexit.register(camera.stop)

# Global state for recognition worker & video stream decoupling
shared_recognition_state = {
    "annotated_frame": None,
    "jpeg_bytes": None,
    "recognized_people": [],
    "last_update": 0
}
recognition_state_lock = threading.Lock()
is_recognition_active = True


def background_recognition_worker():
    """
    Dedicated AI Recognition Worker (Raspberry Pi 5 Optimized):
    Runs decoupled UniFace detection, spatial tracking, and multi-angle prototype matching.
    Uses dynamic adaptive rate:
    - ~8 FPS when faces/activity are detected
    - ~4 FPS heartbeat when scene is empty
    - 0 FPS / full sleep when recognition is disabled via admin panel
    """
    global shared_recognition_state
    prev_thumb = None
    last_static_heartbeat = 0.0

    while True:
        if not is_recognition_active:
            time.sleep(0.25)
            continue

        frame_pil = camera.get_latest_frame()
        if frame_pil is None:
            time.sleep(0.1)
            continue

        now = time.time()
        has_active_tracks = bool(getattr(recognition_service, 'active_tracks', []))

        # Edge Optimization: If no active faces are in the frame, check motion FIRST
        # Tiny 80x60 grayscale diff takes 0.01ms on Raspberry Pi 5!
        if not has_active_tracks:
            thumb = np.asarray(frame_pil.resize((80, 60), Image.Resampling.NEAREST).convert('L'))
            motion_score = 99.0
            if prev_thumb is not None:
                motion_score = float(np.mean(np.abs(thumb.astype(np.int16) - prev_thumb.astype(np.int16))))
            prev_thumb = thumb

            # If room is completely static (< 3.5 diff) and checked recently (< 4.5s):
            # Rest the CPU completely! Do NOT run any deep neural networks or JPEG encoding!
            if motion_score < 3.5 and (now - last_static_heartbeat < 4.5):
                time.sleep(0.35)
                continue
            last_static_heartbeat = now

        sleep_duration = 0.18
        try:
            annotated_img, recognized_list = recognition_service.process_frame(frame_pil)
            jpeg_bytes = UniFaceEngine.image_to_jpeg(annotated_img, quality=75)
            with recognition_state_lock:
                shared_recognition_state["annotated_frame"] = annotated_img
                shared_recognition_state["jpeg_bytes"] = jpeg_bytes
                shared_recognition_state["recognized_people"] = recognized_list
                shared_recognition_state["last_update"] = time.time()

            # Push annotated frame to MediaMTX WebRTC stream
            if mediamtx_service and mediamtx_service.is_active():
                try:
                    import cv2
                    bgr_np = cv2.cvtColor(np.array(annotated_img), cv2.COLOR_RGB2BGR)
                    mediamtx_service.push_frame(bgr_np)
                except Exception:
                    pass

            is_cuda = False
            try:
                providers = getattr(recognition_service.engine, 'providers', [])
                is_cuda = "CUDAExecutionProvider" in providers
            except Exception:
                pass

            has_activity = (
                bool(recognized_list) or
                bool(getattr(recognition_service, 'active_tracks', [])) or
                bool(getattr(recognition_service, 'candidate_tracks', []))
            )
            if is_cuda:
                sleep_duration = 0.025 if has_activity else 0.15
            else:
                sleep_duration = 0.08 if has_activity else 0.35
        except Exception as e:
            print(f"[ERROR] Recognition worker exception: {e}")
            sleep_duration = 0.35

        time.sleep(sleep_duration)


# Start background recognition thread
rec_thread = threading.Thread(target=background_recognition_worker, daemon=True)
rec_thread.start()


# Helper: Admin auth decorator
def login_required(f):
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function


# --- WEB ROUTES ---

@app.route('/')
def index():
    return render_template('index.html')



import hashlib

def verify_password(stored_hash, password):
    if not stored_hash or not password:
        return False
    try:
        if check_password_hash(stored_hash, password):
            return True
    except Exception:
        pass
    try:
        if len(stored_hash) >= 64:
            salt = stored_hash[:64]
            expected_hash = stored_hash[64:]
            pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
            if pwd_hash.hex() == expected_hash:
                return True
    except Exception:
        pass
    return False


@app.route('/login', methods=['GET', 'POST'])
@app.route('/admin', methods=['GET', 'POST'])
@app.route('/api/login', methods=['POST'])
def login():

    # Ensure default admin exists
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM admin_users")
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "INSERT INTO admin_users (username, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
            ("admin", "admin@cafe.com", generate_password_hash("admin123"), datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        )
        conn.commit()

    is_json = request.is_json or request.path.startswith('/api/')

    if request.method == 'POST':
        if is_json:
            data = request.json or {}
            username = data.get('username', '').strip()
            password = data.get('password', '')
        else:
            username = (request.form.get('username') or '').strip()
            password = request.form.get('password') or ''

        cursor.execute("SELECT * FROM admin_users WHERE username = ? AND is_active = 1", (username,))
        admin = cursor.fetchone()
        conn.close()

        if admin and verify_password(admin['password_hash'], password):
            session['admin_id'] = admin['id']
            session['admin_username'] = admin['username']
            if is_json:
                return jsonify({"success": True, "message": "Giriş başarılı!"})
            return redirect(url_for('dashboard'))
        else:
            if is_json:
                return jsonify({"success": False, "message": "Geçersiz kullanıcı adı veya şifre."}), 400
            return render_template('admin.html', error="Geçersiz kullanıcı adı veya şifre.")

    conn.close()
    return render_template('admin.html')



@app.route('/api/forgot-password', methods=['POST'])
def forgot_password():
    return jsonify({"success": True, "message": "Şifre sıfırlama bağlantısı gönderildi."})


@app.route('/logout')
@app.route('/api/logout', methods=['GET', 'POST'])
def logout():
    session.clear()
    if request.path.startswith('/api/'):
        return jsonify({"success": True})
    return redirect(url_for('login'))



@app.route('/api/user/profile')
@app.route('/api/profile')
@login_required
def get_user_profile():
    admin_id = session.get('admin_id')
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, email, created_at, last_login FROM admin_users WHERE id = ?", (admin_id,))
    admin = cursor.fetchone()
    conn.close()

    if admin:
        return jsonify({
            "success": True,
            "username": admin["username"],
            "email": admin["email"],
            "created_at": admin["created_at"],
            "last_login": admin["last_login"]
        })
    return jsonify({
        "success": True,
        "username": session.get('admin_username', 'Admin'),
        "email": "admin@cafe.com",
        "created_at": "",
        "last_login": ""
    })


@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', username=session.get('admin_username', 'Admin'))



@app.route('/dashboard/home')
@app.route('/home', endpoint='home')
@login_required
def dashboard_home():
    return redirect('/dashboard#home')


@app.route('/dashboard/camera')
@app.route('/camera', endpoint='camera_page')
@app.route('/camera', endpoint='camera')
@login_required
def dashboard_camera():
    return redirect('/dashboard#camera')


@app.route('/dashboard/customers')
@app.route('/customers', endpoint='customers')
@login_required
def dashboard_customers():
    return redirect('/dashboard#customers')


@app.route('/dashboard/products')
@app.route('/products', endpoint='products_page')
@app.route('/products', endpoint='products')
@login_required
def dashboard_products():
    return redirect('/dashboard#products')


@app.route('/dashboard/register')
@app.route('/register', endpoint='register_page')
@app.route('/register', endpoint='register')
@login_required
def dashboard_register():
    return redirect('/dashboard#customers')


@app.route('/dashboard/reports')
@app.route('/reports', endpoint='reports_page')
@app.route('/reports', endpoint='reports')
@login_required
def dashboard_reports():
    return redirect('/dashboard#logs')


@app.route('/dashboard/settings')
@app.route('/settings', endpoint='settings_page')
@app.route('/settings', endpoint='settings')
@login_required
def dashboard_settings():
    return redirect('/dashboard#settings')




# --- MJPEG VIDEO STREAM ROUTE (ULTRA-FAST & OPENCV-FREE) ---

# Pre-rendered Standby Frame (0% CPU, camera completely closed)
STANDBY_FRAME_JPEG = None

def get_standby_frame_jpeg():
    global STANDBY_FRAME_JPEG
    if STANDBY_FRAME_JPEG is None:
        img = Image.new('RGB', (1280, 720), color=(15, 23, 42))  # Slate dark background
        try:
            from PIL import ImageDraw
            draw = ImageDraw.Draw(img)
            draw.rounded_rectangle([(340, 220), (940, 500)], radius=16, fill=(30, 41, 59), outline=(51, 65, 85), width=3)
            draw.text((540, 290), "KAMERA KAPALI", fill=(239, 68, 68))
            draw.text((470, 340), "Kamera ve AI Okuma Durduruldu", fill=(148, 163, 184))
            draw.text((450, 380), "Yonetici Panelinden Tekrar Acilabilir", fill=(100, 116, 139))
        except Exception:
            pass
        STANDBY_FRAME_JPEG = UniFaceEngine.image_to_jpeg(img, quality=85)
    return STANDBY_FRAME_JPEG


def generate_mjpeg_stream():
    """
    High-Performance MJPEG Video Streamer:
    - Streams live frames when camera & recognition are active
    - Yields cached standby frame when camera is stopped (0% CPU, camera hardware released)
    """
    while True:
        if not is_recognition_active or not getattr(camera, 'running', True):
            standby = get_standby_frame_jpeg()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + standby + b'\r\n')
            time.sleep(0.5)
            continue

        with recognition_state_lock:
            jpeg_bytes = shared_recognition_state.get("jpeg_bytes")
            last_up = shared_recognition_state.get("last_update", 0)

        if jpeg_bytes is not None and (time.time() - last_up < 1.5):
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + jpeg_bytes + b'\r\n')
            time.sleep(0.035)
            continue

        # Fallback to direct camera frame if live
        raw_frame = camera.get_latest_frame()
        if raw_frame is not None:
            fallback_jpeg = UniFaceEngine.image_to_jpeg(raw_frame, quality=70)
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + fallback_jpeg + b'\r\n')

        time.sleep(0.035)


@app.route('/video_feed')
def video_feed():
    return Response(generate_mjpeg_stream(), mimetype='multipart/x-mixed-replace; boundary=frame')


# --- API ENDPOINTS ---

@app.route('/api/current_recognized_person')
@app.route('/api/recognized_person')
@app.route('/api/recognize', methods=['GET', 'POST'])
def get_current_recognized_person():
    if not is_recognition_active:
        return jsonify({
            "recognized": False,
            "is_active": False,
            "message": "AI Yüz Okuma Duraklatıldı"
        })

    with recognition_state_lock:
        people = shared_recognition_state.get("recognized_people", [])[:]
    
    if people:
        person = people[0]
        name = person['name']
        u_type = person.get('user_type', 'customer')
        similarity = person.get('similarity', 1.0)

        # Fetch latest user stats from DB
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, user_type, image, total_spent, last_login_date FROM users WHERE name = ?", (name,))
        u_row = cursor.fetchone()
        conn.close()

        total_spent = u_row['total_spent'] if u_row else 0.0
        last_login = u_row['last_login_date'] if u_row else datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        user_image = u_row['image'] if (u_row and u_row['image']) else person.get('image', '')
        user_id = u_row['id'] if u_row else 0

        return jsonify({
            "success": True,
            "recognized": True,
            "name": name,
            "user_type": u_type,
            "similarity": similarity,
            "id": user_id,
            "image": user_image,
            "total_spent": total_spent,
            "last_login_date": last_login,
            "people": people,
            "last_person": name
        })
    
    return jsonify({
        "success": True,
        "recognized": False,
        "name": None,
        "user_type": None,
        "people": [],
        "last_person": None
    })


WEATHER_CACHE = {
    "data": None,
    "timestamp": 0,
    "lat": None,
    "lon": None
}
WEATHER_CACHE_TTL = 1200  # 20 minutes (preserves AccuWeather 50 calls/day free quota)


def fetch_weather_by_coords(lat, lon):
    """
    Fetches real-time weather using AccuWeather API with location coordinates.
    Falls back to Open-Meteo if AccuWeather key is not configured or limit reached.
    """
    global WEATHER_CACHE
    now = time.time()

    # Check cache (within 20 mins and approximately same location)
    if (
        WEATHER_CACHE["data"] is not None
        and now - WEATHER_CACHE["timestamp"] < WEATHER_CACHE_TTL
        and WEATHER_CACHE["lat"] is not None
        and abs(WEATHER_CACHE["lat"] - lat) < 0.05
        and abs(WEATHER_CACHE["lon"] - lon) < 0.05
    ):
        return WEATHER_CACHE["data"]

    accuweather_key = get_setting("accuweather_api_key") or os.environ.get("ACCUWEATHER_API_KEY")

    if accuweather_key:
        try:
            # 1. AccuWeather Geoposition Search
            geo_url = "http://dataservice.accuweather.com/locations/v1/cities/geoposition/search"
            geo_res = requests.get(
                geo_url,
                params={"apikey": accuweather_key, "q": f"{lat},{lon}", "language": "tr-tr"},
                timeout=5
            )
            if geo_res.status_code == 200:
                geo_data = geo_res.json()
                location_key = geo_data.get("Key")
                city_name = geo_data.get("LocalizedName") or "İstanbul"

                # 2. AccuWeather Current Conditions
                cond_url = f"http://dataservice.accuweather.com/currentconditions/v1/{location_key}"
                cond_res = requests.get(
                    cond_url,
                    params={"apikey": accuweather_key, "language": "tr-tr", "details": "true"},
                    timeout=5
                )
                if cond_res.status_code == 200:
                    cond_data = cond_res.json()
                    if cond_data and len(cond_data) > 0:
                        first = cond_data[0]
                        temp_val = float(first.get("Temperature", {}).get("Metric", {}).get("Value", 22.0))
                        weather_text = first.get("WeatherText", "Açık")
                        icon_id = first.get("WeatherIcon", 1)

                        result = {
                            "cod": 200,
                            "source": "AccuWeather",
                            "name": city_name,
                            "weather": [{"description": weather_text, "icon": str(icon_id)}],
                            "main": {"temp": temp_val}
                        }
                        WEATHER_CACHE = {"data": result, "timestamp": now, "lat": lat, "lon": lon}
                        return result
            else:
                print(f"[WARN] AccuWeather API returned HTTP {geo_res.status_code}: {geo_res.text[:120]}")
        except Exception as e:
            print(f"[WARN] AccuWeather request failed: {e}")

    # Fallback to Open-Meteo for exact coordinates
    try:
        om_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
        om_res = requests.get(om_url, timeout=5)
        if om_res.status_code == 200:
            om_data = om_res.json()
            curr = om_data.get("current_weather", {})
            temp_val = float(curr.get("temperature", 22.0))
            code = int(curr.get("weathercode", 0))

            # Code to Turkish description mapping
            w_map = {
                0: "Açık", 1: "Çoğunlukla Açık", 2: "Parçalı Bulutlu", 3: "Bulutlu",
                45: "Sisli", 48: "Kırağılı Sis", 51: "Hafif Çisenti", 53: "Çisenti",
                55: "Yoğun Çisenti", 61: "Hafif Yağmur", 63: "Yağmurlu", 65: "Kuvvetli Yağmur",
                71: "Hafif Kar", 73: "Karlı", 75: "Yoğun Kar", 80: "Sağanak Yağış",
                81: "Kuvvetli Sağanak", 82: "Şiddetli Sağanak", 95: "Gök Gürültülü Fırtına"
            }
            weather_text = w_map.get(code, "Açık")

            source_label = "AccuWeather (Anahtar Bekleniyor - Canlı Konum)" if not accuweather_key else "AccuWeather Yedek (Canlı Konum)"
            result = {
                "cod": 200,
                "source": source_label,
                "name": "Konumunuz",
                "weather": [{"description": weather_text, "icon": "01d"}],
                "main": {"temp": temp_val}
            }
            WEATHER_CACHE = {"data": result, "timestamp": now, "lat": lat, "lon": lon}
            return result
    except Exception as e:
        print(f"[WARN] Open-Meteo fallback failed: {e}")

    # Default fallback
    return {
        "cod": 200,
        "source": "Varsayılan",
        "name": "İstanbul",
        "weather": [{"description": "Açık", "icon": "01d"}],
        "main": {"temp": 22.0}
    }


@app.route('/api/weather', methods=['GET', 'POST'])
def get_weather():
    lat = request.args.get('lat')
    lon = request.args.get('lon')

    if not lat or not lon:
        if request.is_json and request.json:
            lat = request.json.get('lat')
            lon = request.json.get('lon')

    try:
        lat = float(lat)
        lon = float(lon)
    except (TypeError, ValueError):
        # Default coordinates (Istanbul center)
        lat = 41.0082
        lon = 28.9784

    data = fetch_weather_by_coords(lat, lon)
    return jsonify(data)



@app.route('/api/entry_logs')
def get_entry_logs():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, user_name, user_type, entry_time, confidence FROM entry_logs ORDER BY id DESC LIMIT 50")
    logs = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify({"success": True, "logs": logs})


@app.route('/api/get_users')
@app.route('/api/users')
def get_users():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, user_type, image, total_spent, last_login_date FROM users ORDER BY id DESC")
    users = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify({"success": True, "users": users})


@app.route('/api/customer/<customer_name>')
def get_customer_details(customer_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, user_type, image, total_spent, last_login_date FROM users WHERE name = ?", (customer_name,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return jsonify({"success": True, "customer": dict(row), "name": row['name'], "total_spent": row['total_spent'], "last_login_date": row['last_login_date']})
    return jsonify({"success": False, "error": "Müşteri bulunamadı."}), 404


@app.route('/api/user/<int:user_id>', methods=['DELETE', 'GET'])
def handle_user_by_id(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    if request.method == 'DELETE':
        cursor.execute("SELECT name FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            u_name = row['name']
            cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
            cursor.execute("DELETE FROM user_embeddings WHERE user_name = ?", (u_name,))
            cursor.execute("DELETE FROM entry_logs WHERE user_name = ?", (u_name,))
            cursor.execute("DELETE FROM customer_preferences WHERE user_name = ?", (u_name,))
            dataset_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dataset', u_name)
            if os.path.isdir(dataset_dir):
                import shutil
                shutil.rmtree(dataset_dir, ignore_errors=True)
        else:
            cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))

        cursor.execute("DELETE FROM user_embeddings WHERE user_name NOT IN (SELECT name FROM users)")
        conn.commit()
        conn.close()

        recognition_service.reload_embeddings()
        with recognition_state_lock:
            shared_recognition_state["recognized_people"] = []
        return jsonify({"success": True, "message": "Kullanıcı ve tüm yüz biyometri kayıtları tamamen silindi."})
    else:
        cursor.execute("SELECT id, name, user_type, image, total_spent, last_login_date FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return jsonify({"success": True, "user": dict(row)})
        return jsonify({"success": False, "error": "Kullanıcı bulunamadı."}), 404


@app.route('/api/delete_users', methods=['POST'])
def delete_users():
    """Delete single or multiple users by ID or Name."""
    data = request.json or {}
    targets = data.get('targets', [])
    if not targets:
        return jsonify({"success": False, "error": "Silinecek hedef seçilmedi."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    names_to_delete = []
    for t in targets:
        if isinstance(t, int) or (isinstance(t, str) and t.isdigit()):
            cursor.execute("SELECT name FROM users WHERE id = ?", (int(t),))
            row = cursor.fetchone()
            if row:
                names_to_delete.append(row['name'])
        else:
            names_to_delete.append(str(t))

    for name in names_to_delete:
        cursor.execute("DELETE FROM users WHERE name = ?", (name,))
        cursor.execute("DELETE FROM user_embeddings WHERE user_name = ?", (name,))
        cursor.execute("DELETE FROM entry_logs WHERE user_name = ?", (name,))
        cursor.execute("DELETE FROM customer_preferences WHERE user_name = ?", (name,))
        dataset_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dataset', name)
        if os.path.isdir(dataset_dir):
            import shutil
            shutil.rmtree(dataset_dir, ignore_errors=True)

    # Purge any remaining orphan embeddings
    cursor.execute("DELETE FROM user_embeddings WHERE user_name NOT IN (SELECT name FROM users)")
    deleted_count = len(names_to_delete)

    conn.commit()
    conn.close()

    recognition_service.reload_embeddings()
    with recognition_state_lock:
        shared_recognition_state["recognized_people"] = []
    return jsonify({"success": True, "message": f"{deleted_count} kullanıcı ve tüm yüz verileri başarıyla silindi.", "deleted_count": deleted_count})




@app.route('/api/register_customer', methods=['POST'])
def register_customer():
    """Register a new customer using uploaded image or current camera snapshot."""
    try:
        name = request.form.get('name')
        if not name:
            return jsonify({"success": False, "error": "Müşteri adı gereklidir."}), 400

        image_file = request.files.get('image')
        if image_file:
            img_pil = Image.open(image_file.stream).convert('RGB')
        else:
            img_pil = camera.get_latest_frame()

        if img_pil is None:
            return jsonify({"success": False, "error": "Görüntü alınamadı."}), 400

        # Analyze face with UniFace
        faces = uniface_engine.analyze(img_pil)
        if not faces:
            return jsonify({"success": False, "error": "Görüntüde yüz tespit edilemedi."}), 400

        emb = faces[0]['embedding']
        if emb is None or len(emb) != 512:
            return jsonify({"success": False, "error": "Yüz özniteliği çıkarılamadı."}), 400

        # Save profile crop
        bbox = faces[0]['bbox']
        profile_base64 = recognition_service._crop_and_save_profile(img_pil, bbox, name)
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (name, user_type, image, total_spent, last_login_date, encoding) VALUES (?, ?, ?, ?, ?, ?)",
            (name, "customer", profile_base64, 0.0, now_str, emb.tobytes())
        )
        conn.commit()
        conn.close()

        recognition_service.reload_embeddings()
        return jsonify({"success": True, "name": name, "message": f"{name} başarıyla kaydedildi."})

    except sqlite3.IntegrityError:
        return jsonify({"success": False, "error": "Bu isimde bir kullanıcı zaten mevcut."}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/rename_guest/<guest_name>/<new_name>', methods=['POST', 'GET'])
@app.route('/api/rename_guest', methods=['POST'])
def rename_guest(guest_name=None, new_name=None):
    """Convert a Guest profile (e.g. Guest_1) to a named customer."""
    if not guest_name or not new_name:
        data = request.json or {}
        guest_name = data.get('guest_name') or data.get('old_name')
        new_name = (data.get('new_name') or '').strip()

    if not guest_name or not new_name:
        return jsonify({"success": False, "error": "Eski ve yeni kullanıcı adı gereklidir."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE users SET name = ?, user_type = 'customer' WHERE name = ?", (new_name, guest_name))
        cursor.execute("UPDATE user_embeddings SET user_name = ?, user_type = 'customer' WHERE user_name = ?", (new_name, guest_name))
        cursor.execute("UPDATE entry_logs SET user_name = ?, user_type = 'customer' WHERE user_name = ?", (new_name, guest_name))
        cursor.execute("UPDATE orders SET user_name = ?, name = ? WHERE user_name = ? OR name = ?", (new_name, new_name, guest_name, guest_name))
        conn.commit()
        conn.close()

        recognition_service.reload_embeddings()
        return jsonify({"success": True, "message": f"{guest_name} başarıyla {new_name} olarak güncellendi."})
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"success": False, "error": "Bu isimde başka bir kayıtlı müşteri zaten mevcut."}), 400
    except Exception as e:
        conn.close()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/get_products', methods=['GET', 'POST'])
def api_get_products():
    """Legacy compatibility endpoint to fetch products."""
    customer_name = request.args.get('customer_name') or request.args.get('customer')
    if request.method == 'POST' and request.is_json:
        data = request.json or {}
        customer_name = customer_name or data.get('customer_name')
    products = recommendation_service.get_products_for_user(customer_name)
    return jsonify({"success": True, "products": products})


@app.route('/api/products', methods=['GET', 'POST'])
def handle_products():
    """
    GET: Return product list (sorted by recommendation if customer_name given).
    POST: Create a new product with optional image file upload or URL.
    """
    if request.method == 'GET':
        customer_name = request.args.get('customer_name') or request.args.get('customer')
        products = recommendation_service.get_products_for_user(customer_name)
        return jsonify({"success": True, "products": products})

    # POST: Add new product
    try:
        # Check if multipart form data (file upload) or JSON
        if request.content_type and 'multipart/form-data' in request.content_type:
            product_name = (request.form.get('product_name') or request.form.get('name') or '').strip()
            category = (request.form.get('category') or '').strip() or 'Genel'
            price_val = (request.form.get('price') or '').strip()
            description = (request.form.get('description') or '').strip()
            image_url = (request.form.get('image_url') or '').strip()
            image_file = request.files.get('image_file') or request.files.get('image')
        else:
            data = request.get_json(silent=True) or {}
            product_name = str(data.get('product_name') or data.get('name') or '').strip()
            category = str(data.get('category') or '').strip() or 'Genel'
            price_val = str(data.get('price') or '').strip()
            description = str(data.get('description') or '').strip()
            image_url = str(data.get('image_url') or '').strip()
            image_file = None

        if not product_name:
            return jsonify({"success": False, "error": "Ürün adı zorunludur."}), 400

        try:
            price = float(price_val)
            if price < 0:
                raise ValueError()
        except Exception:
            return jsonify({"success": False, "error": "Geçerli bir pozitif fiyat giriniz."}), 400

        # Handle uploaded image file
        if image_file and image_file.filename:
            ext = os.path.splitext(image_file.filename)[1].lower()
            if ext in ALLOWED_IMAGE_EXTENSIONS:
                safe_name = f"{int(time.time())}_{secure_filename(image_file.filename)}"
                save_path = os.path.join(UPLOAD_PRODUCTS_DIR, safe_name)
                image_file.save(save_path)
                image_url = f"/static/images/products/{safe_name}"

        # Assign default category image if none provided
        if not image_url:
            cat_lower = category.lower()
            if 'kahve' in cat_lower:
                image_url = '/static/images/espresso.jpg'
            elif 'soğuk' in cat_lower or 'soguk' in cat_lower or 'içecek' in cat_lower or 'icecek' in cat_lower:
                image_url = '/static/images/portakalsuyu.jpg'
            elif 'tatlı' in cat_lower or 'tatli' in cat_lower or 'fırın' in cat_lower or 'firin' in cat_lower:
                image_url = '/static/images/kruvasan.jpg'
            elif 'yiyecek' in cat_lower or 'sandviç' in cat_lower or 'sandvic' in cat_lower:
                image_url = '/static/images/sandvic.jpg'
            else:
                image_url = 'https://images.unsplash.com/photo-1514432324607-a09d9b4aefdd?w=200'

        conn = get_db_connection()
        cursor = conn.cursor()

        # Check for existing product with identical name (case-insensitive)
        cursor.execute("SELECT id FROM products WHERE LOWER(product_name) = LOWER(?)", (product_name,))
        if cursor.fetchone():
            conn.close()
            return jsonify({"success": False, "error": f"'{product_name}' isimli bir ürün zaten mevcut."}), 400

        cursor.execute(
            "INSERT INTO products (product_name, category, price, description, image_url) VALUES (?, ?, ?, ?, ?)",
            (product_name, category, price, description, image_url)
        )
        new_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return jsonify({
            "success": True,
            "status": "success",
            "message": f"'{product_name}' ürünü başarıyla eklendi.",
            "product": {
                "id": new_id,
                "product_name": product_name,
                "category": category,
                "price": price,
                "description": description,
                "image_url": image_url
            }
        })
    except Exception as e:
        return jsonify({"success": False, "error": f"Sunucu hatası: {str(e)}"}), 500


@app.route('/api/products/<int:product_id>', methods=['DELETE'])
@app.route('/api/delete_product/<int:product_id>', methods=['POST', 'DELETE'])
def api_delete_product(product_id):
    """Delete a product from the database."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id, product_name FROM products WHERE id = ?", (product_id,))
        prod = cursor.fetchone()
        if not prod:
            conn.close()
            return jsonify({"success": False, "error": "Silinecek ürün bulunamadı."}), 404

        prod_name = prod['product_name']
        cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))
        conn.commit()
        conn.close()

        return jsonify({
            "success": True,
            "status": "success",
            "message": f"'{prod_name}' ürünü başarıyla silindi."
        })
    except Exception as e:
        return jsonify({"success": False, "error": f"Silme işlemi başarısız: {str(e)}"}), 500



@app.route('/api/orders', methods=['GET', 'POST'])
def handle_orders():
    if request.method == 'POST':
        data = request.json or {}
        user_name = data.get('user_name')
        items = data.get('items', [])
        res = recommendation_service.place_order(user_name, items)
        return jsonify(res)
    else:
        customer_name = request.args.get('customer_name')
        conn = get_db_connection()
        cursor = conn.cursor()
        if customer_name:
            cursor.execute("SELECT * FROM orders WHERE user_name = ? ORDER BY id DESC", (customer_name,))
        else:
            cursor.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 50")
        orders = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return jsonify({"success": True, "orders": orders})


# =====================================================================
# WAITER SERVICE TERMINAL & PRESENCE APIS
# =====================================================================

@app.route('/api/profile_image/<path:user_name>')
def api_get_profile_image(user_name):
    """
    Returns the customer's face image:
    1. Check if dataset/<user_name>/profile.jpg or 1.jpg exists on disk
    2. Check if user has base64 image in users table
    3. Return SVG/PNG fallback default user avatar
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    dataset_dir = os.path.join(base_dir, 'dataset', user_name)

    # 1. Disk dataset check
    for filename in ['profile.jpg', 'profile.png', '1.jpg', '1.png', '1_bak.jpg']:
        file_path = os.path.join(dataset_dir, filename)
        if os.path.isfile(file_path):
            resp = send_from_directory(dataset_dir, filename, mimetype='image/jpeg')
            resp.headers['Cache-Control'] = 'public, max-age=300'
            return resp

    # 2. Check users table in DB for base64 image
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT image FROM users WHERE name = ?", (user_name,))
        row = cursor.fetchone()
        conn.close()

        if row and row['image']:
            img_val = str(row['image']).strip()
            if img_val.startswith('data:image'):
                img_val = img_val.split(',', 1)[1]
            if len(img_val) > 20:
                raw_bytes = base64.b64decode(img_val)
                resp = Response(raw_bytes, mimetype='image/jpeg')
                resp.headers['Cache-Control'] = 'public, max-age=300'
                return resp
    except Exception as e:
        print(f"[WARN] Error loading image for {user_name}: {e}")

    # 3. Fallback default avatar
    static_img_dir = os.path.join(base_dir, 'static', 'images')
    default_svg = os.path.join(static_img_dir, 'default_user.svg')
    if os.path.isfile(default_svg):
        resp = send_from_directory(static_img_dir, 'default_user.svg', mimetype='image/svg+xml')
        resp.headers['Cache-Control'] = 'public, max-age=3600'
        return resp

    resp = send_from_directory(static_img_dir, 'default_user.png', mimetype='image/png')
    resp.headers['Cache-Control'] = 'public, max-age=3600'
    return resp


@app.route('/api/waiter/presence')
def api_waiter_presence():
    """Return active customers in venue grouped by waiting_order and ordered."""
    active_rows = get_active_presences()
    now = datetime.now()
    waiting = []
    ordered = []

    for r in active_rows:
        # Calculate elapsed minutes
        entry_t = r.get("entry_time")
        elapsed_min = 0
        if entry_t:
            try:
                dt = datetime.strptime(str(entry_t).split(".")[0], "%Y-%m-%d %H:%M:%S")
                elapsed_min = max(0, int((now - dt).total_seconds() / 60))
            except Exception:
                pass

        u_name = r["user_name"]
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT total_spent, last_login_date, image FROM users WHERE name = ?", (u_name,))
        u_row = cursor.fetchone()
        cursor.execute("SELECT COUNT(*) FROM orders WHERE user_name = ? OR name = ?", (u_name, u_name))
        order_count = cursor.fetchone()[0]
        conn.close()

        total_spent = u_row["total_spent"] if u_row else 0.0

        # Determine valid avatar URL or data URI
        presence_img = (r.get("face_image") or "").strip()
        if presence_img and (presence_img.startswith("/api/") or presence_img.startswith("data:image") or presence_img.startswith("http://") or presence_img.startswith("https://")):
            face_img = presence_img
        elif presence_img and presence_img.startswith("/static/") and not presence_img.startswith("/static/profiles/"):
            face_img = presence_img
        else:
            face_img = f"/api/profile_image/{u_name}"

        item = {
            "id": r["id"],
            "user_name": u_name,
            "user_type": r["user_type"],
            "status": r["status"],
            "face_image": face_img,
            "entry_time": str(r["entry_time"]),
            "elapsed_minutes": elapsed_min,
            "order_summary": r.get("order_summary") or "",
            "notes": r.get("notes") or "",
            "total_spent": total_spent,
            "order_count": order_count
        }

        if r["status"] == "waiting_order":
            waiting.append(item)
        else:
            ordered.append(item)

    return jsonify({
        "success": True,
        "waiting": waiting,
        "ordered": ordered,
        "total_active": len(active_rows)
    })


@app.route('/api/waiter/set_status', methods=['POST'])
def api_waiter_set_status():
    """Update status of a presence session ('waiting_order', 'ordered', 'exited')."""
    data = request.json or {}
    presence_id = data.get("presence_id")
    status = data.get("status")
    order_summary = data.get("order_summary")
    notes = data.get("notes")

    if not presence_id or not status:
        return jsonify({"success": False, "error": "presence_id ve status gereklidir."}), 400

    set_presence_status(presence_id, status=status, order_summary=order_summary, notes=notes)
    return jsonify({"success": True, "presence_id": presence_id, "status": status})


@app.route('/api/waiter/recommendations/<path:user_name>')
def api_waiter_recommendations(user_name):
    """Fetch situational AI recommendations and waiter pitch for customer."""
    weather_data = {"temp": 24.0, "description": "Açık"}
    try:
        # Use weather endpoint data
        weather_res = get_weather().get_json()
        if weather_res and "main" in weather_res:
            weather_data = {
                "temp": weather_res["main"].get("temp", 24.0),
                "description": weather_res.get("weather", [{}])[0].get("description", "Açık")
            }
    except Exception:
        pass

    res = recommendation_service.get_contextual_recommendations(
        user_name=user_name,
        weather_data=weather_data,
        current_hour=datetime.now().hour
    )
    return jsonify(res)


@app.route('/api/waiter/create_order', methods=['POST'])
def api_waiter_create_order():
    """Create order for customer on waiter terminal and transition to ordered."""
    data = request.json or {}
    presence_id = data.get("presence_id")
    user_name = data.get("user_name")
    items = data.get("items", [])

    if not user_name:
        return jsonify({"success": False, "error": "user_name gereklidir."}), 400
    if not items:
        return jsonify({"success": False, "error": "Sipariş verilecek ürün seçilmedi."}), 400

    res = recommendation_service.place_order(user_name, items)
    if res.get("success"):
        foods_summary = res.get("foods", "")
        if presence_id:
            set_presence_status(presence_id, status="ordered", order_summary=foods_summary)
        else:
            active_list = get_active_presences()
            for p in active_list:
                if p["user_name"] == user_name and p["status"] == "waiting_order":
                    set_presence_status(p["id"], status="ordered", order_summary=foods_summary)
                    break
        return jsonify({"success": True, "order": res})
    else:
        return jsonify({"success": False, "error": res.get("error", "Sipariş oluşturulamadı.")}), 400


@app.route('/api/waiter/notes', methods=['POST'])
def api_waiter_notes():
    """Save waiter notes for customer."""
    data = request.json or {}
    presence_id = data.get("presence_id")
    notes = (data.get("notes") or "").strip()

    if not presence_id:
        return jsonify({"success": False, "error": "presence_id gereklidir."}), 400

    set_presence_status(presence_id, notes=notes)
    return jsonify({"success": True, "presence_id": presence_id, "notes": notes})


@app.route('/api/settings/gemini_token', methods=['POST'])
def api_set_gemini_token():
    """Save optional Gemini API token in system_settings."""
    data = request.json or {}
    token = (data.get("token") or "").strip()
    set_setting("gemini_api_key", token)
    return jsonify({"success": True, "message": "Gemini API anahtarı kaydedildi."})


@app.route('/api/settings/accuweather_token', methods=['POST'])
def api_set_accuweather_token():
    """Save AccuWeather API token in system_settings."""
    data = request.json or {}
    token = (data.get("token") or "").strip()
    set_setting("accuweather_api_key", token)
    # Clear weather cache to fetch fresh data with new key
    global WEATHER_CACHE
    WEATHER_CACHE = {"data": None, "timestamp": 0, "lat": None, "lon": None}
    return jsonify({"success": True, "message": "AccuWeather API anahtarı kaydedildi."})


@app.route('/api/settings/tokens', methods=['GET'])
def api_get_tokens_status():
    """Return whether API tokens are configured (without exposing full secret)."""
    accu_key = get_setting("accuweather_api_key") or os.environ.get("ACCUWEATHER_API_KEY")
    gemini_key = get_setting("gemini_api_key") or os.environ.get("GEMINI_API_KEY")

    def mask(k):
        if not k:
            return ""
        if len(k) <= 8:
            return "****"
        return f"{k[:4]}****{k[-4:]}"

    return jsonify({
        "success": True,
        "accuweather": {
            "configured": bool(accu_key),
            "masked": mask(accu_key)
        },
        "gemini": {
            "configured": bool(gemini_key),
            "masked": mask(gemini_key)
        }
    })




@app.route('/api/stats')
def get_stats():
    """Summary statistics for dashboard home."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM users WHERE user_type = 'customer'")
    customer_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM users WHERE user_type = 'guest'")
    guest_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM orders")
    order_count = cursor.fetchone()[0]

    cursor.execute("SELECT COALESCE(SUM(total_amount), 0) FROM orders")
    total_revenue = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM entry_logs WHERE date(entry_time) = date('now')")
    today_entries = cursor.fetchone()[0]

    conn.close()

    return jsonify({
        "success": True,
        "is_recognition_active": is_recognition_active,
        "customer_count": customer_count,
        "guest_count": guest_count,
        "order_count": order_count,
        "total_revenue": total_revenue,
        "today_entries": today_entries
    })


@app.route('/api/recognition_status', methods=['GET'])
def recognition_status():
    global is_recognition_active
    return jsonify({
        "success": True,
        "is_active": is_recognition_active,
        "status_text": "Aktif" if is_recognition_active else "Duraklatıldı",
        "camera_running": getattr(camera, 'running', False),
        "camera_source": str(camera.camera_source),
        "mediamtx_active": mediamtx_service.is_active() if mediamtx_service else False,
        "webrtc_url": f"http://{request.host.split(':')[0]}:8889/live/whep"
    })


@app.route('/api/toggle_recognition', methods=['GET', 'POST'])
def toggle_recognition():
    global is_recognition_active
    if request.method == 'GET':
        return jsonify({
            "success": True,
            "is_active": is_recognition_active,
            "status_text": "Aktif" if is_recognition_active else "Kapalı",
            "camera_running": getattr(camera, 'running', False),
            "camera_source": str(camera.camera_source),
            "mediamtx_active": mediamtx_service.is_active() if mediamtx_service else False,
            "webrtc_url": f"http://{request.host.split(':')[0]}:8889/live/whep"
        })

    data = request.get_json(silent=True) or {}
    if 'enabled' in data:
        target_state = bool(data['enabled'])
    elif request.form and 'enabled' in request.form:
        val = str(request.form.get('enabled')).strip().lower()
        target_state = val in ('true', '1', 'yes', 'on')
    else:
        target_state = not is_recognition_active

    # Check if a camera source was explicitly specified in request
    req_source = data.get('camera_source')
    if req_source is not None and str(req_source).strip() != '':
        target_src = str(req_source).strip()
        if target_src.isdigit():
            target_src = int(target_src)
        persist_active_camera_to_db(target_src)
        camera.camera_source = target_src
    elif target_state and (str(camera.camera_source) in ('0', '')):
        # If camera is default 0, check if database preferred another active camera source
        db_src = get_active_camera_source_from_db()
        if str(db_src) not in ('0', ''):
            camera.camera_source = db_src

    is_recognition_active = target_state

    if is_recognition_active:
        camera.start()
        if mediamtx_service:
            mediamtx_service.start()
        print(f"[INFO] Camera hardware ({camera.camera_source}) and AI recognition STARTED.")
    else:
        camera.stop()
        if mediamtx_service:
            mediamtx_service.stop()
        with recognition_state_lock:
            shared_recognition_state["recognized_people"] = []
            shared_recognition_state["jpeg_bytes"] = None
            shared_recognition_state["annotated_frame"] = None
        print(f"[INFO] Camera hardware ({camera.camera_source}) and AI recognition STOPPED.")

    return jsonify({
        "success": True,
        "is_active": is_recognition_active,
        "camera_running": getattr(camera, 'running', False),
        "camera_source": str(camera.camera_source),
        "mediamtx_active": mediamtx_service.is_active() if mediamtx_service else False,
        "webrtc_url": f"http://{request.host.split(':')[0]}:8889/live/whep",
        "message": "Kamera ve yüz tanıma aktif edildi." if is_recognition_active else "Kamera ve yüz tanıma kapatıldı."
    })


# --- LEGACY & FRONTEND COMPATIBILITY ENDPOINTS ---

@app.route('/api/get_last_customers', methods=['GET', 'POST'])
def get_last_customers():
    count = 10
    if request.is_json and request.json:
        count = request.json.get('count', 10)
    elif request.form and 'count' in request.form:
        try:
            count = int(request.form.get('count', 10))
        except ValueError:
            count = 10
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, user_type, image, total_spent, last_login_date FROM users ORDER BY id DESC LIMIT ?", (count,))
    users = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify({"success": True, "customers": users, "status": "success"})


@app.route('/api/cam_changed', methods=['POST'])
def cam_changed():
    data = request.get_json(silent=True) or request.form or {}
    cam_val = data.get('camera_source', data.get('cam_number', data.get('cam_value')))
    if cam_val is not None:
        try:
            if isinstance(cam_val, str) and str(cam_val).strip().isdigit():
                cam_val = int(str(cam_val).strip())
            
            # Persist to DB so it survives app restarts and recognition toggle cycles
            persist_active_camera_to_db(cam_val)

            # Check if already streaming from this source and running
            if str(camera.camera_source) == str(cam_val) and camera.running:
                return jsonify({
                    "success": True, 
                    "message": f"Kamera '{cam_val}' zaten aktif.", 
                    "camera_source": str(camera.camera_source),
                    "restarted": False
                })

            if is_recognition_active:
                camera.set_camera_source(cam_val)
            else:
                camera.camera_source = cam_val

            return jsonify({
                "success": True, 
                "message": f"Kamera '{cam_val}' olarak değiştirildi.", 
                "camera_source": str(camera.camera_source),
                "restarted": is_recognition_active
            })
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 400
    return jsonify({"success": False, "error": "Geçersiz kamera parametresi."}), 400



@app.route('/api/camera_settings', methods=['GET', 'POST'])
def camera_settings():
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        data = request.get_json(silent=True) or request.form or {}
        cam_name = data.get('cam_name', '').strip()
        cam_value = data.get('cam_value', '').strip()

        if not cam_name or not cam_value:
            conn.close()
            return jsonify({"success": False, "error": "Kamera adı ve değeri zorunludur."}), 400

        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute(
            "INSERT INTO camera_settings (cam_name, cam_value, is_active, created_at) VALUES (?, ?, 0, ?)",
            (cam_name, cam_value, now_str)
        )
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": f"Kamera '{cam_name}' eklendi."})
    else:
        cursor.execute("SELECT id, cam_name, cam_value, is_active, created_at FROM camera_settings ORDER BY id DESC")
        cams = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return jsonify({"success": True, "cameras": cams, "current_camera_source": str(camera.camera_source)})


@app.route('/api/camera_settings/<int:cam_id>/activate', methods=['POST'])
def activate_camera_setting(cam_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM camera_settings WHERE id = ?", (cam_id,))
    cam = cursor.fetchone()
    if not cam:
        conn.close()
        return jsonify({"success": False, "error": "Kamera bulunamadı."}), 404

    cursor.execute("UPDATE camera_settings SET is_active = 0")
    cursor.execute("UPDATE camera_settings SET is_active = 1 WHERE id = ?", (cam_id,))
    conn.commit()
    conn.close()

    cam_val = cam['cam_value']
    if str(cam_val).strip().isdigit():
        cam_val = int(str(cam_val).strip())

    try:
        if is_recognition_active:
            camera.set_camera_source(cam_val)
        else:
            camera.camera_source = cam_val
        return jsonify({
            "success": True, 
            "message": f"Kamera '{cam['cam_name']}' aktif edildi.",
            "camera_source": str(camera.camera_source)
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route('/api/camera_settings/<int:cam_id>', methods=['DELETE'])
def delete_camera_setting(cam_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM camera_settings WHERE id = ?", (cam_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "Kamera silindi."})


@app.route('/api/customer/<customer_name>/total_spent')
@app.route('/api/get_total_spent/<customer_name>')
def get_customer_total_spent(customer_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT total_spent FROM users WHERE name = ?", (customer_name,))
    row = cursor.fetchone()
    conn.close()
    total_spent = row['total_spent'] if row else 0.0
    return jsonify({"success": True, "customer": customer_name, "total_spent": total_spent})


@app.route('/api/customer/<customer_name>/last_login')
@app.route('/api/get_last_login/<customer_name>')
def get_customer_last_login(customer_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT last_login_date FROM users WHERE name = ?", (customer_name,))
    row = cursor.fetchone()
    conn.close()
    last_login = row['last_login_date'] if row else "Hiç"
    return jsonify({"success": True, "customer": customer_name, "last_login": last_login})


@app.route('/api/customer/<customer_name>/get_orders')
@app.route('/api/get_orders/<customer_name>')
def get_customer_orders(customer_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT id, COALESCE(total_amount, 0) as total_amount, COALESCE(foods, '') as foods, order_date FROM orders WHERE name = ? OR user_name = ? ORDER BY id DESC",
            (customer_name, customer_name)
        )
        rows = cursor.fetchall()
        conn.close()
        orders_list = []
        for r in rows:
            amt = r['total_amount']
            foods_str = r['foods']
            info = f"Sipariş #{r['id']}"
            if foods_str:
                info += f" - {foods_str}"
            if amt:
                info += f" ({amt} TL)"
            if r['order_date']:
                info += f" [{r['order_date']}]"
            orders_list.append(info)
        return jsonify(orders_list)
    except Exception as e:
        conn.close()
        return jsonify([])


@app.route('/api/get_food_percentage/<customer_name>')
def get_food_percentage(customer_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT oi.product_name, SUM(oi.quantity) as total_qty
            FROM order_items oi
            JOIN orders o ON oi.order_id = o.id
            WHERE o.name = ? OR o.user_name = ?
            GROUP BY oi.product_name
        ''', (customer_name, customer_name))
        rows = cursor.fetchall()
        
        if not rows:
            cursor.execute("SELECT foods FROM orders WHERE name = ? OR user_name = ?", (customer_name, customer_name))
            order_rows = cursor.fetchall()
            counts = {}
            for r in order_rows:
                if r['foods']:
                    items = [f.strip() for f in r['foods'].split(',') if f.strip()]
                    for item in items:
                        counts[item] = counts.get(item, 0) + 1
            if counts:
                total_sum = sum(counts.values())
                result = {k: round((v / total_sum) * 100, 1) for k, v in counts.items()}
                conn.close()
                return jsonify(result)

        conn.close()
        total_sum = sum(r['total_qty'] for r in rows) if rows else 0
        if total_sum == 0:
            return jsonify({"Veri yok": 0})
        
        result = {r['product_name']: round((r['total_qty'] / total_sum) * 100, 1) for r in rows}
        return jsonify(result)
    except Exception as e:
        conn.close()
        return jsonify({"Veri yok": 0})

    return jsonify(result)


@app.route('/api/customer/<customer_name>/preferences', methods=['GET'])
def get_customer_preferences(customer_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT food, preference FROM customer_preferences WHERE user_name = ?", (customer_name,))
    rows = cursor.fetchall()
    conn.close()
    if not rows:
        return jsonify({"error": "Tercih bulunamadı."})
    prefs = [f"{r['food']}: {r['preference']}" for r in rows]
    return jsonify({"message": prefs})


@app.route('/api/preferences/<customer_name>', methods=['POST'])
def save_customer_preference(customer_name):
    data = request.json or {}
    food = data.get('food', '').strip()
    preference = data.get('preference', '').strip()

    if not food or not preference:
        return jsonify({"error": "Yemek ve tercih girilmelidir."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO customer_preferences (user_name, food, preference) VALUES (?, ?, ?)",
        (customer_name, food, preference)
    )
    conn.commit()
    conn.close()
    return jsonify({"message": f"{customer_name} için tercih kaydedildi."})


@app.route('/api/suggest_food')
def suggest_food():
    customer_name = request.args.get('customer')
    products = recommendation_service.get_products_for_user(customer_name)
    suggested = products[0]['product_name'] if products else "Kuru Fasulye"
    return jsonify({"food": suggested})


@app.route('/api/order_food/<customer_name>', methods=['POST'])
def order_food(customer_name):
    data = request.json or {}
    items = data.get('items') or data.get('foods') or data.get('food') or data.get('product_name')
    if not items:
        return jsonify({"success": False, "message": "Yemek veya ürün seçilmedi."}), 400

    if isinstance(items, str):
        items = [items]

    res = recommendation_service.place_order(customer_name, items)
    if res.get('success'):
        return jsonify({
            "success": True,
            "message": res.get("message", f"Siparişiniz başarıyla alındı!"),
            "order_id": res.get("order_id"),
            "total_amount": res.get("total_amount"),
            "foods": res.get("foods")
        })
    return jsonify({"success": False, "message": res.get("error", "Sipariş verilemedi.")}), 400


@app.route('/api/recognize_once', methods=['POST', 'GET'])
def recognize_once():
    with recognition_state_lock:
        people = shared_recognition_state.get("recognized_people", [])[:]
    if people:
        person = people[0]
        return jsonify({
            "success": True,
            "name": person['name'],
            "user_type": person.get('user_type', 'customer'),
            "image": person.get('image', ''),
            "id": person.get('id', 0),
            "similarity": person.get('similarity', 1.0),
            "last_login_date": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
    return jsonify({"success": False, "message": "Yüz tespit edilemedi."})



if __name__ == '__main__':
    print("[INFO] Starting UniFace Cafe Recognition System on http://0.0.0.0:5000")
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)