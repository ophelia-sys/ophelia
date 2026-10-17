"""
Phase 5D.3 — Live BingX Capture Verification Script

Connects to BingX Swap WebSocket for a controlled capture window and reports:
- Connection status
- Trade/Depth/Ticker event counts
- CVD/TVI derivation from real trades
- Microstructure metrics from real book data
- Runtime observability counters

USAGE:
    python scripts/phase5d3_live_capture.py [duration_seconds]

Default duration: 60 seconds
"""
import sys
import time
from institutional.data.engine import InstitutionalDataEngine
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

CAPTURE_DURATION = int(sys.argv[1]) if len(sys.argv) > 1 else 60

def main():
    print(f"=" * 72)
    print(f"  OPHELIA Phase 5D.3 — Live BingX Capture Verification")
    print(f"  Duration: {CAPTURE_DURATION}s")
    print(f"=" * 72)

    engine = InstitutionalDataEngine(use_ws=True)
    engine.start(["BTC-USDT"])

    start_time = time.time()
    last_report = 0
    report_interval = 5  # seconds

    while time.time() - start_time < CAPTURE_DURATION:
        now = time.time()
        elapsed = now - start_time

        if now - last_report >= report_interval:
            print(f"\n--- [{elapsed:.0f}s] Status Report ---")

            # WS stats
            ws = engine.ws_manager
            if ws:
                print(f"  WS Trades:     {ws.stats_trade_events}")
                print(f"  WS Depth:      {ws.stats_depth_events}")
                print(f"  WS Ticker:     {ws.stats_ticker_events}")
                print(f"  WS Pongs:      {ws.stats_pong_sent}")
                print(f"  WS Reconnects: {ws.stats_reconnects}")
                print(f"  WS Parse Errs: {ws.stats_parse_errors}")
            else:
                print("  WS: Not enabled")

            # Snapshot
            try:
                snap = engine.get_snapshot("BTC-USDT", "1m")
                print(f"  Snapshot Quality: {snap.data_quality.name}")
                print(f"  Freshness:        {snap.freshness}")

                if snap.order_book:
                    bb = snap.order_book.best_bid
                    ba = snap.order_book.best_ask
                    print(f"  Best Bid:    {bb}")
                    print(f"  Best Ask:    {ba}")
                    print(f"  Spread:      {snap.order_book.spread}")
                    print(f"  Relative Spread: {snap.order_book.relative_spread}")
                    print(f"  Queue Imbalance: {snap.order_book.queue_imbalance}")
                    print(f"  Depth Imbalance: {snap.order_book.depth_imbalance}")
                    print(f"  Microprice:      {snap.order_book.microprice}")
                else:
                    print("  Order Book: None")

                if snap.microstructure:
                    ms = snap.microstructure
                    print(f"  Mid Price (MS):  {ms.mid_price}")
                    print(f"  Queue Imbalance: {ms.queue_imbalance}")
                    print(f"  Depth Imbalance: {ms.depth_imbalance}")
                    print(f"  Microprice:      {ms.microprice}")
                    print(f"  Book Slope Bid:  {ms.book_slope_bid}")
                    print(f"  Book Slope Ask:  {ms.book_slope_ask}")
                    print(f"  Book Concentration: {ms.book_concentration}")
                    print(f"  Visible Impact Buy: {ms.visible_impact_buy}")
                    print(f"  Visible Impact Sell: {ms.visible_impact_sell}")

                print(f"  Buy Volume:  {snap.buy_volume}")
                print(f"  Sell Volume: {snap.sell_volume}")
                print(f"  CVD:         {snap.cvd}")
                print(f"  TVI:         {snap.tvi}")

                trades_count = len(engine._trades.get("BTC-USDT", []))
                print(f"  Trades Buffer: {trades_count}")

                if snap.ticker:
                    print(f"  Last Price:  {snap.ticker.last_price}")
                    print(f"  Volume 24h:  {snap.ticker.volume_24h}")
                    print(f"  Ticker TS:   {snap.ticker.timestamp}")

            except Exception as e:
                print(f"  Snapshot Error: {e}")

            last_report = now

        time.sleep(0.5)

    # Final summary
    print(f"\n{'=' * 72}")
    print(f"  CAPTURE COMPLETE — Final Summary")
    print(f"{'=' * 72}")

    ws = engine.ws_manager
    if ws:
        print(f"  Total Trade Events:  {ws.stats_trade_events}")
        print(f"  Total Depth Events:  {ws.stats_depth_events}")
        print(f"  Total Ticker Events: {ws.stats_ticker_events}")
        print(f"  Total Pongs Sent:    {ws.stats_pong_sent}")
        print(f"  Total Reconnects:    {ws.stats_reconnects}")
        print(f"  Total Parse Errors:  {ws.stats_parse_errors}")

    try:
        final = engine.get_snapshot("BTC-USDT", "1m")
        print(f"  Final Quality: {final.data_quality.name}")
        print(f"  Final CVD:     {final.cvd}")
        print(f"  Final TVI:     {final.tvi}")
        print(f"  Final Freshness: {final.freshness}")
        if final.ticker:
            print(f"  Ticker Last Price: {final.ticker.last_price}")
            print(f"  Ticker Volume 24h: {final.ticker.volume_24h}")
            print(f"  Ticker Source: {final.ticker.source}")
    except Exception as e:
        print(f"  Final Snapshot Error: {e}")

    engine.stop()
    print(f"\n  Engine stopped cleanly.")

if __name__ == "__main__":
    main()
