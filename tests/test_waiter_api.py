import unittest
import json
import os
import sys

# Ensure root dir is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from database import add_or_update_presence, get_active_presences, set_presence_status

class TestWaiterAPI(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_waiter_presence_and_status(self):
        # 1. Simüle varlık oluştur
        pid = add_or_update_presence("Eren", "customer")
        
        # 2. GET /api/waiter/presence
        res = self.client.get('/api/waiter/presence')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        self.assertIn("waiting", data)
        self.assertIn("ordered", data)

        # 3. POST /api/waiter/set_status (ordered yap)
        res_status = self.client.post('/api/waiter/set_status', json={
            "presence_id": pid,
            "status": "ordered",
            "order_summary": "Espresso"
        })
        self.assertEqual(res_status.status_code, 200)
        self.assertTrue(res_status.get_json().get("success"))

        # 4. GET /api/waiter/recommendations/Eren
        res_rec = self.client.get('/api/waiter/recommendations/Eren')
        self.assertEqual(res_rec.status_code, 200)
        rec_data = res_rec.get_json()
        self.assertIn("recommendations", rec_data)
        self.assertIn("waiter_pitch", rec_data)

        # 5. POST /api/waiter/create_order
        res_order = self.client.post('/api/waiter/create_order', json={
            "presence_id": pid,
            "user_name": "Eren",
            "items": [{"product_name": "Espresso", "quantity": 1, "price": 45.0}]
        })
        self.assertEqual(res_order.status_code, 200)
        self.assertTrue(res_order.get_json().get("success"))

        # 6. POST /api/waiter/notes
        res_notes = self.client.post('/api/waiter/notes', json={
            "presence_id": pid,
            "notes": "Cam kenarında oturuyor"
        })
        self.assertEqual(res_notes.status_code, 200)
        self.assertTrue(res_notes.get_json().get("success"))

        # 7. Temizle (exited yap)
        self.client.post('/api/waiter/set_status', json={
            "presence_id": pid,
            "status": "exited"
        })

if __name__ == "__main__":
    unittest.main()
