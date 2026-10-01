import unittest
import threading
import time
from control_plane import db

class TestCrossAssetAndSlotConcurrency(unittest.TestCase):
    def setUp(self):
        db.set_global_autonomous_enabled(True)
        # Reset slots for clean test run
        c = db._connect()
        with db._lock:
            c.execute("DELETE FROM autonomous_trade_slots")
            c.commit()
            
        # Create 3 slots with distinct asset scopes
        self.slot1_id = db.add_autonomous_trade_slot(
            name="Slot 1 - Crypto",
            allocated_margin_usdt=50.0,
            max_leverage=5,
            asset_scope="CRYPTO",
            enabled=True,
            user_id=1
        )
        self.slot2_id = db.add_autonomous_trade_slot(
            name="Slot 2 - US Market",
            allocated_margin_usdt=75.0,
            max_leverage=5,
            asset_scope="US_MARKET",
            strategy_scope="US_OVERNIGHT",
            enabled=True,
            user_id=1
        )
        self.slot3_id = db.add_autonomous_trade_slot(
            name="Slot 3 - Commodities",
            allocated_margin_usdt=100.0,
            max_leverage=10,
            asset_scope="COMMODITIES",
            enabled=True,
            user_id=1
        )

    def test_01_cross_asset_consumption(self):
        """Verify Slot 1 -> Crypto, Slot 2 -> US, Slot 3 -> Commodity, then release Slot 2."""
        # 1. Crypto candidate finds and occupies Slot 1
        crypto_slot = db.find_eligible_available_slot(asset_class="CRYPTO", symbol="BTC-USDT", user_id=1)
        self.assertIsNotNone(crypto_slot)
        self.assertEqual(crypto_slot["id"], self.slot1_id)
        self.assertEqual(crypto_slot["allocated_margin_usdt"], 50.0)
        self.assertTrue(db.reserve_autonomous_trade_slot(self.slot1_id, "CRYPTO-TRADE-1", user_id=1))
        self.assertTrue(db.occupy_autonomous_trade_slot(self.slot1_id, "POS-CRYPTO-1", user_id=1))

        # 2. US candidate finds and occupies Slot 2
        us_slot = db.find_eligible_available_slot(asset_class="US_MARKET", strategy="US_OVERNIGHT", symbol="NVDA", user_id=1)
        self.assertIsNotNone(us_slot)
        self.assertEqual(us_slot["id"], self.slot2_id)
        self.assertEqual(us_slot["allocated_margin_usdt"], 75.0)
        self.assertTrue(db.reserve_autonomous_trade_slot(self.slot2_id, "US-TRADE-1", user_id=1))
        self.assertTrue(db.occupy_autonomous_trade_slot(self.slot2_id, "POS-US-1", user_id=1))

        # 3. Commodity candidate finds and occupies Slot 3
        comm_slot = db.find_eligible_available_slot(asset_class="COMMODITIES", symbol="GOLD-USDT", user_id=1)
        self.assertIsNotNone(comm_slot)
        self.assertEqual(comm_slot["id"], self.slot3_id)
        self.assertEqual(comm_slot["allocated_margin_usdt"], 100.0)
        self.assertTrue(db.reserve_autonomous_trade_slot(self.slot3_id, "COMM-TRADE-1", user_id=1))
        self.assertTrue(db.occupy_autonomous_trade_slot(self.slot3_id, "POS-COMM-1", user_id=1))

        # 4. Verify all 3 are OCCUPIED
        summary = db.get_autonomous_trading_summary(user_id=1)
        self.assertEqual(summary["occupied_slots"], 3)
        self.assertEqual(summary["available_slots"], 0)
        self.assertEqual(summary["reserved_margin_usdt"], 225.0)

        # 5. Subsequent candidate has NO available slot
        extra_slot = db.find_eligible_available_slot(asset_class="US_MARKET", symbol="AAPL", user_id=1)
        self.assertIsNone(extra_slot)

        # 6. Close Slot 2 (US trade completes)
        self.assertTrue(db.release_autonomous_trade_slot(self.slot2_id, user_id=1))
        s2 = db.get_autonomous_trade_slot(self.slot2_id, user_id=1)
        self.assertEqual(s2["status"], "AVAILABLE")
        self.assertIsNone(s2["current_position_id"])

        # 7. Slot 2 can now accept another US candidate
        new_us_slot = db.find_eligible_available_slot(asset_class="US_MARKET", strategy="US_OVERNIGHT", symbol="AAPL", user_id=1)
        self.assertIsNotNone(new_us_slot)
        self.assertEqual(new_us_slot["id"], self.slot2_id)

    def test_02_concurrency_race_condition(self):
        """If one slot is available and 10 threads attempt reservation, EXACTLY ONE succeeds."""
        # Clean down to 1 available slot
        c = db._connect()
        with db._lock:
            c.execute("DELETE FROM autonomous_trade_slots")
            c.commit()
            
        single_slot_id = db.add_autonomous_trade_slot(
            name="Single Slot",
            allocated_margin_usdt=50.0,
            max_leverage=5,
            asset_scope="ALL",
            enabled=True,
            user_id=1
        )

        results = []
        threads = []

        def attempt_reservation(thread_idx):
            trade_id = f"RACE-TRADE-{thread_idx}"
            ok = db.reserve_autonomous_trade_slot(single_slot_id, trade_id, user_id=1)
            results.append(ok)

        for i in range(10):
            t = threading.Thread(target=attempt_reservation, args=(i,))
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Exactly 1 True, exactly 9 False
        successes = [r for r in results if r is True]
        failures = [r for r in results if r is False]
        self.assertEqual(len(successes), 1)
        self.assertEqual(len(failures), 9)

if __name__ == "__main__":
    unittest.main()
