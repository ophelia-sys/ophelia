class ReportGenerator:
    """
    Generates the PHASE6_HISTORICAL_VALIDATION_REPORT.md at the repository root.
    """
    def generate_report(self, results: dict, output_path: str = "PHASE6_HISTORICAL_VALIDATION_REPORT.md"):
        content = f"""# Phase 6 Historical Validation Report

## A. Data Quality
- Status: {results.get('audit', {}).get('status', 'UNKNOWN')}
- Max Data Gap: {results.get('audit', {}).get('max_data_gap', 0)}
- Monotonic: {results.get('audit', {}).get('is_monotonic', False)}

## B. Dataset Coverage
(To be filled by pipeline execution)

## C. Event Counts
- Raw Count: {results.get('power', {}).get('raw_count', 0)}
- Cluster Count: {results.get('power', {}).get('cluster_count', 0)}

## V. Power Analysis
- Estimated N_eff: {results.get('power', {}).get('estimated_n_eff', 0)}
- Status: {results.get('power', {}).get('status', 'UNKNOWN')}

## W. Negative/Falsification Results
Historical validation is currently just a pipeline implementation. Not executed on live historical data.

## X. Feature Promotion Classification
- FVG: REQUIRES MORE DATA
- Liquidity Pools: REQUIRES MORE DATA
- Robust Z-Score: REQUIRES MORE DATA
- Amihud: REQUIRES MORE DATA
- OFI: LIVE_ONLY
- Microprice: LIVE_ONLY
"""
        with open(output_path, 'w') as f:
            f.write(content)
