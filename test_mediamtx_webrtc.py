import subprocess
import time
import os
import urllib.request
import numpy as np

def test_mediamtx_webrtc_stream():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    mediamtx_path = os.path.join(base_dir, "mediamtx_bin", "mediamtx.exe")
    config_path = os.path.join(base_dir, "mediamtx_bin", "mediamtx.yml")
    
    # 1. Start MediaMTX
    mtx_proc = subprocess.Popen([mediamtx_path, config_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    time.sleep(1.0)
    
    # 2. Start FFmpeg publisher
    cmd = [
        "ffmpeg",
        "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-pix_fmt", "bgr24",
        "-s", "640x480",
        "-r", "25",
        "-i", "-",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-tune", "zerolatency",
        "-pix_fmt", "yuv420p",
        "-f", "rtsp",
        "-rtsp_transport", "tcp",
        "rtsp://127.0.0.1:8554/live"
    ]
    
    ff_proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    dummy_frame = np.full((480, 640, 3), 100, dtype=np.uint8).tobytes()
    
    # Feed frames for 2 seconds
    for _ in range(40):
        ff_proc.stdin.write(dummy_frame)
        time.sleep(0.04)
        
    # Check WHEP options / status on port 8889
    try:
        req = urllib.request.Request("http://127.0.0.1:8889/live/whep", method="OPTIONS")
        with urllib.request.urlopen(req, timeout=2) as resp:
            print(f"[SUCCESS] WHEP endpoint http://127.0.0.1:8889/live/whep responded with HTTP {resp.status}!")
            headers = dict(resp.headers)
            print(f"[INFO] WHEP response headers: {headers}")
    except Exception as e:
        print(f"[TEST RESULT] {e}")

    try:
        ff_proc.stdin.close()
        ff_proc.terminate()
        mtx_proc.terminate()
    except Exception:
        pass

if __name__ == '__main__':
    test_mediamtx_webrtc_stream()
