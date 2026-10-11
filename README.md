# UniFace - Smart Facial Recognition & Customer Experience System for Businesses

A modern, high-performance facial recognition and customer intelligence platform tailored for cafes, restaurants, and retail businesses. Designed to run smoothly on edge devices (like Raspberry Pi 5) and standard servers using lightweight ONNX Runtime execution.

---

## 🌟 Key Features

- **Real-Time Facial Recognition**: Instant identification and verification of customers using UniFace and ONNX Runtime.
- **Customer Presence & Visit Tracking**: Automatically registers customer arrivals, visit frequency, and dwell time.
- **Smart Waiter Terminal**: Mobile-friendly terminal providing real-time alerts when recognized customers enter, showing their favorite orders and preferences.
- **Personalized Recommendations**: Context-aware recommendation engine based on past order history and customer preferences.
- **Low-Latency Video Pipeline**: MediaMTX (WebRTC / RTSP / HLS) streaming for real-time live camera feeds with minimal latency.
- **Admin & Management Dashboard**: Responsive management portal for customer profiles, menu/product management, order logging, and analytics.

---

## 🛠️ Tech Stack

- **Backend**: Python 3.10+, Flask 3.0, Werkzeug
- **Face AI Engine**: `uniface`, `onnxruntime`, `numpy`, `Pillow`
- **Video & Streaming**: `av` (PyAV), MediaMTX (RTSP/WebRTC)
- **Database**: SQLite (optimized with local indexing)
- **Frontend**: HTML5, Modern CSS3, Vanilla JavaScript (Fetch API, WebSockets / SSE)

---

## 📁 Project Structure

```text
face-recognize-system-for-business/
├── app.py                      # Main Flask application & API routes
├── uniface_engine.py           # Face detection & feature extraction module
├── recognition_service.py      # Face matching & customer identification
├── recommendation_service.py   # Customer preference & menu recommendation logic
├── database.py                 # SQLite database models & query handlers
├── camera_stream.py            # Video capture and RTSP frame processing
├── mediamtx_service.py         # MediaMTX WebRTC / RTSP server integration
├── create_admin.py             # Script to initialize administrator credentials
├── requirements.txt            # Python dependencies
├── static/                     # CSS stylesheets, JavaScript files, and product images
└── templates/                  # Jinja2 HTML templates (Dashboard, Terminal, Reports)
```

---

## 🚀 Getting Started

### Prerequisites

- Python 3.10 or higher
- A connected webcam or RTSP network camera stream
- (Optional) MediaMTX binary for WebRTC streaming

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/CGhost1908/face-recognize-system-for-business.git
   cd face-recognize-system-for-business
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv .venv
   # Windows:
   .\.venv\Scripts\activate
   # Linux / macOS:
   source .venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Initialize the database & create admin user:**
   ```bash
   python create_admin.py
   ```

5. **Start the application:**
   ```bash
   python app.py
   ```
   Open your browser and navigate to `http://localhost:5000`.

---

## ⚙️ Configuration

You can configure settings via environment variables:
- `SECRET_KEY`: Session encryption key (defaults to a safe local key if unset).
- `CAMERA_SOURCE`: Camera device index (`0`, `1`) or an RTSP stream URL (`rtsp://user:pass@ip:port/stream`).
- `PORT`: Web server port (default: `5000`).

---

## 📄 License

This project is licensed under the MIT License.
