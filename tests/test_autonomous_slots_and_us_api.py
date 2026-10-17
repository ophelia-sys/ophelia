import unittest
import os
import time
from fastapi.testclient import TestClient
from control_plane import api, db, credential_vault

class TestAutonomousSlotsAndUsApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(api.app)
        
        # Ensure admin user (id=1)
        admin = db.get_user_by_id(1)
        if not admin:
            admin = db.create_google_user("admin_sub_001", "admin@ophelia.internal", "Ophelia Admin")
            c = db._connect()
            c.execute("UPDATE users SET role='ADMIN' WHERE id=?", (admin["id"],))
            c.commit()
            admin["role"] = "ADMIN"
        cls.admin_token = api.create_access_token({"sub": str(admin["id"]), "user_id": admin["id"], "role": "ADMIN"})
        cls.admin_headers = {"Authorization": f"Bearer {cls.admin_token}"}
        
        # Ensure standard user
        user = db.get_user_by_google_sub("user_sub_002")
        if not user:
            user = db.create_google_user("user_sub_002", "trader_real@ophelia.internal", "Real Trader")
        cls.user_id = user["id"]
        cls.user_token = api.create_access_token({"sub": str(user["id"]), "user_id": user["id"], "role": "USER"})
        cls.user_headers = {"Authorization": f"Bearer {cls.user_token}"}

    def test_01_god_eye_purge_and_overview(self):
        """God Eye returns only genuine users and zero synthetic ones."""
        res = self.client.get("/api/admin/god-eye/overview", headers=self.admin_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("summary", data)
        self.assertIn("users", data)
        
        # Ensure none of the users have mock or offline in name
        for u in data["users"]:
            name = (u.get("name") or "").lower()
            email = (u.get("email") or "").lower()
            self.assertNotIn("offline", name)
            self.assertNotIn("offline", email)
            self.assertNotIn("brother", name)
            self.assertNotIn("godeye", name)
            if u.get("bingx_connection") != "CONNECTED":
                # Must be None, not 0.0
                self.assertIsNone(u.get("balance"))

    def test_02_dynamic_slot_crud_and_scaling(self):
        """Admin can scale slots from 2 to 5 and delete back down."""
        # Clean up leftover test slots for user 1 to ensure idempotency and exactly 2 base slots
        db.ensure_default_user_slots(user_id=1)
        slots = db.get_autonomous_trade_slots(user_id=1)
        while len(slots) < 2:
            db.add_autonomous_trade_slot(name=f"Slot {len(slots)+1}", allocated_margin_usdt=50.0, user_id=1)
            slots = db.get_autonomous_trade_slots(user_id=1)
        while len(slots) > 2:
            db.delete_autonomous_trade_slot(slots[-1]["id"], user_id=1)
            slots = db.get_autonomous_trade_slots(user_id=1)

        # 1. Get initial slots
        res = self.client.get("/api/autonomous/slots", headers=self.admin_headers)
        self.assertEqual(res.status_code, 200)
        summary = res.json()
        initial_slots = summary["total_slots"]
        self.assertGreaterEqual(initial_slots, 2)
        
        # 2. Add Slot 3 (CRYPTO)
        res = self.client.post("/api/autonomous/slots", headers=self.admin_headers, json={
            "name": "Slot 3 - Crypto ML",
            "allocated_margin_usdt": 40.0,
            "max_leverage": 3,
            "asset_scope": "CRYPTO",
            "strategy_scope": "ALL",
            "enabled": True
        })
        self.assertEqual(res.status_code, 200)
        slot3_id = res.json()["slot_id"]
        
        # 3. Add Slot 4 (COMMODITIES)
        res = self.client.post("/api/autonomous/slots", headers=self.admin_headers, json={
            "name": "Slot 4 - Commodities ML",
            "allocated_margin_usdt": 100.0,
            "max_leverage": 10,
            "asset_scope": "COMMODITIES",
            "strategy_scope": "ALL",
            "enabled": True
        })
        self.assertEqual(res.status_code, 200)
        slot4_id = res.json()["slot_id"]
        
        # 4. Add Slot 5 (US_MARKET)
        res = self.client.post("/api/autonomous/slots", headers=self.admin_headers, json={
            "name": "Slot 5 - US Overnight",
            "allocated_margin_usdt": 60.0,
            "max_leverage": 5,
            "asset_scope": "US_MARKET",
            "strategy_scope": "US_OVERNIGHT",
            "enabled": True
        })
        self.assertEqual(res.status_code, 200)
        slot5_id = res.json()["slot_id"]
        
        # 5. Check updated summary
        res = self.client.get("/api/autonomous/slots", headers=self.admin_headers)
        summary = res.json()
        self.assertEqual(summary["total_slots"], initial_slots + 3)
        self.assertGreaterEqual(summary["total_authorized_margin_usdt"], 250.0)

        # 6. Atomic reservation and safety on Slot 3
        ok = db.reserve_autonomous_trade_slot(slot3_id, "TEST-TRADE-001")
        self.assertTrue(ok)
        db.occupy_autonomous_trade_slot(slot3_id, "POS-001")
        
        # 7. Attempt to delete occupied slot -> MUST FAIL
        res = self.client.delete(f"/api/autonomous/slots/{slot3_id}", headers=self.admin_headers)
        self.assertEqual(res.status_code, 400)
        
        # 8. Release Slot 3
        db.release_autonomous_trade_slot(slot3_id)
        
        # 9. Delete Slot 5, 4, 3
        res = self.client.delete(f"/api/autonomous/slots/{slot5_id}", headers=self.admin_headers)
        self.assertEqual(res.status_code, 200)
        self.client.delete(f"/api/autonomous/slots/{slot4_id}", headers=self.admin_headers)
        self.client.delete(f"/api/autonomous/slots/{slot3_id}", headers=self.admin_headers)

    def test_03_user_app_restrictions(self):
        """Standard user cannot modify slots or execute admin actions (403 Forbidden)."""
        # Clean up leftover slots for test user to ensure idempotency
        for s in db.get_autonomous_trade_slots(user_id=self.user_id):
            db.delete_autonomous_trade_slot(s["id"], user_id=self.user_id)

        # Attempt to add slot
        # Standard user CAN create their own autonomous trade slot within safety limits
        res = self.client.post("/api/autonomous/slots", headers=self.user_headers, json={
            "name": "User Slot 1",
            "allocated_margin_usdt": 50.0,
            "max_leverage": 5,
            "asset_scope": "CRYPTO",
            "strategy_scope": "ALL",
            "enabled": True
        })
        self.assertEqual(res.status_code, 200)
        user_slot_id = res.json()["slot_id"]
        
        # But standard user CANNOT exceed system safety limits (e.g. leverage > 10x fails with 400)
        res = self.client.post("/api/autonomous/slots", headers=self.user_headers, json={
            "name": "Dangerous Leverage Slot",
            "allocated_margin_usdt": 50.0,
            "max_leverage": 20,
            "asset_scope": "ALL",
            "enabled": True
        })
        self.assertEqual(res.status_code, 400)
        
        # Standard user CANNOT modify admin's slot (returns 404 because scoped to user)
        res = self.client.put("/api/autonomous/slots/1", headers=self.user_headers, json={
            "allocated_margin_usdt": 100.0
        })
        self.assertEqual(res.status_code, 404)
        
        # Attempt to toggle global master switch (403 Forbidden)
        res = self.client.post("/api/autonomous/toggle", headers=self.user_headers, json={"enabled": True})
        self.assertEqual(res.status_code, 403)
        
        # Attempt to execute manual US trade (403 Forbidden)
        res = self.client.post("/api/us/trade", headers=self.user_headers, json={
            "symbol": "NVDA",
            "direction": "LONG"
        })
        self.assertEqual(res.status_code, 403)
        
        # Standard user CAN read autonomous summary (with is_admin=False)
        res = self.client.get("/api/autonomous/slots", headers=self.user_headers)
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.json()["is_admin"])

    def test_04_us_market_endpoints(self):
        """Verify all US market intelligence endpoints."""
        # Overview
        res = self.client.get("/api/us/overview", headers=self.user_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("session", data)
        self.assertIn("market_regime", data)
        self.assertIn("data_health", data)
        
        # Top 100
        res = self.client.get("/api/us/top100", headers=self.user_headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["count"], 100)
        
        # Sectors
        res = self.client.get("/api/us/sectors", headers=self.user_headers)
        self.assertEqual(res.status_code, 200)
        self.assertIn("sectors", res.json())
        
        # News
        res = self.client.get("/api/us/news?limit=10", headers=self.user_headers)
        self.assertEqual(res.status_code, 200)
        self.assertIn("news", res.json())
        
        # Overnight setups
        res = self.client.get("/api/us/overnight", headers=self.user_headers)
        self.assertEqual(res.status_code, 200)
        self.assertIn("candidates", res.json())

if __name__ == "__main__":
    unittest.main()
