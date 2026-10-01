# OPHELIA MICROSTRUCTURE METHODOLOGY & PROVENANCE SPECIFICATION
Version: 1.0 (Phase 6 Pre-Implementation Gate)
Authoritative Scope: Upstream Research Intelligence Only (No Autonomous Trading Authority)

---

## 1. MACHINE-READABLE PROVENANCE CONTRACT

Every persisted microstructure observation, feature, model run, and evaluation record must expose the following structured, queryable fields directly:

| Field | Type | Description | Allowed Values / Constraints |
|---|---|---|---|
| `instrument` | `TEXT` | Canonical trading pair | e.g. `BTC-USDT`, `ETH-USDT`, `SOL-USDT`, `XRP-USDT`, `XAU-USDT` |
| `venue_source` | `TEXT` | Exact exchange/feed provenance | `BINGX_PERP_V2`, `BINGX_SPOT`, `INTERNAL_REPLAY` |
| `event_timestamp` | `INTEGER` | Exchange epoch timestamp (ms) | Monotonic integer, future ts rejected |
| `received_timestamp` | `INTEGER` | VPS ingress epoch timestamp (ms) | `received_timestamp >= event_timestamp` |
| `feature_version` | `TEXT` | Version of feature formula | Semantic version (e.g. `1.0.0`) |
| `schema_version` | `TEXT` | Data serialization schema | e.g. `v1` |
| `source_data_type` | `TEXT` | Underlying raw market data feed | `TRADE_TICKS`, `ORDER_BOOK_L2`, `AGGREGATED_BARS` |
| `sample_count` | `INTEGER` | Number of raw observations in window | Non-negative integer (`>= 0`) |
| `quality_state` | `TEXT` | Rigorous categorical quality flag | `VALID`, `STALE`, `MISSING`, `INSUFFICIENT_SAMPLE`, `OUT_OF_ORDER`, `DUPLICATE`, `NOT_AVAILABLE`, `DEGRADED` |
| `freshness_state` | `TEXT` | Staleness evaluation flag | `FRESH`, `STALE`, `DEGRADED`, `NOT_AVAILABLE` |
| `missingness_state`| `TEXT` | Gap/absence categorization | `COMPLETE`, `PARTIAL`, `MISSING` |
| `calculation_window`| `INTEGER`| Lookback calculation window in ms | e.g. `60000` (1 min), `300000` (5 min) |
| `mode` | `TEXT` | Execution environment flag | Strictly `RESEARCH` |

---

## 2. REAL DATA QUALITY STATES (ZERO INVALID IMPUTATION)

Under no circumstances may unavailable or unclassified measurements be replaced with `0`, `0.0`, `false`, `neutral`, or fabricated defaults.

1. `VALID`: Complete data received chronologically within tolerance, prerequisites met.
2. `STALE`: Data received but `received_timestamp - event_timestamp > max_freshness_threshold`.
3. `MISSING`: Expected ticks/book snapshots absent from window.
4. `INSUFFICIENT_SAMPLE`: Observation count $N < N_{\min}$ required by statistical gate.
5. `OUT_OF_ORDER`: Event timestamp is earlier than previously processed event.
6. `DUPLICATE`: Event ID or timestamp + sequence previously processed.
7. `NOT_AVAILABLE`: Structural feed does not support metric (e.g., hidden liquidity, feed lacking aggressor flag).
8. `DEGRADED`: Data present but partial depth or packet drops detected.

---

## 3. RESEARCH EXECUTION MODE BARRIERS (HARD INVARIANTS)

`mode = 'RESEARCH'` is an explicit operational mode, not an isolated database sandbox. The following invariants are hardcoded into production code:
- **Zero Live Orders:** `bingx_client.Client` and `core.py` fail closed on `RESEARCH` mode.
- **Zero Paper Orders:** Paper broker disallows signals originating with `mode = 'RESEARCH'`.
- **Zero Slot Reservation:** `SlotAllocationService.find_eligible_slot` and `reserve_slot` reject `RESEARCH` candidates with `RESEARCH_EXECUTION_BARRED`.
- **Zero Position Mutation:** No database row in `positions`, `user_positions`, `shadow_trades`, or `master_trades` may be written from research modules.
- **Zero P&L Contamination:** Research accounting is isolated in `microstructure_evaluations` and cannot enter user or system P&L.
- **Restart Auditable:** All calculations persist to SQLite under `microstructure_*` tables.

---

## 4. MATHEMATICAL & ALGORITHMIC METHODOLOGY CONTRACTS

### A. Trade-Flow Innovation
- **Purpose:** Measure unexpected signed trade-flow relative to rolling baseline.
- **Inputs:** Signed trade stream $\{v_i, s_i\}_{i=1}^N$ where $s_i \in \{+1 (\text{buyer-initiated}), -1 (\text{seller-initiated})\}$, $v_i > 0$.
- **Sampling Interval:** Event-driven or 1-second/1-minute bucketed rollups.
- **Window:** Short window $W_{\text{fast}} = 20$ trades (or 1m), baseline window $W_{\text{slow}} = 200$ trades (or 15m).
- **Formula:**
  $$\text{Flow}_t = \sum_{i \in t} s_i v_i$$
  $$\mu_t = \text{EMA}(\text{Flow}, W_{\text{slow}}), \quad \sigma_t = \text{std}(\text{Flow}, W_{\text{slow}})$$
  $$\text{trade\_flow\_innovation}_t = \text{Flow}_t - \mu_t$$
  $$\text{trade\_flow\_zscore}_t = \frac{\text{Flow}_t - \mu_t}{\max(\sigma_t, \epsilon)}$$
- **Minimum Sample:** $N \ge 30$ trades.
- **Missing-Data Behavior:** If aggressor flag is missing, flag `NOT_AVAILABLE`; never fabricate buy/sell side.
- **Outlier Handling:** Winsorize z-scores at $\pm 5.0$.
- **Interpretation Limitations:** Measures local aggressor order imbalance; does not imply institutional intent.

### B. Trade Duration / Arrival Pressure (Dufour–Engle Style)
- **Purpose:** Quantify clustering and arrival intensity of market transactions.
- **Inputs:** Trade event timestamps $\{t_i\}_{i=1}^N$.
- **Sampling Interval:** Tick-level trade duration $\Delta t_i = t_i - t_{i-1}$ (in milliseconds).
- **Window:** Rolling $W = 50$ trades.
- **Formula:**
  $$\bar{\Delta t}_t = \text{median}(\{\Delta t_j\}_{j=t-W}^t)$$
  $$\text{arrival\_intensity}_t = \frac{1}{\max(\bar{\Delta t}_t, 1.0)}$$
  $$\text{duration\_pressure}_t = \frac{\Delta t_{\text{baseline}} - \bar{\Delta t}_t}{\sigma_{\Delta t}}$$
- **Minimum Sample:** $N \ge 20$ trade durations.
- **Zero-Duration Handling:** Simultaneous trades ($\Delta t = 0$) aggregated into single arrival event with cumulative volume.
- **Interpretation Limitations:** Non-directional proxy for market activity; never used as a directional signal.

### C. Order-Book Imbalance
- **Purpose:** Measure visible depth disparity between bid and ask sides.
- **Inputs:** Level 2 order-book snapshots: bids $\{(p_b^k, q_b^k)\}_{k=1}^K$, asks $\{(p_a^k, q_a^k)\}_{k=1}^K$ up to depth $K \in \{1, 5, 10, 20\}$.
- **Sampling Interval:** Snapshot event (100ms - 1s).
- **Formula:**
  $$\text{Depth}_B(K) = \sum_{k=1}^K q_b^k, \quad \text{Depth}_A(K) = \sum_{k=1}^K q_a^k$$
  $$\text{Imbalance}(K) = \frac{\text{Depth}_B(K) - \text{Depth}_A(K)}{\text{Depth}_B(K) + \text{Depth}_A(K)}$$
- **Visible vs Inferred Liquidity:**
  - Visible: Sum of quote sizes in resting L2 book.
  - Inferred/Hidden: Strictly `NOT_AVAILABLE` unless an explicit iceberg/hidden liquidity detector is calibrated with supporting trade executions.
- **Minimum Sample:** Both sides must have at least $K$ valid levels. If book crossed or empty, return `DEGRADED` / `NOT_AVAILABLE`.

### D. Spread Stress / Liquidity Stress
- **Purpose:** Monitor bid/ask spread blowout and book thinning.
- **Inputs:** Best bid $p_b^1$, best ask $p_a^1$, cumulative depth near touch.
- **Formula:**
  $$\text{Spread}_t = p_a^1 - p_b^1, \quad \text{SpreadPct}_t = \frac{p_a^1 - p_b^1}{0.5(p_a^1 + p_b^1)}$$
  $$\text{SpreadZScore}_t = \frac{\text{SpreadPct}_t - \text{median}(\text{SpreadPct}_{W})}{\text{IQR}(\text{SpreadPct}_{W})}$$
  $$\text{LiquidityStress}_t = \text{SpreadZScore}_t \cdot \left(\frac{\text{DepthBaseline}}{\max(\text{DepthTouch}_t, \epsilon)}\right)$$
- **Recovery State:** Track decay back toward median spread (`EXPANDING`, `ELEVATED`, `RECOVERING`, `NORMAL`).

### E. Price Impact (Empirical Market Impact)
- **Purpose:** Quantify the empirical association between signed volume and price changes.
- **Labeling Invariant:** Labeled strictly as `EMPIRICAL_ASSOCIATION` (not structural/causal Kyle's Lambda unless Kyle assumptions hold).
- **Inputs:** Net signed volume $Q_t = \sum s_i v_i$ over interval $\tau$, contemporaneous return $R_t = \ln(P_t / P_{t-\tau})$.
- **Formula (Rolling OLS):**
  $$R_t = \alpha + \lambda_{\text{emp}} Q_t + \varepsilon_t$$
  $$\hat{\lambda}_{\text{emp}} = \frac{\widehat{\text{Cov}}(R_t, Q_t)}{\widehat{\text{Var}}(Q_t)}$$
- **Minimum Sample:** $N \ge 60$ intervals.
- **Interpretation Limitations:** Statistical association only; does not prove permanent price discovery vs transient inventory effect.

### F. Toxicity / Informed Flow Regime
- **Purpose:** Quantify probability of adverse selection in order flow.
- **Methodology (VPIN-Inspired Volume Bucketing):**
  - Divide trade stream into equal-volume buckets of size $V_{\text{bucket}}$.
  - In each bucket $k$, compute buy volume $V_k^B$ and sell volume $V_k^S$.
  - Compute order imbalance: $|V_k^B - V_k^S|$.
  - Over $N$ buckets (e.g. $N=50$):
    $$\text{Toxicity\_VPIN} = \frac{\sum_{k=1}^N |V_k^B - V_k^S|}{N \cdot V_{\text{bucket}}}$$
- **Minimum Sample:** At least $N=30$ completed volume buckets.
- **Limitations:** Sensitive to bucket volume selection $V_{\text{bucket}}$; regime indicator only.

### G. Hasbrouck-Style VAR Dynamics
- **Purpose:** Analyze bivariate dynamic interaction between trade flow and midquote price revisions.
- **Endogenous Variables:**
  1. $r_t = \Delta \ln(M_t)$ (midquote return)
  2. $x_t = \text{signed trade indicator or signed square-root volume}$
- **Specification:**
  $$r_t = \sum_{i=1}^p \alpha_i r_{t-i} + \sum_{i=0}^p \beta_i x_{t-i} + e_{1,t}$$
  $$x_t = \sum_{i=1}^p \gamma_i r_{t-i} + \sum_{i=1}^p \delta_i x_{t-i} + e_{2,t}$$
- **Lag Selection:** Fixed $p \in [1, 5]$ (or AIC with max $p=5$).
- **Estimation Window:** Minimum $N \ge 200$ trade events.
- **Statistical Safety Gates:**
  - Augmented Dickey-Fuller (ADF) test to verify stationarity of return and trade series ($p < 0.05$).
  - Invertibility / eigenvalue check of companion matrix (all roots outside unit circle).
  - If $N < 200$ or stationarity rejected: return `status = INSUFFICIENT_SAMPLE` or `NOT_AVAILABLE`. Never substitute 0.

### H. VECM / Long-Run Relationships
- **Purpose:** Estimate cointegration and error correction between closely tied price series (e.g., Perpetual Futures vs Spot Price).
- **Prerequisites & Gates:**
  1. Series selection: $P_1 = \ln(\text{Perp Price}), P_2 = \ln(\text{Spot Price})$.
  2. Unit-root verification: Both series must be integrated of order 1, $I(1)$ (ADF on levels fails to reject unit root; ADF on differences rejects unit root).
  3. Cointegration test: Johansen trace/eigenvalue test or Engle-Granger two-step test.
  4. Cointegration rank $r = 1$ required.
  5. Minimum observations: $N \ge 300$ synchronized timestamps.
- **Formula:**
  $$\Delta Y_t = \Pi Y_{t-1} + \sum_{i=1}^{k-1} \Gamma_i \Delta Y_{t-i} + \mu + \varepsilon_t, \quad \Pi = \alpha \beta'$$
- **Safety Gate:** If rank $r=0$ or stationarity tests fail, output `status = NOT_AVAILABLE: NO_COINTEGRATION`. Never force numerical fit.

### I. Behavioral Proxies
- **Purpose:** Research behavioral and retail flow patterns (e.g. disposition effect proxies, round-number clustering).
- **Measurable Proxies Only:**
  1. Round number quote clustering: Proportion of resting limit orders at psychological levels (e.g. \$100, \$1000).
  2. Sizing asymmetry: Ratio of odd-lot/small retail trades ($<\$500$) vs block trades ($>\$50,000$).
  3. Reference price anchor: Distance to 24h high/low.
- **Zero Psychology Inference:** No psychological states are inferred; only empirical order-size and price-level clustering are reported.
