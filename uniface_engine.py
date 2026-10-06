import io
import os
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# Hardware & NVIDIA CUDA Environment Setup
# ---------------------------------------------------------------------------
def _register_nvidia_dll_paths():
    """Register site-packages/nvidia/*/bin directories so CUDA 12 DLLs are found automatically on Windows."""
    if os.name != 'nt':
        return
    try:
        import sys, glob
        for sp in [p for p in sys.path if 'site-packages' in p]:
            nvidia_dir = os.path.join(sp, 'nvidia')
            if os.path.isdir(nvidia_dir):
                bins = glob.glob(os.path.join(nvidia_dir, '*', 'bin'))
                if bins:
                    os.environ['PATH'] = ';'.join(bins) + ';' + os.environ.get('PATH', '')
                    for b in bins:
                        if hasattr(os, 'add_dll_directory'):
                            try:
                                os.add_dll_directory(b)
                            except Exception:
                                pass
    except Exception:
        pass

_register_nvidia_dll_paths()

# Thread optimization for Raspberry Pi 5 / ARM64 / Low-power CPU execution
os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "2")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "2")

# Imports
try:
    import insightface
    from insightface.app import FaceAnalysis
    INSIGHTFACE_AVAILABLE = True
except ImportError:
    INSIGHTFACE_AVAILABLE = False

try:
    from uniface import FaceAttribNet, Face
    UNIFACE_ATTRIB_AVAILABLE = True
except ImportError:
    UNIFACE_ATTRIB_AVAILABLE = False


def get_optimal_execution_providers():
    """
    Detect available hardware execution providers.
    Uses CUDA on NVIDIA RTX GPUs, gracefully falls back to CPU on Raspberry Pi 5.
    """
    try:
        import onnxruntime as ort
        available = ort.get_available_providers()
        if 'CUDAExecutionProvider' in available:
            return ['CUDAExecutionProvider', 'CPUExecutionProvider']
    except Exception:
        pass
    return ['CPUExecutionProvider']


class UniFaceEngine:
    """
    State-of-the-Art 3D Face Recognition & Multi-Attribute Analysis Engine.
    Powered by InsightFace Buffalo_L (SCRFD-10G + ResNet50 ArcFace + 3D Mesh 68) + FaceAttribNet.
    
    Capabilities:
    - 3D Facial Landmarks (68 points in X, Y, Z space)
    - 3D Head Pose Estimation (Pitch, Yaw, Roll in degrees)
    - ResNet50 512-d ArcFace recognition embeddings
    - SCRFD-10G small face detector with aspect-ratio preserving letterbox
    - Real-Time Demographics (Gender & Age)
    - Real-Time Facial Accessories (Eyeglasses, Sunglasses, Face Mask)
    - Resolution-Independent Adaptive HUD Drawing
    - Hybrid Execution: NVIDIA CUDA (RTX 4060) and Raspberry Pi 5 ARM64 CPU
    """

    CURRENT_HW_LABEL = "CPU (Raspberry Pi 5 / Neon)"

    def __init__(self, confidence_threshold=0.50, min_face_size=18):
        self.confidence_threshold = confidence_threshold
        self.min_face_size = min_face_size
        self.providers = get_optimal_execution_providers()
        self.app = None
        self.attrib_model = None

        hw_label = "NVIDIA CUDA (RTX 4060)" if "CUDAExecutionProvider" in self.providers else "CPU (Raspberry Pi 5 / Neon)"
        self.hw_label = hw_label
        UniFaceEngine.CURRENT_HW_LABEL = hw_label

        if INSIGHTFACE_AVAILABLE:
            try:
                self.app = FaceAnalysis(
                    name='buffalo_l',
                    providers=self.providers,
                    allowed_modules=['detection', 'recognition', 'landmark_3d_68', 'genderage']
                )
                # Aspect-ratio preserving detector size (640x640)
                self.app.prepare(ctx_id=0 if "CUDAExecutionProvider" in self.providers else -1, det_size=(640, 640))
                print(f"[INFO] 3D Face Analysis Engine (Buffalo_L) Ready on [{hw_label}]. Modules: {list(self.app.models.keys())}")
            except Exception as e:
                print(f"[ERROR] Failed to load InsightFace Buffalo_L: {e}")

        if UNIFACE_ATTRIB_AVAILABLE:
            try:
                self.attrib_model = FaceAttribNet(providers=self.providers)
                print(f"[INFO] FaceAttribNet (Eyeglasses/Mask) Ready on [{hw_label}].")
            except Exception as e:
                print(f"[WARN] FaceAttribNet initialization failed: {e}")

    def _ensure_bgr_numpy(self, image_input):
        """Convert PIL Image or array to BGR OpenCV format."""
        if isinstance(image_input, Image.Image):
            rgb = np.array(image_input.convert('RGB'))
            import cv2
            return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        elif isinstance(image_input, np.ndarray):
            if image_input.ndim == 3 and image_input.shape[2] == 3:
                return image_input
        return None

    def detect_faces_only(self, image_input):
        """
        Fast Face Detection with 3D Pose, 3D Mesh (68 pts), Demographics, and Quality.
        Returns list of face dicts.
        """
        if self.app is None:
            return []

        img_bgr = self._ensure_bgr_numpy(image_input)
        if img_bgr is None:
            return []

        try:
            detected_faces = self.app.get(img_bgr)
            results = []
            for f in detected_faces:
                bbox_raw = getattr(f, 'bbox', None)
                if bbox_raw is None:
                    continue

                bbox = [int(round(v)) for v in bbox_raw[:4]]
                w = bbox[2] - bbox[0]
                h = bbox[3] - bbox[1]
                if w < self.min_face_size or h < self.min_face_size:
                    continue

                confidence = float(getattr(f, 'det_score', 1.0))
                if confidence < self.confidence_threshold:
                    continue

                landmarks = getattr(f, 'kps', None)
                landmarks_3d = getattr(f, 'landmark_3d_68', None)
                pose = getattr(f, 'pose', np.zeros(3))  # [pitch, yaw, roll]

                pitch = float(pose[0]) if len(pose) > 0 else 0.0
                yaw = float(pose[1]) if len(pose) > 1 else 0.0
                roll = float(pose[2]) if len(pose) > 2 else 0.0

                age = int(getattr(f, 'age', 0))
                gender_id = getattr(f, 'gender', -1)
                gender_str = "Erkek" if gender_id == 1 else ("Kadın" if gender_id == 0 else "")

                # Normalized ArcFace embedding (if computed by FaceAnalysis)
                emb = getattr(f, 'embedding', None)
                if emb is not None:
                    emb = emb.copy()
                    norm = np.linalg.norm(emb)
                    if norm > 0:
                        emb /= norm

                quality = self.calculate_quality(bbox, confidence, landmarks, yaw, pitch)

                results.append({
                    'bbox': bbox,
                    'confidence': confidence,
                    'landmarks': landmarks,
                    'landmarks_3d': landmarks_3d,
                    'yaw': yaw,
                    'pitch': pitch,
                    'roll': roll,
                    'age': age,
                    'gender': gender_str,
                    'embedding': emb,
                    'quality': quality
                })
            return results
        except Exception as e:
            print(f"[ERROR] detect_faces_only failed: {e}")
            return []

    def extract_embedding(self, image_input, landmarks=None):
        """
        Extract normalized 512-d ArcFace embedding from image.
        Uses ResNet50 (w600k_r50) matching database prototypes.
        """
        img_bgr = self._ensure_bgr_numpy(image_input)
        if img_bgr is None or self.app is None:
            return None

        try:
            faces = self.app.get(img_bgr)
            if faces:
                emb = faces[0].embedding.copy()
                norm = np.linalg.norm(emb)
                if norm > 0:
                    emb /= norm
                return emb
        except Exception as e:
            print(f"[ERROR] extract_embedding failed: {e}")
        return None

    def predict_attributes(self, image_input, bbox, landmarks=None, age=None, gender=None, yaw=0.0, pitch=0.0):
        """
        Predict Age, Gender, Eyeglasses, Sunglasses, and Mask.
        Accepts precomputed demographics/pose to avoid redundant FaceAnalysis passes.
        """
        img_bgr = self._ensure_bgr_numpy(image_input)
        if img_bgr is None:
            return {}

        attrs = {
            'age': age,
            'gender': gender,
            'eyeglasses': False,
            'sunglasses': False,
            'mask': False,
            'pitch': pitch,
            'yaw': yaw,
            'attr_text': ''
        }

        # 1. Fallback for Age, Gender & 3D Pose only if not precomputed
        if (attrs['age'] is None or attrs['gender'] is None) and self.app is not None:
            try:
                faces = self.app.get(img_bgr)
                if faces:
                    target_face = faces[0]
                    if len(faces) > 1 and bbox is not None:
                        cx = (bbox[0] + bbox[2]) / 2.0
                        cy = (bbox[1] + bbox[3]) / 2.0
                        target_face = min(faces, key=lambda f: (f.bbox[0]+f.bbox[2]-2*cx)**2 + (f.bbox[1]+f.bbox[3]-2*cy)**2)

                    if attrs['age'] is None:
                        attrs['age'] = int(target_face.age)
                    if attrs['gender'] is None:
                        attrs['gender'] = "Erkek" if target_face.gender == 1 else "Kadın"
                    if hasattr(target_face, 'pose') and len(target_face.pose) >= 2:
                        attrs['pitch'] = round(float(target_face.pose[0]), 1)
                        attrs['yaw'] = round(float(target_face.pose[1]), 1)
            except Exception:
                pass

        # 2. Eyeglasses & Mask from FaceAttribNet
        if self.attrib_model is not None and bbox is not None:
            try:
                lmk = landmarks if landmarks is not None else np.zeros((5, 2), dtype=np.float32)
                face_obj = Face(bbox=np.array(bbox, dtype=np.float32), confidence=1.0, landmarks=lmk)
                self.attrib_model.predict(img_bgr, face_obj)
                attrs['eyeglasses'] = bool(face_obj.eyeglasses is not None and face_obj.eyeglasses > 0.5)
                attrs['sunglasses'] = bool(face_obj.sunglasses is not None and face_obj.sunglasses > 0.5)
                attrs['mask'] = bool(face_obj.mask is not None and face_obj.mask > 0.5)
            except Exception:
                pass

        # Build clean Turkish display text
        parts = []
        if attrs['age']:
            parts.append(f"{attrs['age']} Yaş")
        if attrs['gender']:
            parts.append(attrs['gender'])
        if attrs['sunglasses']:
            parts.append("Güneş Gözlüklü")
        elif attrs['eyeglasses']:
            parts.append("Gözlüklü")
        else:
            parts.append("Gözlüksüz")
        if attrs['mask']:
            parts.append("Maskeli")

        attrs['attr_text'] = ", ".join(parts)
        return attrs

    def calculate_quality(self, bbox, confidence, landmarks, yaw, pitch):
        """Compute face quality score [0.0 - 1.0]."""
        try:
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
            size_score = min(1.0, max(0.2, (w * h) / (120 * 120)))
            pose_penalty = min(0.6, (abs(yaw) + abs(pitch)) / 50.0)
            pose_score = max(0.2, 1.0 - pose_penalty)
            conf_score = max(0.0, min(1.0, confidence))
            quality = float(conf_score * 0.5 + pose_score * 0.3 + size_score * 0.2)
            return round(min(1.0, max(0.0, quality)), 3)
        except Exception:
            return 0.5

    def compute_similarity(self, emb1, emb2):
        """Compute cosine similarity between two normalized 512-d embeddings."""
        if emb1 is None or emb2 is None:
            return 0.0
        emb1 = np.asarray(emb1, dtype=np.float32)
        emb2 = np.asarray(emb2, dtype=np.float32)
        norm1 = np.linalg.norm(emb1)
        norm2 = np.linalg.norm(emb2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return float(np.dot(emb1 / norm1, emb2 / norm2))

    def compute_max_similarity(self, probe_emb, gallery_embeddings):
        """Compute maximum cosine similarity between probe and gallery prototypes."""
        if probe_emb is None or not gallery_embeddings:
            return -1.0
        probe = np.asarray(probe_emb, dtype=np.float32)
        p_norm = np.linalg.norm(probe)
        if p_norm > 0:
            probe = probe / p_norm

        matrix = np.asarray(gallery_embeddings, dtype=np.float32)
        if matrix.ndim == 1:
            matrix = matrix.reshape(1, -1)

        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        matrix_norm = matrix / norms
        sims = np.dot(matrix_norm, probe)
        return float(np.max(sims))

    @staticmethod
    def draw_faces(image_pil, face_results, default_color=(0, 230, 118)):
        """
        Draw clean, modern HUD bounding boxes with multi-line badges on a PIL Image.
        Resolution-adaptive stroke widths and badge padding.
        """
        img_copy = image_pil.copy()
        draw = ImageDraw.Draw(img_copy)
        w, h = img_copy.size

        box_stroke = max(2, int(round(w / 450.0)))
        corner_stroke = max(4, int(round(w / 300.0)))
        corner_ratio = 0.20

        font_large = None
        font_small = None
        try:
            font_size_large = max(13, int(round(w / 75.0)))
            font_size_small = max(11, int(round(w / 95.0)))
            for font_name in ["segoeui.ttf", "arial.ttf", "calibri.ttf", "DejaVuSans.ttf"]:
                try:
                    font_large = ImageFont.truetype(font_name, font_size_large)
                    font_small = ImageFont.truetype(font_name, font_size_small)
                    break
                except Exception:
                    continue
        except Exception:
            pass

        if font_large is None:
            font_large = ImageFont.load_default()
            font_small = ImageFont.load_default()

        for item in face_results:
            bbox = item.get('bbox')
            if not bbox or len(bbox) < 4:
                continue

            x1, y1, x2, y2 = bbox
            name = item.get('name', item.get('label', ''))
            color = item.get('color', default_color)
            attr_text = item.get('attributes_text', '')

            # Clean, sleek bounding box
            draw.rectangle([x1, y1, x2, y2], outline=color, width=box_stroke)

            # Build clean label lines (No pose debug angles, no cyber jargon)
            lines = [name] if name else []
            if attr_text:
                clean_attr = attr_text.replace(', ', ' • ')
                lines.append(clean_attr)

            if lines:
                pad_x = 10
                pad_y = 6
                line_spacing = 3

                line_bboxes = []
                max_text_w = 0
                total_text_h = 0
                for idx, line in enumerate(lines):
                    f = font_large if idx == 0 else font_small
                    tb = draw.textbbox((0, 0), line, font=f)
                    lw = tb[2] - tb[0]
                    lh = tb[3] - tb[1]
                    line_bboxes.append((lw, lh, f))
                    max_text_w = max(max_text_w, lw)
                    total_text_h += lh
                total_text_h += line_spacing * (len(lines) - 1)

                badge_w = max_text_w + pad_x * 2
                badge_h = total_text_h + pad_y * 2

                if y1 - badge_h - 4 >= 0:
                    badge_y1 = y1 - badge_h - 4
                    badge_y2 = y1 - 4
                else:
                    badge_y1 = y2 + 4
                    badge_y2 = y2 + badge_h + 4

                badge_x1 = max(0, min(w - badge_w, x1))
                badge_x2 = badge_x1 + badge_w

                # Sleek dark pill container
                draw.rounded_rectangle([badge_x1, badge_y1, badge_x2, badge_y2], radius=6, fill=(15, 23, 42, 235), outline=color, width=1)

                curr_y = badge_y1 + pad_y
                for idx, (lw, lh, f) in enumerate(line_bboxes):
                    txt_color = (255, 255, 255) if idx == 0 else (203, 213, 225)
                    draw.text((badge_x1 + pad_x, curr_y), lines[idx], fill=txt_color, font=f)
                    curr_y += lh + line_spacing

        return img_copy

    @staticmethod
    def image_to_jpeg(image_pil, quality=80):
        """Convert a PIL Image to JPEG bytes for MJPEG streaming."""
        buffer = io.BytesIO()
        image_pil.save(buffer, format='JPEG', quality=quality)
        return buffer.getvalue()
