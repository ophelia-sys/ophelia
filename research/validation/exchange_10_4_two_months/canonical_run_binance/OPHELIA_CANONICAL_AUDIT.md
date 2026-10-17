# OPHELIA CANONICAL AUDIT

- run_id: `8c923882b763`
- engine_version: 2.9.0 | spec_version: 1.0
- dataset: DS-BINANCE-VAL DS-BINANCE-VAL.v1 sha256=9e46cccf8585cd28…
- strategy: VWAP_SUPERTREND_ACTIVE_LINE_CROSS_ENGINE v1.0.0 | indicator_source: ENGINE_COMPUTED
- config sha256: a842745afcb18b4c…

## Integrity gates
- G1–G9 executed pre-run; missing candles: None; duplicates: 0; invalid OHLC: 0; zero-volume bars: 0 (volume_available=True)

## Counts
- signals: 128 (LONG 63 / SHORT 65)
- trades taken: 83
- ignored POSITION_OPEN: 45
- ignored SIGNAL_PENDING: 0
- TRIGGER_EXPIRED: 0
- UNFILLED_EOD: 0
- censored (open at dataset end): 0

## Acceptance anchor (D2)
- PASS

## Invariants
- ALL PASS

## Standing notes
- indicator_source=ENGINE_COMPUTED: vendor TV series used for DS-A because export lacks pre-window history (SPEC-GAP S1).
- DS-A has no volume column (SPEC-GAP S2): engine VWAP path inactive; vendor VWAP consumed as data.
- Regime window is DEGRADED for DS-A (<90d history): HIGH_VOL/CHOP split uses expanding post-warmup median (documented limitation L3).
- Ambiguity policy STOP_FIRST biases results downward (conservative, spec A1).
- Secondary exit policies are PATH-INDEPENDENT estimates; only FIXED_R_150 drives the state machine.
- Bootstrap/ESS computed on primary-policy net bps series.

## Funding
- funding_status = NOT_MODELED on every row (spec D17). Funding drag is NOT
  assumed to be zero; it is unaccounted until an external overlay exists.

## Ambiguity policy
- STOP_FIRST: same-candle stop+target resolves as LOSS (A1).
- Within-bar order assumed OPEN → {{HIGH, LOW}} → CLOSE (D14).
