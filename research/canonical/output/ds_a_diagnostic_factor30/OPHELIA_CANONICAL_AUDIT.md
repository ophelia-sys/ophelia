# OPHELIA CANONICAL AUDIT

- run_id: `313194de4f1a`
- engine_version: 2.9.0 | spec_version: 1.0
- dataset: DS-A DS-A.v1 sha256=652da237e21ecbb8…
- strategy: VWAP_SUPERTREND_ACTIVE_LINE_CROSS v1.0.0 | indicator_source: VENDOR_PROVIDED
- config sha256: 641fc245b9fad405…

## Integrity gates
- G1–G9 executed pre-run; missing candles: 0; duplicates: 0; invalid OHLC: 0; zero-volume bars: 0 (volume_available=False)

## Counts
- signals: 183 (LONG 96 / SHORT 87)
- trades taken: 134
- ignored POSITION_OPEN: 49
- ignored SIGNAL_PENDING: 0
- TRIGGER_EXPIRED: 0
- UNFILLED_EOD: 0
- censored (open at dataset end): 0

## Acceptance anchor (D2)
- I7 ANCHOR MISMATCH: got 183/96/87 expected 121/58/63

## Invariants
- FAILURES:
  - I7 ANCHOR MISMATCH: got 183/96/87 expected 121/58/63

## Standing notes
- indicator_source=VENDOR_PROVIDED: vendor TV series used for DS-A because export lacks pre-window history (SPEC-GAP S1).
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
