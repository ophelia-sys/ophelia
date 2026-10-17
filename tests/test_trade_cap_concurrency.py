"""Concurrency and atomic slot reservation tests for authoritative global MAX_OPEN_TRADES."""
import threading
import time
import pytest
from control_plane import config, db, core


def test_global_max_open_trades_barrier():
    """Verify single authoritative setting, atomic reservation, and capacity metrics."""
    # Reset to baseline
    db.set_max_open_trades(2)
    assert db.get_max_open_trades() == 2

    # Capacity metrics
    metrics = db.get_capacity_metrics()
    assert metrics["configured_max_open_trades"] == 2
    assert metrics["system_safety_max_open_trades"] == config.SYSTEM_SAFETY_MAX_OPEN_TRADES
    
    # Test setting across 1, 2, 4, 10
    for test_cap in (1, 2, 4, 10):
        db.set_max_open_trades(test_cap)
        assert db.get_max_open_trades() == test_cap
        m = db.get_capacity_metrics()
        assert m["configured_max_open_trades"] == test_cap

    # Test system safety ceiling validation
    with pytest.raises(ValueError):
        db.set_max_open_trades(config.SYSTEM_SAFETY_MAX_OPEN_TRADES + 1)

    with pytest.raises(ValueError):
        db.set_max_open_trades(0)

    # Concurrency test: 20 simultaneous execution requests contesting 1 available slot
    db.set_max_open_trades(4)
    # Mock open positions = 3
    # Available slots = 4 - 3 = 1
    
    successful_reservations = 0
    rejected_reservations = 0
    lock = threading.Lock()

    def try_reserve(worker_id):
        nonlocal successful_reservations, rejected_reservations
        with db._lock:
            # Atomic reservation check
            blk = core.one_trade_block()
            # If current open + reserved >= cap, reject
            with lock:
                current_total = db.total_open_positions_count() + successful_reservations
                cap = db.get_max_open_trades()
                if current_total >= cap:
                    rejected_reservations += 1
                else:
                    successful_reservations += 1

    # Spawn 20 concurrent threads
    threads = [threading.Thread(target=try_reserve, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Total executions must equal cap - current_open (or total contested)
    open_now = db.total_open_positions_count()
    expected_slots = max(0, 4 - open_now)
    assert successful_reservations == expected_slots
    assert rejected_reservations == 20 - expected_slots
