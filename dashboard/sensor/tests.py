"""
실행:  cd dashboard && python manage.py test
"""
from django.test import Client, TestCase

from dataCollector import parse_line

from .models import Blend, DeviceStatus, StockEvent
from . import services


class ParseLineTests(TestCase):
    def test_board_lines(self):
        self.assertEqual(parse_line("STATUS : SCREEN_BLENDING").data["c_status"], "SCREEN_BLENDING")
        self.assertEqual(parse_line("MOOD : 2").data, {"mood_code": "2"})
        self.assertEqual(parse_line("PERFUME : Lavender : 4").data, {"name": "Lavender", "value": "4"})
        self.assertEqual(parse_line("PERFUME:Vanilla:1.5").data, {"name": "Vanilla", "value": "1.5"})
        self.assertEqual(parse_line("WATER_X : 3").data, {"sensor_id": "3"})
        self.assertEqual(parse_line("WATER_O : 1").data, {"sensor_id": "0"})

    def test_debug_lines_are_ignored(self):
        for line in ["", "System Ready.", "Waiting for OK (Rx_ID = 121)...", "MOOD : abc", "sensor_id: 1, rotation_ml: 8.00"]:
            self.assertIsNone(parse_line(line), line)


class BlendFlowTests(TestCase):
    """보드가 보내는 순서대로 이벤트를 넣었을 때 제조 기록이 맞게 쌓이는지"""

    def run_blend(self, mood, injections, end_screen="SCREEN_FINISH"):
        services.set_mood(mood)
        services.update_screen("SCREEN_CONFIRM")
        services.update_screen("SCREEN_BLENDING")
        for name, ml in injections:
            services.record_injection(name, ml)
        services.update_screen(end_screen)

    def test_completed_blend(self):
        self.run_blend(2, [("Lavender", 8), ("Cedarwood", 4), ("Vanilla", 2), ("Bergamot", 2)])
        blend = Blend.objects.get()
        self.assertTrue(blend.completed)
        self.assertEqual(blend.mood_code, 2)
        self.assertEqual(sum(i.ml for i in blend.injections.all()), 16)

        state = services.dashboard_state()
        self.assertEqual(state["today_count"], 1)
        self.assertEqual(state["recent_blends"][0]["total_ml"], 16)

    def test_aborted_blend(self):
        self.run_blend(4, [], end_screen="SCREEN_MOODSELECT")  # 향료 부족으로 바로 기분 선택으로 돌아감
        blend = Blend.objects.get()
        self.assertFalse(blend.completed)
        self.assertIsNotNone(blend.finished_at)

    def test_injection_does_not_mark_stock_low(self):
        """예전 버그: 1ml 를 주입하면 재고가 '부족'으로 기록됐다"""
        self.run_blend(1, [("Lavender", 1)])
        self.assertFalse(StockEvent.objects.exists())


class WaterTests(TestCase):
    def test_only_changes_are_recorded(self):
        services.record_water(0)
        services.record_water(0)
        self.assertEqual(StockEvent.objects.count(), 4)
        services.record_water(3)
        services.record_water(3)
        self.assertEqual(StockEvent.objects.count(), 5)
        self.assertTrue(services.latest_stock("Vanilla"))
        self.assertFalse(services.latest_stock("Lavender"))

    def test_unknown_sensor(self):
        with self.assertRaises(ValueError):
            services.record_water(9)


class EndpointTests(TestCase):
    def setUp(self):
        self.c = Client(enforce_csrf_checks=True)  # 보드용 엔드포인트는 CSRF 없이도 동작해야 함

    def test_device_endpoints(self):
        self.assertEqual(self.c.post("/sensor/setMood", {"mood_code": "6"}).status_code, 200)
        self.assertEqual(self.c.post("/sensor/setDeviceStatus", {"c_status": "SCREEN_BLENDING", "is_connected": "true"}).status_code, 200)
        self.assertEqual(self.c.post("/sensor/setPerfume", {"name": "Vanilla", "value": "8"}).status_code, 200)
        self.assertEqual(self.c.post("/sensor/setWaterStatus", {"sensor_id": "0"}).status_code, 200)

        state = self.c.get("/sensor/api/state").json()
        self.assertTrue(state["device"]["online"])
        self.assertEqual(state["mood"]["name"], "Cozy")
        self.assertEqual(state["current_blend"]["steps"][2]["injected_ml"], 8)
        self.assertNotIn("mock", state)

    def test_bad_input(self):
        self.assertEqual(self.c.post("/sensor/setMood", {"mood_code": "99"}).status_code, 400)
        self.assertEqual(self.c.post("/sensor/setPerfume", {"name": "Rose", "value": "1"}).status_code, 400)
        self.assertEqual(self.c.get("/sensor/setMood").status_code, 405)

    def test_heartbeat_keeps_screen(self):
        self.c.post("/sensor/setDeviceStatus", {"c_status": "SCREEN_FINISH", "is_connected": "true"})
        self.c.post("/sensor/setDeviceStatus", {"is_connected": "true"})
        self.assertEqual(DeviceStatus.current().screen, "SCREEN_FINISH")

    def test_mock_endpoints_need_mock_mode(self):
        r = Client().post("/sensor/api/mock/press", {"key": "tap"}, content_type="application/json")
        self.assertEqual(r.status_code, 404)

    def test_dashboard_page(self):
        r = self.c.get("/sensor/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("csrftoken", r.cookies)
