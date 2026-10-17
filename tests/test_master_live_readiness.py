import unittest
import time
import os
from fastapi.testclient import TestClient

from control_plane import api, db, opportunity_bus, position_manager_daemon, replication_orchestrator

class TestMasterLiveReadiness(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(api.app)
        
        # Admin user (id=1)
        cls.admin = db.get_user_by_id(1)
        if not cls.admin:
            cls.admin = db.create_google_user("admin_sub_001", "admin@ophelia.internal", "Ophelia Admin")
            c = db._connect()
            c.execute("UPDATE users SET role='ADMIN' WHERE id=?", (cls.admin["id"],))
            c.commit()
            cls.admin["role"] = "ADMIN"
        cls.admin_token = api.create_access_token({"sub": str(cls.admin["id"]), "user_id": cls.admin["id"], "role": "ADMIN"})
        cls.admin_headers = {"Authorization": f"Bearer {cls.admin_token}"}
        
        # User A (id=2)
        cls.user_a = db.get_user_by_google_sub("user_sub_002")
        if not cls.user_a:
            cls.user_a = db.create_google_user("user_sub_002", "usera@ophelia.internal", "User Alpha")
        cls.user_a_token = api.create_access_token({"sub": str(cls.user_a["id"]), "user_id": cls.user_a["id"], "role": "USER"})
        cls.user_a_headers = {"Authorization": f"Bearer {cls.user_a_token}"}

        # User B (id=3)
        cls.user_b = db.get_user_by_google_sub("user_sub_003")
        if not cls.user_b:
            cls.user_b = db.create_google_user("user_sub_003", "userb@ophelia.internal", "User Beta")
        cls.user_b_token = api.create_access_token({"sub": str(cls.user_b["id"]), "user_id": cls.user_b["id"], "role": "USER"})
        cls.user_b_headers = {"Authorization": f"Bearer {cls.user_b_token}"}

    def test_01_user_autonomous_slot_lifecycle_and_safety_bounds(self):
        """Users can manage their own slots; server strictly enforces bounds."""
        uid = self.user_a["id"]
        # Delete pre-existing non-occupied slots for user A
        for s in db.get_autonomous_trade_slots(user_id=uid):
            if s["status"] == "AVAILABLE":
                db.delete_autonomous_trade_slot(s["id"], user_id=uid)

        # 1. Create Slot 1 (50 USDT, 5x, CRYPTO, max loss 10%)
        res = self.client.post("/api/autonomous/slots", headers=self.user_a_headers, json={
            "name": "Slot 1 - BTC/ETH",
            "allocated_margin_usdt": 50.0,
            "max_leverage": 5,
            "asset_scope": "CRYPTO",
            "max_loss_pct": 10.0,
            "tp1_pct": 50.0,
            "breakeven_enabled": True,
            "trailing_enabled": True,
            "slot_mode": "BOTH"
        })
        self.assertEqual(res.status_code, 200)
        s1_id = res.json()["slot_id"]
        self.assertGreater(s1_id, 0)

        # 2. Reject leverage > 10x
        res = self.client.post("/api/autonomous/slots", headers=self.user_a_headers, json={
            "name": "Greedy Slot",
            "allocated_margin_usdt": 50.0,
            "max_leverage": 25,
            "asset_scope": "CRYPTO"
        })
        self.assertEqual(res.status_code, 400)

        # 3. Reject margin > 1000 USDT
        res = self.client.post("/api/autonomous/slots", headers=self.user_a_headers, json={
            "name": "Whale Slot",
            "allocated_margin_usdt": 1500.0,
            "max_leverage": 5,
            "asset_scope": "CRYPTO"
        })
        self.assertEqual(res.status_code, 400)

        # 4. User B cannot see User A's slots in their own list
        res = self.client.get("/api/autonomous/slots", headers=self.user_b_headers)
        self.assertEqual(res.status_code, 200)
        user_b_slot_ids = [s["id"] for s in res.json().get("slots", [])]
        self.assertNotIn(s1_id, user_b_slot_ids)

    def test_02_ml_margin_rule_deterministic_enforcement(self):
        """ML suggested margin (e.g. 500 USDT) NEVER overrides slot margin (50 USDT)."""
        uid = self.user_a["id"]
        # Ensure user A has a slot
        slot = db.find_eligible_available_slot(asset_class="CRYPTO", symbol="BTC-USDT", user_id=uid)
        if not slot:
            s_id = db.add_autonomous_trade_slot("CRYPTO SLOT", 50.0, 5.0, "CRYPTO", user_id=uid)
            slot = db.get_autonomous_trade_slot(s_id, user_id=uid)

        slot_id = slot["id"]
        expected_margin = float(slot["allocated_margin_usdt"])

        # Create opportunity where ML recommends 500 USDT
        opp = opportunity_bus.OpheliaOpportunity(
            candidate_id=f"test_ml_opp_{int(time.time()*1000)}",
            asset_class="CRYPTO",
            symbol="BTC-USDT",
            bingx_symbol="BTC-USDT",
            direction="LONG",
            strategy="BREAKOUT_RETEST_CVD",
            entry_price=65000.0,
            sl_price=64000.0,
            tp1_price=66500.0,
            tp2_price=68000.0,
            recommended_margin=500.0, # ML trying to suggest 500
            causal_score=88.5
        )

        # Dispatch
        res = opportunity_bus.dispatch_opportunity_to_user_slot(opp, user_id=uid)
        self.assertEqual(res.get("status"), "EXECUTED")
        # Margin strictly matches slot policy (50 USDT), NOT ML (500 USDT)
        self.assertEqual(res["authorized_margin_usdt"], expected_margin)
        self.assertEqual(res["slot_id"], slot_id)
        pos_id = res["position_id"]

        # Verify slot is OCCUPIED
        updated_slot = db.get_autonomous_trade_slot(slot_id, user_id=uid)
        self.assertEqual(updated_slot["status"], "OCCUPIED")

        # Clean up by closing position and releasing slot
        db.update_position(pos_id, status="CLOSED")
        db.release_autonomous_trade_slot(slot_id, user_id=uid)
        released_slot = db.get_autonomous_trade_slot(slot_id, user_id=uid)
        self.assertEqual(released_slot["status"], "AVAILABLE")

    def test_03_autonomous_position_manager_lifecycle(self):
        """Test full VPS-side lifecycle: TP1 50% partial close, breakeven move, dynamic trailing, exit & slot release."""
        uid = self.user_a["id"]
        slot = db.find_eligible_available_slot("CRYPTO", "BTC-USDT", user_id=uid)
        if not slot:
            s_id = db.add_autonomous_trade_slot("TEST SLOT", 50.0, 5.0, "CRYPTO", user_id=uid)
            slot = db.get_autonomous_trade_slot(s_id, user_id=uid)
        slot_id = slot["id"]

        # Reserve and occupy slot with a synthetic test position
        db.reserve_autonomous_trade_slot(slot_id, "TEST-PM-01", user_id=uid)
        pos_id = db.create_position({
            "symbol": "BTC-USDT",
            "direction": "LONG",
            "entry": 60000.0,
            "qty": 0.01,
            "margin_usdt": 50.0,
            "leverage": 5.0,
            "stops": [{"type": "price", "value": 59000.0}],
            "targets": [{"price": 62000.0, "pct_qty": 50.0}],
            "stop_current": 59000.0,
            "status": "OPEN",
            "source": "AUTONOMOUS_SLOT",
            "mode": "SHADOW",
            "detail": {
                "slot_id": slot_id,
                "trailing_enabled": True,
                "trailing_pct": 1.5,
                "breakeven_enabled": True,
                "tp1_pct": 50.0
            }
        }, user_id=uid)
        db.occupy_autonomous_trade_slot(slot_id, str(pos_id), user_id=uid)

        # Step 1: Price hits TP1 (62000) -> 50% partial close + breakeven move
        market_feed = {"BTC-USDT": 62100.0}
        actions = position_manager_daemon.evaluate_and_manage_positions(market_data_feed=market_feed, is_mock=True)
        tp1_action = next((a for a in actions if a.get("position_id") == pos_id and a.get("action") == "partial_close"), None)
        self.assertIsNotNone(tp1_action)
        self.assertAlmostEqual(tp1_action["new_quantity"], 0.005, places=4)
        self.assertTrue(tp1_action["breakeven_applied"])
        self.assertGreater(tp1_action["new_stop"], 60000.0) # True cost basis > entry for LONG

        # Step 2: Dynamic Trailing Stop Advances as price rallies to 64000
        market_feed["BTC-USDT"] = 64000.0
        trail_actions = position_manager_daemon.evaluate_and_manage_positions(market_data_feed=market_feed, is_mock=True)
        trail_action = next((a for a in trail_actions if a.get("position_id") == pos_id and a.get("action") == "trailing_stop_advanced"), None)
        self.assertIsNotNone(trail_action)
        self.assertGreater(trail_action["new_stop"], 62000.0)

        # Step 3: Price collapses below trailing stop -> Position exits and slot released
        market_feed["BTC-USDT"] = 61000.0
        exit_actions = position_manager_daemon.evaluate_and_manage_positions(market_data_feed=market_feed, is_mock=True)
        exit_action = next((a for a in exit_actions if a.get("position_id") == pos_id and a.get("action") == "exit_all"), None)
        self.assertIsNotNone(exit_action)

        # Verify slot is back to AVAILABLE
        final_slot = db.get_autonomous_trade_slot(slot_id, user_id=uid)
        self.assertEqual(final_slot["status"], "AVAILABLE")

    def test_04_cross_market_opportunity_bus_ranking(self):
        """Cross-market ranking evaluates Crypto, Commodities, and US Market together."""
        opps = [
            opportunity_bus.OpheliaOpportunity("opp_eth", "CRYPTO", "ETH-USDT", "ETH-USDT", "LONG", "BREAKOUT", 3000, 2900, 3150, 3300, causal_score=72.0),
            opportunity_bus.OpheliaOpportunity("opp_gold", "COMMODITIES", "GOLD (XAU)", "GOLD-USDT", "LONG", "REGIME", 2500, 2480, 2530, 2560, causal_score=81.0),
            opportunity_bus.OpheliaOpportunity("opp_nvda", "US_MARKET", "NVDA", "NVDA.USDT", "LONG", "US_OVERNIGHT", 125, 120, 132, 140, causal_score=89.0),
        ]
        ranked = opportunity_bus.rank_cross_market_candidates(opps)
        self.assertEqual(len(ranked), 3)
        # Highest composite causal score first (NVDA 89.0 > GOLD 81.0 > ETH 72.0)
        self.assertEqual(ranked[0].symbol, "NVDA")
        self.assertEqual(ranked[1].symbol, "GOLD (XAU)")
        self.assertEqual(ranked[2].symbol, "ETH-USDT")

    def test_05_trade_replication_capacity_and_isolation(self):
        """Follower slot capacity enforces 'BLOCKED — NO FREE COPY SLOT' and user capital isolation."""
        user_b_id = self.user_b["id"]
        # Enable copy trading for user B
        db.update_user_copy_enabled(user_b_id, True)
        db.update_admin_copy_allowed(user_b_id, True)

        # Ensure User B has 0 AVAILABLE slots
        for s in db.get_autonomous_trade_slots(user_id=user_b_id):
            db.delete_autonomous_trade_slot(s["id"], user_id=user_b_id)

        master_trade = {
            "master_trade_id": f"master_{int(time.time()*1000)}",
            "symbol": "BTC-USDT",
            "asset_class": "CRYPTO",
            "direction": "LONG",
            "entry_price": 60000.0,
            "sl_price": 59000.0,
            "tp1_price": 61500.0,
            "admin_margin_selected": 200.0,
            "admin_balance_snapshot": 5000.0
        }

        # Attempt replication when user B has no available slots
        res = replication_orchestrator.replicate_master_trade(master_trade, is_mock=True)
        user_b_res = next((r for r in res if r["user_id"] == user_b_id), None)
        self.assertIsNotNone(user_b_res)
        self.assertEqual(user_b_res["status"], "BLOCKED")
        self.assertEqual(user_b_res["blocked_reason"], "BLOCKED — NO FREE COPY SLOT")

        # Now add an enabled slot for User B (75 USDT margin, 5x leverage)
        s_id = db.add_autonomous_trade_slot("B-COPY-SLOT", 75.0, 5.0, "CRYPTO", slot_mode="COPY_OPHELIA", user_id=user_b_id)

        # Re-run replication
        res2 = replication_orchestrator.replicate_master_trade(master_trade, is_mock=True)
        user_b_res2 = next((r for r in res2 if r["user_id"] == user_b_id), None)
        self.assertIsNotNone(user_b_res2)
        self.assertIn(user_b_res2["status"], ("EXECUTED", "FILLED"))
        # Follower margin strictly matches user B's slot (75 USDT), NOT master margin (200 USDT)
        self.assertEqual(user_b_res2["allocated_margin"], 75.0)

        # Clean up
        db.delete_autonomous_trade_slot(s_id, user_id=user_b_id)

    def test_06_live_safety_gates_endpoint(self):
        """API live-gates endpoint audits all safety checks and locks live execution behind explicit gate."""
        res = self.client.get("/api/system/live-gates", headers=self.user_a_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["total_gates"], 19)
        # live_permission_explicitly_on is False by default
        self.assertEqual(data["mode"], "SHADOW_READY")
        self.assertFalse(data["all_gates_passed"])

if __name__ == "__main__":
    unittest.main()
