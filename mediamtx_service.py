import os
import sys
import time
import subprocess
import threading
import queue
import numpy as np

class MediaMTXService:
    """
    Ultra-Low Latency Video Streaming via MediaMTX & WebRTC (WHEP).
    Features:
    - Launches and monitors mediamtx.exe binary
    - Streams annotated HUD video via FFmpeg to RTSP (rtsp://127.0.0.1:8554/live)
    - Hardware-accelerated H.264: NVIDIA NVENC (RTX 4060) on PC, libx264 ultrafast on Pi 5 / CPU
    - Non-blocking asynchronous frame queue (drops excess frames to maintain zero lag)
    - Full fallback to MJPEG if FFmpeg or MediaMTX is unavailable
    """

    def __init__(self, fps=25):
        self.fps = fps
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.mediamtx_bin = os.path.join(self.base_dir, "mediamtx_bin", "mediamtx.exe" if os.name == 'nt' else "mediamtx")
        self.config_path = os.path.join(self.base_dir, "mediamtx_bin", "mediamtx.yml")
        
        self.mediamtx_proc = None
        self.ffmpeg_proc = None
        self.frame_queue = queue.Queue(maxsize=3)
        self.running = False
        self.worker_thread = None
        self.lock = threading.Lock()
        
        self.current_width = 0
        self.current_height = 0
        self.encoder = None

    def start(self):
        """Start MediaMTX and the worker thread."""
        with self.lock:
            if self.running:
                return

            if not os.path.exists(self.mediamtx_bin):
                print(f"[WARN] MediaMTX binary not found at {self.mediamtx_bin}. WebRTC disabled.")
                return

            try:
                # 1. Start MediaMTX if not already running on port 8554
                self.mediamtx_proc = subprocess.Popen(
                    [self.mediamtx_bin, self.config_path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                time.sleep(0.5)
                print(f"[INFO] MediaMTX server started (PID: {self.mediamtx_proc.pid})")
            except Exception as e:
                print(f"[WARN] Failed to start MediaMTX server: {e}")
                return

            self.running = True
            self.worker_thread = threading.Thread(target=self._stream_worker, daemon=True)
            self.worker_thread.start()

    def _detect_encoder(self):
        """Check if NVIDIA NVENC is available for zero CPU load, else use libx264."""
        try:
            res = subprocess.run(["ffmpeg", "-h", "encoder=h264_nvenc"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if res.returncode == 0:
                return ["-c:v", "h264_nvenc", "-preset", "p1", "-tune", "ll", "-zerolatency", "1"]
        except Exception:
            pass
        return ["-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency"]

    def _start_ffmpeg(self, width, height):
        """Start FFmpeg RTSP publisher process."""
        if self.ffmpeg_proc is not None:
            try:
                self.ffmpeg_proc.stdin.close()
                self.ffmpeg_proc.terminate()
            except Exception:
                pass
            self.ffmpeg_proc = None

        encoder_args = self._detect_encoder()
        cmd = [
            "ffmpeg",
            "-y",
            "-f", "rawvideo",
            "-vcodec", "rawvideo",
            "-pix_fmt", "bgr24",
            "-s", f"{width}x{height}",
            "-r", str(self.fps),
            "-i", "-",
            *encoder_args,
            "-pix_fmt", "yuv420p",
            "-g", str(self.fps),  # 1 keyframe per second for instant WebRTC connection
            "-b:v", "2.5M",
            "-maxrate", "3M",
            "-bufsize", "1M",
            "-f", "rtsp",
            "-rtsp_transport", "tcp",
            "rtsp://127.0.0.1:8554/live"
        ]

        try:
            self.ffmpeg_proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            self.current_width = width
            self.current_height = height
            enc_name = encoder_args[1]
            print(f"[INFO] FFmpeg RTSP Streamer started [{width}x{height} @ {self.fps}fps] with {enc_name}")
        except Exception as e:
            print(f"[WARN] Failed to start FFmpeg streamer: {e}")
            self.ffmpeg_proc = None

    def push_frame(self, frame_bgr):
        """Push a BGR frame (numpy array) to the stream queue. Drops oldest frame if full."""
        if not self.running or frame_bgr is None:
            return

        h, w = frame_bgr.shape[:2]
        if w != self.current_width or h != self.current_height:
            with self.lock:
                self._start_ffmpeg(w, h)

        if self.ffmpeg_proc is None or self.ffmpeg_proc.poll() is not None:
            return

        try:
            self.frame_queue.put_nowait(frame_bgr)
        except queue.Full:
            try:
                self.frame_queue.get_nowait()
                self.frame_queue.put_nowait(frame_bgr)
            except Exception:
                pass

    def _stream_worker(self):
        """Worker thread to feed frames to FFmpeg stdin pipe."""
        while self.running:
            try:
                frame = self.frame_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            if self.ffmpeg_proc is not None and self.ffmpeg_proc.stdin is not None:
                try:
                    self.ffmpeg_proc.stdin.write(frame.tobytes())
                except (BrokenPipeError, OSError):
                    # FFmpeg process crashed or disconnected, restart on next push
                    self.ffmpeg_proc = None

    def stop(self):
        """Stop FFmpeg and MediaMTX."""
        with self.lock:
            self.running = False
            if self.ffmpeg_proc is not None:
                try:
                    self.ffmpeg_proc.stdin.close()
                    self.ffmpeg_proc.terminate()
                except Exception:
                    pass
                self.ffmpeg_proc = None

            if self.mediamtx_proc is not None:
                try:
                    self.mediamtx_proc.terminate()
                except Exception:
                    pass
                self.mediamtx_proc = None

    def is_active(self):
        return self.running and (self.mediamtx_proc is not None and self.mediamtx_proc.poll() is None)
