# Phase 6.1: Semantic Definitions for Flow-Price Divergence

Before beginning Phase 6.1 Empirical Feature Validation (EXP 037-041), the following semantic definitions are explicitly documented and locked.

## 1. Z_R (Normalized Price Return)
- **Definition:** The robust Z-score of the short-term logarithmic price return.
- **Meaning:** It measures the local momentum or drift of the asset price relative to its recent historical volatility (typically using a 100-period rolling median absolute deviation). 
- **Sign Convention:** 
  - `Z_R > 0`: The price is increasing relative to its baseline volatility.
  - `Z_R < 0`: The price is decreasing relative to its baseline volatility.

## 2. Z_DeltaOI (Normalized Change in Open Interest)
- **Definition:** The robust Z-score of the 5-minute change in Open Interest (DeltaOI). As established in the Phase 6 Forensic Audit, this operates strictly on the native 5-minute event grid of the exchange.
- **Meaning:** It measures extreme structural shifts in market participation (open contracts).
- **Sign Convention:**
  - `Z_DeltaOI > 0`: Open interest is increasing significantly (new positions are being opened by both longs and shorts).
  - `Z_DeltaOI < 0`: Open interest is decreasing significantly (existing positions are being closed, typically via stop losses, liquidations, or deleveraging).

## 3. Flow-Price Divergence (Bullish)
- **Mathematical Formula:** 
  `flow_price_divergence = max(0, Z_R - Z_DeltaOI)` conditioned on `Z_DeltaOI < -tau`.
- **Meaning:** Bullish divergence occurs when Open Interest drops massively (`Z_DeltaOI < -tau`, indicating forced liquidations or mass closures of existing positions), but the price does not proportionally collapse, or is actually rising (`Z_R` > `Z_DeltaOI`). This implies structural absorption by limit-order liquidity providers (smart money absorbing the aggressive flow).
- **Sign Convention:**
  - The feature value is positive (`> 0`) when the divergence condition is met. The magnitude represents the severity of the divergence between the normalized return and the normalized flow.
  - A value of `0.0` means the divergence condition was not met (e.g., price dropped along with OI, or OI didn't drop enough).
