from institutional.types import FeatureStatus, MarketState

def audit_feature_safety(state: MarketState) -> bool:
    """
    Validates that no experimental features leaked into execution-grade status.
    If any critical execution condition depends on an EXPERIMENTAL feature, it fails the audit.
    (Currently, InstitutionalMathEngine operates strictly in research mode, so this is
    an analytical pass-through check.)
    """
    has_experimental = any(status == FeatureStatus.EXPERIMENTAL for status in state.feature_statuses.values())
    # In the future, we could reject the state or flag it here.
    # For now, simply observe it.
    return not has_experimental
