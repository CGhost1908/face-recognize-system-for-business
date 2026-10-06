import os
import glob
import cv2
import numpy as np
import insightface
from insightface.app import FaceAnalysis
from database import get_db_connection

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

eren_photos = sorted(glob.glob(r'dataset\Eren\*.jpg'))
print(f"Found {len(eren_photos)} photos for Eren")

embeddings = []
for p in eren_photos:
    img = cv2.imread(p)
    if img is None:
        continue
    faces = app.get(img)
    if faces:
        emb = faces[0].embedding.copy()
        emb /= np.linalg.norm(emb)
        embeddings.append((p, emb, faces[0].gender, faces[0].age, faces[0].pose))
        print(f"  Processed {os.path.basename(p)}: Age={faces[0].age}, Gender={faces[0].gender}, Pose={faces[0].pose}")

if embeddings:
    conn = get_db_connection()
    c = conn.cursor()
    # Primary encoding in users
    primary_emb = embeddings[0][1]
    c.execute("UPDATE users SET encoding = ? WHERE name = 'Eren'", (primary_emb.tobytes(),))
    
    # Refresh prototypes in user_embeddings
    c.execute("DELETE FROM user_embeddings WHERE user_name = 'Eren'")
    for path, emb, g, a, pose in embeddings:
        pitch = float(pose[0]) if len(pose) > 0 else 0.0
        yaw = float(pose[1]) if len(pose) > 1 else 0.0
        c.execute(
            "INSERT INTO user_embeddings (user_name, user_type, embedding, quality_score, yaw, pitch, created_at) VALUES ('Eren', 'customer', ?, 1.0, ?, ?, datetime('now'))",
            (emb.tobytes(), yaw, pitch)
        )
    conn.commit()
    conn.close()
    print("Successfully enrolled Eren's 5 multi-angle prototypes with Buffalo_L into DB!")
