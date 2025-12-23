# Quick Reference Card - Cross-Platform Setup

## Installation (Choose Your Platform)

### 🪟 Windows
```bash
# Method 1: Automatic (Recommended)
python setup.py

# Method 2: Manual
python -m venv venv
venv\Scripts\activate
pip install -r requirements-windows.txt
```

### 🍓 Raspberry Pi
```bash
# Method 1: Automatic (Recommended)
python3 setup.py

# Method 2: Manual
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-pi.txt
```

---

## Start the Application

### 🪟 Windows
```bash
# Activate virtual environment
venv\Scripts\activate

# Run application
python app.py
```

### 🍓 Raspberry Pi
```bash
# Activate virtual environment
source venv/bin/activate

# Run application
python3 app.py
```

**Then open:** http://localhost:5000

---

## Configuration

All settings are in `config.py` - auto-detected per platform:

| Setting | Windows | Raspberry Pi |
|---------|---------|--------------|
| Video Resolution | 640x480 | 480x360 |
| Face Detection | CNN (accurate) | HOG (fast) |
| Model Loading | Immediate | Lazy (on-demand) |
| Frame Sleep | 0.01s | 0.02s |
| MJPEG Stream | 0.05s | 0.1s |

---

## Common Commands

```bash
# Test camera
python -c "import cv2; print(cv2.VideoCapture(0).isOpened())"

# Check platform detection
python -c "from config import *; print(f'Pi: {IS_RASPBERRY_PI}, Windows: {IS_WINDOWS}')"

# View logs
python app.py 2>&1 | tee app.log

# Database operations
sqlite3 database.db
```

---

## Key Files

| File | Purpose |
|------|---------|
| `app.py` | Main Flask application |
| `config.py` | Platform detection & settings |
| `setup.py` | Automated installation |
| `requirements-windows.txt` | Full dependencies |
| `requirements-pi.txt` | Lightweight dependencies |
| `database.db` | SQLite database |
| `dataset/` | Training images |
| `trainer/` | LBPH model |

---

## API Endpoints (All Platforms)

```
POST /api/login                    # Admin login
POST /api/logout                   # Logout
POST /api/recognize                # Face recognition
POST /api/suggest_food             # Food recommendation
GET  /api/get_users                # List users
GET  /api/get_products             # List products
POST /api/add_product              # Add product
...and more
```

---

## Features Availability

| Feature | Windows | Pi |
|---------|---------|-----|
| Face Recognition | ✅ | ✅ |
| Face Detection | ✅ | ✅ |
| Food Recommendations | ✅ | ⚠️ Optional |
| Admin Dashboard | ✅ | ✅ |
| Camera Feed | ✅ | ✅ |
| Database | ✅ | ✅ |

---

## Troubleshooting Quick Fixes

### Camera not working
```bash
# Try different index
# Edit config.py: CAMERA_IDX = 1  (or 0, 2, 3...)
```

### Memory error on Pi
```bash
# Edit config.py and reduce:
FRAME_WIDTH = 320
FRAME_HEIGHT = 240
```

### Module not found
```bash
# Reinstall dependencies
pip install -r requirements-pi.txt  # on Pi
pip install -r requirements-windows.txt  # on Windows
```

### Face recognition disabled
```bash
# Library not installed - app still works without it
# To install on Pi (slow): pip install face-recognition
```

---

## Performance Tips

### Raspberry Pi
- Close unnecessary applications
- Disable Bluetooth if not needed
- Use USB 3.0 camera
- Consider SSD over SD card

### Windows
- Close background apps
- Update GPU drivers
- Use powered USB hub for cameras

---

## Environment Info

```bash
# Check Python version
python --version

# Check platform detection
python -c "from config import IS_RASPBERRY_PI, IS_WINDOWS; print(f'Pi: {IS_RASPBERRY_PI}, Win: {IS_WINDOWS}')"

# Check installed packages
pip list

# Check disk space
df -h  # Linux/Pi
wmic logicaldisk get size,freespace  # Windows
```

---

## Production Deployment

### Raspberry Pi (systemd)
```bash
# Create service file
sudo nano /etc/systemd/system/face-app.service

# Add content: (see SETUP_GUIDE.md for full template)
# Then:
sudo systemctl start face-app
sudo systemctl enable face-app
```

### Windows (Task Scheduler)
```bash
# Use Task Scheduler to run at startup
# Or use NSSM for service management
```

---

## File Path Examples

All paths work on Windows and Pi automatically:

```python
# These work everywhere:
DATASET_DIR = os.path.join(BASE_DIR, "dataset")
DB_PATH = os.path.join(BASE_DIR, "database.db")
MODEL_PATH = os.path.join(BASE_DIR, "trained_model.h5")

# NOT needed anymore:
DATASET_DIR = "dataset"
DB_PATH = "database.db"
```

---

## Important Notes

✅ Same code runs on both Windows and Raspberry Pi
✅ No need to modify code for different platforms  
✅ Settings auto-optimize for your hardware
✅ Gracefully handles missing optional libraries
✅ All features available on both (with some performance tradeoffs)

---

## Still Need Help?

📖 **Detailed Setup**: See `SETUP_GUIDE.md`
📖 **All Changes**: See `CHANGES_SUMMARY.md`
📖 **Quick Start**: See `CROSS_PLATFORM_README.md`

---

**Last Updated:** December 23, 2025  
**Compatible With:** Windows 10/11, Raspberry Pi 3/4/Zero, Linux
