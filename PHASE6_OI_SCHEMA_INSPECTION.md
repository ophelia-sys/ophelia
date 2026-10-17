# OI Schema Inspection (Binance Metrics)

Archive: BTCUSDT-metrics-2023-01-01.csv
Shape: (288, 8)

## Columns and Dtypes
`
create_time                             str
symbol                                  str
sum_open_interest                   float64
sum_open_interest_value             float64
count_toptrader_long_short_ratio    float64
sum_toptrader_long_short_ratio      float64
count_long_short_ratio              float64
sum_taker_long_short_vol_ratio      float64
dtype: object
`

## First 5 Rows
`
           create_time  ... sum_taker_long_short_vol_ratio
0  2023-01-01 00:00:00  ...                       0.914929
1  2023-01-01 00:05:00  ...                       0.559590
2  2023-01-01 00:10:00  ...                       0.577667
3  2023-01-01 00:15:00  ...                       1.116552
4  2023-01-01 00:20:00  ...                       1.236449

[5 rows x 8 columns]
`

## True Timestamp Field
The create_time column represents the observation time. It is stored as a string format YYYY-MM-DD HH:MM:SS.

## True Open Interest Field
The sum_open_interest column contains the raw Open Interest in base asset units (e.g. BTC). The sum_open_interest_value contains the notional value (in quote asset, e.g. USDT).
