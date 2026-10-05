import unittest
import sqlite3
import os
import sys

# Ensure root dir is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import (
    init_db,
    add_or_update_presence,
    get_active_presences,
    set_presence_status,
    get_setting,
    set_setting,
    get_db_connection
)

class TestPresenceDB(unittest.TestCase):
    def setUp(self):
        init_db()

    def test_presence_lifecycle(self):
        # 1. Yeni müşteri girişi
        pid = add_or_update_presence("Eren", "customer", "/static/profiles/eren.jpg")
        self.assertIsNotNone(pid)

        # 2. Aktif müşterileri listele
        presences = get_active_presences()
        waiting = [p for p in presences if p["status"] == "waiting_order" and p["user_name"] == "Eren"]
        self.assertEqual(len(waiting), 1)

        # 3. Sipariş alındı durumuna geçir
        set_presence_status(pid, "ordered", order_summary="Filtre Kahve, Kruvasan")
        presences_after = get_active_presences()
        ordered = [p for p in presences_after if p["status"] == "ordered" and p["user_name"] == "Eren"]
        self.assertEqual(len(ordered), 1)

        # 4. Çıkış yap
        set_presence_status(pid, "exited")
        presences_final = get_active_presences()
        remaining = [p for p in presences_final if p["id"] == pid]
        self.assertEqual(len(remaining), 0)

    def test_system_settings(self):
        set_setting("gemini_api_key", "test_key_12345")
        val = get_setting("gemini_api_key")
        self.assertEqual(val, "test_key_12345")

if __name__ == "__main__":
    unittest.main()
