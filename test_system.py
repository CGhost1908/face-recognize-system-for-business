import os
import unittest
import numpy as np
from PIL import Image
import database
from database import init_db
from uniface_engine import UniFaceEngine
from recognition_service import RecognitionService
from recommendation_service import RecommendationService

TEST_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_database.db")


class TestCafeSystem(unittest.TestCase):

    def setUp(self):
        database.DEFAULT_DB_PATH = TEST_DB
        if os.path.exists(TEST_DB):
            try:
                os.remove(TEST_DB)
            except Exception:
                pass
        init_db(TEST_DB)

    def tearDown(self):
        if os.path.exists(TEST_DB):
            try:
                os.remove(TEST_DB)
            except Exception:
                pass

    def test_uniface_engine_and_similarity(self):
        engine = UniFaceEngine()
        emb1 = np.random.randn(512).astype(np.float32)
        emb1 /= np.linalg.norm(emb1)

        emb2 = emb1.copy()
        sim_identical = engine.compute_similarity(emb1, emb2)
        self.assertAlmostEqual(sim_identical, 1.0, places=4)

        emb3 = np.random.randn(512).astype(np.float32)
        emb3 /= np.linalg.norm(emb3)
        sim_diff = engine.compute_similarity(emb1, emb3)
        self.assertLess(sim_diff, 0.8)

    def test_guest_deduplication(self):
        engine = UniFaceEngine()
        rec_service = RecognitionService(uniface_engine=engine)
        rec_service.reload_embeddings()

        # Create dummy 512-d embedding for guest 1
        emb_guest1 = np.random.randn(512).astype(np.float32)
        emb_guest1 /= np.linalg.norm(emb_guest1)
        dummy_img = Image.new('RGB', (640, 480), color=(100, 100, 100))


        # Step 1: Candidate tracklet buffer confirmation (min 3-4 frames before registering)
        for i in range(4):
            name1, type1, sim1, _ = rec_service._identify_or_register_face(emb_guest1, dummy_img, [100, 100, 200, 200])
        
        # After tracklet confirmation, must be Guest_1
        self.assertEqual(name1, "Guest_1")

        # Step 2: Simulate 30 consecutive frames of Person 1 with head movements/noise/angle turns
        for i in range(30):
            noise = np.random.normal(0, 0.06, 512).astype(np.float32)
            head_turn_emb = emb_guest1 + noise
            head_turn_emb /= np.linalg.norm(head_turn_emb)
            
            # Slightly shift bounding box to simulate realistic head turns
            bbox_shift = [100 + (i % 5), 100 + (i % 3), 200 + (i % 5), 200 + (i % 3)]
            name_n, type_n, sim_n, _ = rec_service._identify_or_register_face(head_turn_emb, dummy_img, bbox_shift)
            self.assertEqual(name_n, "Guest_1", f"Failed on frame {i}: created unexpected duplicate {name_n}")

        # Step 3: Different person appears -> confirms as Guest_2 after tracklet
        emb_guest2 = np.random.randn(512).astype(np.float32)
        emb_guest2 /= np.linalg.norm(emb_guest2)
        for i in range(4):
            name2, type2, sim2, _ = rec_service._identify_or_register_face(emb_guest2, dummy_img, [400, 400, 500, 500])
        self.assertEqual(name2, "Guest_2")


    def test_recommendation_engine(self):
        rec_engine = RecommendationService()
        
        # Place order for "Ahmet" for 3x Espresso (product_id 1) and 1x Croissant (product_id 8)
        rec_engine.place_order("Ahmet", [
            {"product_id": 1, "quantity": 3},
            {"product_id": 8, "quantity": 1}
        ])

        # Get recommendations for "Ahmet"
        products_ahmet = rec_engine.get_products_for_user("Ahmet")
        
        # Top recommended product for Ahmet should be Espresso (product_id 1)
        self.assertEqual(products_ahmet[0]["id"], 1)
        self.assertTrue(products_ahmet[0]["is_recommended"])

    def test_flask_web_routes_and_json_login(self):
        from app import app, camera
        app.config['TESTING'] = True
        client = app.test_client()

        try:
            # Test GET /login (Must return 200 OK without TemplateNotFound error)
            res_login = client.get('/login')
            self.assertEqual(res_login.status_code, 200)

            # Test invalid JSON login (POST /api/login)
            res_invalid = client.post('/api/login', json={'username': 'admin', 'password': 'wrongpassword'})
            self.assertEqual(res_invalid.status_code, 400)
            self.assertFalse(res_invalid.json['success'])

            # Test valid JSON login (POST /api/login used by login.js)
            res_valid = client.post('/api/login', json={'username': 'admin', 'password': 'admin123'})
            self.assertEqual(res_valid.status_code, 200)
            self.assertTrue(res_valid.json['success'])

            # Test authenticated dashboard routes
            routes_to_test = [
                '/dashboard',
                '/dashboard/home',
                '/dashboard/camera',
                '/dashboard/customers',
                '/dashboard/products',
                '/dashboard/register',
                '/dashboard/reports',
                '/dashboard/settings',
            ]
            for route in routes_to_test:
                res = client.get(route)
                self.assertEqual(res.status_code, 200, f"Failed on route {route}")

            # Test API endpoints
            api_routes = [
                '/api/recognized_person',
                '/api/entry_logs',
                '/api/users',
                '/api/products',
                '/api/orders',
                '/api/stats',
                '/api/recognition_status'
            ]
            for api in api_routes:
                res = client.get(api)
                self.assertEqual(res.status_code, 200, f"Failed on API {api}")

            # Test Recognition Toggle Endpoint (Both AI and Camera hardware stop/start)
            res_toggle_off = client.post('/api/toggle_recognition', json={'enabled': False})
            self.assertEqual(res_toggle_off.status_code, 200)
            self.assertFalse(res_toggle_off.json['is_active'])
            self.assertFalse(camera.running, "Camera should stop running when recognition is toggled off")

            res_status = client.get('/api/recognition_status')
            self.assertEqual(res_status.status_code, 200)
            self.assertFalse(res_status.json['is_active'])

            res_toggle_on = client.post('/api/toggle_recognition', json={'enabled': True})
            self.assertEqual(res_toggle_on.status_code, 200)
            self.assertTrue(res_toggle_on.json['is_active'])
            self.assertTrue(camera.running, "Camera should start running when recognition is toggled on")
        finally:
            import app as app_module
            app_module.is_recognition_active = False
            camera.stop()

    def test_motion_gating_and_edge_pipeline(self):
        import time
        engine = UniFaceEngine()
        rec_service = RecognitionService(uniface_engine=engine)
        
        # Provide identical static frames
        static_frame = Image.new('RGB', (640, 480), color=(80, 90, 100))
        
        # First frame initializes motion baseline and model cache
        rec_service.process_frame(static_frame)
        
        # Consecutive static frame bypasses inference via motion filter (< 20ms vs 80-120ms normal inference)
        t0 = time.perf_counter()
        img_out, people = rec_service.process_frame(static_frame)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        
        self.assertEqual(people, [])
        self.assertLess(elapsed_ms, 20.0, f"Motion gate bypass was too slow ({elapsed_ms:.2f}ms), expected < 20ms")

    def test_disappearing_face_clears_active_tracks(self):
        """Verify that when a face leaves or is not detected, active_tracks and recognized_people are immediately cleared."""
        import time
        engine = UniFaceEngine()
        rec_service = RecognitionService(uniface_engine=engine)

        # Simulate a previously confirmed person in active_tracks
        rec_service._update_confirmed_track(150, 150, [100, 100, 200, 200], "Ahmet", "customer", time.time(), 0.98)
        self.assertEqual(len(rec_service.active_tracks), 1)

        # Process a frame where no face is present (plain gray frame)
        empty_frame = Image.new('RGB', (640, 480), color=(128, 128, 128))
        # Force frame_counter to trigger detection (counter % 2 == 0)
        rec_service.frame_counter = 1  # Next frame will be frame_counter = 2, triggering detect_faces_only
        annotated_img, people = rec_service.process_frame(empty_frame)

        # Must immediately return empty recognized_people and empty active_tracks
        self.assertEqual(people, [], "Expected empty people list when no face is found")
        self.assertEqual(len(rec_service.active_tracks), 0, "Expected active_tracks to be cleared immediately when no face is found")

        # Next frame (subsampling frame) must also not resurrect the ghost person
        annotated_img2, people2 = rec_service.process_frame(empty_frame)
        self.assertEqual(people2, [], "Ghost person was resurrected on subsequent frame")
        self.assertEqual(len(rec_service.active_tracks), 0, "active_tracks should stay empty")


if __name__ == '__main__':
    unittest.main()
