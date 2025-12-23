# 🎯 Face Recognition System - Cross-Platform Setup

**Now compatible with Windows & Raspberry Pi!**

This project has been updated to run seamlessly on both Windows and Raspberry Pi with automatic platform detection and optimization.

## ✨ What's New

### Platform-Aware Optimizations
- ✅ **Auto-Detection**: Automatically detects Windows/Raspberry Pi/Linux
- ✅ **Smart Configuration**: Applies optimal settings per platform
- ✅ **Resource-Aware**: Reduces CPU/memory usage on Raspberry Pi
- ✅ **Graceful Degradation**: Works even if optional libraries are missing
- ✅ **Cross-Platform Paths**: File paths work correctly on all systems

### Raspberry Pi Optimizations
- Reduced video resolution (480x360) for better performance
- Lazy loading of ML models to save startup memory
- HOG-based face detection (faster than CNN on Pi)
- Configurable frame rates to manage CPU load
- Lighter dependency list

### Windows Features (Full)
- Full resolution (640x480) for better accuracy
- All models loaded at startup for quick responses
- CNN-based face recognition (most accurate)
- All features enabled by default

---

## 🚀 Quick Setup

### Windows

```bash
# Run the setup utility (recommended)
python setup.py

# OR manual setup
python -m venv venv
venv\Scripts\activate
pip install -r requirements-windows.txt

# Start the app
python app.py
```

### Raspberry Pi

```bash
# Run the setup utility (recommended)
python3 setup.py

# OR manual setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-pi.txt

# Start the app
python3 app.py
```

---

## 📋 New Configuration File

The `config.py` file automatically detects your platform:

```python
# Automatically set:
IS_RASPBERRY_PI = True/False
IS_WINDOWS = True/False
IS_LINUX = True/False

# Adjusted automatically:
FRAME_WIDTH = 640 (Windows) or 480 (Pi)
FRAME_HEIGHT = 480 (Windows) or 360 (Pi)
MJPEG_SLEEP_TIME = 0.05 (Windows) or 0.1 (Pi)
LAZY_LOAD_MODEL = False (Windows) or True (Pi)
FACE_RECOGNITION_MODEL = "hog" (Windows/fast) or "cnn" (accurate)
```

---

## 📁 File Structure

```
├── app.py                    # Main Flask app (updated for cross-platform)
├── config.py                 # NEW: Platform detection & settings
├── setup.py                  # NEW: Automated setup script
├── requirements.txt          # Universal dependencies
├── requirements-windows.txt  # Windows-specific (full features)
├── requirements-pi.txt       # Raspberry Pi (optimized)
├── SETUP_GUIDE.md           # Detailed setup guide
└── [other files unchanged]
```

---

## 🔧 Key Changes to app.py

1. **Import from config.py**: All paths and settings now come from centralized config
2. **Optional imports**: face_recognition and tensorflow are now optional
3. **Lazy loading**: ML models can be loaded on-demand on Raspberry Pi
4. **Graceful fallbacks**: App warns but continues if libraries are missing
5. **Performance tuning**: Sleep times adjusted per platform

---

## 🔌 Camera Configuration

Camera settings are now centralized:

```python
# In config.py
FRAME_WIDTH = 640 or 480
FRAME_HEIGHT = 480 or 360
FACE_DETECTION_SCALE = 1.3 (Pi) or 1.1 (Windows)
```

Try different camera indices if needed:
```bash
# Edit app.py, find CAMERA_IDX and change:
CAMERA_IDX = 0  # Try 1, 2, 3 if primary doesn't work
```

---

## 📊 Feature Availability Matrix

| Feature | Windows | Raspberry Pi | Linux |
|---------|---------|--------------|-------|
| Face Detection | ✅ CNN | ✅ HOG | ✅ HOG |
| Face Recognition | ✅ Full | ✅ Optimized | ✅ Full |
| Food Recommendations | ✅ | ⚠️ Optional | ✅ |
| Admin Dashboard | ✅ | ✅ | ✅ |
| Live Camera | ✅ | ✅ | ✅ |
| Database | ✅ | ✅ | ✅ |

---

## ⚙️ Performance Tips

### Raspberry Pi
```bash
# Check current performance
top  # or: htop

# Free up memory
sudo systemctl stop bluetooth
sudo systemctl disable bluetooth

# Use SSD instead of SD card if possible
# Install on USB: sudo nano /etc/fstab
```

### Windows
```bash
# Monitor resource usage
taskmgr  # Task Manager

# Close background applications for better performance
```

---

## 🐛 Troubleshooting

### Camera not detected
```bash
# Test camera access
python -c "import cv2; cap = cv2.VideoCapture(0); print(cap.isOpened())"

# Try different index (0, 1, 2, 3...)
# Change in config.py: CAMERA_IDX = 1
```

### Face recognition library missing (Raspberry Pi)
```bash
# The app will work without it - it will skip face recognition
# To install (very slow on Pi - get pre-built wheel):
# pip install dlib face-recognition
```

### TensorFlow not available
```bash
# Food recommendations will be disabled
# App logs: "[WARNING] TensorFlow not available"
# This is normal on Raspberry Pi
```

### Memory errors on Raspberry Pi
```bash
# Edit config.py and reduce:
FRAME_WIDTH = 320
FRAME_HEIGHT = 240
MJPEG_SLEEP_TIME = 0.2  # Lower = faster, higher = less CPU
```

---

## 📝 Logs & Debugging

```bash
# View detailed logs
python app.py 2>&1 | tee app.log

# Look for platform detection
[CONFIG] Platform detected: Linux (armv7l)
[CONFIG] Raspberry Pi: True

# Check model loading
[INFO] ML models loaded successfully
```

---

## 🌐 Accessing the Application

Once running:
- **Local**: `http://localhost:5000`
- **Over Network**: `http://<your-ip>:5000`
  - Windows: Find IP with `ipconfig`
  - Raspberry Pi: Find IP with `hostname -I`

---

## 📦 Dependencies

### Lightweight Core (All Platforms)
- Flask 2.3.0
- OpenCV 4.8.0
- NumPy 1.24.3
- Pillow 10.0.0
- Requests 2.31.0

### Optional (Recommended for Windows)
- TensorFlow 2.13.0 (food recommendations)
- face-recognition 1.3.5 (face encoding)
- dlib 19.24.2 (required by face-recognition)

### Raspberry Pi Note
- `face-recognition` installation is very slow - consider using pre-built wheels
- `TensorFlow` can be replaced with `tensorflow-lite-runtime` for smaller size

---

## 🚢 Production Deployment

### Raspberry Pi with Systemd

Create `/etc/systemd/system/face-app.service`:
```ini
[Unit]
Description=Face Recognition App
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/face-recognition
Environment="PATH=/home/pi/face-recognition/venv/bin"
ExecStart=/home/pi/face-recognition/venv/bin/python3 app.py
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable face-app
sudo systemctl start face-app
```

### Windows with Service Manager
```bash
# Use NSSM (Non-Sucking Service Manager)
nssm install FaceRecognition "C:\path\to\venv\Scripts\python.exe" app.py
nssm start FaceRecognition
```

---

## 🤝 Contributing & Issues

If you find platform-specific issues:
1. Check the logs for `[CONFIG]` and `[WARNING]` messages
2. Verify your Python version: `python --version`
3. Check file paths are correct
4. Ensure all cascade files exist in `Cascade/` directory

---

## 📖 Full Documentation

See `SETUP_GUIDE.md` for detailed information about:
- Installation for each platform
- Configuration options
- Feature availability matrix
- Troubleshooting guide
- Production deployment

---

## ✅ Tested Environments

- ✅ Windows 10/11 with Python 3.9+
- ✅ Raspberry Pi 4 (32-bit & 64-bit OS)
- ✅ Raspberry Pi Zero W (with reduced performance)
- ✅ Ubuntu 20.04+ (Linux compatibility)

---

**Ready to use on both Windows and Raspberry Pi! 🎉**
