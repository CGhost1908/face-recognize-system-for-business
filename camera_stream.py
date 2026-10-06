import io
import time
import threading
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Try OpenCV for hardware camera capture (Windows/Linux/RTSP)
try:
    import cv2
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False

# Try PyAV for V4L2/RTSP capture without OpenCV
try:
    import av
    PYAV_AVAILABLE = True
except ImportError:
    PYAV_AVAILABLE = False

# Try Picamera2 for Raspberry Pi 5 native libcamera
try:
    from picamera2 import Picamera2
    PICAM2_AVAILABLE = True
except ImportError:
    PICAM2_AVAILABLE = False



class CameraStream:
    """
    OpenCV-free Camera Stream for Raspberry Pi 5 (Linux ARM64) and desktop environments.
    Supports Picamera2 (RPi5), PyAV (V4L2/RTSP/USB), and synthetic test stream fallback.
    """

    def __init__(self, camera_source=0, width=1920, height=1080):
        self.camera_source = camera_source
        self.width = width
        self.height = height
        self.running = False
        self.thread = None
        self.lock = threading.Lock()
        self.latest_frame = None
        self.backend_name = "Synthetic"

    def start(self):
        """Start background camera capture thread."""
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()

    def stop(self):
        """Stop background camera capture thread."""
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)
        with self.lock:
            self.latest_frame = None

    def set_camera_source(self, new_source):
        """Dynamically switch camera source (device index or RTSP URL)."""
        # Normalize input
        if isinstance(new_source, str) and new_source.strip().isdigit():
            target_source = int(new_source.strip())
        else:
            target_source = new_source

        # If camera is already actively running on this source, do NOT restart hardware handle!
        if self.running and str(self.camera_source) == str(target_source):
            return

        self.stop()
        self.camera_source = target_source
        self.start()


    def get_latest_frame(self):
        """
        Get the most recent frame as a PIL.Image.
        Returns None if no frame is ready yet.
        """
        with self.lock:
            if self.latest_frame is not None:
                return self.latest_frame.copy()
            return self._generate_synthetic_frame()

    def _capture_loop(self):
        """Main capture loop running in separate thread."""
        # 1. Try Picamera2 (Raspberry Pi 5)
        if PICAM2_AVAILABLE and (self.camera_source == 0 or self.camera_source == "picam"):
            try:
                print("[INFO] Initializing Picamera2 (Raspberry Pi 5)...")
                picam2 = Picamera2()
                config = picam2.create_preview_configuration(main={"size": (self.width, self.height)})
                picam2.configure(config)
                picam2.start()
                self.backend_name = "Picamera2 (RPi5)"
                print(f"[INFO] Camera started using {self.backend_name}")
                while self.running:
                    frame_np = picam2.capture_array()
                    img = Image.fromarray(frame_np).convert('RGB')
                    with self.lock:
                        self.latest_frame = img
                    time.sleep(0.03)
                picam2.stop()
                return
            except Exception as e:
                print(f"[WARN] Picamera2 failed: {e}. Falling back to PyAV/V4L2.")

        # 2. Try OpenCV VideoCapture (Windows webcam / Linux / RTSP streams)
        if OPENCV_AVAILABLE:
            try:
                src = self.camera_source
                if isinstance(src, str) and src.isdigit():
                    src = int(src)
                print(f"[INFO] Attempting OpenCV VideoCapture ({src})...")
                cap = cv2.VideoCapture(src)
                if cap.isOpened():
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or self.width)
                    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or self.height)
                    self.backend_name = f"OpenCV Hardware ({src}) [{actual_w}x{actual_h}]"
                    print(f"[INFO] Camera started using {self.backend_name}")
                    while self.running:
                        ret, frame = cap.read()
                        if not ret or frame is None:
                            time.sleep(0.05)
                            continue
                        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        img = Image.fromarray(frame_rgb)
                        with self.lock:
                            self.latest_frame = img
                        time.sleep(0.02)
                    cap.release()
                    return
                else:
                    cap.release()
                    print(f"[WARN] OpenCV VideoCapture ({src}) failed to open.")
            except Exception as e:
                print(f"[WARN] OpenCV capture error: {e}")

        # 3. Try PyAV (V4L2 / USB camera / RTSP)
        if PYAV_AVAILABLE:

            device_path = f"/dev/video{self.camera_source}" if isinstance(self.camera_source, int) else str(self.camera_source)
            formats_to_try = [("v4l2", device_path), (None, device_path)]
            
            for fmt, path in formats_to_try:
                try:
                    print(f"[INFO] Attempting PyAV camera connection ({fmt}, {path})...")
                    options = {'video_size': f'{self.width}x{self.height}'} if fmt == "v4l2" else {}
                    container = av.open(path, format=fmt, options=options)
                    stream = container.streams.video[0]
                    self.backend_name = f"PyAV ({fmt or 'auto'})"
                    print(f"[INFO] Camera started using {self.backend_name}")

                    for packet in container.demux(stream):
                        if not self.running:
                            break
                        for frame in packet.decode():
                            img = frame.to_image().convert('RGB')
                            if img.size != (self.width, self.height):
                                img = img.resize((self.width, self.height), Image.Resampling.BILINEAR)
                            with self.lock:
                                self.latest_frame = img
                            time.sleep(0.03)
                    container.close()
                    return
                except Exception as e:
                    print(f"[WARN] PyAV ({fmt}) camera open failed: {e}")

        # 3. Fallback: Synthetic Test Frame Loop
        print("[INFO] Using synthetic test frame stream generator.")
        self.backend_name = "Synthetic Test Generator"
        tick = 0
        while self.running:
            img = self._generate_synthetic_frame(tick)
            with self.lock:
                self.latest_frame = img
            tick += 1
            time.sleep(0.05)

    def _generate_synthetic_frame(self, tick=0):
        """Generates a test frame for UI validation when no camera is attached."""
        img = Image.new('RGB', (self.width, self.height), color=(30, 35, 45))
        draw = ImageDraw.Draw(img)
        
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        title = f"Cafe Monitor - Live Feed ({self.backend_name})"
        
        # Grid lines
        for x in range(0, self.width, 80):
            draw.line([(x, 0), (x, self.height)], fill=(45, 52, 65), width=1)
        for y in range(0, self.height, 60):
            draw.line([(0, y), (self.width, y)], fill=(45, 52, 65), width=1)

        # Status Overlay
        draw.rectangle([10, 10, self.width - 10, 45], fill=(20, 24, 33))
        draw.text((20, 18), title, fill=(0, 220, 130))
        draw.text((self.width - 200, 18), timestamp, fill=(180, 190, 205))

        # Animated Pulse Indicator
        cx = (self.width // 2) + int(50 * np.sin(tick * 0.1))
        cy = (self.height // 2) + int(30 * np.cos(tick * 0.1))
        r = 40
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(0, 200, 255), width=2)
        draw.text((cx - 30, cy - 6), "NO CAMERA", fill=(0, 200, 255))
        
        return img
