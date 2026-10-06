import subprocess
import time
import os
import numpy as np

def test_ffmpeg_rtsp():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    mediamtx_path = os.path.join(base_dir, "mediamtx_bin", "mediamtx.exe")
    config_path = os.path.join(base_dir, "mediamtx_bin", "mediamtx.yml")
    
    # 1. Start MediaMTX
    mtx_proc = subprocess.Popen([mediamtx_path, config_path], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    time.sleep(1.0)
    
    # 2. Try FFmpeg publisher with h264_nvenc, fallback to libx264
    encoders = [
        ["-c:v", "h264_nvenc", "-preset", "p1", "-tune", "ll"],
        ["-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency"]
    ]
    
    success = False
    for enc in encoders:
        cmd = [
            "ffmpeg",
            "-y",
            "-f", "rawvideo",
            "-vcodec", "rawvideo",
            "-pix_fmt", "bgr24",
            "-s", "640x480",
            "-r", "25",
            "-i", "-",
            *enc,
            "-pix_fmt", "yuv420p",
            "-f", "rtsp",
            "-rtsp_transport", "tcp",
            "rtsp://127.0.0.1:8554/live"
        ]
        
        print(f"[TEST] Trying FFmpeg encoder: {enc[1]}...")
        try:
            ff_proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            # Write 25 frames
            dummy_frame = np.full((480, 640, 3), 120, dtype=np.uint8).tobytes()
            for _ in range(25):
                ff_proc.stdin.write(dummy_frame)
                time.sleep(0.02)
            ff_proc.stdin.flush()
            ff_proc.stdin.close()
            ff_proc.wait(timeout=3)
            if ff_proc.returncode == 0:
                print(f"[SUCCESS] FFmpeg successfully streamed to MediaMTX with {enc[1]}!")
                success = True
                break
            else:
                err = ff_proc.stderr.read().decode('utf-8', errors='ignore')
                print(f"[WARN] {enc[1]} exited with {ff_proc.returncode}: {err[-200:]}")
        except Exception as e:
            print(f"[WARN] Exception with {enc[1]}: {e}")

    mtx_proc.terminate()
    try:
        mtx_proc.wait(timeout=2)
    except Exception:
        mtx_proc.kill()
        
    return success

if __name__ == '__main__':
    test_ffmpeg_rtsp()
