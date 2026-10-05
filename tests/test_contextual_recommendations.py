import unittest
import os
import sys

# Ensure root dir is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from recommendation_service import recommendation_service

class TestContextualRecommendations(unittest.TestCase):
    def test_hot_weather_recommendations(self):
        # 30 derece sıcak hava ve ikindi saatinde (16:00)
        res = recommendation_service.get_contextual_recommendations(
            user_name="Eren",
            weather_data={"temp": 30.0, "description": "Güneşli"},
            current_hour=16
        )
        self.assertIn("recommendations", res)
        self.assertIn("waiter_pitch", res)
        self.assertGreaterEqual(len(res["recommendations"]), 1)
        recs = res["recommendations"]
        badges = [r.get("reason_badge", "") for r in recs]
        self.assertTrue(any("Sıcak Hava" in b or "İkindi" in b or "Favori" in b for b in badges))

    def test_cold_morning_recommendations(self):
        # 10 derece soğuk hava ve sabah saatinde (09:00)
        res = recommendation_service.get_contextual_recommendations(
            user_name="Misafir #1",
            weather_data={"temp": 10.0, "description": "Soğuk ve Yağmurlu"},
            current_hour=9
        )
        self.assertIn("recommendations", res)
        self.assertIn("waiter_pitch", res)
        recs = res["recommendations"]
        badges = [r.get("reason_badge", "") for r in recs]
        self.assertTrue(any("Sabah" in b or "Soğuk Hava" in b or "Popüler" in b for b in badges))

if __name__ == "__main__":
    unittest.main()
