# TRIPLE-BARRIER LABELING

The labeling engine evaluates whether an opportunity reaches its take-profit before its stop-loss, capped by a vertical time horizon.

## 1. Parameters
- **Upper Barrier:** `Entry + (ATR * TP_Multiplier)`
- **Lower Barrier:** `Entry - (ATR * SL_Multiplier)`
- **Vertical Barrier:** e.g., 15m, 30m, 1h, 4h.
- *Note: In research, Entry is assumed to be the Close of candle T.*

## 2. Intrabar Tie-Breaking Rule (1m Resolution)
At each timestamp T, we evaluate the forward window `[T+1m, T+Horizon]`.

For each 1m candle in the forward window:
- **CASE A:** `High >= Upper Barrier` AND `Low > Lower Barrier` 
  $\rightarrow$ **LABEL = +1** (Take Profit hit). Break loop.
  
- **CASE B:** `Low <= Lower Barrier` AND `High < Upper Barrier`
  $\rightarrow$ **LABEL = -1** (Stop Loss hit). Break loop.
  
- **CASE D (AMBIGUOUS):** `High >= Upper Barrier` AND `Low <= Lower Barrier` in the *same* 1m candle.
  $\rightarrow$ **LABEL = UNRESOLVED / NULL**. 
  Because we do not have tick data to determine which happened *first* inside that minute, we strictly **exclude** this sample from training to prevent look-ahead bias.

If the loop finishes without hitting Case A, B, or D:
- **CASE C:** Neither barrier touched before the vertical barrier.
  $\rightarrow$ **LABEL = 0** (Time exit).

## 3. Cost Assumptions in Labeling
The labels evaluated above represent GROSS hits. A separate evaluation maps these to NET outputs based on the `COST_MODEL.md`.
