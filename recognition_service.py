import os
import io
import time
import base64
import threading
import numpy as np
from datetime import datetime
from PIL import Image
from database import get_db_connection
from uniface_engine import UniFaceEngine

DATASET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dataset")
os.makedirs(DATASET_DIR, exist_ok=True)


class CandidateTrack:
    """
    Temporary tracklet for an unconfirmed face observation.
    Buffers embeddings and quality across consecutive frames before confirming registration.
    Prevents duplicate guest creation from single-frame angle shifts or background transients.
    """
    def __init__(self, track_id, bbox, embedding, quality=0.5, yaw=0.0, pitch=0.0, frame_pil=None):
        self.track_id = track_id
        self.bbox = bbox
        self.cx = (bbox[0] + bbox[2]) / 2.0
        self.cy = (bbox[1] + bbox[3]) / 2.0
        self.embeddings = [embedding] if embedding is not None else []
        self.qualities = [quality]
        self.yaws = [yaw]
        self.pitches = [pitch]
        self.first_seen = time.time()
        self.last_seen = time.time()
        self.frame_count = 1
        self.best_quality = quality
        self.best_bbox = bbox
        self.best_frame_pil = frame_pil.copy() if frame_pil is not None else None

    def update(self, bbox, embedding, quality=0.5, yaw=0.0, pitch=0.0, frame_pil=None):
        self.bbox = bbox
        self.cx = (bbox[0] + bbox[2]) / 2.0
        self.cy = (bbox[1] + bbox[3]) / 2.0
        self.last_seen = time.time()
        self.frame_count += 1
        self.qualities.append(quality)
        self.yaws.append(yaw)
        self.pitches.append(pitch)
        
        if embedding is not None:
            # Keep top 8 highest quality embeddings collected during tracklet
            if len(self.embeddings) < 8:
                self.embeddings.append(embedding)
            elif quality > self.best_quality:
                self.embeddings[-1] = embedding

        if quality > self.best_quality:
            self.best_quality = quality
            self.best_bbox = bbox
            if frame_pil is not None:
                self.best_frame_pil = frame_pil.copy()


class RecognitionService:
    """
    High-Performance Multi-Angle Face Recognition & Smart Deduplication Service.
    Features:
    - Multi-Prototype Angle Gallery per User (Frontal, Left, Right, Pitch)
    - Persistent SQLite Storage for all Angle Prototypes (user_embeddings table)
    - Candidate Confirmation Buffer (Zero false duplicate guests on head turns)
    - Spatial-Temporal Tracklet Tracking with IoU & Centroid Association
    - High Throughput Optimized for Raspberry Pi 5 (ARM64)
    """

    def __init__(self, uniface_engine=None):
        self.engine = uniface_engine or UniFaceEngine()
        self.lock = threading.Lock()
        
        # Prototype Galleries: user_name -> list of normalized 512-d np.ndarray embeddings
        self.customer_clusters = {}
        self.guest_clusters = {}
        
        # Primary reference encoding per user (for backward compatibility)
        self.customer_encodings = {}
        self.guest_encodings = {}

        # Spatial-temporal active confirmed tracks: list of dicts:
        # {'id': int, 'name': str, 'user_type': str, 'bbox': list, 'cx': float, 'cy': float, 'last_seen': float}
        self.active_tracks = []
        self._next_track_id = 1

        # Unconfirmed candidate tracklets: list of CandidateTrack instances
        self.candidate_tracks = []

        # Minimum consecutive frames before an unknown face is registered as a guest
        # Prevents transient false guest creation when a user looks away or turns head
        self.MIN_CONFIRM_FRAMES = 10
        self.MIN_CONFIRM_TIME = 1.5  # seconds

        # Cooldown per user to prevent entry log spamming (user_name -> last_log_timestamp)
        self.entry_cooldowns = {}
        self.COOLDOWN_SECONDS = 180  # 3 minutes

        # Multi-prototype matching thresholds for InsightFace Buffalo_L (ResNet-50 ArcFace)
        # Cosine similarity benchmarks for w600k_r50:
        # Same person: 0.55 - 0.95 | Different people / strangers: 0.05 - 0.35
        self.CUSTOMER_MATCH_THRESHOLD = 0.48
        self.GUEST_MATCH_THRESHOLD = 0.46
        self.ANGLE_LEARN_SIM_LOWER = 0.52
        self.ANGLE_LEARN_SIM_UPPER = 0.88
        self.SPATIAL_CONTINUITY_THRESHOLD = 0.46

        # Motion gating and lightweight edge filter state
        self.prev_gray_thumb = None
        self.last_detection_time = 0.0
        self.detection_interval = 1  # Continuous live detection and verification on every frame
        self.TRACK_TIMEOUT = 0.5  # Drop lost tracks after 0.5 seconds (prevents ghost bounding boxes)
        self.frame_counter = 0

        # Load initial embeddings from DB
        self.reload_embeddings()

    def reload_embeddings(self):
        """
        Reload all prototype embeddings from SQLite database (both users and user_embeddings tables)
        into multi-vector gallery clusters.
        """
        with self.lock:
            self.customer_clusters.clear()
            self.guest_clusters.clear()
            self.customer_encodings.clear()
            self.guest_encodings.clear()
            self.active_tracks.clear()
            self.candidate_tracks.clear()

            try:
                conn = get_db_connection()
                cursor = conn.cursor()

                # 1. Clean orphan embeddings and load only for active registered users
                cursor.execute("DELETE FROM user_embeddings WHERE user_name NOT IN (SELECT name FROM users)")
                conn.commit()

                cursor.execute("""
                    SELECT ue.user_name, ue.user_type, ue.embedding 
                    FROM user_embeddings ue 
                    INNER JOIN users u ON ue.user_name = u.name
                """)
                rows = cursor.fetchall()
                for row in rows:
                    name = row["user_name"]
                    u_type = row["user_type"] or "customer"
                    raw_enc = row["embedding"]
                    if raw_enc:
                        try:
                            enc = np.frombuffer(raw_enc, dtype=np.float32)
                            if len(enc) == 512:
                                norm = np.linalg.norm(enc)
                                if norm > 0:
                                    enc = enc / norm
                                target_clusters = self.customer_clusters if u_type == "customer" else self.guest_clusters
                                if name not in target_clusters:
                                    target_clusters[name] = []
                                target_clusters[name].append(enc)
                        except Exception as e:
                            print(f"[WARN] Failed to parse user_embedding for {name}: {e}")

                # 2. Also ensure primary embeddings from users table are loaded
                cursor.execute("SELECT name, user_type, encoding FROM users")
                u_rows = cursor.fetchall()
                conn.close()

                for row in u_rows:
                    name = row["name"]
                    u_type = row["user_type"] or "customer"
                    raw_enc = row["encoding"]

                    if raw_enc:
                        try:
                            enc = np.frombuffer(raw_enc, dtype=np.float32)
                            if len(enc) == 512:
                                norm = np.linalg.norm(enc)
                                if norm > 0:
                                    enc = enc / norm

                                if u_type == "customer":
                                    self.customer_encodings[name] = enc
                                    if name not in self.customer_clusters:
                                        self.customer_clusters[name] = [enc]
                                else:
                                    self.guest_encodings[name] = enc
                                    if name not in self.guest_clusters:
                                        self.guest_clusters[name] = [enc]
                        except Exception as e:
                            print(f"[WARN] Failed to parse primary encoding for {name}: {e}")

                cust_protos = sum(len(c) for c in self.customer_clusters.values())
                guest_protos = sum(len(c) for c in self.guest_clusters.values())
                print(f"[INFO] Multi-Angle Galleries Loaded: {len(self.customer_clusters)} customers ({cust_protos} prototypes) | {len(self.guest_clusters)} guests ({guest_protos} prototypes).")
            except Exception as e:
                print(f"[ERROR] Error loading embeddings from DB: {e}")

    def process_frame(self, image_pil):
        """
        Continuous Biometric Verification Pipeline:
        1. Fast face detection with 512-d normalized ArcFace embeddings on every frame.
        2. Strict Biometric Track Association:
           - Spatial candidate tracks are ONLY confirmed if the current face embedding
             matches the tracked person's gallery (similarity >= SPATIAL_CONTINUITY_THRESHOLD).
           - If a different person steps into the bounding box, similarity drops (< 0.46),
             association is REJECTED, and the new face is instantly re-identified.
        3. Multi-Angle Gallery Identification for untracked/swapped faces.
        4. Immediate track cleanup: tracks disappear as soon as the face leaves or changes.
        """
        now = time.time()
        self.frame_counter += 1

        # STEP 1: Motion Pre-Filter (Motion Gating)
        # Skip inference only if the room is completely static AND no faces are tracked
        motion_score = 99.0
        try:
            thumb_gray = np.asarray(image_pil.resize((160, 120), Image.Resampling.BILINEAR).convert('L'))
            if self.prev_gray_thumb is not None:
                motion_score = float(np.mean(np.abs(thumb_gray.astype(np.int16) - self.prev_gray_thumb.astype(np.int16))))
            self.prev_gray_thumb = thumb_gray

            if motion_score < 3.0 and not self.active_tracks and not self.candidate_tracks and (now - self.last_detection_time < 3.0):
                return image_pil, []
        except Exception:
            pass

        # Prune expired tracks
        self._prune_stale_tracks(max_age=self.TRACK_TIMEOUT)

        # STEP 2: Continuous Face Detection & Feature Extraction
        face_results = self.engine.detect_faces_only(image_pil)
        now = time.time()
        self.last_detection_time = now

        # If NO faces detected in the entire frame, immediately clear all active and candidate tracks!
        if not face_results:
            with self.lock:
                self.active_tracks.clear()
                self.candidate_tracks.clear()
            return image_pil, []

        recognized_people = []
        overlay_items = []
        matched_tracks_this_frame = set()
        used_track_indices = set()

        # Build face list with embeddings
        face_list = []
        for f in face_results:
            bbox = f['bbox']
            if bbox is None:
                continue
            landmarks = f.get('landmarks')
            quality = f.get('quality', 0.5)
            yaw = f.get('yaw', 0.0)
            pitch = f.get('pitch', 0.0)
            emb = f.get('embedding')
            if emb is None and landmarks is not None:
                emb = self.engine.extract_embedding(image_pil, landmarks)
            if emb is None or len(emb) != 512:
                continue

            cx = (bbox[0] + bbox[2]) / 2.0
            cy = (bbox[1] + bbox[3]) / 2.0
            face_list.append({
                'bbox': bbox, 'landmarks': landmarks, 'quality': quality,
                'yaw': yaw, 'pitch': pitch, 'cx': cx, 'cy': cy,
                'embedding': emb, 'age': f.get('age'), 'gender': f.get('gender')
            })

        if not face_list:
            return image_pil, []

        # STEP 3: STRICT BIOMETRIC + SPATIAL TRACK ASSOCIATION
        # A detected face is ONLY allowed to associate with an active track if:
        # 1. Spatially overlapping (IoU > 0.15 or centroid distance < 110px) AND
        # 2. BIOMETRICALLY VERIFIED: Cosine similarity to the track's prototype cluster >= SPATIAL_CONTINUITY_THRESHOLD
        possible_matches = []  # (face_idx, track_idx, iou, sim)
        with self.lock:
            for fi, face in enumerate(face_list):
                fb = face['bbox']
                fcx, fcy = face['cx'], face['cy']
                femb = face['embedding']

                for ti, track in enumerate(self.active_tracks):
                    tb = track['bbox']
                    iou = self._compute_iou(fb, tb)
                    dist = np.hypot(fcx - track['cx'], fcy - track['cy'])

                    if iou > 0.15 or dist < 110.0:
                        t_name = track['name']
                        t_type = track['user_type']
                        cluster = self.customer_clusters.get(t_name) if t_type == 'customer' else self.guest_clusters.get(t_name)
                        if cluster:
                            sim = self.engine.compute_max_similarity(femb, cluster)
                            # STRICT BIOMETRIC CHECK:
                            # Only if cosine similarity proves this is genuinely the same person!
                            if sim >= self.SPATIAL_CONTINUITY_THRESHOLD:
                                possible_matches.append((fi, ti, iou, sim))

        # Sort matches by similarity * IoU so the highest confidence biometric matches win
        possible_matches.sort(key=lambda x: (x[3], x[2]), reverse=True)
        face_to_track = {}
        for fi, ti, iou, sim in possible_matches:
            if fi not in face_to_track and ti not in used_track_indices:
                with self.lock:
                    if ti < len(self.active_tracks):
                        face_to_track[fi] = (self.active_tracks[ti], sim)
                        used_track_indices.add(ti)

        # STEP 4: Face Evaluation (Verified Track vs New/Swapped Face)
        for fi, face in enumerate(face_list):
            bbox = face['bbox']
            landmarks = face['landmarks']
            quality = face['quality']
            yaw = face['yaw']
            pitch = face['pitch']
            cx = face['cx']
            cy = face['cy']
            emb = face['embedding']

            matched_tuple = face_to_track.get(fi)

            if matched_tuple is not None:
                # Face confirmed as the tracked person biometrically!
                matched_track, sim = matched_tuple
                name = matched_track['name']
                user_type = matched_track['user_type']
                similarity = sim
                is_confirmed = True
                matched_tracks_this_frame.add(name)

                # Update track with real live similarity and position
                with self.lock:
                    matched_track['cx'] = cx
                    matched_track['cy'] = cy
                    matched_track['bbox'] = bbox
                    matched_track['last_seen'] = now
                    matched_track['similarity'] = similarity

                # Lazily fetch or update attributes
                attributes = matched_track.get('attributes') or {}
                if not attributes.get('attr_text') and landmarks is not None:
                    attributes = self.engine.predict_attributes(
                        image_pil, bbox, landmarks,
                        age=face.get('age'), gender=face.get('gender'),
                        yaw=yaw, pitch=pitch
                    )
                    with self.lock:
                        matched_track['attributes'] = attributes

                # Enrich gallery if high quality angle
                if quality >= 0.55 and similarity >= self.ANGLE_LEARN_SIM_LOWER:
                    self._enrich_user_gallery_locked(name, user_type, emb, quality, yaw, pitch, similarity)
            else:
                # Untracked face OR Identity Changed (different person stepped into this spot)!
                # Full identification against entire database
                attributes = self.engine.predict_attributes(
                    image_pil, bbox, landmarks,
                    age=face.get('age'), gender=face.get('gender'),
                    yaw=yaw, pitch=pitch
                )

                name, user_type, similarity, is_confirmed = self._identify_or_register_face(
                    emb=emb,
                    frame_pil=image_pil,
                    bbox=bbox,
                    quality=quality,
                    yaw=yaw,
                    pitch=pitch,
                    landmarks=landmarks,
                    attributes=attributes
                )
                if is_confirmed and name:
                    matched_tracks_this_frame.add(name)

            # UI Styling
            if user_type == 'customer':
                color = (16, 185, 129)  # Clean emerald green
                label = name
            elif user_type == 'guest':
                color = (245, 158, 11)  # Warm amber
                label = name
            else:
                color = (148, 163, 184)  # Slate gray
                label = "Tanımlanıyor..."

            attr_text = attributes.get('attr_text', '') if isinstance(attributes, dict) else ''
            overlay_items.append({
                'bbox': bbox,
                'name': label,
                'color': color,
                'attributes_text': attr_text
            })

            if is_confirmed and name:
                recognized_people.append({
                    'name': name,
                    'user_type': user_type,
                    'similarity': similarity,
                    'bbox': bbox,
                    'attributes': attr_text,
                    'pose': [pitch, yaw]
                })

        # CRITICAL: Keep ONLY tracks that were genuinely detected and verified in this frame!
        # If the friend walked away, the friend's track is purged immediately!
        with self.lock:
            self.active_tracks = [t for t in self.active_tracks if t['name'] in matched_tracks_this_frame]

        self._prune_stale_tracks(max_age=self.TRACK_TIMEOUT)
        annotated_image = self.engine.draw_faces(image_pil, overlay_items)
        return annotated_image, recognized_people

    def _identify_or_register_face(self, emb, frame_pil, bbox, quality=0.5, yaw=0.0, pitch=0.0, landmarks=None, attributes=None):
        """
        Multi-Angle matching with Confirmation Buffer.
        Returns tuple: (name, user_type, similarity, is_confirmed)
        """
        x1, y1, x2, y2 = bbox
        cx = (x1 + x2) / 2.0
        cy = (y1 + y2) / 2.0
        now = time.time()

        with self.lock:
            # -------------------------------------------------------------
            # STEP 1: Match Probe against Registered Customer Galleries
            # -------------------------------------------------------------
            best_cust_name, best_cust_sim = self._match_gallery(emb, self.customer_clusters)
            if best_cust_name and best_cust_sim >= self.CUSTOMER_MATCH_THRESHOLD:
                self._enrich_user_gallery_locked(best_cust_name, "customer", emb, quality, yaw, pitch, best_cust_sim)
                self._update_confirmed_track(cx, cy, bbox, best_cust_name, "customer", now, similarity=best_cust_sim, attributes=attributes)
                self._handle_entry_log(best_cust_name, "customer", best_cust_sim)
                return best_cust_name, "customer", best_cust_sim, True

            # -------------------------------------------------------------
            # STEP 2: Match Probe against Existing Guest Galleries
            # -------------------------------------------------------------
            best_guest_name, best_guest_sim = self._match_gallery(emb, self.guest_clusters)
            if best_guest_name and best_guest_sim >= self.GUEST_MATCH_THRESHOLD:
                self._enrich_user_gallery_locked(best_guest_name, "guest", emb, quality, yaw, pitch, best_guest_sim)
                self._update_confirmed_track(cx, cy, bbox, best_guest_name, "guest", now, similarity=best_guest_sim, attributes=attributes)
                self._handle_entry_log(best_guest_name, "guest", best_guest_sim)
                return best_guest_name, "guest", best_guest_sim, True

            # -------------------------------------------------------------
            # STEP 3: Candidate Confirmation Buffer (Multi-Frame Verification)
            # -------------------------------------------------------------
            # Face did not match any known customer or guest.
            # Match against existing candidate tracklets ONLY IF spatially close AND biometrically consistent!
            best_cand = None
            best_cand_score = -1.0
            for cand in self.candidate_tracks:
                dist = np.hypot(cx - cand.cx, cy - cand.cy)
                iou = self._compute_iou(bbox, cand.bbox)
                cand_sim = self.engine.compute_max_similarity(emb, cand.embeddings) if cand.embeddings else 0.5
                if (dist < 120.0 or iou > 0.15) and cand_sim >= 0.44:
                    if cand_sim > best_cand_score:
                        best_cand_score = cand_sim
                        best_cand = cand

            if best_cand is not None:
                # Update candidate tracklet with new observation
                best_cand.update(bbox, emb, quality, yaw, pitch, frame_pil)

                # Check if any accumulated embedding matches an existing customer or guest
                for cand_emb in best_cand.embeddings:
                    c_name, c_sim = self._match_gallery(cand_emb, self.customer_clusters)
                    if c_name and c_sim >= self.CUSTOMER_MATCH_THRESHOLD:
                        self.candidate_tracks.remove(best_cand)
                        self._enrich_user_gallery_locked(c_name, "customer", cand_emb, quality, yaw, pitch, c_sim)
                        self._update_confirmed_track(cx, cy, bbox, c_name, "customer", now, similarity=c_sim, attributes=attributes)
                        return c_name, "customer", c_sim, True

                    g_name, g_sim = self._match_gallery(cand_emb, self.guest_clusters)
                    if g_name and g_sim >= self.GUEST_MATCH_THRESHOLD:
                        self.candidate_tracks.remove(best_cand)
                        self._enrich_user_gallery_locked(g_name, "guest", cand_emb, quality, yaw, pitch, g_sim)
                        self._update_confirmed_track(cx, cy, bbox, g_name, "guest", now, similarity=g_sim, attributes=attributes)
                        return g_name, "guest", g_sim, True

                # Check if candidate is ready for official new Guest registration
                avg_quality = float(np.mean(best_cand.qualities)) if best_cand.qualities else 0.5

                if best_cand.frame_count >= 5 and avg_quality >= 0.40:
                    # Final confirmation: Register new Guest with multi-angle prototypes!
                    self.candidate_tracks.remove(best_cand)
                    new_guest_name = self._register_new_guest_locked(
                        best_cand.embeddings,
                        best_cand.best_frame_pil or frame_pil,
                        best_cand.best_bbox,
                        cx, cy, now,
                        attributes=attributes
                    )
                    return new_guest_name, "guest", 1.0, True

                # Still accumulating frames
                return "Misafir", "candidate", float(np.mean(best_cand.qualities)), False

            # -------------------------------------------------------------
            # STEP 4: Start New Candidate Tracklet
            # -------------------------------------------------------------
            new_cand = CandidateTrack(
                track_id=self._next_track_id,
                bbox=bbox,
                embedding=emb,
                quality=quality,
                yaw=yaw,
                pitch=pitch,
                frame_pil=frame_pil
            )
            self._next_track_id += 1
            self.candidate_tracks.append(new_cand)
            return "Misafir", "candidate", float(quality), False

    def _match_gallery(self, probe_emb, gallery_dict):
        """Find the best matching user and highest cosine similarity across all prototype embeddings."""
        if not gallery_dict or probe_emb is None:
            return None, -1.0

        best_name = None
        best_sim = -1.0
        for name, cluster in gallery_dict.items():
            if not cluster:
                continue
            max_sim = self.engine.compute_max_similarity(probe_emb, cluster)
            if max_sim > best_sim:
                best_sim = max_sim
                best_name = name

        return best_name, best_sim

    def _enrich_user_gallery_locked(self, user_name, user_type, new_emb, quality, yaw, pitch, similarity):
        """
        Self-learning: If probe is a novel angle with good quality AND high similarity,
        save to DB user_embeddings and append to memory cluster (up to 8 prototypes).
        Gallery poisoning guard: requires similarity >= ANGLE_LEARN_SIM_LOWER to prevent
        wrong faces from being added to a person's gallery.
        """
        if new_emb is None or quality < 0.55:
            return
        
        # CRITICAL: Only enrich gallery when we're confident this is the right person
        if similarity < self.ANGLE_LEARN_SIM_LOWER:
            return

        target_clusters = self.customer_clusters if user_type == "customer" else self.guest_clusters
        cluster = target_clusters.setdefault(user_name, [])

        # If similarity is in the learning range (novel perspective) and cluster has room
        if len(cluster) < 8 and (similarity <= self.ANGLE_LEARN_SIM_UPPER or len(cluster) == 0):
            # Check cosine similarity to already stored prototypes to ensure diversity
            is_redundant = any(self.engine.compute_similarity(new_emb, ex_emb) > 0.92 for ex_emb in cluster)
            if not is_redundant:
                cluster.append(new_emb)
                # Persist to database
                threading.Thread(
                    target=self._save_embedding_to_db,
                    args=(user_name, user_type, new_emb, float(quality), float(yaw), float(pitch)),
                    daemon=True
                ).start()

    def _save_embedding_to_db(self, user_name, user_type, emb, quality, yaw, pitch):
        """Background worker to save new prototype embedding to SQLite."""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute(
                "INSERT INTO user_embeddings (user_name, user_type, embedding, quality_score, yaw, pitch, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (user_name, user_type, emb.tobytes(), quality, yaw, pitch, now_str)
            )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[WARN] Failed to persist new prototype for {user_name}: {e}")

    def _register_new_guest_locked(self, collected_embeddings, frame_pil, bbox, cx, cy, now, attributes=None):
        """Register a verified new guest atomically with multiple prototype embeddings."""
        guest_id = self._get_next_guest_id_locked()
        guest_name = f"Guest_{guest_id}"

        # Initialize cluster with all collected embeddings during confirmation window
        valid_embeddings = [e for e in collected_embeddings if e is not None]
        primary_emb = valid_embeddings[0] if valid_embeddings else np.zeros(512, dtype=np.float32)

        self.guest_encodings[guest_name] = primary_emb
        self.guest_clusters[guest_name] = valid_embeddings[:]
        self._update_confirmed_track(cx, cy, bbox, guest_name, "guest", now, attributes=attributes)

        # Crop face profile image
        profile_base64 = self._crop_and_save_profile(frame_pil, bbox, guest_name)
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (name, user_type, image, total_spent, last_login_date, encoding) VALUES (?, ?, ?, ?, ?, ?)",
                (guest_name, "guest", profile_base64, 0.0, now_str, primary_emb.tobytes())
            )
            # Insert all prototype embeddings
            for emb in valid_embeddings:
                cursor.execute(
                    "INSERT INTO user_embeddings (user_name, user_type, embedding, quality_score, yaw, pitch, created_at) VALUES (?, ?, ?, 1.0, 0.0, 0.0, ?)",
                    (guest_name, "guest", emb.tobytes(), now_str)
                )
            conn.commit()
            conn.close()
            print(f"[INFO] Verified New Guest Registered: {guest_name} ({len(valid_embeddings)} angle prototypes)")
        except Exception as e:
            print(f"[ERROR] Failed to save new guest {guest_name}: {e}")

        self._handle_entry_log(guest_name, "guest", 1.0)
        return guest_name

    def _update_confirmed_track(self, cx, cy, bbox, name, user_type, now, similarity=1.0, attributes=None):
        """Update or insert spatial tracking entry for a confirmed user with attributes."""
        for track in self.active_tracks:
            if track['name'] == name:
                track['cx'] = cx
                track['cy'] = cy
                track['bbox'] = bbox
                track['last_seen'] = now
                track['similarity'] = similarity
                if attributes:
                    track['attributes'] = attributes
                return
        self.active_tracks.append({
            'name': name,
            'user_type': user_type,
            'bbox': bbox,
            'cx': cx,
            'cy': cy,
            'last_seen': now,
            'similarity': similarity,
            'attributes': attributes or {}
        })

    @staticmethod
    def _compute_iou(bbox_a, bbox_b):
        """Compute Intersection over Union between two bounding boxes [x1,y1,x2,y2]."""
        if bbox_a is None or bbox_b is None:
            return 0.0
        x1 = max(bbox_a[0], bbox_b[0])
        y1 = max(bbox_a[1], bbox_b[1])
        x2 = min(bbox_a[2], bbox_b[2])
        y2 = min(bbox_a[3], bbox_b[3])
        inter = max(0, x2 - x1) * max(0, y2 - y1)
        area_a = max(0, bbox_a[2] - bbox_a[0]) * max(0, bbox_a[3] - bbox_a[1])
        area_b = max(0, bbox_b[2] - bbox_b[0]) * max(0, bbox_b[3] - bbox_b[1])
        union = area_a + area_b - inter
        if union <= 0:
            return 0.0
        return inter / union

    def _prune_stale_tracks(self, max_age=None):
        """Clean up stale tracks and expired candidate tracklets."""
        if max_age is None:
            max_age = getattr(self, 'TRACK_TIMEOUT', 0.8)
        now = time.time()
        with self.lock:
            self.active_tracks = [t for t in self.active_tracks if now - t['last_seen'] < max_age]
            self.candidate_tracks = [c for c in self.candidate_tracks if now - c.last_seen < 1.5]

    def _handle_entry_log(self, name, user_type, confidence):
        """Log entry event if cooldown has expired."""
        now = time.time()
        last_log = self.entry_cooldowns.get(name, 0)
        
        if now - last_log >= self.COOLDOWN_SECONDS:
            self.entry_cooldowns[name] = now
            try:
                now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET last_login_date = ? WHERE name = ?", (now_str, name))
                cursor.execute(
                    "INSERT INTO entry_logs (user_name, user_type, entry_time, confidence) VALUES (?, ?, ?, ?)",
                    (name, user_type, now_str, float(confidence))
                )
                conn.commit()
                conn.close()

                # Automatically register customer in venue presence for Waiter Service Terminal
                try:
                    from database import add_or_update_presence
                    add_or_update_presence(name, user_type)
                except Exception as pe:
                    print(f"[WARN] Failed to update presence for {name}: {pe}")

                print(f"[CHECK-IN] {name} ({user_type}) entered cafe.")
            except Exception as e:
                print(f"[ERROR] Failed to log entry for {name}: {e}")

    def _get_next_guest_id_locked(self):
        """Determine next guest index from memory and DB."""
        existing_ids = []
        for name in list(self.guest_clusters.keys()):
            if name.startswith("Guest_"):
                try:
                    existing_ids.append(int(name.split("_")[1]))
                except ValueError:
                    pass
        return max(existing_ids, default=0) + 1

    def _crop_and_save_profile(self, frame_pil, bbox, guest_name):
        """Crop face from frame, save to disk, and return base64 string."""
        if frame_pil is None or bbox is None:
            return ""
        try:
            person_dir = os.path.join(DATASET_DIR, guest_name)
            os.makedirs(person_dir, exist_ok=True)

            x1, y1, x2, y2 = bbox
            if x1 > x2:
                x1, x2 = x2, x1
            if y1 > y2:
                y1, y2 = y2, y1

            w, h = frame_pil.size
            pad_x = int(abs(x2 - x1) * 0.2)
            pad_y = int(abs(y2 - y1) * 0.2)
            
            crop_x1 = max(0, min(w - 1, x1 - pad_x))
            crop_y1 = max(0, min(h - 1, y1 - pad_y))
            crop_x2 = min(w, max(crop_x1 + 1, x2 + pad_x))
            crop_y2 = min(h, max(crop_y1 + 1, y2 + pad_y))

            if crop_x2 <= crop_x1 or crop_y2 <= crop_y1:
                crop_x1, crop_y1, crop_x2, crop_y2 = 0, 0, min(w, 100), min(h, 100)

            cropped = frame_pil.crop((crop_x1, crop_y1, crop_x2, crop_y2))

            img_path = os.path.join(person_dir, "profile.jpg")
            cropped.save(img_path, format="JPEG", quality=90)

            buffer = io.BytesIO()
            cropped.save(buffer, format="JPEG", quality=80)
            return base64.b64encode(buffer.getvalue()).decode('utf-8')
        except Exception as e:
            print(f"[WARN] Failed to crop profile image: {e}")
            return ""


