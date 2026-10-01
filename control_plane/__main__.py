"""Ophelia Control Plane entrypoint: one process, several threads (spec §39 allows)."""
from __future__ import annotations

import threading
import time

from . import config, db, llm, news, core, intelligence, position_manager_daemon
from .ingest import poll_loop
from .telegram_bot import run_bot


def news_loop(stop_event):
    key = ""
    try:
        res = news.fetch_and_persist_news_feeds()
        print(f"[news] initial RSS feed fetch: {res.get('total_persisted', 0)} articles saved", flush=True)
    except Exception as e:
        print(f"[news] initial fetch error: {e}", flush=True)

    while not stop_event.is_set():
        try:
            key, _ = news.session_refresh_if_due(key)
            res = news.fetch_and_persist_news_feeds()
        except Exception as e:                                    # noqa: BLE001
            print(f"[news] {e}", flush=True)
        stop_event.wait(600)


def llm_keepalive_loop(stop_event):
    """Keep the primary model resident: warmup at start, refresh periodically.

    Eliminates 20-60s cold-load latency after idle periods. Failures are
    logged with the real reason (never silently swallowed).
    """
    llm.warmup()
    while not stop_event.is_set():
        stop_event.wait(240)          # keep_alive is 60m; refresh well before
        if not stop_event.is_set():
            llm.warmup()


def forecast_worker_loop(stop_event):
    """Background scheduler for periodic TimesFM / baseline forecasting."""
    from .forecast_service import ForecastService, UNIVERSAL_WATCHLIST
    svc = ForecastService.get_instance()
    time.sleep(10)  # Initial delay to let ingest warmup
    while not stop_event.is_set():
        try:
            for inst in UNIVERSAL_WATCHLIST:
                if stop_event.is_set():
                    break
                try:
                    svc.generate_forecast(instrument=inst, timeframe="15m", horizon=10)
                except Exception as e:
                    print(f"[forecast] Error forecasting {inst}: {e}", flush=True)
                time.sleep(2.0)
        except Exception as ex:
            print(f"[forecast] Unhandled scheduler error: {ex}", flush=True)
        stop_event.wait(300)  # Evaluate cadence every 5m


def main() -> int:
    symbols = db.ensure_seed_watchlist()
    print(f"[control-plane] starting | watchlist={symbols} "
          f"| llm={config.LLM_PRIMARY} (fallback {config.LLM_FALLBACK}) "
          f"| mode={db.get_mode()}", flush=True)

    # Ensure all active symbols (including GOLD) have candle history
    for s in symbols:
        info = db.oldest_newest(s)
        if not info or not info.get("rows"):
            try:
                from .ingest import backfill_symbol
                backfill_symbol(s, hours=config.RETENTION_HOURS)
            except Exception as e:
                print(f"[ingest] backfill {s} error: {e}", flush=True)
    stop = threading.Event()
    threads = [
        threading.Thread(target=poll_loop, args=(stop,), daemon=True, name="ingest"),
        threading.Thread(target=core.automation_worker_loop, args=(stop,), daemon=True, name="automation-engine"),
        threading.Thread(target=news_loop, args=(stop,), daemon=True, name="news"),
        threading.Thread(target=intelligence.continuous_intelligence_worker, args=(stop, 20), daemon=True, name="continuous-intelligence"),
        threading.Thread(target=llm_keepalive_loop, args=(stop,), daemon=True,
                         name="llm-keepalive"),
        threading.Thread(target=run_bot, args=(stop,), daemon=True, name="telegram"),
        threading.Thread(target=position_manager_daemon.autonomous_position_manager_worker, args=(stop,), daemon=True, name="position-manager"),
        threading.Thread(target=forecast_worker_loop, args=(stop,), daemon=True, name="timesfm-forecaster"),
    ]
    for t in threads:
        t.start()
    try:
        while True:
            time.sleep(60)
            h = db.oldest_newest()
            print(f"[hb] rows={h['rows']} newest={h['newest_ts']}", flush=True)
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
