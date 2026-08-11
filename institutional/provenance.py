from typing import Dict, Any
from institutional.types import FeatureStatus, DataQuality, Provenance

def create_provenance_record(
    symbol: str, 
    timeframe: str, 
    source_name: str, 
    inputs: list, 
    formula: str,
    status: FeatureStatus, 
    quality: DataQuality = DataQuality.VALID
) -> Provenance:
    """
    Helper to standardize provenance creation across all modules.
    Ensures every mathematical output tracks its exact derivation.
    """
    import time
    return Provenance(
        symbol=symbol,
        timestamp=int(time.time() * 1000),
        timeframe=timeframe,
        source=source_name,
        raw_inputs_used=inputs,
        lookback=0, # Default, must be overridden if applicable
        formula=formula,
        normalization_method="none",
        calculation_version="1.0",
        data_quality=quality,
        status=status
    )
