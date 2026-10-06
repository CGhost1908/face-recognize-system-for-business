import subprocess
import time
import os
import urllib.request

def test_mediamtx():
    mediamtx_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mediamtx_bin", "mediamtx.exe")
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mediamtx_bin", "mediamtx.yml")
    
    if not os.path.exists(mediamtx_path):
        print(f"[FAIL] MediaMTX binary not found at: {mediamtx_path}")
        return False

    print(f"[OK] Found MediaMTX at: {mediamtx_path}")
    proc = subprocess.Popen([mediamtx_path, config_path], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        time.sleep(1.5)
        # Check if HTTP WHEP / HLS or API is responsive
        try:
            req = urllib.request.Request("http://127.0.0.1:8889/")
            with urllib.request.urlopen(req, timeout=2) as resp:
                print(f"[OK] MediaMTX WebRTC port 8889 status code: {resp.status}")
        except urllib.error.HTTPError as e:
            # 404 is expected for root url on WHEP port
            print(f"[OK] MediaMTX WebRTC server responded (HTTP {e.code}) as expected")
        except Exception as e:
            print(f"[WARN] Connection check: {e}")

        # Check if process is still running
        poll = proc.poll()
        if poll is None:
            print("[SUCCESS] MediaMTX started successfully and is running!")
            return True
        else:
            out, _ = proc.communicate(timeout=2)
            print(f"[FAIL] MediaMTX exited with code {poll}. Output:\n{out}")
            return False
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except Exception:
            proc.kill()
        print("[INFO] MediaMTX test process terminated.")

if __name__ == '__main__':
    test_mediamtx()
