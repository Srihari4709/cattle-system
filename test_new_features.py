import unittest
import json
import io
from app import app
from database import init_db, seed_data, get_db_connection

class TestNewFeatures(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True
        # Authenticate session
        with self.app.session_transaction() as sess:
            sess['user_id'] = 1
            sess['username'] = 'cattleowner'
            sess['role'] = 'farmer'

    def test_feature_1_cattle_image_support(self):
        """Feature 1: Verify cattle profile accepts image URL or upload"""
        conn = get_db_connection()
        row = conn.execute("SELECT image_url FROM cattle WHERE id = 'KANG-001'").fetchone()
        conn.close()
        self.assertIsNotNone(row)
        self.assertTrue(len(row['image_url']) > 0)
        self.assertTrue(row['image_url'].startswith('http') or row['image_url'].startswith('/static/'))

    def test_feature_2_qr_code_identity(self):
        """Feature 2: QR Code generation and quick-view landing page"""
        # Test QR generation PNG
        res_qr = self.app.get('/cattle/KANG-001/qr')
        self.assertEqual(res_qr.status_code, 200)
        self.assertEqual(res_qr.content_type, 'image/png')
        self.assertTrue(len(res_qr.data) > 100)

        # Test quick-view mobile page
        res_view = self.app.get('/cattle/KANG-001/quick-view')
        self.assertEqual(res_view.status_code, 200)
        self.assertIn(b'Lakshmi', res_view.data)
        self.assertIn(b'KANG-001', res_view.data)

    def test_feature_3_voice_assistant(self):
        """Feature 3: Voice-Based Farmer Assistant NLP queries"""
        queries = [
            ("How is Lakshmi doing?", "Lakshmi"),
            ("Give me weather and heat risk", "THI"),
            ("What is the market price of milk today?", "41.20"),
            ("Show me farm waste and biogas", "biogas"),
            ("Which cattle need attention?", "alert"),
            ("Where is Gauri located?", "Gauri")
        ]

        for q, expected_token in queries:
            res = self.app.post('/api/voice-assistant', 
                                data=json.dumps({"query": q}),
                                content_type='application/json')
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertTrue(data.get("success"))
            self.assertIn("speech_text", data)
            self.assertTrue(len(data["speech_text"]) > 0)

    def test_feature_4_environment_aware_risk_score(self):
        """Feature 4: Weather Risk THI and Heat Stress calculation"""
        res = self.app.get('/api/weather-risk')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("thi", data)
        self.assertIn("risk_score", data)
        self.assertIn("risk_level", data)
        self.assertIn("advisory", data)
        self.assertTrue(0 <= data["risk_score"] <= 100)
        self.assertGreater(data["thi"], 0)

    def test_feature_5_market_timing_advisor(self):
        """Feature 5: Market Timing Advisor page and recommendations"""
        res = self.app.get('/market-timing')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Market Timing Advisor', res.data)
        self.assertIn(b'Optimal Window', res.data)
        self.assertIn(b'KANG-001', res.data)

    def test_feature_6_qr_gps_tracking(self):
        """Feature 6: Cost-efficient QR GPS Logging and Fleet map"""
        # Test GPS log post
        res_post = self.app.post('/cattle/KANG-001/log-gps', data={
            'latitude': 11.0080,
            'longitude': 77.5650,
            'location_name': 'Test Pasture Sector 4',
            'scanned_by': 'Unit Test Runner',
            'notes': 'Test GPS logging'
        })
        self.assertEqual(res_post.status_code, 200)
        data = res_post.get_json()
        self.assertTrue(data.get("success"))

        # Test GPS tracking fleet page
        res_page = self.app.get('/gps-tracking')
        self.assertEqual(res_page.status_code, 200)
        self.assertIn(b'Fleet', res_page.data)
        self.assertIn(b'Test Pasture Sector 4', res_page.data)

    def test_feature_7_alert_system_main_menu(self):
        """Feature 7: Alert system categorized warnings"""
        res = self.app.get('/alerts')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Vaccination Overdue', res.data)
        self.assertIn(b'Sudden Milk Production Decrease', res.data)
        self.assertIn(b'Declining Milk Production', res.data)
        self.assertIn(b'High Production But High Maintenance Cost', res.data)

    def test_feature_8_waste_recording(self):
        """Feature 8: Daily Dung & Organic Waste Logging"""
        res_post = self.app.post('/waste-management', data={
            'cattle_id': 'KANG-001',
            'record_date': '2026-08-27',
            'dung_weight_kg': 15.5,
            'urine_liters': 8.0,
            'notes': 'Test daily dung log'
        }, follow_redirects=True)
        self.assertEqual(res_post.status_code, 200)
        self.assertIn(b'15.5 kg', res_post.data)
        self.assertIn(b'Test daily dung log', res_post.data)

    def test_feature_9_waste_conversion_calculator(self):
        """Feature 9: Waste Conversion Calculator API for Biogas, Compost & LPG"""
        res = self.app.get('/waste-calculator?dung_kg=100&urine_l=50')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["dung_kg"], 100.0)
        self.assertEqual(data["biogas_m3"], 4.5)
        self.assertGreater(data["lpg_savings_rupees"], 0)
        self.assertEqual(data["compost_kg"], 35.0)
        self.assertEqual(data["liquid_fertilizer_liters"], 250.0)
        self.assertEqual(data["carbon_offset_kg_co2e"], 18.0)

    def test_feature_10_market_flash_news_ticker(self):
        """Feature 10: Milk values yesterday, today, and tomorrow ticker"""
        res = self.app.get('/dashboard')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Yesterday Milk:', res.data)
        self.assertIn(b'Today', res.data)
        self.assertIn(b'Tomorrow', res.data)
        self.assertIn(b'Kangeyam A2 Special Rate:', res.data)

if __name__ == '__main__':
    unittest.main()
