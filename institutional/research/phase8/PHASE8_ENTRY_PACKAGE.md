# PHASE 8 ENTRY PACKAGE: PROBABILITY ENGINE

## 1. Entering State
**Phase 7 Alpha Discovery is Closed and Frozen.**

The `PHASE7_FINAL_FEATURE_REGISTRY` has been amended to implement the new 4-state feature tracking model. The original empirical research verdicts are IMMUTABLE.

### Phase 8 Candidate:
Only one feature is permitted to influence the Phase 8 engine.

**S3_CONDITIONAL_VOL_V1 (OI/Funding Crowding Reversal)**
- **research_status:** FRAGILE_VALIDATED_ALPHA_CANDIDATE
- **live_experimental_status:** RUNNING
- **production_status:** DISABLED
- **revalidation_version:** NONE

### Live Experimental Pool (Phase 7 Rejects):
The following features are preserved purely for potential observation in LIVE SHADOW mode.

- S1 (Time-Series Momentum)
- S2 (Residual Momentum)
- S4_TAKER_FLOW_EXHAUSTION_V1 
- S4_1_FLOW_PRICE_DISLOCATION_V1
- S5_CS_DISPERSION_V1

All rejects share the following state:
- **research_status:** REJECTED
- **live_experimental_status:** ELIGIBLE_FOR_SHADOW
- **production_status:** DISABLED
- **revalidation_version:** NONE

**CRITICAL SHADOW RULES:**
Rejected features observed in the live experimental pool MUST NOT:
1. Influence the Probability Engine.
2. Influence production confidence.
3. Influence production position sizing.
4. Trigger orders.
5. Override S3.

## 2. Phase 8 Objective: The Probability Engine
The objective of Phase 8 is to construct the probabilistic forecasting model (Probability Engine) utilizing *strictly* the surviving validated feature set (S3_CONDITIONAL_VOL_V1).

**CORE RULE:** No new alpha features will be developed in Phase 8.

The engine must translate the raw S3 signal strength, coupled with its live structural constraints, into an actionable probability distribution or conviction score for execution sizing.

## 3. Preparation Requirements
Before Phase 8 development commences, we must await authorization to transition from Phase 7's final audit into Phase 8 architecture.

Awaiting next user directive to begin Phase 8.
