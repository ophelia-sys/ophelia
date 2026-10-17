import pandas as pd
from typing import List, Dict, Any, Optional
from .registry import FeatureRegistry, HypothesisFamily, PromotionState, FeatureRecord
from .statistics import fdr_bh
import time
import numpy as np

class ExperimentRunner:
    """
    Strict Dev/OOS separation and Multiple Testing Orchestrator.
    Prevents leakage by isolating OOS data until final evaluation.
    """
    def __init__(self, registry: FeatureRegistry, experiment_id: str, dataset_hash: str):
        self.registry = registry
        self.experiment_id = experiment_id
        self.dataset_hash = dataset_hash
        self._dev_data_accessed = False
        self._oos_data_accessed = False
        self._current_family: Optional[HypothesisFamily] = None
        self._oos_results: List[Dict[str, Any]] = []

    def start_hypothesis_family(self, feature_id: str, family_size: int, hypotheses_definitions: List[Dict[str, Any]]) -> str:
        """
        Locks the hypothesis family size before OOS evaluation.
        """
        family_id = f"fam_{self.experiment_id}_{int(time.time())}"
        family = HypothesisFamily(
            family_id=family_id,
            experiment_id=self.experiment_id,
            feature_id=feature_id,
            dataset_hash=self.dataset_hash,
            family_size=family_size,
            hypotheses=hypotheses_definitions
        )
        self.registry.register_hypothesis_family(family)
        self._current_family = family
        return family_id

    def get_dev_data(self, folds: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Returns only the DEV folds. Marks DEV as accessed.
        """
        if self._oos_data_accessed:
            raise RuntimeError("CRITICAL LEAKAGE: Cannot request DEV data after OOS data has been accessed.")
        self._dev_data_accessed = True
        # Assume folds 1-3 are DEV
        return folds[:3]

    def get_oos_data(self, folds: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Returns only the OOS folds. Marks OOS as accessed.
        """
        if not self._dev_data_accessed:
            raise RuntimeError("Must access DEV data for parameter selection before OOS data.")
        if self._current_family is None:
            raise RuntimeError("Must lock a HypothesisFamily before accessing OOS data.")
            
        self._oos_data_accessed = True
        # Assume folds 4-5 are OOS
        return folds[3:]

    def record_oos_result(self, hypothesis_index: int, p_value: float, effect_size: float, details: Dict[str, Any]):
        """
        Records an OOS evaluation result for FDR correction.
        """
        if not self._oos_data_accessed:
            raise RuntimeError("Cannot record OOS results without accessing OOS data.")
            
        self._oos_results.append({
            "hypothesis_index": hypothesis_index,
            "p_value": p_value,
            "effect_size": effect_size,
            "details": details
        })

    def finalize_family(self) -> List[Dict[str, Any]]:
        """
        Applies FDR correction globally across the pre-registered family.
        """
        if not self._current_family:
            raise RuntimeError("No active family to finalize.")
            
        if len(self._oos_results) == 0:
            return []
            
        # The hypothesis family size MUST be respected. 
        # If we only evaluated 5 out of 90 hypotheses on OOS (e.g. only the winning threshold),
        # the FDR must still penalize against the full family size.
        # We fill un-evaluated hypotheses with p=1.0 to reflect the penalty of selection.
        
        full_p_values = np.ones(self._current_family.family_size)
        for res in self._oos_results:
            idx = res["hypothesis_index"]
            full_p_values[idx] = res["p_value"]
            
        fdr_adjusted = fdr_bh(full_p_values)
        
        for res in self._oos_results:
            idx = res["hypothesis_index"]
            res["fdr_p_value"] = fdr_adjusted[idx]
            res["significant"] = bool(fdr_adjusted[idx] <= self._current_family.global_fdr_threshold)
            
        # Save results back to family in registry
        for res in self._oos_results:
            idx = res["hypothesis_index"]
            if idx < len(self._current_family.hypotheses):
                self._current_family.hypotheses[idx].update(res)
                
        self.registry.save()
        return self._oos_results

    def promote_feature(self, feature_id: str, new_state: PromotionState, reason: str = ""):
        feature = self.registry.get_feature(feature_id)
        if not feature:
            raise ValueError(f"Feature {feature_id} not found.")
            
        if new_state == PromotionState.REJECTED:
            feature.reject(reason)
        else:
            feature.advance_state(new_state)
            
        self.registry.save()
