import os
import glob
import cv2
import numpy as np
import insightface
from insightface.app import FaceAnalysis
from uniface import FaceAttribNet, Face

bins = glob.glob(r'C:\Users\Eren\Desktop\face-recognize-system-for-business\venv\Lib\site-packages\nvidia\*\bin')
os.environ['PATH'] = ';'.join(bins) + ';' + os.environ.get('PATH', '')
for b in bins:
    if hasattr(os, 'add_dll_directory'):
        try:
            os.add_dll_directory(b)
        except Exception:
            pass

app = FaceAnalysis(name='buffalo_l', providers=['CUDAExecutionProvider', 'CPUExecutionProvider'])
app.prepare(ctx_id=0, det_size=(640, 640))
fa = FaceAttribNet(providers=['CUDAExecutionProvider', 'CPUExecutionProvider'])

img = cv2.imread(r'dataset\Eren\2.jpg')
faces = app.get(img)
print(f"Detected {len(faces)} face(s)")

for i, f in enumerate(faces):
    # Attributes
    f_obj = Face(bbox=f.bbox, confidence=f.det_score, landmarks=f.kps)
    fa.predict(img, f_obj)
    
    gender_str = "Erkek" if f.gender == 1 else "Kadın"
    glasses_str = "Gözlüklü" if f_obj.eyeglasses > 0.5 else "Gözlüksüz"
    sunglasses_str = "Güneş Gözlüklü" if f_obj.sunglasses > 0.5 else ""
    
    pitch, yaw, roll = [round(float(v), 1) for v in f.pose]
    
    print(f"Face {i+1}:")
    print(f"  BBox: {f.bbox.astype(int).tolist()}")
    print(f"  Detection Score: {f.det_score:.3f}")
    print(f"  Age: {f.age} | Gender: {gender_str}")
    print(f"  Eyeglasses Prob: {f_obj.eyeglasses:.3f} ({glasses_str})")
    print(f"  3D Head Pose: Pitch={pitch}°, Yaw={yaw}°, Roll={roll}°")
    print(f"  3D Landmark Points: {f.landmark_3d_68.shape} (X, Y, Z)")
