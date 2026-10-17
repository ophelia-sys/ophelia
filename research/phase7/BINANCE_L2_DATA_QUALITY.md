# Binance L2 Data Quality & Reconstruction Audit

## 1. Known Anomalies in Historical L2 (`T_DEPTH`)

When processing historical incremental depth streams, the following anomalies are expected and must be explicitly handled by the reconstruction engine:

- **Sequence Gaps (`pu` != previous `u`):** WS disconnects or UDP packet loss during archival. 
- **Out-of-order Events:** Network jitter causing updates to arrive non-sequentially.
- **Crossed Books:** Bid > Ask. Usually a transient artifact of rapid matching engine state changes before the snapshot fully resolves.
- **Missing Levels:** A price level quantity drops to 0 but the message is missed, leaving a "ghost" order in the local book.
- **Reconnect Resets:** The archiver drops connection and establishes a new stream, requiring a fresh `S_DEPTH` snapshot to initialize.

## 2. Statistical Validity Despite Gaps

A sequence gap does **not** render the dataset useless, provided the reconstruction engine correctly flags it.

**Valid despite gaps:**
- **Snapshots:** Immediately requesting an `S_DEPTH` snapshot upon detecting a gap resets the book perfectly. The period *after* the snapshot is statistically pristine.
- **Aggregated Horizons:** Microstructure features (like Book Slope or Imbalance) sampled at 1-second intervals are robust if the book is frequently synced.

**Invalidated by gaps:**
- **Canonical OFI (Order Flow Imbalance):** OFI relies on the *difference* between successive states. A gap in sequence IDs completely invalidates the OFI calculation for that specific tick delta. OFI must be reset/paused across any sequence gap.
- **Queue Tracking:** Estimating your place in the limit order queue is entirely broken by a sequence gap.

## 3. OFI (Order Flow Imbalance) Strictness

**Rule:** Canonical Cont-Kukanov-Stoikov OFI must **only** be calculated on a contiguous, sequence-validated `T_DEPTH` event stream.

Do NOT approximate OFI by differencing 1-minute `bookDepth` snapshots or using `aggTrades` (which is CVD, not OFI). If the sequence is broken, OFI for that interval must be returned as `NaN` and excluded from model training.

## 4. Book Reconstruction Requirements

Any historical L2 processor in Ophelia must implement the official Binance reconstruction algorithm:
1. Buffer `T_DEPTH` events.
2. Fetch/Load an `S_DEPTH` snapshot.
3. Drop `T_DEPTH` events where `u` <= `lastUpdateId` of the snapshot.
4. Verify the first processed event has `U` <= `lastUpdateId` + 1 AND `u` >= `lastUpdateId` + 1.
5. Apply updates iteratively, strictly validating `pu` == previous `u`.
6. Purge levels when quantity == 0.
