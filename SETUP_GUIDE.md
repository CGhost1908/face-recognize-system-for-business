# Cross-Platform Setup Guide for Windows & Raspberry Pi

## Quick Start

### Windows Installation

```bash
# Create virtual environment
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements-windows.txt

# Run the application
python app.py
```

### Raspberry Pi Installation

```bash
# Update system
sudo apt-get update
sudo apt-get upgrade

# Install Python and pip (usually pre-installed)
sudo apt-get install python3 python3-pip

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install lightweight dependencies
pip install -r requirements-pi.txt

# For Raspberry Pi with GPU (optional)
# pip install tensorflow-lite-runtime  # Lighter than full TensorFlow

# Run the application
python3 app.py
```

---

## Configuration

The system auto-detects your platform and applies optimizations:

### Windows
- Full resolution: 640x480
- Fast frame refresh rates
- All features enabled
- Loads all models at startup

### Raspberry Pi
- Reduced resolution: 480x360 (faster processing)
- Slower frame refresh rates (lower CPU usage)
- Lazy loading of ML models
- Face detection optimized for Pi

**To override settings**, edit `config.py` before starting:

```python
# config.py
FRAME_WIDTH = 640  # Change resolution
FRAME_HEIGHT = 480

CAMERA_SLEEP_TIME = 0.02  # Adjust camera refresh
MJPEG_SLEEP_TIME = 0.1   # Adjust video stream speed

LAZY_LOAD_MODEL = True   # Load ML models on-demand
```

---

## Features Availability

| Feature | Windows | Raspberry Pi |
|---------|---------|--------------|
| Face Recognition | ✅ Full | ✅ Optimized (HOG model) |
| Food Recommendations (ML) | ✅ | ⚠️ Optional |
| Live Camera Feed | ✅ | ✅ |
| Admin Dashboard | ✅ | ✅ |
| Database | ✅ | ✅ |

**Optional Features:**
- Face Recognition: Can be disabled if `face-recognition` library not available
- Food Recommendations: Requires TensorFlow (skip if not installed)

---

## Troubleshooting

### Raspberry Pi: Out of Memory

If you get memory errors on Pi:
```bash
# Reduce Python heap
export PYTHONHASHSEED=0

# Use lightweight models
# Edit config.py: FACE_RECOGNITION_MODEL = "hog"  # Faster, less accurate
```

### Missing Libraries on Raspberry Pi

If `face-recognition` or `tensorflow` won't install:

```bash
# Install without heavy optional dependencies
pip install -r requirements-pi.txt

# The app will auto-fallback to available features
```

### Camera Not Working

1. Check camera access:
```bash
# Windows
python -c "import cv2; print(cv2.VideoCapture(0).isOpened())"

# Raspberry Pi
python3 -c "import cv2; print(cv2.VideoCapture(0).isOpened())"
```

2. Try different camera index:
   - Edit `config.py`: `CAMERA_IDX = 0` (or 1, 2, 3...)
   - Or use dashboard to switch cameras

---

## Performance Optimization Tips

### Raspberry Pi
- Disable unnecessary background services
- Use a USB 3.0 camera for better performance
- Install `python3-dev` for faster compilation
- Consider using SSD for database (faster than SD card)

### Windows
- Close unnecessary applications
- Update GPU drivers for faster processing
- Use a powered USB hub for cameras

---

## File Structure

```
.
├── app.py                  # Main Flask application
├── config.py               # Auto-detect platform & settings
├── requirements.txt        # Universal dependencies
├── requirements-windows.txt # Windows-specific
├── requirements-pi.txt     # Raspberry Pi optimized
├── database.db             # SQLite database
├── dataset/                # Face training images
├── trainer/                # LBPH model
├── Cascade/                # Haar cascades
├── templates/              # HTML templates
├── static/                 # CSS, JS, images
└── trained_model.h5       # ML model for food recommendations
```

---

## Environment Variables

```bash
# Optional: Set custom database path
export DB_PATH="/path/to/database.db"

# Optional: Set Flask host/port
export FLASK_HOST="0.0.0.0"
export FLASK_PORT="5000"
```

---

## Running in Production on Raspberry Pi

```bash
# Use Gunicorn for production
pip install gunicorn

# Run with multiple workers
gunicorn --workers 2 --threads 2 --timeout 60 app:app
```

For systemd service:
```bash
sudo nano /etc/systemd/system/face-recognition.service
```

```ini
[Unit]
Description=Face Recognition Service
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/yuz-tanima-performance
Environment="PATH=/home/pi/yuz-tanima-performance/venv/bin"
ExecStart=/home/pi/yuz-tanima-performance/venv/bin/gunicorn -b 0.0.0.0:5000 app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable face-recognition
sudo systemctl start face-recognition
```

---

## API Compatibility

All endpoints work on both Windows and Raspberry Pi. The only difference is performance:
- Windows: Faster response times
- Raspberry Pi: Slower but functional

If a feature is unavailable (e.g., TensorFlow not installed), the API returns:
```json
{
  "error": "Service unavailable",
  "code": 503
}
```

---

## Support & Debugging

For detailed logs:
```bash
# Windows
python app.py 2>&1 | tee app.log

# Raspberry Pi
python3 app.py 2>&1 | tee app.log
```

Check output for:
- `[CONFIG]` - Platform detection messages
- `[INFO]` - Normal operations
- `[WARNING]` - Non-critical issues
- `[ERROR]` - Critical errors
