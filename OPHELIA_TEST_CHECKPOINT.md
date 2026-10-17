# OPHELIA TEST CHECKPOINT

| Test File | Command | Outcome | Purpose |
|-----------|---------|---------|---------|
| `tests/test_phase6_4_p7_causality.py` | `pytest tests/test_phase6_4_p7_causality.py` | PASS | Verified strict causality of P7 features (no target leakage or future lookahead in rolling windows). |
| `tests/test_phase6_4_p6_causality.py` | `pytest tests/test_phase6_4_p6_causality.py` | PASS | Verified strict causality of P6 features. |
| `tests/test_phase6_3_p5_causality.py` | `pytest tests/test_phase6_3_p5_causality.py` | PASS | Verified causality of P5 cross-asset features. |
| `tests/test_phase6_2_p3_causality.py` | `pytest tests/test_phase6_2_p3_causality.py` | PASS | Verified causality of P3 Spot/Perp features. |
| `tests/test_phase6_2_p1_causality.py` | `pytest tests/test_phase6_2_p1_causality.py` | PASS | Verified causality of P1 OI features. |
| `tests/test_cvd_live_edge_cases.py` | `pytest tests/test_cvd_live_edge_cases.py` | PASS | Verified CVD edge case handling. |
| `tests/test_historical_feature_causality.py` | `pytest tests/test_historical_feature_causality.py` | PASS | General historical causality suite. |

*Note: All expensive full experiments are skipped in this manifest. Only automated unit tests are tracked.*
