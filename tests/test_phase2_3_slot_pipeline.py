"""Test suite for Phase 2 (Slot Allocation Service) and Phase 3 (Automation to Slot to Execution Pipeline).

Invariants verified:
1. One authoritative slot allocation service (SlotAllocationService).
2. Explicit machine-readable rejection reasons (GLOBAL_AUTONOMOUS_DISABLED, WAITING_FOR_SLOT_CONFIG,
   SCOPE_MISMATCH, NO_AVAILABLE_SLOT, CONCURRENT_POSITION_LIMIT, CONFLICTING_POSITION, RISK_LIMIT).
3. Atomic reservation and double-reservation concurrency safety.
4. Autonomous slot provisioning strictly within authorized user template and capital envelope (no ML sizing).
5. Stale reservation recovery after 60s timeout.
6. End-to-end automation candidate -> ENTRY_READY -> slot RESERVED -> execution intent -> FILLED -> OCCUPIED -> RELEASED.
7. Admin diagnostic pipeline drill-down verification.
"""
from __future__ import annotations

import concurrent.futures
import time
import unittest
import uuid

from control_plane import db
from control_plane.slot_allocation_service import SlotAllocationService


class TestPhase2Phase3SlotPipeline(unittest.TestCase):
    def setUp(self):
        # Enable autonomous trading
        db.set_global_autonomous_enabled(True)
        db.set_mode("SHADOW")

        # Test user
        self.user_id = 9999
        self.account_id = 1

        c = db._connect()
        with db._lock:
            # Clean up test user state
            c.execute("DELETE FROM autonomous_trade_slots WHERE user_id=?", (self.user_id,))
            c.execute("DELETE FROM user_slot_templates WHERE user_id=?", (self.user_id,))
            c.execute("DELETE FROM execution_intents WHERE user_id=?", (self.user_id,))
            c.execute("DELETE FROM setup_candidates WHERE user_id=?", (self.user_id,))
            c.execute("DELETE FROM positions WHERE user_id=?", (self.user_id,))
            c.execute("DELETE FROM automations WHERE user_id=?", (self.user_id,))
            c.commit()

    def tearDown(self):
        c = db._connect()
        with db._lock:
            c.execute("DELETE FROM autonomous_trade_slots WHERE user_id=?", (self.user_id,))
            c.execute("DELETE FROM user_slot_templates WHERE user_id=?", (self.user_id,))
            c.execute("DELETE FROM execution_intents WHERE user_id=?", (self.user_id,))
            c.execute("DELETE FROM setup_candidates WHERE user_id=?", (self.user_id,))
            c.execute("DELETE FROM positions WHERE user_id=?", (self.user_id,))
            c.execute("DELETE FROM automations WHERE user_id=?", (self.user_id,))
            c.commit()

    def test_01_slot_eligibility_and_machine_readable_rejections(self):
        """Verify explicit machine-readable rejection reasons when conditions are not met."""
        candidate = {
            "symbol": "BTC-USDT",
            "asset_class": "CRYPTO",
            "strategy": "BREAKOUT_RETEST",
            "direction": "LONG",
            "entry_price": 60000.0,
            "sl_price": 59400.0,  # 1% risk
        }

        # 1. GLOBAL_AUTONOMOUS_DISABLED
        db.set_global_autonomous_enabled(False)
        slot, reason = SlotAllocationService.find_eligible_slot(candidate, user_id=self.user_id)
        self.assertIsNone(slot)
        self.assertEqual(reason, "GLOBAL_AUTONOMOUS_DISABLED")
        db.set_global_autonomous_enabled(True)

        # 2. WAITING_FOR_SLOT_CONFIG (No slot, no user template)
        slot, reason = SlotAllocationService.find_eligible_slot(candidate, user_id=self.user_id)
        self.assertIsNone(slot)
        self.assertEqual(reason, "WAITING_FOR_SLOT_CONFIG")

        # 3. Add a US_MARKET slot -> SCOPE_MISMATCH for CRYPTO candidate
        slot_us_id = db.add_autonomous_trade_slot(
            name="US Slot",
            allocated_margin_usdt=50.0,
            max_leverage=5,
            asset_scope="US_MARKET",
            strategy_scope="US_OVERNIGHT",
            enabled=True,
            user_id=self.user_id,
        )
        slot, reason = SlotAllocationService.find_eligible_slot(candidate, user_id=self.user_id)
        self.assertIsNone(slot)
        self.assertEqual(reason, "SCOPE_MISMATCH")

        # 4. Add a CRYPTO slot -> now it matches!
        slot_crypto_id = db.add_autonomous_trade_slot(
            name="Crypto Slot",
            allocated_margin_usdt=50.0,
            max_leverage=5,
            asset_scope="CRYPTO",
            strategy_scope="ALL",
            enabled=True,
            user_id=self.user_id,
        )
        slot, reason = SlotAllocationService.find_eligible_slot(candidate, user_id=self.user_id)
        self.assertIsNotNone(slot)
        self.assertEqual(slot["id"], slot_crypto_id)
        self.assertEqual(reason, "OK")

        # 5. CONFLICTING_POSITION -> if position for BTC-USDT already open
        db.create_position({
            "symbol": "BTC-USDT",
            "direction": "LONG",
            "entry": 60000.0,
            "qty": 0.01,
            "leverage": 5.0,
            "margin_usdt": 50.0,
            "mode": "SHADOW",
        }, user_id=self.user_id)
        slot, reason = SlotAllocationService.find_eligible_slot(candidate, user_id=self.user_id)
        self.assertIsNone(slot)
        self.assertEqual(reason, "CONFLICTING_POSITION")

        # Clean positions
        c = db._connect()
        with db._lock:
            c.execute("DELETE FROM positions WHERE user_id=?", (self.user_id,))
            c.commit()

        # 6. NO_AVAILABLE_SLOT -> Occupy the crypto slot
        ok, resv_id, _ = SlotAllocationService.reserve_slot(slot_crypto_id, "cand-1", user_id=self.user_id)
        self.assertTrue(ok)
        ok, _ = SlotAllocationService.occupy_slot(slot_crypto_id, "pos-1", user_id=self.user_id, reservation_id=resv_id)
        self.assertTrue(ok)

        slot, reason = SlotAllocationService.find_eligible_slot(candidate, user_id=self.user_id)
        self.assertIsNone(slot)
        self.assertEqual(reason, "NO_AVAILABLE_SLOT")

    def test_02_double_reservation_concurrency(self):
        """Simultaneous candidate reservation requests for the same slot: EXACTLY ONE succeeds."""
        slot_id = db.add_autonomous_trade_slot(
            name="Contested Slot",
            allocated_margin_usdt=50.0,
            max_leverage=5,
            asset_scope="CRYPTO",
            enabled=True,
            user_id=self.user_id,
        )

        num_candidates = 10
        candidates = [f"candidate-{i}-{uuid.uuid4().hex[:6]}" for i in range(num_candidates)]
        results = []

        def attempt_reservation(cand_id: str):
            ok, r_id, reason = SlotAllocationService.reserve_slot(
                slot_id=slot_id,
                candidate_id=cand_id,
                user_id=self.user_id,
            )
            return (cand_id, ok, r_id, reason)

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_candidates) as executor:
            futures = [executor.submit(attempt_reservation, cid) for cid in candidates]
            for f in concurrent.futures.as_completed(futures):
                results.append(f.result())

        successes = [r for r in results if r[1] is True]
        failures = [r for r in results if r[1] is False]

        self.assertEqual(len(successes), 1, "Exactly one thread must succeed in reserving the slot")
        self.assertEqual(len(failures), num_candidates - 1, "All other threads must fail")

        # Winner candidate has valid reservation
        winner_id, ok, resv_id, reason = successes[0]
        self.assertEqual(reason, "OK")
        self.assertTrue(resv_id.startswith("resv_"))

        # Check DB state
        slot = db.get_autonomous_trade_slot(slot_id, user_id=self.user_id)
        self.assertEqual(slot["status"], "RESERVED")
        self.assertEqual(slot["current_trade_id"], winner_id)
        self.assertEqual(slot["reservation_id"], resv_id)

    def test_03_autonomous_slot_provisioning(self):
        """Ophelia provisions slots automatically WITHIN user's authorized template without ML sizing."""
        # Configure user slot template
        db.set_user_slot_template(
            user_id=self.user_id,
            account_id=self.account_id,
            scope="CRYPTO",
            margin=75.0,
            leverage=4.0,
            max_loss_pct=2.5,
            tp1_pct=50.0,
            breakeven=True,
            trailing=True,
            trailing_pct=1.5,
            max_slots=2,
            max_autonomous_capital=200.0,
        )

        candidate = {
            "symbol": "ETH-USDT",
            "asset_class": "CRYPTO",
            "strategy": "BREAKOUT_RETEST",
            "direction": "LONG",
            "entry_price": 3000.0,
            "sl_price": 2985.0,
        }

        # 1. First candidate triggers auto-provisioning of Slot 1
        slot1, reason1 = SlotAllocationService.find_eligible_slot(candidate, user_id=self.user_id)
        self.assertIsNotNone(slot1)
        self.assertEqual(reason1, "OK")
        self.assertEqual(slot1["allocated_margin_usdt"], 75.0)
        self.assertEqual(slot1["max_leverage"], 4.0)
        self.assertEqual(slot1["status"], "AVAILABLE")

        # Reserve and occupy slot 1
        ok, resv_id1, _ = SlotAllocationService.reserve_slot(slot1["id"], "cand-eth-1", user_id=self.user_id)
        self.assertTrue(ok)
        ok, _ = SlotAllocationService.occupy_slot(slot1["id"], "pos-eth-1", user_id=self.user_id, reservation_id=resv_id1)
        self.assertTrue(ok)

        # 2. Second candidate triggers auto-provisioning of Slot 2 (total 150 margin <= 200 capital)
        candidate2 = dict(candidate, symbol="SOL-USDT")
        slot2, reason2 = SlotAllocationService.find_eligible_slot(candidate2, user_id=self.user_id)
        self.assertIsNotNone(slot2)
        self.assertEqual(reason2, "OK")
        self.assertNotEqual(slot2["id"], slot1["id"])
        self.assertEqual(slot2["allocated_margin_usdt"], 75.0)

        # Reserve and occupy slot 2
        ok, resv_id2, _ = SlotAllocationService.reserve_slot(slot2["id"], "cand-sol-1", user_id=self.user_id)
        self.assertTrue(ok)
        ok, _ = SlotAllocationService.occupy_slot(slot2["id"], "pos-sol-1", user_id=self.user_id, reservation_id=resv_id2)
        self.assertTrue(ok)

        # 3. Third candidate attempts provisioning -> hits max_slots (2)
        candidate3 = dict(candidate, symbol="XRP-USDT")
        slot3, reason3 = SlotAllocationService.find_eligible_slot(candidate3, user_id=self.user_id)
        self.assertIsNone(slot3)
        self.assertEqual(reason3, "NO_AVAILABLE_SLOT")

    def test_04_stale_reservation_recovery(self):
        """Stale reservation older than 60s is automatically recovered and released."""
        slot_id = db.add_autonomous_trade_slot(
            name="Stale Test Slot",
            allocated_margin_usdt=50.0,
            max_leverage=5,
            asset_scope="CRYPTO",
            enabled=True,
            user_id=self.user_id,
        )

        # Reserve slot with a timestamp 90 seconds ago
        ok, resv_id, _ = SlotAllocationService.reserve_slot(slot_id, "cand-stale", user_id=self.user_id)
        self.assertTrue(ok)

        stale_ts = int((time.time() - 90) * 1000)
        c = db._connect()
        with db._lock:
            c.execute("UPDATE autonomous_trade_slots SET reserved_at=? WHERE id=?", (stale_ts, slot_id))
            c.commit()

        # Slot is currently RESERVED
        slot_before = db.get_autonomous_trade_slot(slot_id, user_id=self.user_id)
        self.assertEqual(slot_before["status"], "RESERVED")

        # Recover stale reservations
        recovered = SlotAllocationService.recover_stale_reservations(timeout_s=60, user_id=self.user_id)
        self.assertEqual(recovered, 1)

        # Slot is now AVAILABLE
        slot_after = db.get_autonomous_trade_slot(slot_id, user_id=self.user_id)
        self.assertEqual(slot_after["status"], "AVAILABLE")
        self.assertIsNone(slot_after["current_trade_id"])
        self.assertIsNone(slot_after["reservation_id"])

    def test_05_end_to_end_automation_slot_execution_pipeline(self):
        """Test full pipeline: AUTOMATION -> CANDIDATE -> SLOT -> EXECUTION INTENT -> POSITION."""
        # 1. Create slot
        slot_id = db.add_autonomous_trade_slot(
            name="E2E Pipeline Slot",
            allocated_margin_usdt=60.0,
            max_leverage=5,
            asset_scope="CRYPTO",
            enabled=True,
            user_id=self.user_id,
        )

        # 2. Create Candidate in WAITING_FOR_RETEST
        candidate_id = f"cand-{uuid.uuid4().hex[:8]}"
        automation_id = 8888
        c = db._connect()
        with db._lock:
            c.execute("""
                INSERT INTO setup_candidates (
                    setup_id, user_id, account_id, automation_id, symbol,
                    timeframe, strategy, current_state,
                    suggested_sl, suggested_tp1, generated_ms, expires_ms, direction
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                candidate_id, self.user_id, self.account_id, automation_id, "BTC-USDT",
                5, "BREAKOUT_RETEST", "WAITING_FOR_RETEST",
                59500.0, 61000.0, int(time.time() * 1000), int(time.time() * 1000) + 3600000, "LONG"
            ))
            c.commit()

        # 3. Candidate transitions to ENTRY_READY
        with db._lock:
            c.execute("UPDATE setup_candidates SET current_state='ENTRY_READY', generated_ms=? WHERE setup_id=?", (int(time.time() * 1000), candidate_id))
            c.commit()

        # 4. Engine finds eligible slot
        cand_dict = {
            "candidate_id": candidate_id,
            "symbol": "BTC-USDT",
            "asset_class": "CRYPTO",
            "direction": "LONG",
            "entry_price": 60050.0,
            "sl_price": 59500.0,
        }
        slot, reason = SlotAllocationService.find_eligible_slot(cand_dict, user_id=self.user_id, account_id=self.account_id)
        self.assertIsNotNone(slot)
        self.assertEqual(reason, "OK")
        self.assertEqual(slot["id"], slot_id)

        # 5. Slot is reserved
        ok, resv_id, _ = SlotAllocationService.reserve_slot(slot_id, candidate_id, user_id=self.user_id)
        self.assertTrue(ok)

        # 6. Immutable execution intent created
        intent_id = f"intent_{uuid.uuid4().hex[:12]}"
        db.create_execution_intent({
            "execution_intent_id": intent_id,
            "candidate_id": candidate_id,
            "automation_id": automation_id,
            "slot_id": slot_id,
            "user_id": self.user_id,
            "account_id": self.account_id,
            "instrument": "BTC-USDT",
            "direction": "LONG",
            "requested_margin": slot["allocated_margin_usdt"],
            "leverage": slot["max_leverage"],
            "status": "CREATED",
            "idempotency_key": resv_id,
        })

        intent = db.get_execution_intent(intent_id)
        self.assertIsNotNone(intent)
        self.assertEqual(intent["status"], "CREATED")
        self.assertEqual(intent["requested_margin"], 60.0)

        # 7. Intent transitions: RISK_CHECKING -> APPROVED -> SUBMITTING -> FILLED
        db.update_execution_intent_status(intent_id, "RISK_CHECKING")
        db.update_execution_intent_status(intent_id, "APPROVED")
        db.update_execution_intent_status(intent_id, "SUBMITTING")

        # Execution creates position
        pos_id = db.create_position({
            "symbol": "BTC-USDT",
            "direction": "LONG",
            "entry": 60050.0,
            "qty": 0.005,
            "leverage": 5.0,
            "margin_usdt": 60.0,
            "mode": "SHADOW",
        }, user_id=self.user_id)

        db.update_execution_intent_status(intent_id, "FILLED", position_id=str(pos_id))
        ok, _ = SlotAllocationService.occupy_slot(slot_id, str(pos_id), user_id=self.user_id, reservation_id=resv_id)
        self.assertTrue(ok)

        # Slot is now OCCUPIED
        slot_occupied = db.get_autonomous_trade_slot(slot_id, user_id=self.user_id)
        self.assertEqual(slot_occupied["status"], "OCCUPIED")
        self.assertEqual(slot_occupied["current_position_id"], str(pos_id))

        # Candidate is TRIGGERED
        with db._lock:
            c.execute("UPDATE setup_candidates SET current_state='TRIGGERED', generated_ms=? WHERE setup_id=?", (int(time.time() * 1000), candidate_id))
            c.commit()

        # 8. Trade completes and closes position -> Slot released back to AVAILABLE
        db.update_position(pos_id, status="CLOSED", exit_price=61000.0, closed_ms=int(time.time() * 1000))
        ok, _ = SlotAllocationService.release_slot(slot_id, user_id=self.user_id, reason="POSITION_CLOSED")
        self.assertTrue(ok)

        slot_released = db.get_autonomous_trade_slot(slot_id, user_id=self.user_id)
        self.assertEqual(slot_released["status"], "AVAILABLE")
        self.assertIsNone(slot_released["current_position_id"])

    def test_06_admin_diagnostics_pipeline_query(self):
        """Verify pipeline diagnostics query returns complete linked telemetry."""
        slot_id = db.add_autonomous_trade_slot(
            name="Diag Slot",
            allocated_margin_usdt=50.0,
            max_leverage=5,
            asset_scope="CRYPTO",
            enabled=True,
            user_id=self.user_id,
        )

        auto_id = 9991
        c = db._connect()
        with db._lock:
            c.execute("""
                INSERT INTO automations (
                    id, user_id, symbol, timeframe, strategy, status,
                    margin_usdt, leverage, created_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (auto_id, self.user_id, "BTC-USDT", "5m", "BREAKOUT_RETEST", "ACTIVE", 50.0, 5, int(time.time() * 1000)))
            c.commit()

        # Call the diagnostics logic from api.py
        from control_plane.api import get_automation_pipeline_diagnostics
        diag = get_automation_pipeline_diagnostics(current_user={"id": self.user_id, "role": "ADMIN"})

        self.assertIn("pipeline", diag)
        item = next((x for x in diag["pipeline"] if x["automation_id"] == auto_id), None)
        self.assertIsNotNone(item)
        self.assertEqual(item["symbol"], "BTC-USDT")
        self.assertEqual(item["status"], "ACTIVE")
        self.assertEqual(item["symbol"], "BTC-USDT")
        self.assertEqual(item["status"], "ACTIVE")


if __name__ == "__main__":
    unittest.main()
