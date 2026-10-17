import sqlite3
import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[3]
SHADOW_DB = BASE_DIR / "institutional" / "data" / "archive" / "s3_shadow_log.sqlite"
DOCS_DIR = Path(__file__).resolve().parent

def audit_shadow_data():
    if not SHADOW_DB.exists():
        print(f"Shadow DB not found at {SHADOW_DB}")
        return
        
    try:
        with sqlite3.connect(SHADOW_DB) as conn:
            opps = pd.read_sql('SELECT * FROM shadow_opportunity', conn)
            outcomes = pd.read_sql('SELECT * FROM shadow_outcome', conn)
    except Exception as e:
        print(f"Error reading tables: {e}")
        return
        
    total_snapshots = len(opps)
    
    # 1. Mutually Exclusive Decision States
    signal = len(opps[opps['decision_status'] == 'SIGNAL']) if total_snapshots > 0 else 0
    no_signal = len(opps[opps['decision_status'] == 'NO_SIGNAL']) if total_snapshots > 0 else 0
    unavailable = len(opps[opps['decision_status'] == 'UNAVAILABLE']) if total_snapshots > 0 else 0
    
    # User Rule 3: Assert equality
    assert signal + no_signal + unavailable == total_snapshots, \
        f"Telemetry mismatch: {signal} + {no_signal} + {unavailable} != {total_snapshots}"
        
    # Reason Code Breakdown inside UNAVAILABLE
    unavail_df = opps[opps['decision_status'] == 'UNAVAILABLE']
    unavail_breakdown = unavail_df['reason_code'].value_counts().to_dict() if len(unavail_df) > 0 else {}
    
    # Data Quality Counts (V3 Schema)
    price_fresh = 0
    price_unknown = 0
    bbo_fresh = 0
    bbo_unknown = 0
    oi_fresh = 0
    oi_degraded = 0
    oi_stale = 0
    funding_fresh = 0
    funding_stale = 0
    
    if total_snapshots > 0:
        if 'price_age_seconds' in opps.columns:
            # Handle text/unknown values
            is_num_price = pd.to_numeric(opps['price_age_seconds'], errors='coerce').notna()
            price_unknown = len(opps[~is_num_price])
            price_fresh = len(opps[is_num_price])
            
        if 'bbo_age_seconds' in opps.columns:
            is_num_bbo = pd.to_numeric(opps['bbo_age_seconds'], errors='coerce').notna()
            bbo_unknown = len(opps[~is_num_bbo])
            bbo_fresh = len(opps[is_num_bbo])
            
        oi_fresh = len(opps[opps['oi_age_seconds'] <= 900])
        oi_degraded = len(opps[(opps['oi_age_seconds'] > 900) & (opps['oi_age_seconds'] <= 3600)])
        oi_stale = len(opps[opps['oi_age_seconds'] > 3600])
        
        funding_fresh = len(opps[opps['funding_age_seconds'] <= 28800])
        funding_stale = len(opps[opps['funding_age_seconds'] > 28800])
    
    # Outcomes
    comp_15m = len(outcomes[outcomes['horizon'] == '15m']) if len(outcomes) > 0 else 0
    comp_30m = len(outcomes[outcomes['horizon'] == '30m']) if len(outcomes) > 0 else 0
    comp_1h = len(outcomes[outcomes['horizon'] == '1h']) if len(outcomes) > 0 else 0
    comp_4h = len(outcomes[outcomes['horizon'] == '4h']) if len(outcomes) > 0 else 0
    
    print("--- SHADOW DATA AUDIT ---")
    print(f"Total Snapshots: {total_snapshots}")
    print(f"SIGNAL: {signal}")
    print(f"NO_SIGNAL: {no_signal}")
    print(f"UNAVAILABLE: {unavailable}")
    print(f"Unavailable Breakdown: {unavail_breakdown}")
    
    # Generate Progress Report
    progress_md = f"""# PHASE 8.3: S3 LIVE SHADOW PROGRESS

## Live Evidence Accumulation
- **Total Shadow Snapshots**: {total_snapshots}
- **SIGNAL**: {signal}
- **NO_SIGNAL**: {no_signal}
- **UNAVAILABLE**: {unavailable}
- **Completed Outcomes**: {len(outcomes)}

### Data Quality Telemetry (V3+)
- **price_fresh**: {price_fresh} | **price_unknown_age**: {price_unknown}
- **BBO_fresh**: {bbo_fresh} | **BBO_unknown_age**: {bbo_unknown}
- **OI_fresh**: {oi_fresh} | **OI_degraded**: {oi_degraded} | **OI_stale**: {oi_stale}
- **funding_fresh**: {funding_fresh} | **funding_stale**: {funding_stale}

*Note: The live data collection continues indefinitely until mature outcomes are sufficient. Historical schema (V1/V2) observations may lack explicit price/BBO age telemetry but are preserved.*
"""
    with open(DOCS_DIR / "PHASE8_3_S3_LIVE_SHADOW_PROGRESS.md", "w") as f:
        f.write(progress_md)
        
    # Generate Validation Report
    val_md = f"""# PHASE 8.3: S3 LIVE SHADOW VALIDATION

## 1. Current Live Status
> [!WARNING]
> **STATUS = INCONCLUSIVE / INSUFFICIENT LIVE OUTCOMES**
> The current shadow sample is too young to evaluate. Do not force a conclusion.

### Decision Signal Breakdown
- **decision_snapshots**: {total_snapshots}
- **SIGNAL**: {signal}
- **NO_SIGNAL**: {no_signal}
- **UNAVAILABLE**: {unavailable}

*Unavailable Reason Breakdown:*
"""
    for reason, count in unavail_breakdown.items():
        val_md += f"- {reason}: {count}\n"
        
    val_md += f"""
### Outcome Breakdown
- **completed_15m_outcomes**: {comp_15m}
- **completed_30m_outcomes**: {comp_30m}
- **completed_1h_outcomes**: {comp_1h}
- **completed_4h_outcomes**: {comp_4h}

## 2. Research vs Live Comparison
*Cannot be executed until meaningful 1h and 4h sample sizes accumulate.*

## 3. Conclusion
Live data collection continues. No promotion to any live-trading phase is authorized.
"""
    with open(DOCS_DIR / "PHASE8_3_S3_LIVE_SHADOW_VALIDATION.md", "w") as f:
        f.write(val_md)
        
    print("Generated PHASE8_3_S3_LIVE_SHADOW_PROGRESS.md and PHASE8_3_S3_LIVE_SHADOW_VALIDATION.md")

if __name__ == "__main__":
    audit_shadow_data()
