"""
Configuration management for cross-platform deployment (Windows & Raspberry Pi)
"""
import os
import sys
import platform

# Detect platform
IS_RASPBERRY_PI = 'arm' in platform.machine().lower() or os.path.exists('/proc/device-tree/model')
IS_WINDOWS = sys.platform.startswith('win')
IS_LINUX = sys.platform.startswith('linux')

print(f"[CONFIG] Platform detected: {platform.system()} ({platform.machine()})")
print(f"[CONFIG] Raspberry Pi: {IS_RASPBERRY_PI}, Windows: {IS_WINDOWS}, Linux: {IS_LINUX}")

# Base paths - cross-platform compatible
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_DIR = os.path.join(BASE_DIR, "dataset")
TRAINER_DIR = os.path.join(BASE_DIR, "trainer")
CASCADE_DIR = os.path.join(BASE_DIR, "Cascade")
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")

# Database
DB_PATH = os.path.join(BASE_DIR, "database.db")

# Model paths
MODEL_PATH = os.path.join(BASE_DIR, "trained_model.h5")
LABEL_ENCODERS_PATH = os.path.join(BASE_DIR, "label_encoders.pkl")
SCALER_PATH = os.path.join(BASE_DIR, "scaler.pkl")
TRAINER_MODEL_PATH = os.path.join(TRAINER_DIR, "trainer.yml")

# Cascade classifier paths
FACE_CASCADE_PATH = os.path.join(CASCADE_DIR, "haarcascade_frontalface_default.xml")
LBPCASCADE_PATH = os.path.join(CASCADE_DIR, "lbpcascade_frontalface_improved.xml")

# Camera settings
FRAME_WIDTH = 640
FRAME_HEIGHT = 480

# Raspberry Pi specific optimizations
if IS_RASPBERRY_PI:
    print("[CONFIG] Raspberry Pi optimizations enabled")
    # Reduce resolution on Pi for better performance
    FRAME_WIDTH = 480
    FRAME_HEIGHT = 360
    # Reduce camera fetch frequency
    CAMERA_SLEEP_TIME = 0.02
    # Increase MJPEG sleep for lower CPU usage
    MJPEG_SLEEP_TIME = 0.1
    # Model loading - lazy loading on Pi
    LAZY_LOAD_MODEL = True
    # Use lower quality face recognition on Pi
    FACE_RECOGNITION_MODEL = "cnn"  # "hog" is faster on Pi, "cnn" is more accurate
    # Reduce threading overhead
    ENABLE_CAMERA_THREAD = True
    # Face detection scale factor
    FACE_DETECTION_SCALE = 1.3
else:
    print("[CONFIG] Windows/Linux optimizations enabled")
    CAMERA_SLEEP_TIME = 0.01
    MJPEG_SLEEP_TIME = 0.05
    LAZY_LOAD_MODEL = False
    FACE_RECOGNITION_MODEL = "hog"
    ENABLE_CAMERA_THREAD = True
    FACE_DETECTION_SCALE = 1.1

# Flask settings
FLASK_HOST = "0.0.0.0"
FLASK_PORT = 5000
FLASK_DEBUG = False
FLASK_THREADED = True

# Performance settings
MAX_FACE_ENCODINGS_BATCH = 100  # Limit batch processing
ENCODING_CACHE_ENABLED = True

# Ensure directories exist
for dir_path in [DATASET_DIR, TRAINER_DIR, CASCADE_DIR, STATIC_DIR, TEMPLATE_DIR]:
    os.makedirs(dir_path, exist_ok=True)

print(f"[CONFIG] Base directory: {BASE_DIR}")
print(f"[CONFIG] Database: {DB_PATH}")
print(f"[CONFIG] Frame resolution: {FRAME_WIDTH}x{FRAME_HEIGHT}")
