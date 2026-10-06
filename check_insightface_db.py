import cv2
import numpy as np
import insightface
from insightface.app import FaceAnalysis
from database import get_db_connection

app = FaceAnalysis(name='buffalo_l', providers=['CPUExecutionProvider'])
app.prepare(ctx_id=0, det_size=(640, 640))

img = cv2.imread(r'dataset\Eren\1.jpg')
faces = app.get(img)
if faces:
    ins_emb = faces[0].embedding.copy()
    ins_emb /= np.linalg.norm(ins_emb)

    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT encoding FROM users WHERE name='Eren'")
    db_enc = np.frombuffer(c.fetchone()['encoding'], dtype=np.float32).copy()
    db_enc /= np.linalg.norm(db_enc)

    sim = float(np.dot(ins_emb, db_enc))
    print(f'Similarity between InsightFace Buffalo_L on Eren 1.jpg and Eren in DB: {sim:.4f}')

    c.execute("SELECT embedding FROM user_embeddings WHERE user_name='Eren'")
    for i, r in enumerate(c.fetchall()):
        proto = np.frombuffer(r['embedding'], dtype=np.float32).copy()
        proto /= np.linalg.norm(proto)
        print(f'  InsightFace vs DB Proto {i+1}: {float(np.dot(ins_emb, proto)):.4f}')
