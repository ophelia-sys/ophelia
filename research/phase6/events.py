import pandas as pd
import numpy as np
from typing import List, Dict, Any
from institutional.features import (
    detect_bullish_fvg, 
    update_fvg_state, 
    detect_liquidity_pools, 
    update_liquidity_pool_state,
    FVGState,
    LiquidityPoolState
)

class EventGenerator:
    """
    Generates historical events for Phase 6 Empirical Validation Pipeline.
    Events are confirmed at timestamp t.
    """
    def __init__(self, alpha: float = 1.0, gamma: float = 1.0, w: int = 5, epsilon: float = 0.5, beta: float = 1.0):
        self.alpha = alpha
        self.gamma = gamma
        self.w = w
        self.epsilon = epsilon
        self.beta = beta
        
        self.active_fvgs: List[FVGState] = []
        self.active_pools: List[LiquidityPoolState] = []
        self.events: List[Dict[str, Any]] = []

    def generate_events(self, df: pd.DataFrame, atr_series: pd.Series) -> List[Dict[str, Any]]:
        """
        Process a historical dataframe and generate a list of events.
        Must be done iteratively to simulate walk-forward causality.
        """
        self.events = []
        self.active_fvgs = []
        self.active_pools = []
        
        # Convert columns to numpy arrays for O(1) slicing
        timestamps = df['timestamp'].values
        highs = df['high'].values
        lows = df['low'].values
        closes = df['close'].values
        opens = df['open'].values
        atrs = atr_series.values
        symbols = df['symbol'].values if 'symbol' in df.columns else np.array(["UNKNOWN"] * len(df))
        
        # Divergence features
        z_r_arr = df['Z_R'].values if 'Z_R' in df.columns else np.zeros(len(df))
        z_oi_arr = df['Z_DeltaOI'].values if 'Z_DeltaOI' in df.columns else np.zeros(len(df))
        
        min_rows = max(2, 2 * self.w)
        
        for i in range(min_rows, len(df)):
            timestamp_t = int(timestamps[i])
            close_t = float(closes[i])
            low_t = float(lows[i])
            high_t = float(highs[i])
            
            # --- GAP COLD START ---
            prev_timestamp = int(timestamps[i-1])
            if (timestamp_t - prev_timestamp) > 3600000:
                self.active_fvgs = []
                self.active_pools = []

            
            # --- UPDATE STATES ---
            # Update FVGs
            for fvg in self.active_fvgs:
                update_fvg_state(fvg, low_t, close_t)
            self.active_fvgs = [fvg for fvg in self.active_fvgs if fvg.is_active]
            
            # Update Pools
            for pool in self.active_pools:
                update_liquidity_pool_state(pool, close_t, self.epsilon)
            self.active_pools = [pool for pool in self.active_pools if pool.is_active]

            # --- DETECT NEW ---
            # 1. Bullish FVG
            # Gap_t = L_{t-2} - H_t
            atr_t_2 = float(atrs[i-2])
            low_t_2 = float(lows[i-2])
            close_t_1 = float(closes[i-1])
            open_t_1 = float(opens[i-1])
            
            new_fvg = None
            if not (pd.isna(atr_t_2) or atr_t_2 <= 0):
                gap_t = low_t_2 - high_t
                cond_1 = gap_t > (self.alpha * atr_t_2)
                cond_2 = (close_t_1 - open_t_1) / atr_t_2 > self.gamma
                if cond_1 and cond_2:
                    new_fvg = FVGState(
                        fvg_id=f"fvg_bull_{timestamp_t}",
                        created_timestamp=timestamp_t,
                        fvg_top=low_t_2,
                        fvg_bottom=high_t,
                        original_top=low_t_2,
                        original_bottom=high_t
                    )
            
            if new_fvg:
                self.active_fvgs.append(new_fvg)
                
                # FVG Confirmation event
                self.events.append({
                    "event_id": f"event_fvg_{timestamp_t}",
                    "event_type": "FVG_CONFIRMATION",
                    "symbol": symbols[i],
                    "timestamp": timestamp_t,
                    "confirmation_timestamp": timestamp_t,
                    "fvg_id": new_fvg.fvg_id,
                    "feature_snapshot": {
                        "fvg_top": new_fvg.fvg_top,
                        "fvg_bottom": new_fvg.fvg_bottom,
                        "z_r": float(z_r_arr[i]),
                        "z_delta_oi": float(z_oi_arr[i])
                    }
                })

            # 2. Liquidity Pool
            prev_pool_count = len(self.active_pools)
            
            # Segment from t-2w to t (length 2w+1)
            # Center is at i-w
            if i >= 2 * self.w:
                start_w = i - 2 * self.w
                segment_lows = lows[start_w:i+1]
                low_t_w = segment_lows[self.w]
                min_low = np.min(segment_lows)
                
                if low_t_w == min_low:
                    new_pool_price = low_t_w
                    timestamp_t_w = int(timestamps[i-self.w])
                    
                    merged = False
                    for pool in self.active_pools:
                        if pool.is_active and abs(pool.price - new_pool_price) <= self.epsilon:
                            pool.price = (pool.price + new_pool_price) / 2.0
                            pool.age = 0
                            merged = True
                            break
                            
                    if not merged:
                        self.active_pools.append(
                            LiquidityPoolState(
                                pool_id=f"liq_pool_{timestamp_t_w}",
                                created_timestamp=timestamp_t_w,
                                price=new_pool_price
                            )
                        )
            
            if len(self.active_pools) > prev_pool_count:
                new_pool = self.active_pools[-1]
                # Pool Confirmation event
                self.events.append({
                    "event_id": f"event_pool_{timestamp_t}",
                    "event_type": "POOL_CONFIRMATION",
                    "symbol": symbols[i],
                    "timestamp": timestamp_t,
                    "confirmation_timestamp": timestamp_t,
                    "pool_id": new_pool.pool_id,
                    "feature_snapshot": {
                        "price": new_pool.price,
                        "z_r": float(z_r_arr[i]),
                        "z_delta_oi": float(z_oi_arr[i])
                    }
                })

            # 3. Sweep Event (using beta)
            for pool in self.active_pools:
                if low_t < pool.price and close_t >= pool.price:
                    sweep_depth = (pool.price - low_t) / pool.price
                    if sweep_depth > self.beta:
                        self.events.append({
                            "event_id": f"event_sweep_{timestamp_t}_{pool.pool_id}",
                            "event_type": "LIQUIDITY_SWEEP",
                            "symbol": symbols[i],
                            "timestamp": timestamp_t,
                            "confirmation_timestamp": timestamp_t,
                            "pool_id": pool.pool_id,
                            "feature_snapshot": {
                                "sweep_depth": sweep_depth,
                                "pool_price": pool.price,
                                "z_r": float(z_r_arr[i]),
                                "z_delta_oi": float(z_oi_arr[i])
                            }
                        })
                        
        self._cluster_events()
        return self.events

    def _cluster_events(self):
        """
        Assigns cluster_id and primary_event flag.
        Simple logic: if events are within 5 time periods of same type, cluster them.
        """
        # Sort by timestamp
        self.events.sort(key=lambda x: x["confirmation_timestamp"])
        
        # Group by type
        by_type = {}
        for ev in self.events:
            by_type.setdefault(ev["event_type"], []).append(ev)
            
        cluster_counter = 0
        for ev_type, ev_list in by_type.items():
            current_cluster_id = f"cluster_{cluster_counter}"
            for i, ev in enumerate(ev_list):
                if i == 0:
                    ev["cluster_id"] = current_cluster_id
                    ev["primary_event"] = True
                else:
                    prev_ev = ev_list[i-1]
                    # Timestamps are in milliseconds, cluster if < 5 candles of 1m = 300000ms
                    if ev["confirmation_timestamp"] - prev_ev["confirmation_timestamp"] <= 300000:
                        ev["cluster_id"] = current_cluster_id
                        ev["primary_event"] = False
                    else:
                        cluster_counter += 1
                        current_cluster_id = f"cluster_{cluster_counter}"
                        ev["cluster_id"] = current_cluster_id
                        ev["primary_event"] = True
            cluster_counter += 1

    def get_event_statistics(self) -> Dict[str, Any]:
        """
        Returns exact event accounting.
        """
        raw_events = len(self.events)
        cluster_count = len(set(ev.get("cluster_id") for ev in self.events if "cluster_id" in ev))
        primary_events = sum(1 for ev in self.events if ev.get("primary_event", False))
        non_primary_events = raw_events - primary_events
        
        type_counts = {}
        for ev in self.events:
            if ev.get("primary_event", False):
                t = ev["event_type"]
                type_counts[t] = type_counts.get(t, 0) + 1
                
        return {
            "raw_events": raw_events,
            "cluster_count": cluster_count,
            "primary_events": primary_events,
            "non_primary_events": non_primary_events,
            "primary_type_counts": type_counts
        }
